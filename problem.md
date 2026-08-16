---
title: Problem Bot Tele Keuangan
status: active
created: 2026-08-13
updated: 2026-08-15
tags:
  - personal-finance
  - telegram
  - diagnosis
  - ocr
  - reporting
---

# Problem Bot Tele Keuangan

## Kesimpulan

Tiga keluhan pengguna berasal dari tiga kontrak yang tidak tegas: tanggal relatif terlalu dipercayakan kepada model, format laporan belum memiliki template tetap, dan jalur OCR memakai dua identifier model yang sudah mati. Perbaikan dilakukan pada sumber masalah, bukan pada satu contoh chat.

Dokumen ini adalah log masalah kanonis. Masalah baru ditambahkan setelah ada bukti, akar penyebab, perbaikan, dan hasil verifikasi.

## Model Salah Memahami Tanggal Relatif

**Kata kunci:** intent laporan, kemarin, typo, rentang tanggal, off-by-one, weekday.

**Klasifikasi:** correctness, AI orchestration, high.

**Gejala:** Pada 13 Agustus 2026, pertanyaan `kemarin aku bli apa` menghasilkan periode 11 Agustus 2026. Database justru memiliki satu transaksi pada 12 Agustus.

**Akar penyebab:** Model mengubah kata `kemarin` menjadi `weekday_range` hari Selasa. Backend menerima hasil itu tanpa mendahulukan arti relatif yang deterministik.

**Perbaikan:**

- Resolver Python menangani langsung `kemarin`, `kemaren`, `hari ini`, `N hari terakhir`, `minggu ini`, `bulan ini`, dan `1 bulan terakhir`.
- Model hanya menangani rentang bahasa bebas yang tidak bisa dipastikan dengan aturan sederhana.
- Rentang uang dan waktu tetap dihitung backend, bukan dijumlahkan atau ditebak model.

**Hasil akhir:** `kemarin aku bli apa` pada 13 Agustus sekarang selalu menjadi 12 Agustus pukul 00:00–23:59 tanpa memanggil model.

## Rentang Laporan Pernah Tidak Konsisten

**Kata kunci:** 3 hari, 7 hari, satu bulan, Senin Jumat, jam 8 malam.

**Klasifikasi:** correctness, regression, high.

**Masalah yang pernah ditemukan:**

- Model menghitung “3 hari terakhir” sebagai empat tanggal.
- “Selasa kemarin aku beli apa?” pernah dianggap pencatatan baru.
- “Senin sampai Jumat jam 8 malam” pernah dipetakan menjadi Sabtu sampai Rabu.
- Tes onboarding lama membuat service tanpa constructor dan tidak memiliki router laporan.

**Akar penyebab:** Model diminta melakukan intent classification sekaligus aritmetika kalender. Kontrak antarkomponen juga belum dicakup regression test.

**Perbaikan:** Intent fleksibel tetap dibaca model, sedangkan jumlah hari dan resolusi weekday dihitung Python. Router laporan dipasang pada boundary Telegram dan dilindungi tes integrasi service.

**Hasil akhir:** Kasus jumlah hari, weekday, jam akhir, typo `bli`, transaksi baru, dan rentang future/reversed memiliki regression test.

## Respons Bot Tidak Rapi dan Tidak On-point

**Kata kunci:** format Telegram, laporan pengeluaran, respons kosong, error message.

**Klasifikasi:** UX, observability, medium.

**Gejala:** Laporan kosong hanya menyatakan data tidak ada; respons OCR menyebut “data transaksi tidak ditemukan” walaupun provider sebenarnya gagal.

**Akar penyebab:** Tidak ada template keluaran tetap dan semua kegagalan OCR diratakan menjadi list kosong.

**Perbaikan:**

- Laporan memakai urutan tetap: judul, periode, total, jumlah transaksi, ringkasan kategori, dan rincian.
- Label kategori ditampilkan dalam bahasa Indonesia.
- Kondisi laporan kosong tetap menampilkan `Total: Rp0` dan `Jumlah transaksi: 0`.
- Kegagalan provider dan foto tidak terbaca memiliki pesan berbeda.
- Seluruh output tetap tanpa emotikon.

**Hasil akhir:** User dapat membedakan tidak ada transaksi, foto tidak terbaca, database bermasalah, dan provider OCR tidak tersedia.

## OCR Tidak Dapat Digunakan

**Kata kunci:** OCR struk, Gemini 404, Qwen 404, vision model, FamilyMart.

