# Architecture

```text
main.py                              Telegram composition root
config/                              Environment configuration
services/telegram/                   Authentication and thin Telegram adapter
services/transactions/capture.py     AI capture lifecycle and confirmation
services/reporting/service.py        Natural-language expense reports
services/reporting/sql_assistant.py  Read-only SQL analytics on an in-memory snapshot
services/ai/service.py               Text, receipt, and voice AI processing
services/infrastructure/database.py  Supabase ledger adapter
services/memory/service.py           Short session and explicit user memory
services/infrastructure/events.py    Operational event logging
migrations/                          Transaction idempotency migration
scripts/manual/                      Credentialed AI/Supabase checks
tests/                               Offline safety and characterization tests
```

## Runtime flow

SQL analytics berjalan setelah laporan deterministik dan sebelum capture/conversation. Service mengambil `transactions` dan `income` yang sudah difilter dengan `user_id`, menormalkannya menjadi tabel virtual `ledger`, meminta Groq menghasilkan satu `SELECT`, lalu memvalidasi dan menjalankannya pada SQLite `:memory:`. SQLite authorizer menolak write, akses tabel lain, PRAGMA, attach, dan fungsi di luar allowlist. Supabase tetap source of truth dan tidak menerima SQL buatan model.

`Telegram update → private-user check → report/capture router → AI intent → clarification, conversation, or structured transaction → user confirmation → Supabase income/transactions`.

OCR text and voice transcripts remain visible artifacts until the user confirms a write. The product intentionally excludes budgets, goals, reminders, coaching, RAG, and general-purpose chat; conversation is limited to the finance capture experience.

Session memory reads only the latest six user/assistant messages from the active chat session. Explicit memory is written only by direct `ingat`, `ubah ingatan`, and `lupakan` requests, can be listed with `ingat apa`, and stays separate from the financial ledger. Neither memory source can authorize a transaction write.

Provider AI memakai satu kebijakan timeout/retry dan mencatat operation, provider, model, attempt, durasi, status, tipe error, serta hasil terstruktur tanpa menyimpan prompt, transkrip, gambar, email, atau data transaksi. SDK Supabase tetap sinkron, tetapi seluruh aksesnya dari handler async dijalankan melalui worker thread agar Telegram event loop tidak tertahan. Write database tidak di-retry otomatis.

Database detail and table purposes are documented in [docs/database.md](database.md).

SQL Assistant detail, data contract, guardrail, dan verification ada di [finance-sql-assistant.md](finance-sql-assistant.md).
