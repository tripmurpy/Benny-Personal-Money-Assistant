# Strategi Produk Benny Personal Money Assistant

**Versi:** 1.0  
**Tanggal:** 15 Juli 2026  
**Status:** Proposed  
**Horizon:** 90 hari  
**Mode produk yang direkomendasikan:** Private single-user

---

## 1. Ringkasan Eksekutif

Benny harus menjadi cara tercepat dan paling dapat dipercaya untuk mencatat serta memahami keuangan pribadi melalui Telegram.

Strategi ini tidak mengejar jumlah fitur. Fokusnya adalah satu core loop yang sederhana:

> Kirim satu pesan, transaksi tercatat dengan benar, lalu mudah dibatalkan atau diperbaiki.

Fondasi produk saat ini sudah kuat: input teks natural, OCR struk, voice note, pencarian pengeluaran, budget, goals, laporan, dan coaching. Namun, pengalaman pengguna masih memiliki tiga masalah utama:

1. Pencatatan teks meminta keputusan tambahan tetapi tidak memperlihatkan hasil parsing sebelum simpan.
2. Arti budget, saldo, kategori, dan sumber dana belum konsisten.
3. Beberapa fitur terlihat selesai di UI, tetapi belum memiliki loop yang lengkap, terutama progress goals dan laporan pemasukan-pengeluaran.

Karena itu, urutan strategi adalah:

1. Benarkan kebenaran data dan status penyimpanan.
2. Pangkas langkah pencatatan transaksi.
3. Jadikan riwayat sebagai pusat kontrol.
4. Lengkapi budget dan goals.
5. Tambahkan engagement yang relevan setelah core loop stabil.

Keputusan utama: pertahankan Benny sebagai private single-user product selama horizon strategi ini. Target multi-user, subscription, dan dashboard web ditunda sampai penggunaan harian dan kepercayaan data terbukti.

---

## 2. Konteks Produk Saat Ini

### 2.1 Kemampuan yang sudah tersedia

- Pencatatan pengeluaran dan pemasukan melalui bahasa natural.
- Ekstraksi beberapa transaksi dari satu pesan.
- OCR foto struk dengan fallback model vision.
- Transkripsi voice note dan parsing transaksi.
- Konfirmasi sebelum menyimpan hasil OCR dan voice.
- Pencarian pengeluaran berdasarkan periode dengan bahasa natural.
- Perubahan dan penghapusan transaksi melalui bahasa natural.
- Budget kategori dan peringatan terjadwal.
- Pembuatan dan tampilan financial goals.
- Ringkasan saldo, laporan periode, trend, coaching, dan PDF.
- Pembatasan akses ke satu Telegram `ADMIN_ID`.

### 2.2 Realitas implementasi

- Produk berjalan sebagai bot privat untuk satu user, bukan platform multi-user.
- Pengeluaran dan pemasukan disimpan pada sumber data yang berbeda.
- Budget saat ini diperlakukan sebagai saldo yang berkurang, walaupun diberi nama `monthly_limit`.
- Goal dapat dibuat dan ditampilkan, tetapi belum ada user flow untuk menambah tabungan.
- State konfirmasi disimpan di memory proses dan dapat hilang ketika bot restart.
- Login username/password masih digunakan meskipun Telegram ID sudah menjadi whitelist.
- Beberapa klaim pada PRD lama tidak lagi sejalan dengan implementasi Supabase saat ini.

### 2.3 Masalah pengguna yang harus diselesaikan

| Masalah pengguna | Dampak | Prioritas |
|---|---|---:|
| Mencatat transaksi terasa memiliki terlalu banyak langkah | User malas mencatat konsisten | P0 |
| User tidak yakin hasil AI benar sebelum/ketika disimpan | Kepercayaan terhadap bot turun | P0 |
| Angka budget dan laporan dapat memiliki arti yang berbeda | Keputusan finansial bisa salah | P0 |
| Sulit melihat dan memperbaiki transaksi terakhir | Koreksi terasa seperti pekerjaan teknis | P0 |
| Goal tidak bisa menerima kontribusi | Fitur terlihat ada tetapi tidak memberi nilai | P1 |
| Reminder tidak memiliki preferensi waktu/snooze | Bot dapat terasa mengganggu | P1 |
| Terlalu banyak tombol utama | Fokus produk tidak jelas | P1 |

