# Natural Chat and Evidence-Based Roast Design

## Tujuan

Membuat Benny terasa seperti teman keuangan yang natural tanpa melemahkan batas keselamatan transaksi, lalu menambahkan roast keras yang hanya memakai fakta ledger milik user.

## Scope

Fitur yang ditambahkan:

- Percakapan ringan dengan bahasa Indonesia yang lebih natural dan tidak memakai template kaku.
- Preferensi gaya eksplisit dari memory dipakai untuk menyesuaikan panjang dan nada jawaban selama tidak bertentangan dengan aturan keuangan.
- Keyword `roast` dan command `/roast` untuk mengulas 30 hari terakhir.
- `/help` yang hanya menjelaskan kemampuan yang benar-benar tersedia beserta contoh singkat.

Fitur yang tidak ditambahkan:

- Budget, goal, reminder, coaching platform, dashboard, atau dependency baru.
- Roast generik yang tidak didukung ledger.
- Perubahan transaksi, income, atau memory selama roast.
- Penyimpanan riwayat roast; tabel `roast_runs` tetap tidak dipakai sampai audit/replay benar-benar dibutuhkan.

## Arsitektur

Alur yang sudah ada tetap dipakai:

```text
Telegram update
  -> private-user guard
  -> memory command
  -> roast route
  -> deterministic report
  -> read-only SQL assistant
  -> transaction/conversation capture
```

Tambahan minimum:

1. `TelegramService` memiliki handler `help` dan satu roast service.
2. `main.py` mendaftarkan `/help` dan `/roast` dengan admin filter yang sama seperti `/start`.
3. Pesan teks biasa dengan keyword utama `roast` masuk ke roast route sebelum report, SQL assistant, dan capture.
4. Roast service membaca transaksi dan income user melalui helper database yang sudah ada, membatasi periode 30 hari, lalu menghitung fakta ringkas di aplikasi.
5. `AIService` menerima snapshot agregat terbatas dan menghasilkan roast, bukan menerima akses database atau SQL.

Tidak dibuat framework fitur, base class, registry command, atau dependency baru.

## Natural Conversation

Kontrak `interpret_message` tetap menghasilkan satu dari `transaction`, `clarification`, atau `conversation`.

Perubahan hanya pada aturan conversation:

- Jawaban terasa spontan, langsung, dan tidak selalu memakai pembuka yang sama.
- Panjang default satu sampai tiga kalimat.
- Preferensi eksplisit seperti singkat, santai, formal, atau detail boleh memengaruhi gaya.
- Memory tidak boleh mengubah fakta ledger, menghapus konfirmasi, atau memerintahkan write.
- Transaksi, laporan, konfirmasi, dan error tetap deterministik dan terstruktur.
- Benny tidak mengarang saldo, kebiasaan, transaksi, atau kemampuan.

## Roast

### Trigger

- `/roast`
- `roast`
- Kalimat yang dimulai dengan `roast`, misalnya `roast pengeluaran aku`

Kata `roast` yang hanya dikutip di tengah percakapan tidak perlu mengambil alih routing.

### Periode dan fakta

Periode default adalah 30 hari kalender termasuk hari ini. Backend menghitung:

- total income;
- total expense;
- cashflow bersih;
- jumlah transaksi;
- kategori pengeluaran terbesar;
- item pengeluaran yang paling sering;
- total dan frekuensi item tersebut;
- maksimal lima transaksi terbesar sebagai bukti pendukung.

Jika ledger kosong, bot menjawab langsung bahwa belum ada bahan untuk meroast dan memberi contoh cara mencatat transaksi. AI tidak dipanggil.

### Kontrak keluaran

Roast memakai bahasa Indonesia, tanpa emotikon, maksimal sekitar 900 karakter, dan tersusun sebagai:

1. satu kalimat pukulan utama;
2. dua atau tiga bukti angka;
3. satu tindakan konkret.

Nada boleh keras dan mengejek keputusan belanja. Roast dilarang menyerang ras, agama, gender, orientasi seksual, disabilitas, kondisi kesehatan, penampilan tubuh, trauma, atau nilai diri user. Roast juga tidak boleh menyarankan tindakan berbahaya, mempermalukan di ruang publik, atau mengarang fakta.

Jika provider gagal atau menghasilkan keluaran kosong, bot menampilkan ringkasan deterministik dari snapshot dan menyatakan roast AI sedang tidak tersedia. Tidak ada write database.

## Help

`/help` menampilkan contoh aktual untuk:

- mencatat expense atau income lewat teks;
- mengirim struk atau voice note;
- menanyakan laporan dan analitik;
- mengelola explicit memory;
- menjalankan roast.

Pesan tetap pendek dan tidak mengiklankan budget, goal, reminder, atau kemampuan lain yang tidak aktif.

## Batas Data dan Keselamatan

- Semua pembacaan ledger wajib memakai `user_id` dari Telegram user yang sudah lolos admin guard.
- Roast tidak menjalankan SQL buatan model dan tidak memberi model koneksi Supabase.
- Snapshot yang dikirim ke model hanya berisi agregat dan transaksi pendukung terbatas.
- Tidak ada mutation ke `transactions`, `income`, `user_preferences`, `spending_assessments`, atau `roast_runs`.
- Request memakai timeout, retry, dan audit provider yang sudah ada; prompt dan transaksi mentah tidak dicatat ke log.

## Error Handling

- Database gagal: pesan menyatakan data keuangan belum dapat dibaca.
- Tidak ada data: pesan deterministik tanpa provider call.
- Provider gagal: fallback deterministik dari angka yang sudah dihitung.
- Output provider kosong atau terlalu panjang: fallback deterministik dipakai.
- Command dari user yang tidak diizinkan tetap diabaikan oleh admin filter.

## Testing

Satu regression surface melindungi:

- `/roast` terdaftar dengan admin filter;
- plain-text `roast` dirutekan sebelum report, SQL, dan capture;
- keyword yang hanya disebut di tengah kalimat tidak salah route;
- pembacaan database selalu user-scoped dan read-only;
- agregasi kopi atau item berulang menghasilkan fakta yang tepat;
- ledger kosong tidak memanggil model;
- provider gagal memakai fallback deterministik;
- prompt roast hanya menerima snapshot terbatas dan memuat batas target serangan;
- `/help` hanya menyebut fitur aktif;
- conversation prompt memakai preferensi gaya tanpa melemahkan kontrak transaksi;
- seluruh output melewati sanitasi Telegram tanpa emotikon.

Verifikasi akhir:

```powershell
python -m unittest discover -s tests -v
python -m compileall -q main.py config services tests
git diff --check
```

## Definition of Done

- Chat ringan lebih natural dan tetap tidak mengarang fakta.
- `roast` dan `/roast` bekerja berdasarkan ledger user 30 hari terakhir.
- Roast keras, berbukti, read-only, user-scoped, dan memiliki satu tindakan konkret.
- `/help` menjelaskan fitur aktif dengan contoh yang dapat langsung dipakai.
- Tidak ada dependency, abstraction layer, tabel, atau migrasi baru.
- Regression test dan verifikasi penuh lulus.
