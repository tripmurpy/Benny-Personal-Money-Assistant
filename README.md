<div align="center">

# 💸 Benny Personal Money Assistant v1.0
### *Your Intelligent Telegram Financial Companion*

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](#)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](#)
[![Version](https://img.shields.io/badge/Version-1.0.0-00C7B7?style=for-the-badge)](#)

*An intuitive, AI-powered personal finance manager built directly into Telegram. No apps to install, no complicated sheets to update—just chat naturally like you would with a friend.*

</div>

---

## 🎯 Vision

The Money Management module (v1.0) is designed to eliminate the friction of daily expense tracking. By leveraging Natural Language Processing and AI, we transform tedious financial data entry into a casual chat experience. 

## ✨ Key Features (Versi Pertama)

### 1. 🤖 Seamless Natural Language Input (Powered by Google Gemma 4 E4B)
Forget rigid forms and dropdowns. Log your transactions naturally via chat, powered by Google's native multimodal AI, Gemma 4 E4B.
- **Text:** *"Beli kopi 25rb di Starbucks"* ➔ Automatically categorizes as `Food`, deducts `Rp 25.000`, and records the location.
- **Voice Notes (Audio Recognition):** Too busy to type? Send a quick voice note, and Gemma 4 E4B will process the audio natively into text.
  - *Usecase:* Sedang sibuk menyetir lalu mengisi bensin? Cukup tekan tombol mic di Telegram dan ucapkan *"Bensin pertamax 100 ribu,"* dan AI akan otomatis mencatat pengeluaran Rp 100.000 dengan kategori Gas.
- **Image/OCR (Visual Understanding):** Snap a picture of your receipt or payment proof. Gemma 4 E4B will extract the purchased items, date, location, and exact prices.
  - *Usecase:* Selesai belanja mingguan di supermarket dan struknya panjang? Fotokan saja ke bot, lalu AI akan mengenali lokasi/toko, mengekstrak item beserta harga dan merangkum totalnya otomatis ke dalam database tanpa perlu ketik manual.

### 2. 📊 Smart Balance & Analytics
Real-time visibility into your financial health.
- **Live Balance (`/saldo`):** Instantly check your remaining balance. Memisahkan laporan **PEMASUKAN** dan **PENGELUARAN** secara jelas dan rapi.
- **Categorized Spending:** Automatically sorts expenses into intuitive categories (`Food`, `Transport`, `Shopping`, `Bills`, `Other`).
- **Rich PDF Reports:** Generate stunning monthly reports directly in chat to review your financial habits.
- **Spending Trends:** Track your up/down trends over the last 14 days.

### 3. 🎯 Goal Tracking
Visualize and achieve your financial targets.
- Set specific saving goals (e.g., *"MacBook"* or *"Liburan"*).
- Visual progress bars keep you motivated (`75% - TINGGAL DIKIT LAGI!`).
- Commands: `/setgoal`, `/goals`, `/deletegoal`.

### 4. 🧮 Intelligent Budget Management
Prevent overspending before it happens.
- Set monthly limits for specific categories (e.g., `Rp 1.000.000` for `Food`).
- **Smart Alerts:** Receive gentle, supportive warnings when you hit 80%, 90%, or exceed your budget. *"⚠️ Budget Food udah 90%! Yuk, jaga biar ga tembus! 🛡️"*
- **Split Deduction:** If an expense exceeds a category budget, the system smartly handles the overflow from your general balance.
- Commands: `/setbudget`, `/budgets`, `/topupbudget`, `/deletebudget`.

### 5. 🧠 Proactive AI Coaching
Your personal financial advisor.
- Weekly insights and personalized tips based on your spending patterns.
- Evaluates if you're spending too fast or saving well, offering warm, non-judgmental guidance.

---

## 🚀 Cara Menggunakan (User Guide)

Using the bot is as simple as texting a friend. 

### 🟢 Memulai (Getting Started)
1. Buka aplikasi Telegram.
2. Temukan bot pada daftar obrolan Anda (Akses Private).
3. Ketik `/start` untuk memulai percakapan.
4. Bot akan menampilkan *Persistent Keyboard* di bawah layar untuk akses cepat ke menu-menu utama.

### 📝 Mencatat Transaksi (Pemasukan & Pengeluaran)
Anda **tidak perlu** menggunakan command khusus (`/`) untuk mencatat transaksi harian. Cukup ajak chat seperti biasa!
- **Mencatat Pengeluaran:** `"Makan siang padang 35000"` atau `"Bayar air dan listrik 500rb"`
- **Mencatat Pemasukan:** `"Gaji bulan ini 5000000"` atau `"Dapet kembalian utang 200rb"`
- **Voice Note:** Sedang di jalan? Tekan tombol mic di Telegram dan ucapkan pengeluaran Anda.
- **Foto Struk (OCR):** Kirim foto struk belanja, biarkan AI yang membaca angka dan itemnya!

### ⚙️ Manajemen Keuangan (Daftar Perintah / Menu)

| Command / Tombol | Fungsi | Contoh Penggunaan |
|------------------|---------|-------------------|
| `💵 Saldo` / `/saldo` | Cek total pemasukan, pengeluaran, dan sisa uang saat ini. | Klik tombol menu **💵 Saldo** |
| `/setbudget` | Membuat batas pengeluaran per kategori. | `/setbudget Food 1500000` |
| `/budgets` | Melihat daftar budget yang sedang aktif & sisa kuotanya. | `/budgets` |
| `/setgoal` | Membuat target alat tabungan baru. | `/setgoal Liburan 5000000` |
| `/goals` | Melihat progress dari semua target tabungan. | `/goals` |
| `📊 Laporan` / `/laporan` | Mengunduh PDF Laporan Keuangan. Tersedia opsi bulanan, mingguan, harian. | Klik tombol menu **📊 Laporan** |
| `🧠 Coaching` | Mendapatkan insight & saran keuangan personal dari AI. | Klik tombol menu **🧠 Coaching** |

---

## 🏗️ Architecture & Philosophy

- **Zero-Friction:** Every feature is designed to take less than 3 seconds to use.
- **State-of-the-Art NLP:** Powered by advanced LLMs to extract intents, amounts, and categories probabilistically.
- **Idempotent Operations:** Robust handling of duplicated requests to ensure financial data integrity.
- **Secure & Private:** Built with a privacy-first approach. Environment configurations, tokens, and database integrations are fully abstracted and strictly kept private.
- **Modular Design:** Budget logic, Goal handlers, and AI Parsers are decoupled to allow seamless scaling in future versions.

---

<div align="center">
<i>"Managing money shouldn't feel like accounting. It should feel like a conversation."</i>
</div>
## 🔎 Retrieval‑Augmented Generation (RAG) Architecture

**Supabase‑backed RAG System** – The bot stores all knowledge‑base documents in a Supabase Postgres database. Data yang diserap (*ingested*) secara spesifik mencakup FAQ umum dan informasi kontekstual seperti **data menu harga di Fore Coffee**. Vector embeddings are generated and persisted in the ` embeddings` table. At query time, the user's message is embedded, a similarity search is performed via Supabase's `pgvector` extension, retrieving the most relevant chunks. These chunks are then supplied to the LLM as context, enabling accurate, up‑to‑date answers (contohnya saat bertanya *"Berapa harga Fore Amerikano?"*).

**Key Highlights**
- **Rich Knowledge Base Ingestion** – Ekstraksi dan konsumsi (*ingest*) database spesifik seperti harga menu Fore Coffee.
- **Scalable Vector Search** using Supabase `pgvector` for fast similarity lookup.
- **Real‑time Updates** – New documents are upserted instantly; the RAG index refreshes automatically.
- **Secure & Private** – All data resides in your Supabase project; no external vector DB.
- **Modular Design** – The RAG pipeline is encapsulated in a dedicated service module.
