# Product Requirements Document (PRD)
## Benny - Personal Finance AI

**Version:** 1.0  
**Last Updated:** 2026-01-26  
**Author:** Development Team  
**Status:** Active Development

---

## 1. Executive Summary

**Benny** adalah asisten keuangan pribadi proaktif berbasis AI Agent di Telegram. Produk ini tidak hanya mencatat transaksi via teks, suara, dan gambar (struk), tetapi juga berperan sebagai **sahabat** yang memberikan analisis cerdas, pengingat proaktif, dan strategi penghematan yang terintegrasi langsung ke Google Sheets pengguna.

### 1.1 Product Vision
> *"Mencatat keuangan semudah ngobrol dengan teman."*

### 1.2 Key Value Propositions
| Value | Description |
|-------|-------------|
| 🚀 **Zero Friction** | Input transaksi via chat natural, tanpa form rumit |
| 🧠 **AI-Powered** | Otomatis kategorisasi & ekstraksi data dari teks |
| 📊 **Real-time Insights** | Analisis pengeluaran instan kapan saja |
| 🔗 **Seamless Integration** | Sinkronisasi otomatis ke Google Sheets |

---

## 2. Problem Statements

| Problem | Impact | Severity |
|---------|--------|----------|
| **High Friction** | Mencatat keuangan secara manual di aplikasi/Excel terasa membosankan dan sering terlupa | 🔴 High |
| **Lack of Insight** | User tahu mereka boros, tapi tidak tahu di mana tepatnya bisa berhemat | 🟡 Medium |
| **Invisible Spending** | Transaksi digital membuat pengeluaran tidak terkendali tanpa "tegur sapa" real-time | 🟡 Medium |
| **Data Scattered** | Data keuangan tersebar di berbagai tempat, sulit dianalisis | 🟡 Medium |

---

## 3. User Personas

### 3.1 Primary Persona: Andi (Mahasiswa)
| Attribute | Detail |
|-----------|--------|
| **Age** | 19-24 tahun |
| **Goal** | Menabung untuk beli gadget (PS5/Drone) |
| **Pain Point** | Sering habis uang di tengah bulan karena jajan kopi |
| **Tech Savvy** | High (aktif di Telegram) |
| **Expected Behavior** | Input via chat santai, cek progress mingguan |

### 3.2 Secondary Persona: Budi (Pekerja)
| Attribute | Detail |
|-----------|--------|
| **Age** | 25-35 tahun |
| **Goal** | Tracking pengeluaran rutin bulanan |
| **Pain Point** | Sibuk, butuh laporan otomatis tanpa manual input |
| **Tech Savvy** | Medium |
| **Expected Behavior** | Foto struk, terima laporan bulanan otomatis |

---

## 4. Key Features & Functional Requirements

### Feature Status Legend
| Status | Meaning |
|--------|---------|
| ✅ **DONE** | Sudah diimplementasi dan production-ready |
| 🚧 **IN PROGRESS** | Sedang dikerjakan |
| 📋 **PLANNED** | Dalam roadmap, belum dimulai |

---

### A. Multimodal Input (The "Brain")

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| **FR-01** | NLP Text Processing | AI harus mampu mengekstrak nominal, kategori, dan merchant dari chat santai. *Contoh: "Makan bakso 25rb pakai QRIS"* → Otomatis jadi data terstruktur | ✅ DONE |
| **FR-02** | OCR Receipt Scanner | AI harus mampu membaca foto struk, mengambil data item, total harga, pajak, dan tanggal | ✅ DONE |
| **FR-03** | Voice-to-Data | AI mampu mengubah pesan suara menjadi data transaksi yang valid | ✅ DONE |

---

### B. Proactive Engagement (The "Sahabat" Mode)

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| **FR-04** | Smart Nudging | Jika user tidak mencatat dalam 24 jam, AI akan menyapa dengan gaya bahasa santai | ✅ DONE |
| **FR-05** | Goal Tracking | AI memberikan progres real-time terhadap target. *Contoh: "Tabungan PS5 sudah 60%!"* | 📋 PLANNED |
| **FR-06** | Budget Warning | AI mengirim peringatan jika pengeluaran di kategori tertentu mendekati limit | 📋 PLANNED |

---

