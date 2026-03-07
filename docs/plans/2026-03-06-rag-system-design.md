# 🧠 RAG System Architecture — Bot Benny

## Overview

Menambahkan **Retrieval-Augmented Generation (RAG)** system ke Bot Benny dengan 3 pilar:

| Pilar | Fungsi | Sumber Data |
|-------|--------|-------------|
| 📱 **Product Help** | Cara pakai bot, commands, fitur | Dokumen Markdown di `knowledge/product/` |
| 💡 **Financial Knowledge** | Tips keuangan, budgeting, saving | Dokumen Markdown di `knowledge/financial/` |
| 📊 **Transaction Analyzer** | Analisis historis, advice kontekstual | Google Sheets (live data) |

**Stack**: ChromaDB (vector store) + HuggingFace API (embeddings) + Groq LLM (generation)

---

## 🏗️ File Structure

```
bot-tele-keuangan/
│
├── main.py                          # Entry point (existing)
├── config.py                        # Config — tambah RAG settings (modify)
├── requirements.txt                 # Tambah chromadb, dll (modify)
│
├── config/
│   ├── ai_personality.json          # (existing)
│   ├── chat_templates.json          # (existing)
│   ├── memory_config.json           # (existing)
│   └── rag_config.json              # [NEW] RAG settings & thresholds
│
├── services/
│   ├── ai_service.py                # (existing) 
│   ├── chat_service.py              # (modify) — integrate RAG pipeline
│   ├── sheets_service.py            # (existing)
│   ├── telegram_service.py          # (existing)
│   │
│   ├── ai/
│   │   ├── prompts.py               # (modify) — tambah RAG-specific prompts
│   │   ├── coaching_engine.py       # (existing)
│   │   ├── personality_engine.py    # (existing)
│   │   ├── chat_memory.py           # (existing)
│   │   └── context_processor.py     # (existing)
│   │
│   └── rag/                         # [NEW] — RAG System Module
│       ├── __init__.py              # Module exports
│       ├── embeddings.py            # HuggingFace API embedding service
│       ├── vector_store.py          # ChromaDB wrapper & collection manager
│       ├── retriever.py             # Smart retriever — routes query ke collection yg tepat
│       ├── chunker.py               # Document chunker — split dokumen jadi chunks
│       ├── pipeline.py              # RAG pipeline orchestrator (retrieve → augment → generate)
│       ├── indexer.py               # Indexing service — load & index documents
│       └── transaction_rag.py       # Transaction-specific RAG (sheets → vector → analysis)
│
├── knowledge/                       # [NEW] — Knowledge Base Documents
│   ├── product/                     # Pilar 1: Product Help
│   │   ├── getting_started.md       # Cara mulai pakai Benny
│   │   ├── commands.md              # Daftar semua commands & cara pakai
│   │   ├── features.md              # Fitur-fitur bot (OCR, Voice, Export, dll)
│   │   ├── budgets_guide.md         # Cara set & manage budget
│   │   ├── goals_guide.md           # Cara set & manage goals
│   │   ├── export_guide.md          # Cara export laporan PDF/CSV
│   │   └── faq.md                   # Frequently asked questions
│   │
│   └── financial/                   # Pilar 2: Financial Knowledge
│       ├── budgeting_101.md         # Dasar-dasar budgeting
│       ├── saving_tips.md           # Tips menabung
│       ├── expense_categories.md    # Panduan kategorisasasi pengeluaran
│       ├── financial_goals.md       # Cara set target keuangan
│       └── common_mistakes.md       # Kesalahan keuangan yg sering terjadi
│
├── data/                            # [NEW] — Persistent Data
│   └── chroma_db/                   # ChromaDB storage (auto-generated)
│
├── scripts/                         # [NEW] — Utility Scripts
│   └── index_knowledge.py          # Script untuk index/reindex knowledge base
│
└── tests/
    ├── test_income_parsing.py       # (existing)
    └── test_rag/                    # [NEW] — RAG Tests
        ├── test_embeddings.py       # Test embedding service
        ├── test_retriever.py        # Test retrieval accuracy
        └── test_pipeline.py         # Test end-to-end RAG pipeline
```

