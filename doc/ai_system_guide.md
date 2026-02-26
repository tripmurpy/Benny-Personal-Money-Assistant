# AI System Guide

## Overview

Sistem AI Natural untuk bot Telegram keuangan dengan kemampuan:
- 🧠 **Memory System**: Mengingat percakapan dan konteks user
- 🎭 **Personality Engine**: Berbicara dengan personality teman yang supportive
- 🎯 **Context-Aware**: Response yang intelligent berdasarkan histori user

---

## Arsitektur

### Komponen Utama

```
services/ai/
├── chat_memory.py         # Mengelola memori & persistent storage
├── personality_engine.py  # Mengatur personality & tone
├── context_processor.py   # Analisis konteks & personalisasi
└── prompts.py            # Template prompt untuk LLM
```

### Data Flow

```
User Message
    ↓
Context Processor (analyze user context)
    ↓
Chat Memory (retrieve relevant history)
    ↓
Personality Engine (apply personality)
    ↓
LLM with Prompts (generate response)
    ↓
Save to Memory
    ↓
Response to User
```

---

## Memory System

### Google Sheets Structure

**1. UserProfiles**
Menyimpan profil dasar user:
- `user_id`: Telegram user ID
- `name`: Nama user
- `timezone`: Zona waktu
- `join_date`: Tanggal bergabung
- `last_active`: Terakhir aktif
- `preferences`: Preferensi (JSON)
- `communication_style`: Style komunikasi preferred

**2. ChatHistory**
Riwayat percakapan lengkap:
- `timestamp`: Waktu percakapan
- `user_id`: ID user
- `message_type`: Tipe pesan (text, command, etc)
- `user_message`: Pesan dari user
- `bot_response`: Response bot
- `context_used`: Konteks yang digunakan (JSON)

**3. UserContext**
Konteks & insight user:
- `user_id`: ID user
- `total_spending_pattern`: Pola spending keseluruhan
- `top_categories`: Kategori spending utama (JSON array)
- `active_goals`: Goal yang sedang berjalan (JSON array)
- `achievements`: Pencapaian user (JSON array)
- `sentiment_trend`: Trend sentiment terakhir
- `last_updated`: Waktu update terakhir

**4. KnowledgeBase**
Hal-hal yang AI pelajari tentang user:
- `user_id`: ID user
- `knowledge_type`: Tipe knowledge (preference, habit, goal, etc)
- `knowledge_item`: Konten knowledge
- `confidence`: Tingkat kepercayaan (0.0 - 1.0)
- `learned_date`: Tanggal dipelajari
- `last_referenced`: Terakhir direferensi

### Usage Example

```python
from services.ai import ChatMemory

# Initialize
memory = ChatMemory(sheets_service)

# Save conversation
memory.save_conversation(
    user_id=12345,
    user_message="Habis beli kopi 25rb",
    bot_response="Oke! Udah dicatet ya ☕"
)

# Get history
history = memory.get_conversation_history(user_id=12345, limit=5)

# Store learned insight
memory.learn_about_user(
    user_id=12345,
    knowledge_type="preference",
    knowledge_item="Suka beli kopi di pagi hari",
    confidence=0.8
)
```

---

## Personality Engine

### Configuration

File: `config/ai_personality.json`

```json
{
  "name": "TeleBuddy",
  "personality_type": "supportive_friend",
  "tone": "friendly_casual",
  "emoji_usage": "moderate"
}
```

### Personality Traits

- **Friendly & Casual**: Menggunakan bahasa santai Indonesia
- **Supportive**: Selalu encourage dan motivasi
- **Non-Judgmental**: Tidak menghakimi, gentle reminders
- **Fun**: Menggunakan emoji dan ekspresi casual

### Usage Example

```python
from services.ai import PersonalityEngine

# Initialize
personality = PersonalityEngine(config_path="config/ai_personality.json")

# Generate greeting
greeting = personality.generate_greeting(
    user_name="Benny",
    time_of_day="morning"
)
# Output: "Pagi Benny! ☀️ Semangat pagi!"

# Add encouragement
encourage = personality.add_encouragement(context_type="saving")
# Output: "Keren banget! Konsisten nabung tuh kuncinya! 💪"

# Format response with personality
response = personality.format_response(
    message="Budget kamu masih aman kok",
    tone="supportive"
)
# Output: "Budget kamu masih aman kok 😊"
```