---

## 3. Arah dan Positioning Produk

### 3.1 Product vision

> Benny adalah asisten keuangan pribadi di Telegram yang membuat pencatatan uang terasa seperti mengirim chat, bukan mengisi pembukuan.

### 3.2 Target pengguna utama

Pengguna Telegram yang:

- Ingin mengetahui ke mana uangnya pergi.
- Tidak konsisten menggunakan spreadsheet atau aplikasi keuangan formal.
- Melakukan 1-10 transaksi pribadi per hari.
- Menginginkan input cepat melalui teks, foto, atau suara.
- Membutuhkan ringkasan sederhana, bukan laporan akuntansi kompleks.

### 3.3 Jobs to be Done

#### JTBD utama

> Ketika baru melakukan transaksi, saya ingin mencatatnya dalam beberapa detik agar tidak lupa dan tidak perlu membuka aplikasi keuangan yang rumit.

#### JTBD pendukung

> Ketika ingin membeli sesuatu, saya ingin tahu apakah pengeluaran saya masih aman sampai pemasukan berikutnya.

> Ketika melihat angka yang salah, saya ingin memperbaikinya langsung tanpa mencari command.

> Ketika mendekati batas pengeluaran, saya ingin mendapat peringatan yang jelas dan tidak menghakimi.

### 3.4 Product promise

- Satu pesan cukup untuk mencatat transaksi normal.
- Tidak ada transaksi dianggap tersimpan sebelum database mengonfirmasi keberhasilan.
- Semua transaksi yang baru dicatat dapat dibatalkan atau diedit dengan mudah.
- Ringkasan selalu menjelaskan periode dan sumber perhitungannya.
- Bot hanya bertanya ketika informasi yang diperlukan benar-benar belum cukup.

### 3.5 North Star Metric

**Verified Logging Days per Week**  
Jumlah hari dalam satu minggu ketika user berhasil menyimpan minimal satu transaksi yang valid.

Metric ini dipilih karena mengukur kebiasaan yang menghasilkan data finansial berguna. Jumlah pesan, chat AI, atau PDF yang dibuat bukan ukuran nilai utama.

---

## 4. Prinsip Pengalaman Pengguna

### 4.1 One message, one outcome

Setiap pesan user harus menghasilkan salah satu outcome yang jelas:

- Tersimpan.
- Membutuhkan satu informasi tambahan.
- Menampilkan jawaban/ringkasan.
- Gagal dan dapat dicoba ulang.

Bot tidak boleh meninggalkan user dalam state yang ambigu.

### 4.2 Ask only when necessary

Tidak perlu membangun confidence engine baru. Gunakan validasi sederhana:

- Jika jenis transaksi, nominal positif, item, dan tanggal valid: simpan.
- Jika salah satu field wajib tidak valid: tanyakan satu hal yang hilang.
- OCR dan voice tetap menggunakan review karena risiko interpretasinya lebih tinggi.

### 4.3 Fast path dan safe path

- **Fast path:** teks yang lengkap langsung disimpan, kemudian menyediakan `Batalkan` dan `Edit`.
- **Safe path:** OCR, voice, transaksi multi-item kompleks, atau input tidak lengkap menampilkan preview dahulu.

### 4.4 Progressive disclosure

Menu utama hanya menampilkan kebutuhan yang paling sering digunakan. Detail, PDF, trend, dan coaching ditempatkan di dalam Ringkasan.

### 4.5 Calm financial language

Copy harus:

