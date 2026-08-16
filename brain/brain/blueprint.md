# Blueprint AI SQL Assistant

**Status:** Diimplementasikan  
**Updated:** 2026-08-14

## Tujuan

Menambahkan kemampuan bertanya tentang data keuangan melalui Telegram dengan bahasa natural, memakai model Groq yang sudah digunakan Benny dan data ledger dari Supabase.

Contoh:

- `total pengeluaran bulan ini berapa`
- `kategori paling boros bulan ini`
- `pengeluaran terbesar 30 hari terakhir`
- `berapa pemasukan dibanding pengeluaran bulan ini`
- `5 transaksi paling besar`

SQL buatan model tidak boleh dijalankan langsung pada Supabase production.

## Keputusan Arsitektur

Pola artikel tetap dipakai:

`pertanyaan -> schema context -> SQL generation -> execution -> jawaban`

Adaptasinya untuk Benny:

```text
Telegram query
-> private-user check
-> intent dan transaction guard
-> ambil ledger milik user dari Supabase
-> bangun SQLite in-memory snapshot
-> Groq membuat SELECT
-> validasi SQL read-only
-> eksekusi pada snapshot
-> format jawaban Telegram
```

Supabase tetap menjadi source of truth. SQLite hanya snapshot sementara untuk satu request dan tidak disimpan ke disk.

## Alasan Tidak Menjalankan SQL Langsung di Supabase

Backend saat ini memakai service-role yang dapat membaca dan menulis data. Memberikan koneksi itu kepada SQL agent akan membuka risiko query salah, akses lintas user, dan perubahan data.

Snapshot memberi tiga boundary:

1. Data sudah difilter berdasarkan `telegram_user_id` sebelum model membuat query.
2. Snapshot hanya berisi kolom keuangan yang diperlukan.
3. Jika validasi SQL gagal, query tetap tidak dapat menyentuh production.

## Data Contract

Snapshot memiliki satu tabel virtual:

| Kolom | Isi |
| --- | --- |
| `kind` | `expense` atau `income` |
| `date` | Tanggal transaksi |
| `time` | Waktu transaksi |
| `name` | Nama item atau sumber pemasukan |
| `category` | Kategori ledger |
| `amount` | Nominal integer dalam IDR |

Tidak dimasukkan pada MVP:

- `user_id`, karena data sudah ownership-scoped sebelum snapshot dibuat
- chat history
- explicit memory
- profil personal
- location dan notes
- tabel audit atau internal AI

## Routing Telegram

Urutan routing:

1. Verifikasi private user.
2. Tangani explicit-memory command.
3. Lindungi transaction capture dari salah routing.
4. Jalankan laporan deterministik yang sudah ada.
5. Jalankan SQL assistant untuk pertanyaan analitik.
6. Teruskan input lain ke capture atau conversation flow.

Contoh boundary:

| Input | Route |
| --- | --- |
| `beli kopi 25 ribu` | Transaction capture |
| `laporan kemarin` | Existing deterministic report |
| `kategori terbesar bulan ini` | SQL assistant |
| `hapus semua transaksi` | Tolak |
| `halo Benny` | Conversation |

## SQL Safety Contract

