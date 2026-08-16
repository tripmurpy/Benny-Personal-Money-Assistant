# Tech Stack dan Arsitektur

**Status:** Stack aktif dan stack rencana dipisahkan  
**Updated:** 2026-08-14

## Stack Aktif

| Area | Teknologi | Fungsi |
| --- | --- | --- |
| Interface | Telegram | Input teks, foto, voice, confirmation, undo, dan edit |
| Backend | Python 3.9+ | Runtime service Benny |
| Telegram SDK | `python-telegram-bot[job-queue]` | Polling, handler, callback, persistence, dan Gmail job |
| AI utama | Groq SDK | Intent, transaction extraction, report parsing, email parsing, dan voice |
| Model teks | `llama-3.1-8b-instant` | Model default dari `Config.GROQ_MODEL` |
| OCR fallback | Gemini dan OpenRouter bila dikonfigurasi | Ekstraksi struk |
| Database | Supabase Postgres | Ledger, session, dan explicit memory |
| Database SDK | `supabase` Python client | Akses backend ownership-scoped |
| Gmail | Google API Python clients | Ingest email finance dari sumber yang dibatasi |
| State lokal | `PicklePersistence` | State Telegram dan pending confirmation |
| Test | Python `unittest` | Regression tests tanpa framework tambahan |

## Stack Rencana AI SQL Assistant

| Teknologi | Fungsi | Status |
| --- | --- | --- |
| `langchain` | Agent orchestration dan tool contract | Belum dicatat di requirements |
| `langchain-community` | SQL database utilities | Belum dicatat di requirements |
| `langchain-groq` | Adapter Groq untuk model project | Belum dicatat di requirements |
| SQLite stdlib | Database snapshot `:memory:` | Tidak membutuhkan dependency baru |

Versi package harus dipin setelah compatibility dan security check pada fase implementasi. Jangan memakai `langchain-experimental`, Streamlit, Ollama, CodeLlama, atau direct Postgres driver untuk MVP.

## Arsitektur Aktif

```text
main.py
-> services.telegram
-> services.reporting atau services.transactions
-> services.ai
-> services.infrastructure.database
-> Supabase
```

Boundary penting:

- Telegram hanya adapter dan router.
- AI memahami input, tetapi tidak mengotorisasi write.
- Setiap AI-derived write memerlukan confirmation.
- Supabase adapter menjadi satu boundary database.
- Akses database sinkron dari handler async dijalankan melalui worker thread.

## Arsitektur Rencana SQL Assistant

```text
Telegram finance question
-> reporting router
-> Supabase user-scoped read
-> normalized ledger snapshot
-> SQLite in-memory
-> LangChain + existing Groq model
-> read-only SQL guard
-> deterministic Telegram response
```

SQL assistant tidak menerima service-role key dan tidak memiliki koneksi ke Postgres production.

## Konfigurasi

Environment yang sudah ada dan tetap dipakai:

```text
TELEGRAM_BOT_TOKEN
ADMIN_CHAT_ID
GROQ_API_KEY
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
AI_TIMEOUT_SECONDS
AI_MAX_RETRIES
```

Tidak diperlukan environment baru untuk database SQL assistant karena snapshot memakai Supabase client dan SQLite in-memory.

## Dependency Policy

- Reuse model dan provider yang sudah ada.
- Pin dependency LangChain di `requirements.txt`.
- Jangan menambah framework UI.
- Jangan menambah direct database driver sebelum snapshot terbukti tidak memenuhi kebutuhan.
- Jalankan dependency compatibility check, regression tests, dan `compileall` setelah instalasi.

## Operational Boundary

- Snapshot maksimum awal: 10.000 ledger rows per request.
- Hasil detail maksimum: 100 rows.
- Tidak ada automatic retry untuk database write.
- SQL assistant tidak memiliki jalur write.
- Audit menyimpan operation, status, provider, model, duration, dan error type; bukan prompt atau data ledger.

Blueprint lengkap: [blueprint.md](blueprint.md).
