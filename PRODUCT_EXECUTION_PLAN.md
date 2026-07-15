# Benny 90-Day Product Execution Plan

**Sumber:** `PRODUCT_STRATEGY.md`  
**Periode:** 15 Juli-13 Oktober 2026  
**Mode:** Private single-user  
**Status:** Ready for execution

## 1. Keputusan eksekusi

Gunakan pola **orchestrator dengan dependency DAG**, fan-out tim fitur yang independen, lalu fan-in melalui QA evaluator.

- Maksimal tiga tim fitur aktif bersamaan.
- Satu tim memegang satu fitur dan satu set file utama.
- Hanya integration captain yang mengubah router bersama di `services/telegram_service.py` saat fan-in.
- Tidak membuat framework multi-agent atau dependency baru.
- Semua perhitungan uang tetap deterministik; AI hanya mengekstrak dan mengklasifikasi.
- P0 harus selesai sebelum P1/P2 dimulai.

```text
Product Strategy
      |
      v
Ledger Integrity -----> Fast Capture ------> History/Correction
      |                       |                       |
      +----> Unified Summary -+-----------------------+
      |
      +----> Budget -----------+
      |
      +----> Goals ------------+----> Useful Engagement
                                      |
                                      v
                                 QA Release Gate
```

## 2. Baseline repo yang memengaruhi rencana

- `services/telegram_service.py` adalah shared hotspot berukuran 1.542 baris; kepemilikan file harus eksklusif saat integrasi.
- Write expense dan income masih memakai dua tabel dan hanya mengembalikan `bool`, sehingga receipt belum mendapat ID record untuk Undo/Edit.
- Update/delete transaksi belum dibatasi dengan `user_id` dan belum memverifikasi jumlah row yang berubah.
- Batch campuran dirutekan berdasarkan keberadaan satu income; expense dalam batch tersebut berisiko masuk jalur income.
- Text capture masih meminta pilihan sumber dana; ini bertentangan dengan fast path pada strategi.
- Budget dikurangi dengan mengubah `monthly_limit`; limit dan usage belum terpisah.
- Goal sudah punya `current_amount`, tetapi belum memiliki flow kontribusi, penarikan, dan riwayat.
- Auth username/password masih berada di depan whitelist Telegram ID.
- Pending confirmation tersimpan di memory proses dan hilang ketika restart.

## 3. Kontrak fondasi sebelum fan-out

Tim Ledger Integrity membekukan kontrak transaksi v1 pada Minggu 1:

```text
id, user_id, type, item, amount, category,
date, time, note, operation_id, created_at
```

Aturan kontrak:

- `type` hanya `expense` atau `income`.
- `amount` harus integer positif.
- `operation_id` berasal dari Telegram message/callback dan memiliki unique constraint untuk mencegah duplikasi.
- Semua mutation menerima `user_id` dan memverifikasi record hasil operasi.
- Save mengembalikan hasil sederhana: `ok`, `records`, dan `error`; bukan hanya `bool`.
- Riwayat dapat membaca data expense dan income lama melalui normalisasi di `SupabaseService`; migrasi tabel penuh tidak dilakukan sebelum benar-benar diperlukan.

## 4. Tim dan batas kepemilikan

