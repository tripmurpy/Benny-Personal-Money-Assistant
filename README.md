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

Environment wajib: `TELEGRAM_BOT_TOKEN`, `ADMIN_CHAT_ID`, `GROQ_API_KEY`, `SUPABASE_URL`, dan `SUPABASE_SERVICE_ROLE_KEY` (server-only; `SUPABASE_KEY` hanya fallback). Provider OCR tambahan dibaca dari konfigurasi environment bila tersedia. Kebijakan request AI dapat diatur dengan `AI_TIMEOUT_SECONDS` (default 30) dan `AI_MAX_RETRIES` (default 1, maksimum 3).

Gmail finance aktif secara default dan hanya mengambil kandidat dari alamat resmi BCA,
Jago, receipt GoPay/Gojek, dan Google Pay. Agent mengklasifikasikan setiap kandidat
sebagai `expense`, `income`, atau `neither`; hanya dua kelas pertama yang masuk ledger.
Setelah transaksi berhasil disimpan, bot mengirim notifikasi Telegram berisi jenis,
transaksi, waktu, note bila ada, harga, dan lokasi.
Pencarian mencakup email dua bulan terakhir, lalu Gmail message ID mencegah pemrosesan
dan penyimpanan ulang.
OAuth memakai `credintial.json` dan token lokal `gmail-token.json` (keduanya diabaikan
Git). Sinkronisasi berjalan tiap 30 detik; atur lewat `GMAIL_POLL_SECONDS`, override
sumber lewat `GMAIL_FINANCE_QUERY`, atau matikan dengan `GMAIL_ENABLED=false`.

## Verifikasi

```powershell
python -m unittest discover -s tests -v
python -m compileall -q main.py config services scripts tests
```

Detail struktur ada di [docs/architecture.md](docs/architecture.md).

Standar output AI Telegram ada di [docs/ai-response-output-standard.md](docs/ai-response-output-standard.md).

Detail schema database ada di [docs/database.md](docs/database.md).
