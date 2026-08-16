# Agent Finance Gap Analysis

Dokumen ini merangkum apa yang diminta untuk "agent finance" dan gap yang masih terlihat di codebase saat ini. Fokusnya sengaja dibuat sederhana: cari yang paling penting dulu, jangan overengineering.

## Yang Kamu Mau

- Persona agent yang terasa seperti teman yang paham konteks, bukan bot kaku.
- Chat natural, fleksibel, dan enak diajak ngobrol.
- Output tetap terstruktur saat menyangkut uang, transaksi, laporan, atau konfirmasi.
- Bisa memahami input tidak rapi: typo, slang, campur konteks, dan kalimat tidak lengkap.
- Bisa menangani OCR, voice-to-text, fitur, system message, LLM, fallback, memory, database, harness, dan infrastruktur AI secara rapi.
- Ada analisis celah yang belum kelihatan supaya desainnya tidak bocor di belakang.

## Ringkasan Temuan

Saat ini produk lebih dekat ke "transaction capture bot" daripada "finance friend agent".

Yang sudah ada:

- Input teks, foto struk, dan voice note.
- Ekstraksi AI untuk transaksi.
- Konfirmasi sebelum simpan transaksi manual.
- Supabase sebagai penyimpanan ledger.
- Fallback OCR dan voice transcription.

Yang masih lemah:

- Persona belum konsisten sebagai teman yang natural.
- Sistem pesan belum dirancang sebagai kontrak percakapan yang tegas.
- Jalur fallback belum dibedakan dengan jelas antara gagal baca, gagal model, dan tidak ada transaksi.
- Memory belum jadi fitur percakapan yang jelas, masih campur dengan kebutuhan data.
- Ada gap antara dokumen scope dan harapan user untuk chat yang lebih hidup.

## Celah Utama

### 1. Unclear message

- Pesan user yang pendek, ambigu, atau campur konteks belum punya jalur klarifikasi yang tegas.
- Bot perlu tahu kapan harus bertanya balik, kapan harus mengekstrak, dan kapan harus menolak asumsi.

### 2. OCR

- OCR butuh status yang jelas: terbaca, tidak terbaca, confidence rendah, atau provider gagal.
- Hasil OCR sebaiknya ditampilkan ke user sebelum diproses lanjut.

### 3. Voice-to-text

- Transkrip suara perlu dianggap sebagai artefak antara, bukan hasil final.
- Kalau transkrip tidak yakin, bot harus minta konfirmasi, bukan diam-diam menebak.

### 4. Fitur

- Harus dibedakan mana fitur inti dan mana fitur tambahan.
- Kalau semua masuk sekaligus, produk jadi berat dan kabur.

### 5. System message

- Persona harus ditulis sebagai kontrak: gaya bahasa, batasan, tujuan, dan cara bicara.
- Untuk transaksi, jawaban harus pendek dan terstruktur.
- Untuk chat ringan, jawaban boleh lebih natural.

### 6. LLM

- LLM dipakai untuk pemahaman, bukan untuk mengarang fakta.
- Output LLM perlu dibatasi schema sederhana supaya tidak liar.

### 7. Fallback

- Fallback harus beda antara:
  - provider mati,
  - hasil ambigu,
  - parsing gagal,
  - data tidak ada.
- Kalau semua disamaratakan, user tidak tahu masalahnya di mana.

### 8. Infrastruktur AI

- Perlu timeout, retry, logging, dan jejak model/provider yang dipakai.
- Harus jelas kapan request jatuh ke provider cadangan.

### 9. Bot Telegram

- Telegram adalah transport, bukan tempat logic utama.
- Controller harus tetap tipis, supaya alur gampang dirawat.

### 10. Memory

- Memory perlu dipisah menjadi:
  - session memory pendek,
  - memory eksplisit yang disimpan,
  - data ledger yang memang sumber kebenaran.
- Jangan campur "ingat" dengan "asumsi model".

### 11. Database

- Database harus memegang fakta yang bisa diaudit.
- Kalau ada chat memory, harus jelas beda dengan ledger transaksi.

### 12. Harness

- Perlu harness minimal untuk cek:
  - intent,
  - ekstraksi,
  - fallback,
  - persona,
  - format output,
  - regresi chat penting.

### 13. Potensi Yang Belum Kelihatan

- Ada risiko konflik antara scope dokumen lama dan harapan produk baru.
- Ada risiko state confirmation tertimpa kalau user kirim pesan berurutan.
- Ada risiko data provider langsung masuk tanpa boundary konfirmasi yang cukup jelas.
- Ada risiko async flow terganggu kalau akses DB masih sync.
- Ada risiko state lokal tidak aman kalau bot jalan di lebih dari satu instance.
- Ada risiko prompt injection dari OCR, voice transcript, atau teks user.

## Prinsip Desain

- Satu input, satu intent utama.
- Kalau ragu, tanya balik.
- Kalau uang, tetap struktural.
- Kalau chat biasa, tetap natural.
- Jangan simpan asumsi sebagai fakta.
- Jangan bikin banyak layer kalau satu guard cukup.

## Plan P0-P4

### P0

Wajib dulu. Ini fondasi supaya produk tidak salah arah.

- Tegaskan persona agent finance di system message.
- Buat format respons yang natural tapi tetap terstruktur.
- Pisahkan intent percakapan biasa dari intent transaksi.
- Tambahkan jalur klarifikasi untuk input yang ambigu.
- Pastikan fallback punya alasan yang jelas.
- Tutup risiko konfirmasi yang bisa ketimpa state baru.

### P1

Robustness input multimodal.