- Singkat dan konsisten dalam Bahasa Indonesia.
- Menyebut angka dan tindakan yang dapat dilakukan.
- Tidak menghakimi atau terlalu ceria saat kondisi keuangan buruk.
- Menggunakan emoji hanya sebagai penanda, bukan dekorasi setiap baris.

Contoh:

- Baik: `Budget Food sudah 82%. Sisa Rp180.000 sampai akhir bulan.`
- Hindari: `Waduh boros banget nih bos! Semangat pasti bisa balance lagi!`

### 4.6 Truth before delight

Animasi, personality, coaching, dan copy ramah tidak boleh menutupi status penyimpanan atau kegagalan database.

---

## 5. Definisi Produk yang Harus Konsisten

### 5.1 Transaksi

Catatan perpindahan uang yang memiliki:

- Tipe: `expense` atau `income`.
- Item/sumber.
- Nominal.
- Tanggal dan waktu.
- Kategori.
- Lokasi atau catatan opsional.

### 5.2 Kategori

Menjelaskan tujuan pengeluaran, misalnya Food, Transport, Bills, Shopping, atau Other. Kategori bukan sumber dana.

### 5.3 Budget

Batas pengeluaran kategori dalam periode tertentu.

Rumus:

```text
Sisa budget = limit bulanan - total transaksi kategori pada bulan berjalan
```

Budget tidak dikurangi dengan mengubah nilai limit. Nilai limit tetap, penggunaan dihitung dari transaksi.

### 5.4 Goal

Target tabungan yang memiliki target, jumlah terkumpul, dan kontribusi. Goal bukan sisa saldo otomatis.

### 5.5 Saldo dan arus kas

Jika Benny belum menyimpan opening balance dan seluruh mutasi rekening, istilah `Saldo Rekening` tidak boleh digunakan. Gunakan:

- `Arus kas bulan ini`, atau
- `Sisa sejak pemasukan terakhir`.

### 5.6 Status penyimpanan

Setiap transaksi pada UI harus memiliki salah satu status konseptual:

- `Memproses`
- `Tersimpan`
- `Belum tersimpan`
- `Dibatalkan`

User tidak perlu melihat istilah teknis database.

---

## 6. Desain Core User Flow

### 6.1 Onboarding private mode

```text
User membuka bot atau mengetik /start
        ↓
Telegram ID diverifikasi terhadap ADMIN_ID
        ↓
Bot menampilkan manfaat + satu contoh input
        ↓
Menu utama tersedia
```

Respons yang direkomendasikan:

```text
Halo, aku Benny.

Kirim transaksi seperti:
"Makan siang 35rb"

Aku akan mencatat dan merangkum keuanganmu.
```

Tidak ada username, password, nama lengkap, atau ulang tahun yang wajib diisi. Nama Telegram cukup untuk personalisasi dasar. Profil tambahan hanya diminta ketika benar-benar dipakai oleh suatu fitur.

### 6.2 Pencatatan teks lengkap

```text
User: Makan padang 35rb
        ↓
AI mengekstrak transaksi
        ↓
Validasi field wajib
        ↓
Simpan ke database
        ↓
Tampilkan receipt + aksi koreksi
```

Respons:

```text
Tersimpan

Makan Padang · Rp35.000
Food · Hari ini, 12:30

[Batalkan] [Edit]
```

### 6.3 Input tidak lengkap

```text
User: Bayar listrik

Benny: Nominalnya berapa?

User: 450rb
```

Bot menggabungkan konteks tanpa mengirim ulang kalimat panjang yang tidak diperlukan.

### 6.4 Multi-item text

```text
User: Kopi 20rb, makan 35rb, parkir 5rb

Benny:
3 transaksi
• Kopi · Rp20.000
• Makan · Rp35.000
• Parkir · Rp5.000
Total Rp60.000

[Simpan Semua] [Edit] [Batal]
```

Multi-item menggunakan safe path karena satu kesalahan dapat menghasilkan beberapa data salah.

### 6.5 OCR