| Tim fitur | Tanggung jawab tunggal | File utama | Handoff |
|---|---|---|---|
| Ledger Integrity | Save yang jujur, idempotency, mutation ter-scope | `services/supabase_service.py`, migration SQL, focused test | Transaction contract v1 |
| Private Onboarding | `/start` tanpa login tambahan dan akses via `ADMIN_ID` | `services/auth_service.py`, `config/__init__.py` | Start flow + secret checklist |
| Fast Capture | Auto-save teks, safe path multi-item/OCR/voice, receipt Undo/Edit/Retry | `services/telegram_service.py`, `services/ai_service.py` | Capture flow end-to-end |
| History & Correction | Daftar terbaru, detail, edit, hapus, catat lagi, reply-to-edit | handler history + transaction query methods | History callbacks |
| Unified Summary | Income, expense, arus kas, periode, detail/trend/PDF | `services/analytics_service.py`, `services/export_service.py` | Summary payload deterministik |
| Budget | Fixed limit, usage dari transaksi, alert 80/100% satu kali | `services/budget_service.py`, `services/budget_handlers.py` | Budget calculation contract |
| Goals | Kontribusi, penarikan, progress, riwayat | `services/goals_service.py`, `services/goal_handlers.py` | Goal ledger contract |
| Reminder | Preferensi waktu, snooze, off, weekly digest | scheduler di `main.py` + existing context storage | Reminder preference contract |

QA evaluator dan security reviewer bersifat lintas tim, bukan pemilik fitur. Mereka tidak menambah scope; mereka hanya menguji acceptance criteria dan menolak perubahan yang melanggar release gate.

## 5. Roadmap paralel

### Wave 0 — Product truth baseline, 15-21 Juli

Berjalan paralel:

1. **Ledger Integrity:** audit semua write, buat transaction contract v1, scope update/delete dengan `user_id`, dan tetapkan idempotency key.
2. **Private Onboarding:** hapus kebutuhan login chat, pertahankan whitelist `ADMIN_ID`, hapus fallback secret hardcoded, dan siapkan rotasi key yang pernah terekspos.
3. **QA evaluator:** buat baseline untuk 12 dogfood scenario dari strategi dan reproduksi false-success/double-tap/database-down.

Gate:

- Tidak ada mutation yang sukses hanya karena exception tidak muncul.
- Tidak ada update/delete berdasarkan ID tanpa `user_id`.
- Tidak ada secret aktif di tracked source.
- Contract v1 disetujui semua tim downstream.

### Wave 1 — Fast and trustworthy capture, 22 Juli-11 Agustus

Dependency: Wave 0 lulus.

Berjalan paralel:

1. **Fast Capture:** teks lengkap langsung divalidasi dan disimpan; hapus pilihan sumber dana.
2. **Private Onboarding:** sederhanakan copy `/start` dan menu menjadi empat tombol.
3. **QA evaluator:** uji input lengkap, input tanpa nominal, batch tiga item, database failure, retry, double tap, dan restart.

Fan-in oleh integration captain:

- Teks satu item: save lalu receipt `[Batalkan] [Edit]`.
- Multi-item, OCR, dan voice: preview `[Simpan] [Edit] [Batal]`.
- Retry menggunakan `operation_id` yang sama.
- Callback kedua tidak mengulang mutation.

Gate:

- False success = 0.
- Duplicate transaction = 0.
- Input teks lengkap selesai tanpa pertanyaan lanjutan.
- Nominal nol/negatif ditolak sebelum DB call.

### Wave 2 — Control and clarity, 12 Agustus-1 September

Berjalan paralel:

1. **History & Correction:** riwayat terbaru, detail tanpa AI, edit/hapus/catat lagi, dan reply-to-edit berbasis transaction ID.
2. **Unified Summary:** agregasi deterministic income-expense, label periode, dan istilah `Arus kas`.
3. **Navigation integration:** wiring empat menu utama; detail, trend, PDF, dan coaching masuk ke Ringkasan.

Gate:

- Koreksi transaksi terakhir maksimal dua interaksi.
- Edit/delete memengaruhi summary secara langsung.
- Semua laporan menyebut periode.
- Tidak ada istilah `Saldo Rekening` tanpa opening balance dan mutasi lengkap.

### Wave 3 — Budget and goals, 2-22 September

Berjalan paralel:

1. **Budget:** hapus deduction terhadap `monthly_limit`; hitung usage dari transaksi bulan berjalan.
2. **Goals:** tambah kontribusi, penarikan, status selesai, dan audit history.
3. **QA evaluator:** rekonsiliasi hasil dengan query transaksi dan uji edit/delete terhadap budget.

