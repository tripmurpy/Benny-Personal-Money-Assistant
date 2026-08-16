# Gmail Finance Flow — Writer Handoff

## Diagram source

- Mermaid source: [`gmail-finance-flow.mmd`](gmail-finance-flow.mmd)
- README-ready image: [`gmail-finance-flow.svg`](gmail-finance-flow.svg)
- Primary runtime sources: [`main.py`](../../main.py), [`config/__init__.py`](../../config/__init__.py), [`services/gmail/ingestion.py`](../../services/gmail/ingestion.py), [`services/ai/service.py`](../../services/ai/service.py), and [`services/infrastructure/database.py`](../../services/infrastructure/database.py).

## Components shown

- `main.py`: validates config, builds the Telegram application, and registers the repeating Gmail job when `GMAIL_ENABLED` is true.
- `Config`: supplies the Gmail query, OAuth credential/token paths, and poll interval. The minimum interval is 30 seconds.
- `GmailTransactionIngestion`: loads `gmail-state.json`, authenticates Gmail read-only, lists bounded candidates, fetches raw messages, parses content, classifies, writes, notifies, and updates local status.
- `AIService.parse_finance_email`: returns exactly `expense`, `income`, or `neither`; incomplete or ambiguous evidence becomes `neither`.
- `SupabaseService`: writes expenses through `add_transactions_bulk` and income through `add_income`, using an idempotent `operation_id`.
- Telegram bot context: sends the post-write notification to `Config.ADMIN_ID` when a bot is available.

## Data flow order

1. `Config.validate()` runs during startup; invalid configuration logs an error and exits.
2. When Gmail is enabled, `Application.job_queue.run_repeating(gmail.sync, ...)` schedules the poll.
3. Gmail OAuth uses scope `https://www.googleapis.com/auth/gmail.readonly`; credentials are refreshed or obtained through local browser OAuth and cached in the configured token file.
4. `_fetch()` calls Gmail `messages.list` with `GMAIL_FINANCE_QUERY` and `maxResults=2`, skips IDs already marked as final, then fetches each remaining message with `format="raw"`.
5. `_body()` prefers `text/plain`; if empty, `_HTMLText` extracts visible text from HTML while ignoring `script` and `style` content.
6. `parse_finance_email()` classifies the normalized email. It treats email content as untrusted data and requires explicit IDR evidence, a positive amount, a name/source, and a transaction date for ledger classes.
7. `neither` is marked in `gmail-state.json` and stops without a ledger write. `expense` and `income` ensure the admin owner profile, then use `operation_id = gmail:<message_id>`.
8. Expense and income use different database writers. A confirmed write is followed by Telegram notification when `_context.bot` exists, then the local state becomes `expense:notified` or `income:notified`; without a bot it becomes `expense` or `income`.

## Verified runtime facts

- Gmail ingestion is enabled by default, but can be disabled with `GMAIL_ENABLED=false`.
- The default query is bounded to recent messages from configured BCA, Jago, GoPay/Gojek, and Google Pay senders; `GMAIL_FINANCE_QUERY` can override it.
- Each poll asks Gmail for at most two messages.
- The state file is local JSON. It prevents normal reprocessing; it does not label, archive, or mutate Gmail messages.
- Supabase write confirmation requires the returned record count to match the input row count. Database failures return `ok: false`.
- Database writes are synchronous adapter calls executed from the async ingestion flow through worker threads.
- The shared AI request policy retries only timeout/rate-limit failures, bounded by `AI_MAX_RETRIES` (default 1, maximum 3). A classification exception is logged and skipped for the current cycle.
- Offline tests verify plain-text and HTML parsing, trusted-query contents, the two-message bound, state eligibility, income-writer routing, and Telegram notification formatting. They do not prove live Gmail OAuth or live production writes.

## Security and data boundaries

- Gmail scope is read-only. Keep credential and token files local and excluded from Git.
- The classifier prompt explicitly treats email content as untrusted instructions and limits the payload passed to the model to the first 8,000 serialized characters.
- The ledger owner is `Config.ADMIN_ID`; the ingestion path is not a generic multi-user Gmail importer.
- `operation_id` is the duplicate-write boundary. The database adapter stores row keys as `gmail:<message_id>:0` for the single-row ingestion path and upserts on `user_id,operation_id`.
- Local state is written only after `neither` is classified or after a successful ledger path and notification decision. A failed write or notification leaves the message eligible for a later poll.
- Gmail ingestion does not route through `TransactionCaptureController`, does not create a Telegram confirmation prompt, and does not use the interactive text/photo/voice confirmation lifecycle.

## Claims the writer must not make

- Do not claim Gmail messages are archived, labeled, deleted, or marked read.
- Do not claim a distributed queue, durable job history, or immediate retry scheduler. The runtime uses the Telegram application's in-process repeating job queue.
- Do not claim every message is processed in one poll; the bound is two messages per poll.
- Do not claim Gmail ingestion asks the user to confirm before saving. Its direct write behavior differs from the interactive Telegram capture flow.
- Do not claim live Gmail/Supabase integration was proven by `tests/test_gmail_ingestion.py`; the tests use mocks and temporary state files.
- Do not call the local state file a source of truth for the ledger. Supabase is the ledger store; the state file is a local processing-status guard.

## Image reference guidance

Use the SVG for README or other rendered views:

```markdown
![Gmail finance ingestion flow](docs/visuals/gmail-finance-flow.svg)
```

Use the Mermaid file when the destination supports editable diagrams. Keep the SVG and Mermaid topology synchronized if labels or runtime behavior change. Cite the failure/retry boundary as a limitation: AI retries only selected transient failures; unmarked messages are revisited by a later scheduled poll.