```text
Foto dikirim
        ↓
Satu status message: Membaca struk
        ↓
Ekstraksi dan validasi total
        ↓
Preview item + total
        ↓
[Simpan] [Edit] [Batal]
```

Aturan UX:

- Gunakan satu message yang diperbarui agar chat tidak penuh.
- Tampilkan total dan jumlah item.
- Jika jumlah item tidak cocok dengan total struk, tampilkan warning.
- Terima foto Telegram dan gambar yang dikirim sebagai document.
- Error harus memberi tindakan: foto ulang, crop, atau ketik manual.

### 6.6 Voice

```text
Voice note dikirim
        ↓
Transkripsi ditampilkan
        ↓
Transaksi hasil parsing ditampilkan
        ↓
[Simpan] [Edit Teks] [Batal]
```

User harus dapat memperbaiki teks transkripsi, bukan hanya mengetik ulang seluruh transaksi dari awal.

### 6.7 Edit melalui reply

```text
User reply receipt: Harusnya 20rb
        ↓
Bot mengikat reply ke transaksi tersebut
        ↓
Tampilkan perubahan lama → baru
        ↓
[Konfirmasi] [Batal]
```

Jika reply tidak menunjuk receipt transaksi, barulah diproses sebagai chat biasa.

### 6.8 Riwayat

```text
Riwayat Terakhir

1. Kopi · Rp25.000
2. Makan Siang · Rp35.000
3. Parkir · Rp5.000

[Pilih Transaksi] [Cari]
```

Setelah transaksi dipilih:

```text
[Edit] [Hapus] [Catat Lagi]
```

### 6.9 Kegagalan penyimpanan

```text
Belum tersimpan

Koneksi sedang bermasalah. Datamu belum masuk.

[Coba Lagi] [Salin Detail]
```

Bot tidak boleh mengirim copy sukses jika operasi database gagal.

---

## 7. Struktur Navigasi

### 7.1 Menu utama

```text
[Ringkasan] [Riwayat]
[Budget]    [Goals]
```

User tetap dapat langsung mengetik transaksi tanpa membuka menu.

### 7.2 Ringkasan

```text
Ringkasan Juli

Pemasukan      Rp8.000.000
Pengeluaran    Rp4.200.000
Arus kas       Rp3.800.000

Terbesar: Food · Rp1.400.000
Budget terdekat: Transport · 82%

[Detail] [Trend] [PDF]
```

Coaching diberikan sebagai satu insight di bawah ringkasan, bukan menjadi menu utama terpisah.

### 7.3 Budget

```text
Budget Juli

Food
Rp650.000 / Rp1.000.000 · 65%

Transport
Rp410.000 / Rp500.000 · 82%

[Atur Budget] [Detail]
```

### 7.4 Goals

```text
Goal Liburan
Rp2.000.000 / Rp5.000.000 · 40%

[Tambah Tabungan] [Riwayat] [Edit]
```

---

## 8. Strategi Fitur dan Prioritas

### 8.1 P0 — Trust dan core loop

| Inisiatif | Nilai pengguna | Reach | Impact | Confidence | Effort relatif |
|---|---|---:|---:|---:|---:|
| Instant save + Undo/Edit | Pencatatan tercepat dan aman | Sangat tinggi | Sangat tinggi | Tinggi | Sedang |
| Status simpan yang jujur | Mencegah kehilangan data tersembunyi | Sangat tinggi | Sangat tinggi | Tinggi | Rendah |
| Perbaikan definisi budget | Angka budget dapat dipercaya | Tinggi | Sangat tinggi | Tinggi | Sedang |
| Ringkasan income-expense terpadu | User memahami kondisi uang | Tinggi | Sangat tinggi | Tinggi | Sedang |
| Riwayat + kontrol transaksi | Koreksi mudah dan transparan | Tinggi | Tinggi | Tinggi | Sedang |
| Onboarding tanpa login tambahan | Menghapus friksi masuk | Sedang | Tinggi | Tinggi | Rendah |

### 8.2 P1 — Completion dan retention