Reuse yang diwajibkan:

- Simpan status alert budget dan preferensi sederhana di `user_context`; jangan membuat storage baru.
- Tambahkan tabel riwayat goal hanya karena perubahan uang membutuhkan audit trail yang durable.

Gate:

- Limit budget tidak berubah saat transaksi dibuat.
- Usage sama dengan total expense kategori pada periode aktif.
- Alert threshold yang sama hanya terkirim sekali per bulan.
- Penarikan goal tidak dapat menghasilkan nilai negatif.

### Wave 4 — Useful engagement, 23 September-13 Oktober

Berjalan paralel:

1. **Reminder:** waktu pilihan, snooze, off, dan anti-spam.
2. **Weekly Digest:** satu insight dan satu tindakan, dihitung dari summary deterministik.
3. **OCR/Voice Reliability:** hanya memperbaiki pola kegagalan yang tercatat pada Wave 1-3.

Recurring suggestion dikerjakan hanya jika data historis menunjukkan pola berulang yang cukup. Safe-to-spend, anomaly detection, dashboard web, multi-user, dan subscription tetap di luar scope.

Gate:

- Reminder mengikuti preferensi user.
- Satu pola tidak menghasilkan notifikasi berulang.
- Digest dapat dibaca kurang dari 20 detik.

## 6. Kontrak komunikasi antar-agent

Setiap handoff wajib menggunakan payload terbatas berikut:

```json
{
  "workflow_id": "benny-90d-2026",
  "step_id": "wave-feature",
  "task": "satu outcome fitur",
  "constraints": ["private single-user", "no new dependency", "money is deterministic"],
  "upstream_artifacts": ["transaction-contract-v1"],
  "budget_tokens": 12000,
  "timeout_seconds": 1800,
  "changed_files": [],
  "checks": [],
  "open_risks": []
}
```

Aturan komunikasi:

- Tim mengirim perubahan contract segera; perubahan internal tidak perlu broadcast.
- Agent hanya menerima bagian strategi, contract, dan file yang relevan dengan fiturnya.
- Satu retry diperbolehkan untuk failure yang dapat direproduksi; setelah itu kembali ke orchestrator dengan error dan bukti.
- Jangan meneruskan full chat, `.env`, token, atau seluruh history transaksi ke agent lain.
- Tidak ada dua tim yang mengedit shared hotspot pada waktu yang sama.

## 7. Merge dan quality gate

Urutan per feature branch/worktree:

1. Implementasi minimum pada file milik tim.
2. Jalankan satu focused check yang gagal jika logic utama rusak.
3. Security review untuk mutation, user scope, secret, dan data sensitif.
4. QA evaluator menjalankan acceptance criteria fitur.
5. Integration captain memasang wiring shared router.
6. Jalankan dogfood scenario phase dan smoke test bot satu instance.

PR ditolak jika ada salah satu kondisi berikut:

- UI menyatakan sukses sebelum DB mengembalikan record.
- Retry/double tap membuat duplikasi.
- Update/delete tidak dibatasi `user_id`.
- Total finansial berasal dari output AI.
- State penting hanya hidup di memory tanpa expiry atau recovery yang jelas.
- Fitur menambah dependency atau scope di luar `PRODUCT_STRATEGY.md`.

## 8. Urutan PR pertama

1. `p0-ledger-integrity`: mutation result, user scope, mixed-batch correctness, idempotency migration, focused tests.
2. `p0-private-access`: hilangkan login chat dan hardcoded secret fallback; rotasi key dilakukan di provider, bukan melalui commit.
3. `p1-instant-save`: fast path text + truthful receipt + Undo/Edit/Retry.
4. `p1-safe-capture`: multi-item/OCR/voice preview dan callback idempotent.

Setelah empat PR ini lulus, Wave 2 dapat fan-out tanpa menebak kontrak data.
