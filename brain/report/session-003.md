# Session 003

**Tanggal:** 2026-08-12
**Topik Sesi:** Penyempitan scope menjadi AI pemasukan dan pengeluaran

## Keputusan Penting
- Scope runtime hanya mencakup capture pemasukan dan pengeluaran melalui teks, foto, dan voice.
- Konfirmasi, idempotency, ownership, retry, undo, dan edit dipertahankan sebagai kontrak keselamatan.
- Budget, goals, reminder, reporting, coaching, RAG, general chat, dan recommendation dikeluarkan.

## Perubahan Teknis
- `TelegramService` dijadikan adapter tipis.
- Lifecycle capture dipindahkan ke `TransactionCaptureController`.
- Modul, test, dependency, data, migration, script, dan dokumentasi di luar scope dihapus.

## Status / Todo Selanjutnya
- Verifikasi koneksi Telegram, provider AI, dan Supabase secara live sebelum deployment.