**Klasifikasi:** provider drift, runtime, critical.

**Bukti:**

- `gemini-2.0-flash` mengembalikan 404 `model no longer available`.
- Fallback `qwen/qwen-vl-plus` mengembalikan 404 `No endpoints found`.
- Karena kedua error ditelan menjadi `[]`, bot salah melaporkan bahwa transaksi tidak ditemukan.

**Akar penyebab:** Identifier model di-hardcode tanpa smoke test request nyata dan exception provider tidak dipertahankan sampai Telegram boundary.

**Perbaikan:**

- Provider utama diganti ke `gemini-3.6-flash`, yang berhasil pada request gambar nyata dengan credential aktif.
- Fallback diganti ke `qwen/qwen2.5-vl-72b-instruct`, yang memiliki endpoint aktif.
- Output fallback dibatasi 1.000 token agar request OCR pendek tidak ditolak oleh limit kredit provider.
- Log provider hanya menyimpan tipe error dan tidak memuntahkan payload gambar.
- OCR membuat satu transaksi ledger per struk dan memakai total akhir setelah diskon agar tidak double count.
- Hasil OCR divalidasi: item wajib ada, nominal harus positif, kategori dibatasi, dan maksimal satu record.
- `ReceiptProcessingError` mempertahankan kegagalan provider sampai pesan Telegram.

**Hasil akhir:** Screenshot struk FamilyMart menghasilkan satu kandidat: dua Ice Caramel Macchiato L, total Rp32.000, tanggal 13 Agustus 2026 pukul 12:18, lokasi FamilyMart Bojongsari Depok, pembayaran tunai.

## Konfigurasi Environment Malformed

**Kata kunci:** python-dotenv, .env line 12, startup warning.

**Klasifikasi:** configuration hygiene, low.

**Gejala:** Setiap startup menampilkan `python-dotenv could not parse statement starting at line 12`.

**Akar penyebab:** Ada satu baris tanpa nama variabel dan tanpa tanda sama dengan.

**Perbaikan:** Hanya baris invalid tersebut dihapus. Credential bernama tetap dipertahankan dan tidak dicatat di dokumentasi.

**Hasil akhir:** Konfigurasi dapat dimuat tanpa warning parser tersebut.

## Intent, Konfirmasi, dan Artefak Multimodal Belum Aman

**Kata kunci:** persona finance, unclear message, pending confirmation, stale callback, OCR confidence, voice transcript, provider fallback.

**Klasifikasi:** correctness, user safety, AI orchestration, critical.

**Gejala:** Pesan biasa dan transaksi hanya dipisahkan oleh keyword; kegagalan text/voice provider berubah menjadi hasil kosong; input baru dapat mengganti satu `pending_confirmation`; tombol konfirmasi lama tidak terikat pada transaksi asal; teks OCR dan transkrip voice tidak selalu terlihat sebelum save.

**Bukti:** `parse_expense` dan `transcribe_audio` sebelumnya mengembalikan nilai kosong setelah exception. Callback `confirm_save_yes` tidak membawa operation ID. Satu key `pending_confirmation` selalu ditulis ulang saat preview berikutnya dibuat.

**Akar penyebab:** Boundary AI belum memiliki schema intent dan error taxonomy. Artefak multimodal direduksi langsung menjadi transaksi, sedangkan lifecycle confirmation menyimpan state tanpa identitas pada callback.

**Perbaikan:**

- System message Benny sekarang menghasilkan tepat satu dari `transaction`, `clarification`, atau `conversation` dengan schema transaksi tervalidasi.
- Text, OCR, dan voice mempertahankan perbedaan provider gagal, respons invalid, kosong, ambigu, dan confidence rendah sampai Telegram boundary.
- OCR membawa raw text dan voice membawa transkrip ke layar review sebelum penyimpanan.
- Input baru ditolak saat confirmation masih pending, dan seluruh tombol confirmation membawa operation ID yang harus cocok dengan state aktif.
- Confidence OCR di bawah 0,7 dan confidence voice yang hilang atau average log probability di bawah -0,8 ditandai perlu dicek; threshold dapat dikalibrasi dari sampel produksi.

**Tes regresi:** Tes mencakup tiga intent, provider fallback, OCR/voice preview, empty versus provider failure, unknown voice confidence, pending-state overwrite, dan stale callback.

**Hasil akhir:** 31 tes lulus. Smoke test live tanpa write ledger berhasil merutekan greeting, klarifikasi, slang, dan nominal berbentuk kata; OCR fallback menghasilkan satu transaksi Rp25.000; voice tanpa confidence tidak lagi dianggap yakin.

