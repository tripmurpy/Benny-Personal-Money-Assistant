# Product Requirement Document

**Product:** Benny AI SQL Assistant  
**Status:** Planned, belum diimplementasikan  
**Updated:** 2026-08-14

## Ringkasan

Benny adalah bot Telegram privat untuk mencatat pemasukan dan pengeluaran. Pengguna saat ini dapat meminta laporan pengeluaran berdasarkan periode, tetapi belum dapat mengajukan pertanyaan analitik yang lebih fleksibel.

AI SQL Assistant memperluas reporting agar pengguna dapat bertanya tentang ledger dengan bahasa natural tanpa memberi model akses langsung ke Supabase production.

## Problem Statement

Pengguna harus mengetahui format laporan yang tersedia atau membaca rincian transaksi secara manual untuk menjawab pertanyaan seperti kategori paling besar, rata-rata pengeluaran, dan perbandingan pemasukan dengan pengeluaran.

Produk membutuhkan query natural yang:

- akurat untuk perhitungan uang
- tetap ownership-scoped
- read-only
- memakai interface Telegram
- memakai model project yang sudah ada
- tidak merusak transaction capture dan confirmation flow

## Goals

- Menjawab pertanyaan analitik ledger melalui Telegram.
- Menggunakan Groq `llama-3.1-8b-instant` yang sudah aktif.
- Mengambil data dari Supabase sebagai source of truth.
- Menjalankan SQL hanya pada snapshot SQLite in-memory.
- Mempertahankan perhitungan uang di database engine, bukan mengandalkan aritmetika model.
- Memberikan respons singkat, terstruktur, dan tanpa emotikon.

## Non-Goals

- Menjalankan SQL model langsung di Supabase.
- Menambah, mengedit, atau menghapus ledger melalui SQL assistant.
- Menampilkan atau menjelaskan schema database.
- Query chat history, memory, profil, atau tabel internal AI.
- Budget, goals, reminders, dashboard, PDF, RAG, coaching, forecasting, atau spending recommendation.
- Menjadi general-purpose assistant.

## Target User

Satu private user yang sudah diizinkan melalui `ADMIN_CHAT_ID` dan memakai Benny sebagai personal finance ledger.

## User Stories

### US-1 Total periode

Sebagai pengguna, saya ingin bertanya `total pengeluaran bulan ini berapa` agar mengetahui jumlah tanpa memilih menu atau menulis tanggal manual.

### US-2 Insight kategori

Sebagai pengguna, saya ingin bertanya `kategori paling boros bulan ini` agar mengetahui kategori dengan nominal tertinggi.

### US-3 Income versus expense

Sebagai pengguna, saya ingin bertanya `berapa pemasukan dibanding pengeluaran bulan ini` agar mengetahui cashflow periode tersebut.

### US-4 Top transaction

Sebagai pengguna, saya ingin bertanya `5 transaksi terbesar 30 hari terakhir` agar dapat melihat pengeluaran utama.

### US-5 Safe refusal

Sebagai pengguna, ketika saya meminta perubahan data lewat SQL assistant, saya harus mendapat penolakan dan ledger tidak berubah.

## Functional Requirements

### FR-1 Query routing

Sistem harus membedakan transaction statement, deterministic report, analytic query, dan conversation.

### FR-2 User-scoped retrieval

Sistem harus memfilter `transactions` dan `income` berdasarkan Telegram user aktif sebelum membuat snapshot.

### FR-3 Snapshot

Sistem harus membuat satu tabel SQLite in-memory yang hanya berisi `kind`, `date`, `time`, `name`, `category`, dan `amount`.

### FR-4 SQL generation

LangChain harus memakai model dari `Config.GROQ_MODEL` untuk membuat query berdasarkan schema snapshot dan pertanyaan user.

### FR-5 SQL validation

Sistem harus menolak statement selain read-only query terhadap tabel `ledger`.

### FR-6 Execution

SQL yang lolos validasi hanya boleh dijalankan pada snapshot SQLite.

### FR-7 Response

Jawaban harus menggunakan Bahasa Indonesia, format Rupiah, periode yang jelas, dan menyatakan jika data kosong atau terpotong.

### FR-8 Existing behavior

Transaction capture, confirmation, stale-button protection, OCR, voice, Gmail ingestion, memory, undo, edit, dan laporan lama harus tetap bekerja.

