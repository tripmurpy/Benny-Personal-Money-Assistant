"""Poll only Gmail messages sorted into the approved finance labels."""

import asyncio
import base64
import json
import logging
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import Config

logger = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, _attrs):
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())

    def text(self):
        return " ".join(" ".join(self.parts).split())


class GmailTransactionIngestion:
    """Classify trusted-provider mail and save real transactions idempotently."""

    def __init__(self, ai, db, state_file="gmail-state.json"):
        self.ai, self.db = ai, db
        self.state_path = Path(state_file)
        self.processed = {}
        if self.state_path.exists():
            saved = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.processed.update(
                saved if isinstance(saved, dict) else {message_id: "processed" for message_id in saved}
            )

    @staticmethod
    def finance_query():
        return Config.GMAIL_FINANCE_QUERY

    def _service(self):
        token_path = Path(Config.GMAIL_TOKEN_FILE)
        credentials = Credentials.from_authorized_user_file(token_path, SCOPES) if token_path.exists() else None
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        if not credentials or not credentials.valid:
            flow = InstalledAppFlow.from_client_secrets_file(Config.GMAIL_CREDENTIALS_FILE, SCOPES)
            credentials = flow.run_local_server(port=0)
        token_path.write_text(credentials.to_json(), encoding="utf-8")
        return build("gmail", "v1", credentials=credentials, cache_discovery=False)

    @staticmethod
    def _body(raw):
        message = BytesParser(policy=policy.default).parsebytes(
            base64.urlsafe_b64decode(raw["raw"] + "===")
        )
        body = message.get_body(preferencelist=("plain",))
        content = body.get_content() if body else ""
        if not content:
            body = message.get_body(preferencelist=("html",))
            if body:
                parser = _HTMLText()
                parser.feed(body.get_content())
                content = parser.text()
        return {
            "subject": str(message.get("subject", "")),
            "sender": str(message.get("from", "")),
            "date_header": str(message.get("date", "")),
            "body": content,
        }

    def _fetch(self):
        service = self._service()
        messages = []
        page = service.users().messages().list(
            userId="me", q=self.finance_query(), maxResults=2
        ).execute()
        for item in page.get("messages", []):
            if self._needs_processing(self.processed.get(item["id"])):
                raw = service.users().messages().get(
                    userId="me", id=item["id"], format="raw"
                ).execute()
                messages.append((item["id"], self._body(raw)))
        return messages

    @staticmethod
    def _needs_processing(status):
        return status is None or status in {"expense", "income"}

    def _mark_processed(self, email_id, classification):
        self.processed[email_id] = classification
        self.state_path.write_text(
            json.dumps(self.processed, indent=2, sort_keys=True), encoding="utf-8"
        )

    @staticmethod
    def _notification(transaction):
        kind = "Pemasukan" if transaction["transaction_type"] == "income" else "Pengeluaran"
        name = transaction.get("source") if kind == "Pemasukan" else transaction.get("item")
        lines = [
            "Transaksi baru dari Gmail",
            "",
            f"Jenis: {kind}",
            f"Transaksi: {name or '-'}",
            f"Waktu: {transaction.get('date') or '-'} {transaction.get('time') or ''}".rstrip(),
        ]
        if transaction.get("notes"):
            lines.append(f"Note: {transaction['notes']}")
        lines.extend([
            f"Harga: Rp{int(transaction.get('amount', 0)):,}".replace(",", "."),
            f"Lokasi: {transaction.get('location') or '-'}",
        ])
        return "\n".join(lines)

    async def sync(self, _context=None):
        """Check new sorted mail every poll interval."""
        try:
            profile_ready = False
            for email_id, email_data in await asyncio.to_thread(self._fetch):
                try:
                    transaction = await self.ai.parse_finance_email(email_data)
                except Exception:
                    logger.exception("Skipping failed Gmail classification for this cycle")
                    continue
                kind = transaction["transaction_type"]
                if kind == "neither":
                    await asyncio.to_thread(self._mark_processed, email_id, kind)
                    logger.info("Skipped non-transaction Gmail message")
                    continue
                uid = str(Config.ADMIN_ID)
                if not profile_ready:
                    profile_ready = await asyncio.to_thread(
                        self.db.upsert_user, uid, {"username": "", "first_name": ""}
                    )
                if not profile_ready:
                    logger.error("Gmail transaction owner profile could not be initialized")
                    continue
                operation_id = f"gmail:{email_id}"
                write = (
                    self.db.add_income
                    if kind == "income"
                    else self.db.add_transactions_bulk
                )
                result = await asyncio.to_thread(
                    write, uid, [transaction], operation_id
                )
                if result["ok"]:
                    bot = getattr(_context, "bot", None)
                    if bot:
                        await bot.send_message(
                            chat_id=Config.ADMIN_ID,
                            text=self._notification(transaction),
                        )
                    await asyncio.to_thread(
                        self._mark_processed,
                        email_id,
                        f"{kind}:notified" if bot else kind,
                    )
                    logger.info("Saved classified Gmail %s", kind)
        except Exception:
            logger.exception("Gmail finance sync failed")