## Model Mengarang Nominal Saat Input Tidak Lengkap

**Kata kunci:** harness P3, nominal hilang, clarification, invented amount, live smoke.

**Klasifikasi:** correctness, AI orchestration, user safety, high.

**Gejala:** Smoke test P3 pada provider nyata mengembalikan intent `transaction` dengan satu item untuk input `beli kopi`, walaupun user tidak menyebut nominal.

**Bukti:** Harness deterministik awal lulus, tetapi request Groq nyata menghasilkan `transaction`; ini membuktikan prompt saja tidak cukup sebagai boundary keselamatan.

**Akar penyebab:** Validator hanya memeriksa nominal hasil model bernilai positif dan tidak memastikan input user memiliki bukti nominal.

**Perbaikan:** Shared validator intent sekarang mengubah hasil menjadi `clarification` bila input transaksi tidak mengandung angka atau kata bilangan Indonesia. Nominal berbentuk digit dan kata tetap diterima.

**Tes regresi:** Harness sengaja mensimulasikan model yang mengarang Rp10.000 untuk `beli kopi` dan memastikan backend menolaknya. Kasus `beli kopi dua puluh lima ribu` tetap menjadi transaksi.

**Hasil akhir:** 38 tes lulus. Smoke test Groq nyata menghasilkan conversation untuk greeting, clarification tanpa item untuk `beli kopi`, dan satu transaction untuk `beli kopi dua puluh lima ribu`; tidak ada write ledger.

## Runtime Memakai Supabase Publishable Key

**Kata kunci:** Supabase, service role, publishable key, RLS, ledger write, project ref.

**Klasifikasi:** configuration, authorization, critical.

**Gejala:** Runtime terhubung ke URL project Benny, tetapi memilih `SUPABASE_KEY` publishable sementara seluruh tabel ledger mencabut akses `anon` dan `authenticated`.

**Bukti:** `.env` memiliki service-role JWT untuk project `lpwcleoguytgoxfgxxek`; schema live memiliki sembilan tabel yang diharapkan dan runtime sebelumnya tidak membaca key tersebut.

**Akar penyebab:** `Config.SUPABASE_KEY` hanya membaca `SUPABASE_KEY`, walaupun bot adalah backend server-only dan `SUPABASE_SERVICE_ROLE_KEY` sudah tersedia.

**Perbaikan:** Boundary konfigurasi sekarang mendahulukan `SUPABASE_SERVICE_ROLE_KEY` dan mempertahankan `SUPABASE_KEY` sebagai fallback kompatibilitas.

**Tes regresi:** Tes memastikan service-role key selalu menang saat kedua variabel tersedia. Smoke live membuat satu user uji, satu expense, dan satu income; retry memakai ID yang sama, ownership lintas user ditolak, update berhasil, lalu seluruh record uji dibersihkan.

**Hasil akhir:** Seluruh pemeriksaan smoke live lulus dan jumlah record milik user uji kembali nol pada `user_profiles`, `transactions`, dan `income`.

## SQL Agent Kurang Memahami Bahasa Sederhana dan Gmail Tidak Memberi Notifikasi

**Kata kunci:** SQL agent, bahasa Indonesia informal, output lengkap, question validation, Gmail, notifikasi transaksi lama.

**Klasifikasi:** routing, UX, background ingestion, high.

**Gejala:** Pertanyaan `aku beli apa aja range 10-60 ribu` dan `kapan aku subscribe chatgpt` masuk ke alur pencatatan. Jawaban `pengeluaran apa yg paling sering` hanya menampilkan nama atau kategori. Transaksi Gmail berhasil disimpan, tetapi tidak menghasilkan pesan Telegram.

**Bukti:** Router SQL mewajibkan irisan keyword finansial dan analitik yang tidak mencakup `beli`, `subscribe`, `kapan`, `range`, atau `apa aja`. Snapshot SQL hanya memiliki enam kolom tanpa `notes` dan `location`. Setelah write Gmail sukses, kode hanya memanggil `_mark_processed` dan logger.

**Akar penyebab:** Pemahaman bahasa berhenti di regex sempit sebelum mencapai model, kontrak detail SQL tidak mewajibkan field presentasi, formatter memotong satu pesan pada 4.000 karakter, dan job Gmail tidak memiliki langkah pengiriman Telegram.