- Tepat satu statement.
- Hanya `SELECT` atau `WITH ... SELECT`.
- Hanya tabel `ledger`.
- Maksimum 100 baris hasil.
- Query detail wajib memiliki `LIMIT`.
- Tolak `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `ATTACH`, `DETACH`, dan `PRAGMA`.
- SQLite authorizer menjadi guard terakhir, bukan hanya pemeriksaan string.
- Timeout mengikuti `AI_TIMEOUT_SECONDS`.
- Model tidak menerima Supabase key, connection string, atau schema production.
- Raw rows, prompt, dan nominal transaksi tidak ditulis ke operational log.

## Error Contract

| Kondisi | Respons |
| --- | --- |
| Data kosong | Jelaskan bahwa tidak ada data pada periode tersebut |
| Pertanyaan ambigu | Minta satu klarifikasi singkat |
| Query di luar domain | Jelaskan bahwa Benny hanya membaca data keuangan pribadi |
| SQL tidak aman | Tolak tanpa eksekusi |
| Model/provider gagal | Jelaskan layanan analitik sementara tidak tersedia |
| Supabase gagal | Jelaskan data belum dapat diambil |
| Snapshot terpotong | Nyatakan bahwa hasil memakai batas data |

## Batas MVP

Didukung:

- total, count, average, minimum, dan maximum
- perbandingan income dan expense
- group by kategori, item, hari, minggu, atau bulan
- top-N transaksi atau kategori
- rentang tanggal sampai batas aman reporting yang sudah ada

Tidak didukung:

- write melalui SQL assistant
- schema exploration
- query tabel non-ledger
- forecasting
- spending recommendation
- budget, goals, coaching, dashboard, PDF, atau general-purpose chat

## Rencana Implementasi

### Fase 1 - Dependency dan contract

- Gunakan client Groq yang sudah terpasang; LangChain tidak diperlukan untuk satu panggilan terstruktur.
- Gunakan `Config.GROQ_MODEL` dan `Config.GROQ_API_KEY` yang sudah ada.
- Definisikan schema snapshot dan SQL safety contract.

### Fase 2 - Supabase snapshot

- Tambahkan satu read method pada `SupabaseService`.
- Query `transactions` dan `income` dengan filter `user_id`.
- Normalisasi keduanya menjadi bentuk `ledger`.
- Gunakan pagination dengan hard limit awal 10.000 baris per request.

### Fase 3 - SQL assistant

- Buat SQLite `:memory:`.
- Masukkan snapshot ledger.
- Gunakan Groq untuk menghasilkan query.
- Validasi lalu jalankan query pada SQLite.
- Format hasil secara deterministik dalam Bahasa Indonesia dan Rupiah.

### Fase 4 - Telegram integration

- Pasang service sebagai perluasan reporting.
- Pertahankan routing capture dan confirmation state yang sudah ada.
- Jalankan kerja sinkron melalui worker thread agar event loop tidak tertahan.

### Fase 5 - Verification

- Jalankan seluruh regression test lama.
- Tambahkan satu test file khusus SQL assistant.
- Jalankan live smoke read-only terhadap Supabase.
- Pastikan smoke test tidak membuat, mengubah, atau menghapus data.

## File Impact

```text
services/infrastructure/database.py
services/reporting/sql_assistant.py
services/telegram/bot.py
tests/test_finance_sql_assistant.py
README.md
docs/architecture.md
```

Tidak membutuhkan migration Supabase baru.

## Verification Matrix

| Skenario | Hasil wajib |
| --- | --- |
| Total expense | Sama dengan perhitungan fixture |
| Income vs expense | Nilai dan selisih benar |
| Top category | Urutan dan nominal benar |
| Date range | Tidak mengambil data di luar periode |
| Empty data | Jawaban eksplisit, bukan error palsu |
| Transaction statement | Tetap masuk confirmation flow |
| DML atau DDL request | Ditolak sebelum eksekusi |
| Prompt injection | Tidak dapat memperluas tabel atau permission |
| User isolation | Snapshot hanya berisi user aktif |
| Provider timeout | Telegram tetap responsif |

## Definition of Done

- Pertanyaan natural dikirim dari Telegram.
- Model tetap model project yang aktif.
- Jawaban dihitung dari ledger Supabase milik user aktif.
- SQL model hanya berjalan pada SQLite in-memory.
- Tidak ada jalur write baru.
- Capture, confirmation, OCR, voice, Gmail, memory, dan laporan lama tidak regresi.
- Offline tests dan live read-only smoke lulus.
- Dokumentasi menjelaskan scope, boundary, dan keterbatasan.

## Known Ceiling

Snapshot dibatasi 10.000 baris per user per request. Jika data melewati batas atau latency terukur tidak memadai, upgrade path adalah RPC atau reporting view read-only yang ownership-scoped. Direct production SQL bukan default berikutnya.

## Referensi

- https://amanxai.com/2026/05/13/create-an-ai-sql-assistant-with-langchain/
- https://docs.langchain.com/oss/python/langchain/sql-agent
- https://supabase.com/docs/guides/database/connecting-to-postgres
- https://supabase.com/docs/guides/database/postgres/roles
