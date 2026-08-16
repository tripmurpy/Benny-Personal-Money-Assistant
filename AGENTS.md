# Bot Tele Keuangan Rules

- Jangan pakai emotikon sama sekali.
- Jangan menulis komentar di kode, kecuali komentar singkat untuk struktur atau fitur yang memang membantu memahami alur.
- Jangan mengulang function, algoritma, atau logic yang sudah ada.
- Kalau ada function dengan kegunaan yang sama, pakai yang sudah ada.
- Utamakan efisiensi, kesederhanaan, dan hindari over-engineering.
- Kalau suatu fitur atau program sudah final, sudah sesuai goals, atau sudah jadi, jangan dikerjakan lagi kecuali user minta.
- Kalau pekerjaan sudah selesai dan user lupa, ingatkan user secara singkat.
- Sebelum memperbaiki bug yang pernah terjadi, baca `problem.md` dan gunakan bukti yang sudah tercatat.
- Setelah bug user-facing terverifikasi selesai, perbarui `problem.md` dengan gejala, klasifikasi, bukti, akar penyebab, perbaikan, tes regresi, dan hasil akhir.
- Tidak boleh ada secret yang bocor di source code, dokumentasi, tests, screenshot, log, atau commit: API key, token, password, private key, service-role JWT, dan credential lain hanya boleh dibaca dari environment atau secret manager.
- Gunakan `.env` lokal yang di-ignore Git untuk development; dokumentasi dan tests hanya boleh memakai nama variable atau placeholder yang tidak dapat dipakai.
- Jika secret pernah masuk ke Git, hapus dari working tree, rotasi/revoke credential di providernya, lalu bersihkan history melalui proses terpisah yang disetujui sebelum menutup alert.