---

## 🔧 Component Details

### 1. `services/rag/embeddings.py` — Embedding Service

```
┌─────────────────────────┐
│   EmbeddingService      │
├─────────────────────────┤
│ - api_key: str          │
│ - model: str            │
│ - base_url: str         │
├─────────────────────────┤
│ + embed_text(text)      │  → HuggingFace API call
│ + embed_batch(texts[])  │  → Batch embedding
│ + embed_query(query)    │  → Query embedding (bisa beda model)
└─────────────────────────┘
```

- Model: `sentence-transformers/all-MiniLM-L6-v2` (fast, 384 dims)
- Fallback ke local model jika API gagal

### 2. `services/rag/vector_store.py` — ChromaDB Wrapper

```
┌──────────────────────────────┐
│   VectorStoreManager         │
├──────────────────────────────┤
│ - client: ChromaDB           │
│ - collections: dict          │
├──────────────────────────────┤
│ + get_collection(name)       │
│ + add_documents(docs, coll)  │
│ + search(query, coll, top_k) │
│ + delete_collection(name)    │
│ + get_stats()                │
└──────────────────────────────┘
```

**3 Collections** di ChromaDB:

| Collection | Sumber | Update |
|-----------|--------|--------|
| `product_help` | `knowledge/product/*.md` | Manual / saat startup |
| `financial_knowledge` | `knowledge/financial/*.md` | Manual / saat startup |
| `transactions` | Google Sheets | Periodic sync (setiap query) |

### 3. `services/rag/retriever.py` — Smart Retriever

```
┌──────────────────────────────────┐
│   SmartRetriever                 │
├──────────────────────────────────┤
│ + classify_query(query)          │ → Tentukan pilar mana yg relevan
│ + retrieve(query, top_k=5)       │ → Cari di collection yg tepat
│ + retrieve_multi(query, colls[]) │ → Cari di beberapa collection
└──────────────────────────────────┘
```

**Query Classification Flow:**
```
User: "Gimana cara export PDF?"
  → classify → PRODUCT_HELP
  → search product_help collection
  → return relevant chunks

User: "Tips menabung buat anak kos"
  → classify → FINANCIAL_KNOWLEDGE
  → search financial_knowledge collection
  → return relevant chunks

User: "Bulan ini aku boros ga sih?"
  → classify → TRANSACTION
  → fetch recent transactions from Sheets
  → analyze + return context
```

### 4. `services/rag/pipeline.py` — RAG Pipeline Orchestrator

```
┌─────────────────────────────────────────────────────┐
│                  RAG Pipeline                        │
├─────────────────────────────────────────────────────┤
│                                                      │
│  User Query                                          │
│      │                                               │
│      ▼                                               │
│  ┌──────────────┐                                    │
│  │  Classifier   │ ← Tentukan pilar / intent         │
│  └──────┬───────┘                                    │
│         │                                            │
│    ┌────┴────┬──────────┐                            │
│    ▼         ▼          ▼                            │
│ Product   Finance   Transaction                      │
│  Help    Knowledge   Analyzer                        │
│    │         │          │                            │
│    └────┬────┘          │                            │
│         ▼               ▼                            │
│  ┌─────────────┐  ┌──────────────┐                   │
│  │  ChromaDB    │  │ Sheets API   │                   │
│  │  Retrieval   │  │ + ChromaDB   │                   │
│  └──────┬──────┘  └──────┬───────┘                   │
│         │                │                            │
│         └───────┬────────┘                            │
│                 ▼                                     │
│     ┌───────────────────┐                             │
│     │   Context Builder  │ ← Gabung retrieved docs    │
│     └─────────┬─────────┘                             │
│               ▼                                       │
│     ┌───────────────────┐                             │
│     │    Groq LLM        │ ← Generate answer          │
│     │   (Llama 3.1)      │   with context              │
│     └─────────┬─────────┘                             │
│               ▼                                       │
│         Final Answer                                  │
│     (warm Benny style)                                │
│                                                       │
└─────────────────────────────────────────────────────┘
```