## Non-Functional Requirements

### Security

- Model tidak menerima credential Supabase.
- SQL assistant tidak memiliki koneksi production.
- Tidak ada write tool.
- Data lintas user tidak boleh masuk snapshot.
- Prompt injection tidak dapat memperluas tabel atau permission.

### Accuracy

- Total dan agregasi dihitung oleh SQLite.
- Date range divalidasi dengan aturan reporting project.
- Jawaban tidak boleh mengarang data ketika hasil kosong.

### Performance

- Handler Telegram tidak boleh diblokir oleh database sync atau SQL execution.
- Maksimum awal 10.000 ledger rows per request.
- Maksimum 100 detail rows pada jawaban.

### Reliability

- Provider failure, invalid SQL, empty data, dan database failure memiliki respons berbeda.
- Kegagalan SQL assistant tidak boleh memengaruhi jalur transaction capture.

### Privacy

- Operational log tidak menyimpan prompt, raw query result, atau detail transaksi.
- Snapshot tidak disimpan ke disk.

## User Flow

1. User mengirim pertanyaan melalui private Telegram chat.
2. Bot melakukan authentication dan routing.
3. Reporting service mengenali analytic query.
4. Backend mengambil ledger milik user dari Supabase.
5. Backend membuat SQLite in-memory snapshot.
6. LangChain dan Groq menghasilkan read-only SQL.
7. SQL guard memvalidasi statement.
8. Backend menjalankan query pada snapshot.
9. Bot mengirim jawaban yang sudah diformat.
10. Snapshot dibuang setelah request selesai.

## Acceptance Criteria

- `total pengeluaran bulan ini berapa` menghasilkan total fixture yang tepat.
- `kategori paling boros bulan ini` menghasilkan kategori dan nominal tertinggi.
- `pemasukan dibanding pengeluaran` menghasilkan kedua total dan selisih.
- Rentang tanggal tidak mengambil row di luar periode.
- Input `beli kopi 25 ribu` tetap masuk confirmation flow.
- Input `hapus semua transaksi` tidak mengeksekusi query atau write.
- Query hanya dapat mengakses tabel snapshot `ledger`.
- User isolation test membuktikan row user lain tidak masuk snapshot.
- Empty result menghasilkan pesan yang jelas.
- Timeout tidak memblokir Telegram event loop.
- Seluruh regression tests lama tetap lulus.
- Live verification hanya melakukan read dari Supabase.

## Release Plan

### Milestone 1 - Local contract

- Dependency dipin.
- Snapshot dan SQL guard selesai.
- Unit tests keamanan dan perhitungan lulus.

### Milestone 2 - Telegram integration

- Routing terpasang.
- Transaction capture tidak regresi.
- Error responses terverifikasi.

### Milestone 3 - Live read-only smoke

- Query memakai ledger Supabase user aktif.
- Hasil dibandingkan dengan query backend yang deterministik.
- Tidak ada perubahan jumlah row ledger.

## Success Metrics

- 100% test ownership dan read-only lulus.
- 100% golden query menghasilkan angka yang benar.
- 0 database write dari SQL assistant.
- 0 regresi pada capture dan confirmation tests.
- Respons analitik berhasil untuk minimal lima pola query acceptance.

## Risks dan Mitigasi

| Risiko | Mitigasi |
| --- | --- |
| Model membuat DML atau DDL | Validator dan SQLite authorizer |
| Salah routing transaksi | Transaction guard dan regression test |
| Data lintas user | Filter Supabase sebelum snapshot dan hilangkan `user_id` dari snapshot |
| Hallucinated column | Schema terbatas dan safe error |
| Snapshot terlalu besar | Pagination, hard limit, dan disclosure ketika terpotong |
| Provider unavailable | Pesan failure terpisah tanpa fallback ke write path |

## Dependency

- Telegram bot dan authorization aktif.
- Groq API aktif.
- Supabase `transactions` dan `income` dapat dibaca backend.
- LangChain packages kompatibel dan dipin.

## Definition of Done

Fitur selesai ketika seluruh acceptance criteria lulus, live read-only smoke berhasil, dokumentasi runtime diperbarui, dan tidak ada jalur SQL yang dapat mengubah Supabase atau mengakses data di luar ledger user aktif.

Blueprint teknis: [blueprint.md](blueprint.md).  
Stack teknis: [tech-stack.md](tech-stack.md).