### C. Backend & Analytics

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| **FR-07** | Google Sheets Sync | Sinkronisasi satu arah (Telegram → Sheets). Data di Sheets mencerminkan input Telegram | ✅ DONE |
| **FR-08** | Automatic Categorization | AI secara otomatis menentukan kategori berdasarkan item. *Contoh: "Indomaret" → "Shopping"* | ✅ DONE |
| **FR-09** | Expense Analysis | Ringkasan pengeluaran harian/mingguan/bulanan dengan breakdown per kategori | ✅ DONE |
| **FR-10** | Interactive Menu | Keyboard menu untuk akses cepat fitur-fitur utama | ✅ DONE |

---

## 5. Technical Architecture

### 5.1 System Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   User Device   │────▶│  Telegram Bot    │────▶│  Google Sheets  │
│   (Telegram)    │◀────│  (Python)        │◀────│  (Database)     │
└─────────────────┘     └────────┬─────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │   Groq AI API    │
                        │   (LLM Engine)   │
                        └──────────────────┘
```

### 5.2 Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Telegram Bot API | User interface & interaction |
| **Backend** | Python 3.x | Core application logic |
| **AI Engine** | Groq API (Llama 3.1-8B-Instant) | NLP parsing & text understanding |
| **Database** | Google Sheets API | Data storage & sync |
| **Auth** | Google Service Account | Sheets API authentication |
| **Config** | python-dotenv | Environment management |

### 5.3 Key Dependencies

```
python-telegram-bot    # Telegram Bot Framework
groq                   # AI/LLM API Client
gspread                # Google Sheets Integration
google-auth            # Google API Authentication
python-dotenv          # Environment Variables
flask                  # Keep-alive server (deployment)
```

---

## 6. User Experience (Flow)

### 6.1 User Journey Map

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Onboarding │───▶│  Daily Use  │───▶│  Analysis   │───▶│   Repeat    │
│  /start     │    │  Chat Input │    │  Menu Click │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### 6.2 Interaction Examples

| Scenario | User Action | Bot Response |
|----------|-------------|--------------|
| **Onboarding** | Ketik `/start` | "Halo! Aku Benny, sahabat keuanganmu! 💰" + Menu keyboard |
| **Input Transaksi** | "Makan siang 35rb di warteg" | "✅ Tercatat! Makan siang Rp 35.000 (Food)" |
| **Multiple Items** | "Beli kopi 25rb, parkir 5rb" | "✅ Tercatat 2 transaksi: Total Rp 30.000" |
| **Analisis Harian** | Klik "📊 Analisis AI" → "Hari Ini" | Ringkasan + breakdown kategori |
| **Analisis Bulanan** | Klik "📊 Analisis AI" → "Bulan Ini" | Ringkasan + kategori terboros |

---

## 7. Data Model

### 7.1 Transaction Schema (Google Sheets)

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **Date** | String (YYYY-MM-DD) | Tanggal transaksi | 2026-01-26 |
| **Time** | String (HH:MM) | Waktu transaksi | 12:30 |
| **Item Name** | String | Nama item/deskripsi | Makan Siang |
| **Category** | Enum | Kategori otomatis | Food |
| **Amount (IDR)** | Integer | Nominal dalam Rupiah | 35000 |
| **Location** | String | Lokasi/merchant | Warteg Bahari |

### 7.2 Supported Categories

| Category | Description | Keywords |
|----------|-------------|----------|
| **Food** | Makanan & minuman | makan, kopi, resto, warteg |
| **Transport** | Transportasi | grab, gojek, bensin, parkir |
| **Bills** | Tagihan rutin | listrik, wifi, pulsa |
| **Shopping** | Belanja | indomaret, shopee, baju |
| **Income** | Pemasukan | gaji, transfer masuk |
| **Other** | Lainnya | (default fallback) |

---

## 8. Non-Functional Requirements

### 8.1 Performance

| Metric | Target | Current |
|--------|--------|---------|
| Response Time (Text Parsing) | < 3 seconds | ~1-2 seconds ✅ |
| Response Time (Analysis) | < 2 seconds | ~1 second ✅ |
| Uptime | 99% | Depends on hosting |
| Concurrent Users | 100+ | Not tested |

### 8.2 Security

| Requirement | Implementation |
|-------------|----------------|
| API Keys Protection | Environment variables (.env) |
| Google Auth | Service Account (creds.json) |
| Data Privacy | Data hanya disimpan di user's own Google Sheet |
| Token Security | Bot token tidak di-hardcode |

### 8.3 Scalability

| Aspect | Current State | Future Plan |
|--------|---------------|-------------|
| Database | Single Google Sheet | Multiple sheets per user |
| Hosting | Local/Free tier | Cloud deployment (Railway/Render) |
| Multi-user | Single admin | Multi-user support |

---

## 9. Success Metrics & KPIs

### 9.1 Adoption Metrics

| Metric | Target (6 months) |
|--------|-------------------|
| Monthly Active Users (MAU) | 100+ |
| Daily Transactions Logged | 500+ |
| Retention Rate (30-day) | > 40% |

### 9.2 Engagement Metrics

| Metric | Target |
|--------|--------|
| Avg. transactions per user/day | 3+ |
| Analysis feature usage | > 50% users/week |
| Response satisfaction | > 4/5 rating |

### 9.3 Technical Metrics

| Metric | Target |
|--------|--------|
| AI Parsing Accuracy | > 90% |
| System Uptime | > 99% |
| Error Rate | < 1% |

---

## 10. Roadmap

### Phase 1: MVP (✅ COMPLETED)
- [x] Text-based transaction input
- [x] AI parsing (NLP)
- [x] Google Sheets integration
- [x] Basic expense analysis
- [x] Interactive menu

### Phase 2: Enhanced Input (📋 Q2 2026)
- [ ] OCR Receipt Scanner (FR-02)
- [ ] Voice message support (FR-03)
- [ ] Image attachment handling

### Phase 3: Proactive Features (📋 Q3 2026)
- [ ] Smart Nudging / Daily reminders (FR-04)
- [ ] Goal Tracking (FR-05)
- [ ] Budget Warning alerts (FR-06)

### Phase 4: Advanced Analytics (📋 Q4 2026)
- [ ] Spending predictions
- [ ] Savings recommendations
- [ ] Export to PDF reports
- [ ] Multi-currency support

---

## 11. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Groq API rate limiting | Medium | High | Implement caching, fallback to local analysis |
| Google Sheets API quota | Low | Medium | Batch writes, implement queue |
| AI parsing errors | Medium | Medium | Fallback prompts, user confirmation |
| Telegram Bot downtime | Low | High | Keep-alive server, monitoring alerts |
| Data loss | Low | Critical | Regular Sheets backup, error logging |

---

## 12. Monetization Strategy (Future)

### 12.1 Freemium Model

| Tier | Features | Price |
|------|----------|-------|
| **Free** | Text input, basic analysis, 100 tx/month | Rp 0 |
| **Pro** | Unlimited tx, OCR, voice, goals | Rp 29.000/month |
| **Premium** | All Pro + AI insights, export, priority support | Rp 59.000/month |

### 12.2 Value Justification

| Feature | User Value |
|---------|------------|
| **Convenience** | Hemat waktu berjam-jam vs manual input |
| **Premium Insights** | Strategi penghematan personal berbasis data |
| **Personalization** | AI yang mengenal pola spending user |

---

## 13. Glossary

| Term | Definition |
|------|------------|
| **NLP** | Natural Language Processing - AI memahami bahasa manusia |
| **OCR** | Optical Character Recognition - AI membaca teks dari gambar |
| **LLM** | Large Language Model - Model AI seperti Llama, GPT |
| **Groq** | Platform AI inference yang cepat & murah |
| **MVP** | Minimum Viable Product - Versi pertama yang bisa dipakai |

---

## 14. Appendix

### 14.1 Bot Personality (Benny)

```
Nama: Benny
Personality: Santai, gaul, tapi tetap sopan (seperti teman akrab)
Panggilan ke user: "Benny" (nama user)
Trait khusus:
- Benci kalau user beli barang tidak berguna
- Sangat teliti soal angka
- Supportive tapi jujur
```

### 14.2 Sample Conversations

**Input transaksi:**
```
User: "Makan bakso 25rb sama minum es teh 5rb"
Benny: "✅ Tercatat 2 transaksi:
   • Makan bakso - Rp 25.000 (Food)
   • Minum es teh - Rp 5.000 (Food)
   Total: Rp 30.000"
```

**Analisis:**
```
User: [Klik "📊 Analisis AI" → "Bulan Ini"]
Benny: "📊 Ringkasan Bulan Ini

💰 Total: Rp 1.250.000
🏆 Terboros: Food (Rp 450.000)

📋 Rincian:
▫️ Food: Rp 450.000
▫️ Transport: Rp 300.000
▫️ Shopping: Rp 250.000
▫️ Bills: Rp 200.000
▫️ Other: Rp 50.000"
```

---

**Document End**

*For questions or clarifications, contact the development team.*