### 5. `services/rag/transaction_rag.py` — Transaction RAG

```
┌────────────────────────────────────┐
│   TransactionRAG                   │
├────────────────────────────────────┤
│ + sync_transactions()             │ → Sync dari Sheets ke ChromaDB
│ + analyze_spending(query, period) │ → Analisis pengeluaran
│ + compare_periods(p1, p2)        │ → Bandingkan 2 periode
│ + get_category_insights(cat)     │ → Insight per kategori
└────────────────────────────────────┘
```

### 6. `config/rag_config.json`

```json
{
  "embedding": {
    "provider": "huggingface_api",
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "dimension": 384
  },
  "vector_store": {
    "provider": "chromadb",
    "persist_directory": "data/chroma_db",
    "distance_metric": "cosine"
  },
  "retrieval": {
    "top_k": 5,
    "similarity_threshold": 0.7,
    "max_context_tokens": 2000
  },
  "chunking": {
    "chunk_size": 500,
    "chunk_overlap": 50,
    "separators": ["\n## ", "\n### ", "\n\n", "\n"]
  },
  "collections": {
    "product_help": {
      "source_dir": "knowledge/product",
      "auto_reload": true
    },
    "financial_knowledge": {
      "source_dir": "knowledge/financial",
      "auto_reload": true
    },
    "transactions": {
      "sync_interval_minutes": 30
    }
  }
}
```

---

## 🗺️ Implementation Roadmap

### Phase 1: Foundation (Core RAG Infrastructure)
> *Estimasi: 2-3 hari*

- [ ] Setup dependencies (`chromadb`, `httpx` for HF API)
- [ ] `rag_config.json` — konfigurasi
- [ ] `embeddings.py` — HuggingFace API embed service
- [ ] `vector_store.py` — ChromaDB wrapper
- [ ] `chunker.py` — Document splitting

### Phase 2: Knowledge Base (Product Help + Financial)
> *Estimasi: 2-3 hari*

- [ ] Tulis dokumen `knowledge/product/*.md`
- [ ] Tulis dokumen `knowledge/financial/*.md`
- [ ] `indexer.py` — Load & index documents ke ChromaDB
- [ ] `scripts/index_knowledge.py` — CLI indexing tool

### Phase 3: Smart Retriever & Pipeline
> *Estimasi: 2-3 hari*

- [ ] `retriever.py` — Query classification + retrieval
- [ ] `pipeline.py` — Full RAG pipeline (retrieve → augment → generate)
- [ ] Tambah RAG prompts di `ai/prompts.py`
- [ ] Integrate ke `chat_service.py` (tambah RAG layer)

### Phase 4: Transaction RAG
> *Estimasi: 2-3 hari*

- [ ] `transaction_rag.py` — Sheets → vector sync & analysis
- [ ] Periodic transaction syncing
- [ ] Spending analysis & comparison queries

### Phase 5: Testing & Polish
> *Estimasi: 1-2 hari*

- [ ] Unit tests untuk setiap component
- [ ] End-to-end integration test
- [ ] Fine-tune retrieval thresholds
- [ ] Optimize chunking strategy

---

## 🔄 Integration dengan Existing Code

### `chat_service.py` — Modified Flow

```
SEBELUM (current):
  User Message → Pattern Match → AI Fallback → Response

SESUDAH (with RAG):
  User Message → Pattern Match → RAG Pipeline → AI Fallback → Response
                                    ↓
                              [Classify Intent]
                                    ↓
                        ┌───────────┼──────────┐
                        ▼           ▼          ▼
                   Product     Financial   Transaction
                    Help       Knowledge    Analyzer
                        ↓           ↓          ↓
                        └───────────┼──────────┘
                                    ↓
                           [Groq + Context]
                                    ↓
                              Benny Response
```

---

## 📦 New Dependencies

```txt
chromadb>=0.4.0        # Vector store
tiktoken>=0.5.0        # Token counting for chunking
```

> `httpx` sudah ada di project untuk HuggingFace API calls.
