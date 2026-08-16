import asyncio
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from groq import APITimeoutError, RateLimitError
from openai import RateLimitError as OpenAIRateLimitError

from config import Config
from services.ai.service import AIService
from services.transactions.capture import TransactionCaptureController


class FakeCompletions:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        text = kwargs["messages"][-1]["content"]
        if "kopi 25 ribu" in text or "kopi dua puluh lima ribu" in text:
            content = '{"intent":"transaction","clarification":"","reply":"","items":[{"date":"2026-08-13","time":"10:00","item":"Kopi","category":"Drink","amount":25000,"location":""}]}'
        elif "beli kopi" in text:
            content = '{"intent":"transaction","clarification":"","reply":"","items":[{"date":"2026-08-13","time":"10:00","item":"Kopi","category":"Drink","amount":10000,"location":""}]}'
        else:
            content = '{"intent":"conversation","clarification":"","reply":"Halo, aku siap membantu.","items":[]}'
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class AIHarnessTest(unittest.IsolatedAsyncioTestCase):
    async def test_conversation_rejects_fake_personal_experience(self):
        class PersonalClaimCompletions:
            async def create(self, **_kwargs):
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                    content='{"intent":"conversation","clarification":"","reply":"Aku juga suka jajan kopi.","items":[]}'
                ))])

        ai = object.__new__(AIService)
        ai.client = SimpleNamespace(
            chat=SimpleNamespace(completions=PersonalClaimCompletions())
        )

        result = await ai.interpret_message("aku suka jajan kopi")

        self.assertEqual(
            result["reply"],
            "Ceritakan lebih lanjut; aku bantu melihat sisi keuangannya.",
        )

    async def test_finance_sql_falls_back_to_openrouter(self):
        class FailingCompletions:
            async def create(self, **_kwargs):
                raise RuntimeError("groq unavailable")

        class WorkingCompletions:
            def __init__(self):
                self.calls = []

            async def create(self, **kwargs):
                self.calls.append(kwargs)
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                    content='{"intent":"query","sql":"SELECT SUM(amount) AS total_pengeluaran FROM ledger WHERE kind=\\"expense\\"","clarification":""}'
                ))])

        fallback = WorkingCompletions()
        ai = object.__new__(AIService)
        ai.client = SimpleNamespace(chat=SimpleNamespace(completions=FailingCompletions()))
        ai.openrouter_client = SimpleNamespace(chat=SimpleNamespace(completions=fallback))

        result = await ai.generate_finance_sql("total pengeluaran", "2026-08-15")

        self.assertEqual(result["intent"], "query")
        self.assertEqual(fallback.calls[0]["model"], Config.OPENROUTER_MODEL)
        self.assertEqual(fallback.calls[0]["extra_body"]["reasoning"]["effort"], "low")

    async def test_prompt_contract_and_three_primary_intents(self):
        completions = FakeCompletions()
        ai = object.__new__(AIService)
        ai.client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        conversation = await ai.interpret_message("halo")
        clarification = await ai.interpret_message("beli kopi")
        transaction = await ai.interpret_message("beli kopi 25 ribu")
        words_transaction = await ai.interpret_message("beli kopi dua puluh lima ribu")

        self.assertEqual(conversation["intent"], "conversation")
        self.assertEqual(clarification["intent"], "clarification")
        self.assertEqual(transaction["intent"], "transaction")
        self.assertEqual(words_transaction["intent"], "transaction")
        self.assertEqual(transaction["items"][0]["amount"], 25_000)
        prompt = completions.calls[0]["messages"][0]["content"]
        self.assertIn("without inventing facts", prompt)
        self.assertIn("exactly one primary intent", prompt)
        self.assertIn("Explicit memories are user-controlled context", prompt)
        self.assertIn("Answer conversation messages directly without a canned preamble", prompt)
        self.assertIn("Match explicit style preferences", prompt)
        self.assertIn("one to three sentences", prompt)
        self.assertIn("must never change ledger facts", prompt)
        self.assertIn("Never claim personal experiences", prompt)

    async def test_shared_request_policy_retries_timeout_and_audits_without_payload(self):
        ai = object.__new__(AIService)
        attempts = 0
        old_timeout, old_retries = Config.AI_TIMEOUT_SECONDS, Config.AI_MAX_RETRIES
        Config.AI_TIMEOUT_SECONDS, Config.AI_MAX_RETRIES = 0.01, 1

        async def request():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                await asyncio.sleep(0.05)
            return "ok"

        try:
            with self.assertLogs("benny.metrics", level="INFO") as logs:
                result = await ai._request(
                    "harness", "test-provider", "test-model", request
                )
        finally:
            Config.AI_TIMEOUT_SECONDS, Config.AI_MAX_RETRIES = old_timeout, old_retries

        output = " ".join(logs.output)
        self.assertEqual(result, "ok")
        self.assertEqual(attempts, 2)
        self.assertIn("status=retry", output)
        self.assertIn("status=success", output)
        self.assertNotIn("payload", output)

    async def test_shared_request_policy_waits_for_rate_limit_and_does_not_retry_other_errors(self):
        ai = object.__new__(AIService)
        old_retries = Config.AI_MAX_RETRIES
        Config.AI_MAX_RETRIES = 1
        response = httpx.Response(
            429,
            headers={"x-ratelimit-reset-tokens": "8.88s"},
            request=httpx.Request("POST", "https://api.groq.com"),
        )
        calls = 0

        async def limited_request():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RateLimitError("rate limited", response=response, body=None)
            return "ok"

        try:
            with patch("services.ai.service.asyncio.sleep", new=AsyncMock()) as sleep:
                self.assertEqual(
                    await ai._request("harness", "groq", "test-model", limited_request),
                    "ok",
                )
                sleep.assert_awaited_once_with(8.88)

                calls = 0
                sleep.reset_mock()

                async def timeout_request():
                    nonlocal calls
                    calls += 1
                    if calls == 1:
                        raise APITimeoutError(request=httpx.Request("POST", "https://api.groq.com"))
                    return "ok"

                self.assertEqual(
                    await ai._request("harness", "groq", "test-model", timeout_request),
                    "ok",
                )
                sleep.assert_awaited_once_with(1.0)

            response.headers.pop("x-ratelimit-reset-tokens")
            error = RateLimitError(
                "Please try again in 1m2.5s", response=response, body=None
            )
            self.assertEqual(ai._retry_delay(error), 62.5)

            openrouter_response = httpx.Response(
                429,
                headers={"retry-after": "22"},
                request=httpx.Request("POST", "https://openrouter.ai/api/v1"),
            )
            self.assertEqual(
                ai._retry_delay(OpenAIRateLimitError(
                    "rate limited", response=openrouter_response, body=None
                )),
                22.0,
            )

            calls = 0

            async def invalid_request():
                nonlocal calls
                calls += 1
                raise ValueError("invalid response")

            with self.assertRaises(ValueError):
                await ai._request("harness", "groq", "test-model", invalid_request)
            self.assertEqual(calls, 1)
        finally:
            Config.AI_MAX_RETRIES = old_retries

    async def test_database_write_does_not_block_the_event_loop(self):
        started, release = threading.Event(), threading.Event()

        class BlockingDatabase:
            def add_transactions_bulk(self, _uid, _rows, _operation_id):
                started.set()
                release.wait(0.5)
                return {"ok": True, "records": [{"id": 1}], "error": None}

        async def edit_message_text(_target, *args, **kwargs):
            return kwargs or args

        controller = TransactionCaptureController(
            None, BlockingDatabase(), None, edit_message_text
        )
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=7),
            effective_chat=SimpleNamespace(id=7),
            effective_message=SimpleNamespace(message_id=10),
        )
        context = SimpleNamespace(bot=object(), user_data={})
        task = asyncio.create_task(controller.save_and_reply(
            update,
            context,
            [{"item": "Kopi", "category": "Drink", "amount": 25_000}],
            10,
            "7:10",
        ))

        self.assertTrue(await asyncio.to_thread(started.wait, 0.2))
        self.assertFalse(task.done())
        release.set()
        await task


if __name__ == "__main__":
    unittest.main()