| Inisiatif | Nilai pengguna | Effort relatif |
|---|---|---:|
| Reply-to-edit | Koreksi terasa natural | Sedang |
| Kontribusi dan riwayat goals | Goal menjadi actionable | Sedang |
| Reminder preference + snooze | Engagement tanpa mengganggu | Rendah |
| Recurring transaction suggestion | Mengurangi pencatatan berulang | Sedang |
| Weekly digest satu insight | Membantu tindakan nyata | Rendah |
| Forward-to-Benny | Mempercepat input notifikasi pembayaran | Sedang |

### 8.3 P2 — Differentiation

| Inisiatif | Prasyarat |
|---|---|
| Safe-to-spend per hari | Income, tagihan, periode, dan budget sudah akurat |
| Duplicate/anomaly detection | Data historis cukup dan core save stabil |
| OCR total reconciliation | OCR dasar terukur akurasinya |
| Catch-up prompt harian | Reminder preference sudah tersedia |

### 8.4 Tidak dibangun dalam horizon ini

- Dashboard web.
- Multi-currency.
- Prediksi finansial kompleks.
- Integrasi bank langsung.
- Multi-user SaaS dan subscription.
- Chatbot general-purpose untuk semua topik.
- RAG harga menu atau katalog yang tidak mendukung JTBD keuangan.
- Banyak rekening, wallet, dan transfer antar-account.
- Auto-save transaksi rutin tanpa konfirmasi.

---

## 9. Roadmap 90 Hari

### Phase 0 — Product truth baseline (Minggu 1)

Tujuan: menyepakati arti angka dan mengukur kondisi awal.

Deliverables:

- Tetapkan definisi transaction, budget, goal, dan arus kas.
- Catat baseline waktu pencatatan, error simpan, dan koreksi.
- Audit seluruh copy sukses agar bergantung pada hasil database.
- Tentukan bahwa mode produk tetap single-user.
- Bekukan penambahan fitur non-core.

Exit criteria:

- Tidak ada istilah keuangan yang memiliki dua arti berbeda.
- Semua operasi mutasi mempunyai success/failure outcome yang eksplisit.
- Baseline core metrics tersedia.

### Phase 1 — Fast and trustworthy capture (Minggu 2-4)

Tujuan: menjadikan pencatatan teks selesai dalam satu pesan.

Deliverables:

- Hapus pilihan sumber dana dari transaksi normal.
- Auto-save teks lengkap.
- Tambahkan tombol Batalkan dan Edit pada receipt.
- Safe path untuk multi-item dan input tidak lengkap.
- Perbaiki state kegagalan database dan tombol Coba Lagi.
- Sederhanakan `/start` untuk private mode.

Exit criteria:

- Median transaksi teks selesai dalam maksimal 3 detik.
- Satu transaksi teks lengkap tidak memerlukan input lanjutan.
- Undo tidak menghasilkan transaksi duplikat atau data yatim.
- Database failure tidak pernah ditampilkan sebagai sukses.

### Phase 2 — Control and clarity (Minggu 5-7)

Tujuan: user dapat memahami dan mengontrol data tanpa command.

Deliverables:

- Menu Riwayat transaksi terakhir.
- Edit, Hapus, dan Catat Lagi.
- Reply-to-edit pada receipt transaksi.
- Ringkasan pemasukan dan pengeluaran terpadu.
- Konsolidasi menu utama menjadi empat tombol.
- Copy Bahasa Indonesia yang konsisten.

Exit criteria:

- User dapat mengoreksi transaksi terakhir maksimal dua interaksi.
- Semua laporan menjelaskan periodenya.
- Ringkasan tidak mencampur saldo rekening dengan arus kas tercatat.

### Phase 3 — Budget and goals that work (Minggu 8-10)

Tujuan: melengkapi dua loop finansial utama setelah pencatatan.

Deliverables:

- Budget memiliki fixed monthly limit.
- Penggunaan budget dihitung dari transaksi kategori bulan berjalan.
- Alert 80% dan 100% tanpa alert berulang setiap enam jam.
- Flow tambah kontribusi, ambil dana, dan riwayat goal.
- Ringkasan budget dan goal di menu utama.

Exit criteria:

- Budget tidak perlu di-reset manual setiap bulan.
- Nilai penggunaan budget sama dengan total transaksi kategori pada periode tersebut.
- Goal dapat bergerak dari 0% tanpa perubahan database manual.

### Phase 4 — Useful engagement (Minggu 11-13)

Tujuan: meningkatkan konsistensi tanpa membuat bot berisik.

Deliverables:

- Pengaturan waktu reminder, snooze, dan off.
- Weekly digest dengan satu insight dan satu tindakan.
- Saran transaksi berulang setelah pola yang cukup ditemukan.
- Peningkatan OCR/voice berdasarkan data kegagalan aktual.

Exit criteria:

- Reminder hanya dikirim sesuai preferensi user.
- Satu pola transaksi tidak menghasilkan notifikasi berulang.
- Weekly digest dapat dibaca dalam kurang dari 20 detik.

---

## 10. Acceptance Criteria per Fitur Utama

### 10.1 Instant save

- Input `makan siang 35rb` menghasilkan item, amount, category, dan waktu yang valid.
- Transaksi baru hanya disebut tersimpan setelah database berhasil.
- Receipt menyediakan Batalkan dan Edit.
- Double tap tidak membuat transaksi ganda.
- Nominal 0 atau negatif tidak dapat disimpan sebagai pengeluaran normal.

### 10.2 Undo

- Hanya transaksi yang terkait receipt tersebut yang dibatalkan.
- Aksi kedua pada tombol yang sama tidak menghapus data lain.
- UI berubah menjadi `Dibatalkan` setelah berhasil.
- Jika gagal, receipt tetap menunjukkan bahwa transaksi masih tersimpan.

### 10.3 Riwayat

- Urutan menggunakan tanggal dan waktu, terbaru lebih dahulu.
- Income dan expense memiliki indikator berbeda.
- User dapat membuka detail tanpa AI call.
- Edit dan hapus selalu meminta konfirmasi perubahan yang jelas.

### 10.4 Budget

- Limit tidak berubah ketika transaksi dicatat.
- Usage hanya berasal dari transaksi pada periode aktif.
- Transaksi yang diedit atau dihapus langsung memengaruhi usage.
- Alert tidak dikirim ulang untuk threshold yang sama pada periode yang sama.

### 10.5 Goals

- Kontribusi menambah `current_amount`.
- Penarikan tidak dapat membuat nilai negatif.
- Goal selesai ketika target tercapai.
- Setiap perubahan mempunyai riwayat yang dapat ditinjau.

### 10.6 OCR dan voice

- Tidak ada data disimpan sebelum preview dikonfirmasi.
- User dapat mengedit hasil tanpa mengulang dari awal.
- Error memberi tindakan yang spesifik.
- Tombol konfirmasi menjadi nonaktif setelah digunakan.

---

## 11. Measurement Plan

### 11.1 Product metrics

| Metric | Definisi | Target 90 hari |
|---|---|---:|
| Verified Logging Days | Hari dengan minimal satu transaksi tersimpan | ≥5 hari/minggu |
| Capture Completion Rate | Input transaksi yang berakhir tersimpan | ≥95% |
| Median Capture Time | Dari pesan masuk hingga receipt tersimpan | ≤3 detik untuk teks |
| Correction Rate | Transaksi diedit/dibatalkan dalam 10 menit | <10% setelah stabil |
| Weekly Summary Usage | Ringkasan dibuka minimal sekali per minggu | ≥1 kali/minggu |
| Reminder Opt-out | Reminder dimatikan setelah diterima | <30% |

Target single-user diperlakukan sebagai health threshold, bukan statistik populasi.

### 11.2 Reliability metrics