**Perbaikan:** Router menerima bentuk bahasa informal yang tetap memiliki cue histori atau analitik. Prompt model memetakan rentang ribuan, pembelian, langganan, waktu transaksi, dan makna `paling sering`; query detail membawa transaksi, waktu, note, harga, dan lokasi. Formatter menambahkan pembuka, validasi pertanyaan, hasil, catatan pendukung, serta membagi output panjang. Snapshot tetap user-scoped dan read-only dengan tambahan `notes` dan `location`. Gmail mengirim notifikasi setelah write idempoten sukses dan sebelum menandai email selesai. Status lama `expense`/`income` diproses ulang satu kali untuk notifikasi lalu berubah menjadi `expense:notified`/`income:notified`.

**Tes regresi:** Tes mencakup routing langganan, query rentang Rp10.000-Rp60.000, format detail lengkap, agregasi frekuensi beserta jumlah dan total, serta notifikasi transaksi Gmail lama.

**Hasil akhir:** 50 tes penuh dan compile lulus. Smoke Groq nyata memahami lima pertanyaan dari screenshot sebagai query; setelah kontrak frekuensi diperjelas, query `pengeluaran apa yg paling sering` mengembalikan transaksi, jumlah transaksi, dan total pengeluaran. Smoke ini read-only dan tidak menulis ledger production.

## Sinkronisasi Gmail Mencapai Rate Limit Groq

**Kata kunci:** Groq 429, token per minute, Gmail polling, retry delay, batch limit.

**Klasifikasi:** provider rate limit, reliability, high.

**Gejala:** Sinkronisasi Gmail menerima HTTP 429 setelah pemakaian mencapai 5.902 dari batas 6.000 token per menit. Provider meminta menunggu sekitar 8,88 detik, tetapi request berikutnya langsung dicoba.

**Bukti:** Gmail mengambil hingga 100 pesan per polling dan shared AI request mengulang seluruh jenis exception tanpa jeda.

**Akar penyebab:** Batch Gmail tidak disesuaikan dengan batas token provider dan retry policy tidak membedakan error sementara dari respons invalid atau error permanen.

**Perbaikan:** Setiap polling minimal 30 detik mengambil maksimal dua email. HTTP 429 membaca waktu reset dari header Groq atau pesan error sebelum retry; timeout menunggu satu detik. Exception lain langsung diteruskan tanpa retry.

**Tes regresi:** Tes memastikan Gmail meminta maksimal dua email, 429 menunggu durasi provider termasuk format menit-detik, timeout tetap dapat retry, dan error non-transien hanya dipanggil sekali.

**Hasil akhir:** 52 tes lulus, compile seluruh aplikasi lulus, dan pemeriksaan whitespace diff bersih.

## SQL Agent Menolak Pencarian Nama dan Belum Menangani Rate Limit OpenRouter

**Kata kunci:** SQL agent, ChatGPT, LIKE, SQLite authorizer, OpenRouter fallback, GPT OSS 20B, rate limit.

**Klasifikasi:** correctness, provider fallback, user-facing, high.

**Gejala:** Pertanyaan `berapa total pengeluaran ku untuk subscribe chatgpt?` menghasilkan pesan `Query analitik tidak aman atau tidak dapat dijalankan`, walaupun log Groq mencatat request sukses.

**Bukti:** Groq menghasilkan query read-only `SELECT SUM(amount) ... lower(name) LIKE '%chatgpt%'`. Eksekusi snapshot gagal dengan `not authorized to use function: LIKE`. Saat Groq dipaksa gagal, OpenRouter sempat mengembalikan HTTP 429 dengan `Retry-After: 22` dan tidak dicoba ulang.

**Akar penyebab:** SQLite mengekspos operator `LIKE` kepada authorizer sebagai fungsi, tetapi allowlist hanya memiliki `lower`. Shared retry policy juga hanya mengenali tipe rate-limit dari SDK Groq, bukan tipe yang setara dari SDK OpenAI yang dipakai OpenRouter.

**Perbaikan:**

- Tambahkan fungsi SQLite `like` ke allowlist tanpa memperluas akses tabel atau izin write.
- SQL agent mencoba Groq terlebih dahulu, lalu `openai/gpt-oss-20b:free` melalui OpenRouter jika provider utama gagal atau memberi respons invalid.
- OpenRouter memakai reasoning rendah dan output JSON agar token tersedia untuk jawaban akhir.
- Rate limit OpenRouter menghormati `Retry-After` sebelum satu retry sesuai kebijakan bersama.
- Output memakai struktur deterministik: pertanyaan, ringkasan, hasil, dan catatan sumber data.