- Rapikan alur OCR.
- Rapikan alur voice-to-text.
- Tampilkan hasil transkrip/ekstrak sebelum final save.
- Bedakan gagal provider vs hasil kosong vs hasil ambigu.

### P2

Memory yang minimal tapi benar.

- Tambah session memory singkat.
- Tambah explicit memory yang bisa diset user.
- Bedakan memory dari ledger dan dari asumsi model.
- Sediakan perilaku yang jelas untuk remember, show, update, dan forget.

### P3

Kualitas operasional.

- Tambah logging yang berguna untuk audit AI.
- Tambah harness/regression check untuk prompt dan intent.
- Tambah timeout/retry yang konsisten.
- Cek dampak async vs sync di jalur DB dan AI.

### P4

Fitur lanjutan kalau fondasi sudah stabil.

- Chat keuangan yang lebih panjang.
- Ringkasan dan insight yang lebih pintar.
- Kustomisasi gaya bicara per user.
- Reporting yang lebih kaya.
- Ekspansi fitur non-inti bila scope produk memang sudah disepakati.

## Kesimpulan Singkat

Kalau targetnya adalah "agent finance yang terasa seperti teman", maka urutan benar bukan nambah fitur dulu, tapi:

1. tegaskan persona,
2. rapikan intent dan klarifikasi,
3. amankan fallback dan confirmation,
4. baru tambah memory dan chat lebih natural.

Itu cara paling aman dan paling sedikit kode untuk mencapai efek yang kamu mau.

## Status Implementasi P0, P1, P2, dan P3

Selesai dan diverifikasi pada 13 Agustus 2026.

### P0

- [x] Persona Benny sebagai teman keuangan privat menjadi kontrak system message: natural, singkat, tanpa emotikon, tidak mengarang fakta, dan satu intent utama.
- [x] Respons percakapan dipisahkan dari respons uang; preview transaksi selalu memakai field jenis, tanggal, item/sumber, kategori, nominal, dan lokasi.
- [x] Satu schema AI merutekan `transaction`, `clarification`, atau `conversation`.
- [x] Input yang diduga transaksi tetapi belum lengkap menghasilkan satu pertanyaan klarifikasi dan dapat dilanjutkan pada pesan berikutnya.
- [x] Provider gagal, respons AI invalid, hasil kosong, dan input ambigu memiliki pesan berbeda serta tidak menulis ledger.
- [x] Input baru tidak dapat menimpa `pending_confirmation`; callback menyertakan operation ID sehingga tombol lama tidak dapat menyimpan state baru.

### P1

- [x] OCR menghasilkan artefak `status`, `confidence`, `raw_text`, `items`, dan provider; status dibedakan menjadi terbaca, confidence rendah, dan tidak terbaca.
- [x] OCR menolak instruksi dalam gambar, membatasi satu record ledger, dan tetap memakai total akhir struk.
- [x] Voice-to-text menghasilkan artefak transkrip dan status confidence; confidence yang tidak tersedia diperlakukan sebagai perlu dicek.
- [x] Teks OCR atau transkrip voice tampil di layar review sebelum tombol simpan.
- [x] Provider gagal, artefak kosong, dan hasil ambigu dibedakan untuk OCR maupun voice.

### P2

- [x] Session memory dibatasi pada enam pesan user/assistant terakhir dalam sesi chat aktif.
- [x] Explicit memory hanya tersimpan dari perintah langsung user di `user_preferences` dengan source `explicit`.
- [x] Perintah remember, show, update, dan forget tersedia melalui `ingat`, `ingat apa`, `ubah ingatan`, dan `lupakan`.
- [x] Update dan forget yang cocok ke beberapa ingatan ditolak sampai user memberi frasa lebih spesifik.
- [x] Session memory dan explicit memory hanya menjadi konteks percakapan; fakta uang tetap berasal dari `transactions` dan `income` serta tetap memerlukan konfirmasi sebelum write.

### P3

- [x] Seluruh request Groq, Gemini, dan OpenRouter memakai kebijakan timeout/retry yang sama dan dapat dikonfigurasi melalui environment.
- [x] Audit AI mencatat operation, provider, model, attempt, durasi, status, tipe error, intent atau status hasil tanpa mencatat prompt, gambar, voice, email, maupun isi transaksi.
- [x] Harness regresi melindungi kontrak system prompt, tiga intent utama, schema transaksi, timeout/retry, dan sanitasi audit.
- [x] Seluruh akses Supabase sinkron dari jalur async Telegram, capture, report, memory, callback, dan Gmail dipindahkan ke worker thread agar event loop tidak tertahan.
- [x] Write database tidak di-retry otomatis; idempotency dan konfirmasi tetap menjadi boundary keselamatan mutasi.

### Bukti

- 38 regression tests lulus, termasuk intent, klarifikasi, fallback, artefak multimodal, stale callback, idempotency, laporan, ledger ownership, seluruh lifecycle memory, prioritas routing memory, audit AI, timeout/retry, dan non-blocking database write.
- `compileall` dan `git diff --check` lulus.
- Smoke test live tanpa write database membuktikan conversation, clarification, slang transaction, nominal berbentuk kata, OCR primary-to-fallback, dan voice transcription. Struk sintetis terbaca sebagai satu transaksi Rp25.000; voice tanpa confidence ditandai perlu dicek.
- Smoke test live P2 membuktikan session history, remember, show, update, dan forget pada Supabase aktif; data sintetis dibersihkan sampai nol. Request AI live memakai explicit memory sebagai konteks percakapan dan menghasilkan nol item ledger.
