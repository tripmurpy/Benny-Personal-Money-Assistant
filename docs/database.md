# Database

Schema Benny saat ini ada di Supabase dan dipakai untuk dua hal:

1. pencatatan keuangan pribadi
2. konteks AI yang membaca kebiasaan, preferensi, dan bahan roast

Schema ini sengaja dipisah dari logika Telegram supaya data tetap bisa dipakai ulang oleh agent lain tanpa tergantung satu alur pesan.

## Tujuan

- Simpan pemasukan dan pengeluaran secara idempotent.
- Simpan sesi chat AI yang dipakai untuk percakapan dan roast.
- Simpan profil, preferensi, dan konteks personal agar agent punya memori kerja yang konsisten.
- Simpan penilaian pengeluaran yang tidak wise tanpa menduplikasi transaksi utama.

## Ringkasan tabel

| Table | Fungsi |
| --- | --- |
| `user_profiles` | Identitas dasar pengguna dan metadata akun. |
| `transactions` | Pencatatan pengeluaran. |
| `income` | Pencatatan pemasukan. |
| `chat_sessions` | Satu sesi percakapan AI per chat / konteks kerja. |
| `chat_messages` | Riwayat pesan di dalam sesi chat. |
| `agent_harness` | Memorisasi preferensi dan fakta pribadi untuk AI agent. |
| `user_preferences` | Preferensi eksplisit yang dapat diaktifkan/nonaktifkan. |
| `spending_assessments` | Hasil review atas pengeluaran, termasuk label `wise` / `unwise`. |
| `roast_runs` | Snapshot hasil roast AI atas pemasukan dan pengeluaran pada periode tertentu. |

## Entitas inti

### `user_profiles`

Satu baris per pengguna. Ini adalah tabel induk untuk semua tabel lain.

Dipakai untuk:

- mengikat seluruh data ke `user_id`
- menyimpan nama, nickname, timezone, dan mata uang
- menyimpan aktivitas terakhir

### `transactions`

Berisi pengeluaran.

Field penting:

- `operation_id` untuk idempotensi
- `date` dan `time` untuk urutan kejadian
- `item_name`, `category`, `amount`, `location`, `payment_method`, `notes`

Aturan penting:

- `operation_id` unik per user jika terisi
- `amount` harus lebih dari 0
- baris ini dihapus otomatis kalau profil user dihapus

### `income`

Berisi pemasukan.

Strukturnya mirip dengan `transactions`, tetapi dipisahkan supaya query pendapatan tidak bercampur dengan pengeluaran.

Aturan penting:

- `operation_id` unik per user jika terisi
- `amount` harus lebih dari 0
- baris ini dihapus otomatis kalau profil user dihapus

## Chat dan agent

### `chat_sessions`

Satu sesi percakapan AI untuk satu user dan satu `telegram_chat_id`.

Dipakai untuk:

- mengelompokkan percakapan
- melacak status sesi
- menyimpan konteks terakhir

### `chat_messages`

Isi pesan per sesi.

Dipakai untuk:

- menyimpan history prompt / reply
- trace perilaku agent
- bahan debugging saat ada output AI yang aneh

Relasi penting:

- `session_id` harus cocok dengan `user_id`
- pesan ikut terhapus kalau session dihapus

### `agent_harness`

Ini adalah tabel memori kerja AI agent.

Gunanya untuk menyimpan hal-hal seperti:

- kesukaan user
- kebiasaan
- preferensi gaya bahasa
- fakta personal yang relevan untuk membantu agent menjawab

Prinsipnya:

- satu baris per user
- lebih cocok untuk state agregat daripada riwayat mentah
- cocok untuk data yang sering dibaca AI, bukan log interaksi

### `user_preferences`

Tempat preferensi eksplisit yang bisa diaktifkan atau dimatikan.

Contoh use case:

- user suka roast yang agresif atau lembut
- user ingin AI fokus ke pengeluaran boros
- user ingin output singkat atau detail

Kolom `is_active` dipakai agar satu key bisa punya histori tanpa kehilangan state aktif.

## Evaluasi pengeluaran

### `spending_assessments`

Tabel ini menyimpan hasil penilaian untuk pengeluaran.

Dipakai untuk:

- label `wise` / `unwise`
- menyimpan alasan penilaian
- menyimpan siapa / apa yang memberi penilaian
- mengaitkan penilaian ke transaksi asli

Desain ini sengaja tidak membuat tabel pengeluaran baru untuk kategori `unwise`. Satu transaksi tetap satu sumber kebenaran, lalu penilaian disimpan sebagai lapisan di atasnya.

## Roast

### `roast_runs`

Menyimpan hasil roast AI untuk periode tertentu.

Kolom penting:

- rentang periode
- total income
- total expense
- net cashflow
- text roast
- `session_id` bila roast lahir dari chat session tertentu

Ini berguna untuk:

- audit hasil roast
- replay output AI
- melihat versi roast per periode tanpa menghitung ulang semua data

## Constraint dan indeks

Schema ini memakai:

- primary key untuk identitas baris
- foreign key dengan cascade untuk menjaga konsistensi
- `check` constraint untuk nominal dan state yang valid
- unique index untuk mencegah data dobel
- index query utama di user/date/category/session

Implikasi praktis:

- retry aman untuk transaksi yang pakai `operation_id`
- query timeline per user tetap cepat
- sesi chat aktif tidak gampang dobel

## Keamanan

Semua tabel di schema ini memakai row level security.

Pada implementasi saat ini:

- `anon` dan `authenticated` tidak diberi akses langsung
- akses tulis/baca dimaksudkan lewat backend service role

Artinya schema ini cocok untuk bot privat dan agent backend, bukan untuk akses publik langsung dari browser.

## File sumber

- Migration utama: [supabase/migrations/20260812071752_create_benny_finance_ai_schema.sql](../supabase/migrations/20260812071752_create_benny_finance_ai_schema.sql)
- Smoke test schema: [supabase/tests/benny_schema_smoke.sql](../supabase/tests/benny_schema_smoke.sql)