| Metric | Target |
|---|---:|
| False success response | 0 |
| Duplicate transaction rate | 0 |
| Database write failure yang tidak terlihat user | 0 |
| Text parse valid rate | ≥95% untuk pola transaksi umum |
| OCR success pada foto jelas | ≥90% |
| Voice transcription usable | ≥90% untuk audio Indonesia yang jelas |

### 11.3 Event minimum

Gunakan logging atau storage yang sudah tersedia sebelum menambah analytics dependency baru.

Event minimum:

- `capture_received`
- `capture_needs_clarification`
- `capture_saved`
- `capture_failed`
- `capture_undone`
- `transaction_edited`
- `summary_viewed`
- `budget_threshold_reached`
- `goal_contribution_added`
- `reminder_snoozed`
- `reminder_disabled`

Jangan menyimpan isi pesan sensitif pada analytics jika ID event dan hasil sudah cukup.

---

## 12. Reliability, Privacy, dan Safety

### 12.1 Data integrity

- Semua write harus memeriksa hasil database.
- Callback harus idempotent.
- Retry tidak boleh membuat record duplikat.
- Update dan delete harus dibatasi oleh user dan transaction ID.
- State penting tidak boleh hanya bergantung pada dictionary in-memory jika harus bertahan setelah restart.

### 12.2 Privacy

- Private mode menggunakan Telegram ID whitelist sebagai kontrol akses utama.
- Jangan meminta password di chat untuk mode single-user.
- Jelaskan bahwa chat dan data transaksi diproses oleh Telegram, provider AI, dan Supabase.
- Sediakan command atau menu untuk menghapus chat history AI jika history disimpan.
- Jangan mengirim seluruh histori transaksi ke model jika ringkasan agregat sudah cukup.

### 12.3 AI boundaries

- AI digunakan untuk ekstraksi, klasifikasi, dan bahasa natural.
- Perhitungan uang, budget, total, dan progress menggunakan kode deterministik.
- AI tidak menjadi sumber kebenaran untuk saldo atau jumlah total.
- Coaching tidak boleh dianggap sebagai nasihat investasi profesional.

---

## 13. Content and Tone Guidelines

### 13.1 Format receipt

```text
Tersimpan

Kopi Susu · Rp25.000
Drink · 15 Jul, 10:32

[Batalkan] [Edit]
```

### 13.2 Format error

```text
Belum tersimpan

Koneksi sedang bermasalah. Datamu belum masuk.

[Coba Lagi]
```

### 13.3 Format budget warning

```text
Budget Transport sudah 82%.

Terpakai Rp410.000 dari Rp500.000.
Sisa Rp90.000 sampai akhir Juli.
```

### 13.4 Format insight

```text
Pengeluaran makan di luar naik Rp180.000 minggu ini.

Mengurangi satu pembelian Rp30.000 akan mengembalikan pengeluaran ke level minggu lalu.
```

### 13.5 Terminologi

Gunakan secara konsisten:

- `Tersimpan`, bukan bergantian dengan saved/success.
- `Pengeluaran`, bukan expense pada UI.
- `Pemasukan`, bukan income pada UI.
- `Ringkasan`, bukan dashboard/analytics.
- `Batas budget` dan `Terpakai`, bukan saldo budget.

---

## 14. Risiko dan Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Auto-save menyimpan hasil AI yang salah | Kepercayaan turun | Undo/Edit selalu tersedia; safe path untuk input kompleks |
| Perubahan budget merusak data lama | Laporan tidak konsisten | Tetapkan periode transisi dan verifikasi total sebelum/akhir migrasi |
| Callback ditekan dua kali | Duplikat atau delete ganda | Idempotency pada operasi mutasi |
| Bot restart saat ada pending confirmation | User kehilangan flow | Beri expiry jelas; persist hanya state yang benar-benar perlu |
| Reminder terasa mengganggu | User mematikan bot | Opt-in, waktu pilihan, snooze, dan threshold anti-spam |
| Terlalu banyak AI call memperlambat bot | Capture melewati target | Gunakan deterministic routing dan template untuk flow sederhana |
| Scope berkembang menjadi platform finansial | Core loop tidak selesai | Out-of-scope list menjadi release gate |