---

## Context Processor

### Features

1. **Sentiment Analysis**: Deteksi mood user dari percakapan
2. **Intent Extraction**: Pahami maksud user
3. **Pattern Detection**: Identifikasi pola behavior
4. **Personalization**: Response disesuaikan dengan konteks

### Usage Example

```python
from services.ai import ContextProcessor

# Initialize
processor = ContextProcessor(chat_memory, personality_engine)

# Analyze full context
context = processor.analyze_context(user_id=12345)
# Returns: {
#   'sentiment': 'positive',
#   'engagement_level': 'high',
#   'recent_conversations': [...],
#   'user_context': {...}
# }

# Generate personalized response
response = processor.generate_personalized_response(
    user_id=12345,
    base_response="Total spending kamu 500rb bulan ini",
    include_greeting=True
)
# Output: "Pagi kak! ☀️ Btw, total spending kamu 500rb bulan ini 💪"

# Extract intent
intent = processor.extract_user_intent("Mau cek budget bulan ini")
# Returns: {'intent': 'check_budget', 'confidence': 0.8}
```

---

## Integration dengan AI Service

Update `services/ai_service.py` untuk menggunakan AI system:

```python
from services.ai import ChatMemory, PersonalityEngine, ContextProcessor, PromptTemplates
from services.sheets_service import SheetsService

class AIService:
    def __init__(self):
        # Initialize components
        self.sheets = SheetsService()
        self.memory = ChatMemory(self.sheets)
        self.personality = PersonalityEngine("config/ai_personality.json")
        self.processor = ContextProcessor(self.memory, self.personality)
        self.prompts = PromptTemplates()
    
    def chat(self, user_id, message):
        # Analyze context
        context = self.processor.analyze_context(user_id)
        
        # Build LLM prompt
        system_prompt = self.prompts.get_system_prompt()
        context_str = self.processor.build_context_for_llm(user_id, message)
        
        # Get LLM response (using Groq or other)
        llm_response = self.get_llm_response(system_prompt, context_str, message)
        
        # Apply personality
        final_response = self.personality.format_response(llm_response)
        
        # Save to memory
        self.memory.save_conversation(user_id, message, final_response)
        
        return final_response
```

---

## Best Practices

### 1. Memory Management
- Update user context setelah setiap transaksi
- Save conversation history untuk semua interaksi
- Learn new insights secara incremental

### 2. Personality Consistency
- Gunakan personality engine untuk semua responses
- Maintain tone yang consistent
- Adjust berdasarkan sentiment user

### 3. Context Awareness
- Always analyze context sebelum respond
- Reference past conversations when relevant
- Personalize berdasarkan user patterns

### 4. Performance
- Cache user profile untuk mengurangi API calls
- Limit conversation history lookup (max 5-10 messages)
- Update context secara asynchronous jika possible

---

## Troubleshooting

### Issue: Response tidak personal
**Solution**: 
- Pastikan conversation history tersimpan
- Check user context di Google Sheets
- Verify context processor mengambil data dengan benar

### Issue: Personality tidak consistent
**Solution**:
- Review `config/ai_personality.json`
- Pastikan personality engine digunakan di semua responses
- Check system prompt di LLM

### Issue: Memory tidak tersimpan
**Solution**:
- Verify Google Sheets connection
- Check sheet names di `config/memory_config.json`
- Ensure proper permissions untuk write ke Sheets

---

## Future Enhancements

- [ ] Machine learning untuk pattern detection
- [ ] Multi-language support
- [ ] Voice personality untuk voice messages
- [ ] Proactive insights & recommendations
- [ ] A/B testing untuk personality variants
- [ ] Analytics dashboard untuk AI performance

---

## Support

Untuk pertanyaan atau issues, check:
- `doc/personality_templates.md` untuk template examples
- Source code di `services/ai/`
- Configuration di `config/`