**Tes regresi:** Tes menjalankan `lower(name) LIKE '%chatgpt%'` di sandbox SQLite, memaksa Groq gagal lalu memastikan OpenRouter dipakai, memeriksa konfigurasi reasoning, dan memverifikasi pembacaan `Retry-After` OpenRouter.

**Hasil akhir:** 54 tes lulus dan compile aplikasi lulus. Retrieval read-only live melalui Groq dan melalui fallback OpenRouter sama-sama menghasilkan `Total pengeluaran: Rp995.670` dari snapshot Supabase user yang sama.

## Conversation Mengaku Punya Pengalaman dan Roast Mengarang Motivasi

**Kata kunci:** human-like text, personal experience, roast, fakta ledger, nominal Rupiah, provider smoke.

**Klasifikasi:** correctness, AI orchestration, user-facing, medium.

**Gejala:** Smoke Groq untuk percakapan santai menghasilkan `Aku juga suka jajan`, seolah Benny memiliki pengalaman pribadi. Smoke roast sintetis menyatakan user tidak punya tujuan pembelanjaan, padahal snapshot hanya berisi nominal, frekuensi, kategori, dan cashflow. Nominal juga ditulis sebagai angka mentah.

**Bukti:** Request memakai explicit memory `jawab singkat dan santai` dan menghasilkan klaim pengalaman pribadi. Snapshot roast dengan tiga transaksi kopi Rp25.000 menghasilkan klaim motivasi yang tidak tersedia pada input serta angka `105000 rupiah`.

**Akar penyebab:** Prompt natural-chat belum melarang klaim pengalaman pribadi secara eksplisit. Roast hanya mengandalkan instruksi model tanpa guard backend yang memastikan output menyebut item dan nominal yang benar serta menolak klaim tujuan, kecanduan, atau nilai diri.

**Perbaikan:**

- Kontrak conversation melarang Benny mengaku memiliki pengalaman, pembelian, preferensi, atau perasaan pribadi.
- Shared conversation boundary mengganti klaim `aku juga suka/pernah/merasa/punya` dengan respons finance-safe.
- Prompt roast melarang inferensi tujuan, motivasi, kecanduan, kekayaan, atau disiplin dan mewajibkan format Rupiah.
- Roast service menerima output model hanya jika menyebut item teratas dan nominal agregat yang benar serta tidak mengandung pola klaim yang tidak didukung; selain itu dipakai fallback deterministik.

**Tes regresi:** Tes memaksa provider mengembalikan `Aku juga suka jajan kopi` dan roast `Kamu tidak punya tujuan hidup`, lalu memastikan keduanya tidak pernah sampai ke user. Tes prompt juga memeriksa batas data, larangan inferensi, dan format Rupiah.

**Hasil akhir:** Focused regression suite lulus. Smoke Groq ulang menghasilkan intent conversation dengan respons `Ceritakan lebih lanjut; aku bantu melihat sisi keuangannya.` Roast yang tidak memenuhi kontrak jatuh ke fallback faktual: total Rp75.000, Kopi tiga kali, dan satu tindakan konkret. Smoke memakai snapshot sintetis dan tidak membaca atau menulis ledger produksi.

## Aturan Verifikasi Masalah Berikutnya

1. Reproduksi input user dan catat output aktual.
2. Trace jalur dari Telegram, intent, resolver, provider, sampai database.
3. Bedakan kegagalan provider, parsing, data kosong, dan write database.
4. Perbaiki shared boundary yang menjadi akar masalah.
5. Tambahkan satu regression test yang gagal sebelum fix.
6. Jalankan request provider nyata bila masalahnya terkait model eksternal.
7. Perbarui dokumen ini dengan gejala, bukti, akar penyebab, fix, dan hasil akhir.

## Dokumen Terkait

- [[agents-finance]]
- [[Gmail Transaction Ingestion]]

## Sumber

- Repository lokal `bot-tele-keuangan`, screenshot Telegram, log runtime, regression test, request Gemini/OpenRouter nyata, dan read-only query Supabase — diperiksa 2026-08-13.
- [Gemini API text and multimodal generation](https://ai.google.dev/gemini-api/docs/text-generation) — diakses 2026-08-13.
- [OpenRouter Qwen2.5 VL 72B Instruct](https://openrouter.ai/qwen/qwen2.5-vl-72b-instruct) — diakses 2026-08-13.