---

## 15. Launch dan Validation Strategy

### 15.1 Dogfood scenario wajib

Sebelum setiap phase dianggap selesai, jalankan skenario nyata berikut:

1. Pengeluaran teks satu item.
2. Pemasukan teks.
3. Input tanpa nominal dan follow-up nominal.
4. Tiga item dalam satu pesan.
5. Foto struk dengan total cocok.
6. Voice note dan koreksi transkripsi.
7. Undo setelah save.
8. Edit nominal dan kategori.
9. Database tidak tersedia saat save.
10. Double tap tombol konfirmasi.
11. Restart bot ketika callback lama masih ada.
12. Edit/hapus transaksi yang memengaruhi budget.

### 15.2 Release gates

Sebuah phase tidak diluncurkan jika:

- Ada false success.
- Ada duplikasi dari double tap/retry.
- Perhitungan ringkasan tidak dapat direkonsiliasi dengan data transaksi.
- Flow utama hanya dapat diselesaikan melalui command yang tidak terlihat.
- Error tidak menjelaskan apakah data sudah tersimpan atau belum.

### 15.3 Kill criteria 90 hari

| Inisiatif | Kill/iterate signal | Tindakan |
|---|---|---|
| Auto-save teks | Correction rate >20% | Kembali ke preview untuk pola bermasalah |
| Reminder | Lebih dari 50% di-snooze/disable | Kurangi frekuensi atau ubah menjadi opt-in penuh |
| Weekly digest | Tidak dibuka empat minggu berturut-turut | Hapus job otomatis; pertahankan on-demand |
| Rekomendasi transaksi berulang | Saran salah >20% | Naikkan ambang pola atau hentikan fitur |
| Coaching | Tidak menghasilkan tindakan terukur | Gabungkan menjadi satu insight di Ringkasan |

---

## 16. Product Decision Log

| Keputusan | Alasan |
|---|---|
| Private single-user untuk 90 hari | Sesuai implementasi nyata dan menghindari scope autentikasi/RLS multi-user |
| Hapus login tambahan pada private mode | Telegram ID whitelist sudah menjadi gate; login menambah friksi |
| Teks lengkap menggunakan auto-save + Undo | Jalur paling sering harus menjadi yang tercepat |
| OCR/voice tetap preview-first | Risiko interpretasi lebih tinggi |
| Budget adalah limit, bukan wallet | Perhitungan dapat diturunkan dari transaksi dan tidak merusak limit |
| AI tidak menghitung total finansial | Uang membutuhkan hasil deterministik |
| Empat tombol menu utama | Memprioritaskan pekerjaan user yang paling penting |
| Tidak membuat dashboard web | Telegram sudah cukup untuk core JTBD |
| Tidak menambah dependency analytics | Metric awal dapat memakai data/logging yang sudah ada |

---

## 17. Definition of Product Success

Strategi ini berhasil jika setelah 90 hari:

1. User dapat mencatat transaksi teks lengkap dengan satu pesan.
2. Tidak ada data yang diklaim tersimpan ketika database gagal.
3. Setiap transaksi baru mudah dibatalkan atau diedit.
4. Ringkasan pemasukan dan pengeluaran dapat dipercaya.
5. Budget tetap memiliki limit asli dan usage yang akurat.
6. Goal dapat menerima kontribusi serta menunjukkan progress nyata.
7. Menu utama hanya memuat empat tujuan utama.
8. Reminder mengikuti preferensi user dan tidak spam.
9. Tidak ada fitur non-core baru yang mengganggu penyelesaian core loop.

North Star akhirnya bukan jumlah fitur yang tersedia, melainkan kebiasaan sederhana: user tetap nyaman mencatat ke Benny hampir setiap hari karena cepat, jelas, dan dapat dipercaya.
