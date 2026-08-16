# Benny — AI Pencatat Keuangan Telegram

Bot Telegram privat untuk mencatat pemasukan dan pengeluaran dari:

- Pesan teks natural, misalnya `makan 25 ribu` atau `gaji 5 juta`.
- Foto struk.
- Voice note.
- Pertanyaan analitik, misalnya `kategori paling boros bulan ini` atau `5 transaksi paling besar`.

Benny membedakan transaksi, pertanyaan klarifikasi, dan percakapan ringan seputar pencatatan. Hasil OCR dan transkrip voice ditampilkan sebelum penyimpanan; input baru dan tombol lama tidak dapat mengganti konfirmasi yang sedang aktif.

Benny membawa enam pesan percakapan terakhir sebagai konteks singkat. Ingatan eksplisit hanya berubah lewat perintah user: `ingat ...`, `ingat apa`, `ubah ingatan ... menjadi ...`, dan `lupakan ...`. Ingatan ini bukan transaksi dan tidak pernah menjadi sumber kebenaran ledger.

Ingatan eksplisit juga dapat mengatur gaya percakapan, misalnya `ingat jawab singkat dan santai`. Gunakan `/help` untuk melihat fitur aktif dan contoh pemakaiannya.

Kirim `roast` atau `/roast` untuk mendapat ulasan keras berdasarkan pengeluaran 30 hari terakhir. Backend menghitung faktanya dari snapshot agregat milik user, tidak mengubah ledger, dan tidak menyimpan hasilnya ke `roast_runs`.

Setiap hasil AI harus dikonfirmasi sebelum ditulis ke Supabase. Penulisan memakai operation ID agar retry tidak menggandakan transaksi. Setelah tersimpan, transaksi dapat dibatalkan atau diedit dari tombol pada pesan hasil.

## Agent SQL

Agent SQL memungkinkan pengguna menanyakan data keuangan dengan bahasa sehari-hari, misalnya `pengeluaran apa yang paling sering?` atau `5 transaksi paling besar apa saja?`. Model menerjemahkan pertanyaan tersebut menjadi satu query SQL read-only. Hasil query kemudian diformat oleh aplikasi menjadi jawaban bahasa Indonesia yang mudah dibaca; pengguna tidak perlu menulis atau memahami SQL.

Untuk menjaga data production, SQL buatan model tidak dijalankan langsung di Supabase. Backend hanya mengambil ledger milik pengguna, menyalinnya ke SQLite sementara di memori, lalu menjalankan query yang sudah lolos validasi keamanan. Agent hanya mendukung analisis data dan tidak dapat menambah, mengubah, atau menghapus transaksi.

Pelajari komponen, flowchart, data flow, user flow, AI flow, proses retrieval, guardrail, workflow, dan contoh penggunaannya di [Dokumentasi Finance SQL Assistant](docs/finance-sql-assistant.md).

## Menjalankan

```powershell
pip install -r requirements.txt
python main.py
```

## Gmail finance ingestion

Agent Gmail membaca email transaksi dari sumber finance yang dikonfigurasi, mengambil
isi email dalam mode read-only, lalu meminta AI mengklasifikasikan email sebagai
`expense`, `income`, atau `neither`. Email yang memenuhi bukti minimum ditulis langsung
ke tabel ledger yang sesuai setelah klasifikasi; jalur ini tidak melewati confirmation
flow Telegram. Setelah write terkonfirmasi, bot dapat mengirim ringkasan ke admin.

Tools yang dipakai:

- Gmail API dengan OAuth scope `gmail.readonly` untuk mencari dan mengambil email.
- In-process job queue Telegram untuk polling berkala, minimal 30 detik.
- AI service untuk klasifikasi dan ekstraksi field transaksi.
- Supabase service untuk menulis expense ke `transactions` dan income ke `income`.
- `gmail-state.json` untuk mencegah email yang sudah selesai diproses ulang.

Dua contoh use case:

1. Email pembayaran BCA yang berisi merchant, nominal IDR, dan tanggal transaksi diklasifikasikan sebagai `expense`, lalu ditulis ke `transactions`.
2. Email penerimaan dana dari sumber eksternal yang berisi pengirim, nominal IDR, dan tanggal transaksi diklasifikasikan sebagai `income`, lalu ditulis ke `income`.

![Alur Gmail finance ingestion](docs/visuals/gmail-finance-flow.svg)

Baca [dokumentasi lengkap Gmail finance ingestion](docs/gmail-finance-ingestion.md),
atau buka [source Mermaid](docs/visuals/gmail-finance-flow.mmd) bila diagram perlu diedit.

Gmail aktif secara default. Atur `GMAIL_POLL_SECONDS`, override sumber lewat
`GMAIL_FINANCE_QUERY`, atau matikan dengan `GMAIL_ENABLED=false`. OAuth memakai
`credintial.json` dan token lokal `gmail-token.json`; keduanya diabaikan Git.

## Verifikasi

```powershell
python -m unittest discover -s tests -v
python -m compileall -q main.py config services scripts tests
```

Detail struktur ada di [docs/architecture.md](docs/architecture.md).

Standar output AI Telegram ada di [docs/ai-response-output-standard.md](docs/ai-response-output-standard.md).

Detail schema database ada di [docs/database.md](docs/database.md).
