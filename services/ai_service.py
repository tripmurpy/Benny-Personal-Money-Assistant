import json
import re
import base64
import logging
import io
from typing import List, Dict, Any

# Third-party async libraries
import httpx
from groq import AsyncGroq
from PIL import Image

# Config
from config import Config

# Setup production logger
logger = logging.getLogger(__name__)


class AIService:
    def __init__(self):
        try:
            # Initialize Async Client
            self.client = AsyncGroq(api_key=Config.GROQ_API_KEY)
            self.hf_headers = {"Authorization": f"Bearer {Config.HUGGINGFACE_API_KEY}"}
            
            from openai import AsyncOpenAI
            self.openrouter_client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=Config.OPENROUTER_API_KEY,
            )
            
            if Config.GEMINI_API_KEY:
                from google import genai
                self.gemini_client = genai.Client(api_key=Config.GEMINI_API_KEY)
            else:
                self.gemini_client = None
        except Exception as e:
            logger.critical(f"❌ Failed to initialize AI Service: {e}", exc_info=True)
            raise

    def _clean_json_output(self, raw_content: str) -> Dict[str, Any]:
        """
        Robust JSON extraction/repair.
        Raises ValueError if JSON cannot be parsed after attempts.
        """
        content = raw_content.strip()

        # 1. Strip Markdown Code Blocks
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
        if match:
            content = match.group(1).strip()

        # 2. Strip comments (JS Style //)
        content = re.sub(r'//.*', '', content)

        # 3. Find first { and last }
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1:
            content = content[start:end + 1]

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Initial JSON parse failed: {e}. Raw: {content[:100]}...")
            # Todo: Implement 'json_repair' lib logic here if needed for critical paths
            # For now, let's try a simple common fix: trailing commas
            try:
                content_fixed = re.sub(r',\s*}', '}', content)
                content_fixed = re.sub(r',\s*]', ']', content_fixed)
                return json.loads(content_fixed)
            except json.JSONDecodeError:
                # Re-raise to let caller handle failure (e.g. ask user to repeat)
                # DO NOT return empty dict silently.
                logger.error(f"❌ JSON Repair failed for content: {content}")
                raise ValueError("AI response returned invalid JSON format")

    async def parse_expense(self, user_text: str) -> List[Dict]:
        """[ASYNC] Membaca Chat Biasa -> JSON using Groq Llama 3"""
        from datetime import datetime
        now = datetime.now()

        system_prompt = f"""You are a financial extraction engine for Indonesian rupiah transactions.
Target: Extract transactions from user text into valid JSON.

Current Context:
- Date: {now.strftime('%Y-%m-%d')}
- Time: {now.strftime('%H:%M')}

Output Schema:
{{
  "items": [
    {{
      "date": "YYYY-MM-DD", 
      "time": "HH:MM", 
      "item": "string", 
      "category": "Food/Drink/Shopping/Gas/Transport/Income/Komunikasi/Study/Other", 
      "amount": integer, 
      "location": "string"
    }}
  ]
}}

ITEM NAME RULES (CRITICAL):
- "item" is the PRODUCT/SERVICE name only, NOT the action verb.
- REMOVE verbs like "beli", "bayar", "isi" from the item name.
- Capitalize the first letter of each word.
- Examples:
  - "beli ayam" → item: "Ayam"
  - "beli kopi" → item: "Kopi"
  - "bayar listrik" → item: "Listrik"
  - "isi bensin" → item: "Bensin"
  - "beli fore amerikano" → item: "Fore Amerikano"
  - "makan naspad" → item: "Naspad"
  - "jajan mochi" → item: "Mochi"

CATEGORY RULES (CRITICAL — use EXACTLY these categories):
- "Food" → meals, snacks, rice, nasi, mie, ayam, bakso, etc.
- "Drink" → coffee, tea, juice, kopi, teh, amerikano, latte, boba, es, minuman
- "Shopping" → clothing, electronics, household items, belanja
- "Gas" → bensin, pertamax, pertalite, fuel, BBM
- "Transport" → ojek, grab, gojek, angkot, bus, kereta, taxi, MRT, KRL
- "Income" → gaji, salary, bonus, THR, hadiah, received money
- "Komunikasi" → pulsa, kuota, internet, paket data, wifi
- "Study" → pensil, buku, notebook, alat tulis, fotokopi, print
- "Other" → anything that doesn't fit above

CRITICAL AMOUNT CONVERSION RULES (Indonesian Currency Context):
1. "rb" or "ribu" means thousands (×1000):
   - "10 rb" = 10000 
   - "50rb" = 50000 
   - "20 ribu" = 20000 
   - "100 ribu" = 100000 

2. "k" also means thousands (×1000):
   - "10k" = 10000
   - "50k" = 50000

3. Plain numbers in food/item context mean thousands (×1000):
   - "naspad 10" = 10000
   - "mochi 7" = 7000

4. Numbers with explicit decimals/dots are literal:
   - "10.000" = 10000

5. "juta" or "jt" means millions (×1000000):
   - "1 juta" = 1000000
   - "5jt" = 5000000

INCOME DETECTION RULES (CRITICAL):
6. Category = 'Income' when user mentions:
   - 'dapat' (got/received) → "Hari ini dapat 100rb" (Item: Uang, Amount: 100000, Category: Income)
   - 'dapet' 
   - 'terima'
   - 'gaji' / 'salary'
   - 'masuk' → "Ada transfer masuk 500rb"
   - 'dikasih' → "Dikasih tante 200rb" (Item: Dari tante, Amount: 200000, Category: Income)
   - 'bonus', 'THR', 'hadiah'
   
   For income, the amount is often the MAIN focus. E.g., "dapat 100rb" means the User RECEIVED 100000 IDR.

OTHER RULES:
7. DATE RULES (CRITICAL):
   - "kemarin" (yesterday) = subtract 1 day from Current Context Date.
   - "hari ini" (today) = use Current Context Date.
   - Default to Current Context Date if no date is specified.
8. Default missing values to reasonable defaults or empty string.
9. OUTPUT JSON ONLY. NO MARKDOWN."""

        try:
            chat_completion = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ],
                model=Config.GROQ_MODEL,
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            raw_response = chat_completion.choices[0].message.content
            result = self._clean_json_output(raw_response)
            return result.get("items", [])

        except Exception as e:
            logger.error(f"Error parsing expense text: {e}", exc_info=True)
            return []  # Return empty list gracefully only after logging

    async def parse_modification(self, user_text: str, recent_transactions: List[Dict]) -> Dict:
        """[ASYNC] Parse natural language for updating or deleting an existing transaction."""
        import json
        
        # Prepare context data
        tx_data = []
        for t in recent_transactions:
            tx_data.append({
                "id": t.get("id"),
                "date": t.get("date"),
                "time": t.get("time"),
                "item": t.get("item_name"),
                "amount": t.get("amount"),
                "category": t.get("category")
            })

        system_prompt = f"""Kamu adalah bot pendeteksi niat ubah/hapus transaksi keuangan.
Tugas: Temukan transaksi mana dari history user yang ingin diubah atau dihapus berdasarkan input teksnya.

History transaksi terakhir:
{json.dumps(tx_data)}

Output Schema:
{{
  "action": "update" | "delete" | "not_found",
  "target_id": "string atau angka id dari transaksi yang cocok" | null,
  "new_data": {{
    "amount": integer,
    "item": "string",
    "category": "string"
  }}
}}

Aturan:
- "action": "not_found" jika transaksi tidak ada yang cocok secara masuk akal (toleransi wajar).
- Jika nama mirip (kopi vs teh) atau disebut harganya, periksa dengan teliti.
- "target_id" HARUS diambil dari "id" transaksi di history. Jika ada 2 transaksi kembar di hari yg sama, ambil record yang masuk di index pertama (yg terakhir user masukkan).
- "new_data" berlaku hanya untuk "action": "update". HANYA cantumkan atribut yang dirubah. Misal rubah nominal angka: konversikan 15k atau 15rb dsb ke 15000. OUTPUT PURE JSON!
"""

        try:
            chat_completion = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ],
                model=Config.GROQ_MODEL,
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            raw_response = chat_completion.choices[0].message.content
            return self._clean_json_output(raw_response)
        except Exception as e:
            logger.error(f"Error parsing modification: {e}", exc_info=True)
            return {"action": "not_found", "target_id": None}

    async def parse_receipt_image(self, image_bytes: bytes) -> List[Dict]:
        """[ASYNC] OCR Struk -> JSON using Gemini 2.5 Flash"""
        prompt = """Tolong analisa foto struk belanja atau bukti pembayaran ini.
Lakukan ekstraksi data secara komprehensif agar siap diinput ke database.
Kembalikan **HANYA** dalam format JSON (tanpa awalan/akhiran text lain):
{
  "items": [
    {
      "item": "Nama Barang atau Pembayaran",
      "category": "Food/Drink/Shopping/Gas/Transport/Komunikasi/Study/Other",
      "amount": harga_dalam_angka_bulat_integer,
      "date": "YYYY-MM-DD",
      "time": "HH:MM",
      "location": "Lokasi Pembelian / Nama Toko (jika ada)"
    }
  ]
}
Aturan Ekstraksi:
- 'amount': Konversi nominal harga ke angka bulat (cth: Rp 50.000 atau 50,000 -> 50000).
- 'location': Ambil lokasi pembelian dari logogram gerai, kop surat struk, atau info bill. Jika tidak ada kosongkan ("").
- 'date': Cari format tanggal transaksi di struk. Jika tidak ada kosongkan ("").
- 'time': Cari format jam/waktu transaksi ("Waktu" / "Time") di struk (CTH: 14:30). Jika tidak ada kosongkan ("").
- 'category': Kategorikan dengan cerdas (contoh: KFC -> Food, Excelso -> Drink)."""

        try:
            if not self.gemini_client:
                raise ValueError("Gemini API Key missing")
            
            logger.debug("🔍 Membaca gambar struk dengan Gemini 2.0 Flash...")
            from google.genai import types
            
            response = await self.gemini_client.aio.models.generate_content(
                model='gemini-2.0-flash',
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                    prompt
                ],
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )

            result_text = response.text
            result = self._clean_json_output(result_text)
            return result.get("items", [])

        except Exception as e:
            logger.error(f"FAILED Gemini Vision OCR: {e}")
            # Fallback to Qwen 2.5 VL via OpenRouter
            logger.info("🔄 Falling back to Qwen 2.5 VL (OpenRouter)...")
            return await self._ocr_fallback_qwen(image_bytes, prompt)

    async def _ocr_fallback_qwen(self, image_bytes: bytes, prompt: str) -> List[Dict]:
        """Fallback OCR using Qwen VL Plus via OpenRouter (Async)"""
        encoded_image = base64.b64encode(image_bytes).decode('utf-8')
        try:
            response = await self.openrouter_client.chat.completions.create(
                model="qwen/qwen-vl-plus",
                messages=[
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}
                    ]}
                ],
                temperature=0.1
            )
            
            raw_response = response.choices[0].message.content
            result = self._clean_json_output(raw_response)
            return result.get("items", [])
            
        except Exception as e:
            logger.error(f"Qwen Fallback Error: {e}")
            return []

    async def transcribe_audio(self, audio_bytes: bytes) -> str:
        """[ASYNC] Voice -> Text using Whisper via Groq"""
        try:
            logger.debug("🎤 Mendengarkan Voice Note dengan Whisper (Groq)...")
            prompt = "Tolong dengarkan dan transkripsikan rekaman suara (voice note) ini secara utuh dan akurat ke dalam teks bahasa Indonesia. JIKA ADA nominal uang angka (cth: sepuluh ribu), tuliskan juga angkanya bila perlu."
            
            response = await self.client.audio.transcriptions.create(
                file=("voice.ogg", audio_bytes),
                model="whisper-large-v3-turbo",
                prompt=prompt,
                response_format="json",
                language="id"
            )
            return response.text.strip()

        except Exception as e:
            logger.error(f"❌ Whisper Audio Error: {e}")
            return ""

    def _optimize_image_to_bytes(self, image_bytes: bytes) -> bytes:
        """Resize and convert image to compressed JPEG bytes (CPU Bound)"""
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode != 'RGB':
            image = image.convert('RGB')

        image.thumbnail((1024, 1024))

        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=85)
        return buffered.getvalue()

    def _optimize_image(self, image_bytes: bytes) -> str:
        """Resize and encode image to base64 (CPU Bound)"""
        return base64.b64encode(self._optimize_image_to_bytes(image_bytes)).decode('utf-8')

    async def chat_with_user(self, user_text: str, user_id: str | None = None, reply_context: str = "") -> str:
        """
        [ASYNC] Conversational chat using Groq with warm personality.

        Unlike parse_expense (which extracts JSON), this returns natural
        friendly text responses for casual conversation.

        Args:
            user_text: User's message
            user_id: User ID to fetch and save chat history
            reply_context: Optional text from the message user is replying to
        """
        from services.ai.prompts import PromptTemplates
        from config import Config
        from services.supabase_service import SupabaseService
        from services.rag_service import get_rag_service

        system_prompt = PromptTemplates.get_system_prompt(
            Config.get_personality_config()
        )

        # Add chat-specific instructions
        system_prompt += """

INSTRUKSI TAMBAHAN UNTUK CHAT:
- Jawab dengan SINGKAT (1-3 kalimat), natural, dan hangat
- Kamu adalah TEMAN DEKAT bernama Benny, bukan robot/AI
- Bahasamu santai banget kayak chat WhatsApp sama bestie
- Pakai "lo/gue" atau "kamu/aku" tergantung vibes-nya
- Jika user curhat atau cerita, dengerin dan beri empati yang tulus
- Jika user tanya hal di luar keuangan, tetap jawab dengan fun
- Gunakan emoji secukupnya (1-3 emoji per pesan)
- JANGAN memberi tutorial kecuali diminta
- Kalau user balas (reply) pesan sebelumnya, PAHAMI konteks pesan yang dibalas dan jawab relevan
- JIKA ada konteks dari Knowledge Base (RAG) yang disediakan, gunakan informasi tersebut untuk menjawab pertanyaan. Jangan sebutkan "Berdasarkan knowledge base..." tapi jawab secara natural seolah kamu memang tahu."""

        # Build messages builder
        messages = [{"role": "system", "content": system_prompt}]

        # 1. RAG: Fetch Knowledge Base Context
        rag_service = get_rag_service()
        kb_context = rag_service.get_knowledge_base_context(user_text)
        if kb_context:
            messages.append({"role": "system", "content": f"REFERENSI PENGETAHUAN (Gunakan jika relevan dengan pertanyaan user):\n{kb_context}"})

        # 2. Fetch up to 10 recent messages from Supabase History if user_id is provided
        if user_id:
            try:
                db = SupabaseService()
                chat_history = db.get_chat_history(user_id, limit=10)
                for chat in chat_history:
                    role = chat.get("role")
                    msg_content = chat.get("message")
                    if role and msg_content:
                        # Prevent appending system messages or unexpected roles if any in db
                        if role in ["user", "assistant"]:
                            messages.append({"role": role, "content": msg_content})
            except Exception as e:
                logger.error(f"Failed to fetch chat history for user {user_id}: {e}")

        # If user is replying to a bot message, add it as context
        if reply_context:
            messages.append({"role": "assistant", "content": f"[Konteks Pesan Dibalas]: {reply_context}"})

        messages.append({"role": "user", "content": user_text})

        try:
            chat_completion = await self.client.chat.completions.create(
                messages=messages,
                model=Config.GROQ_MODEL,
                temperature=0.7,
                max_tokens=256,
            )

            response = chat_completion.choices[0].message.content
            final_response = response.strip() if response else ""

            # Save user interaction and AI response to Supabase History asynchronously
            if final_response and user_id:
                try:
                    # Execute sequentially or fire-and-forget logic if needed
                    # We run it synchronously (or within async context) to avoid race conditions
                    # with multiple rapid messages
                    db.add_chat(user_id, "user", user_text)
                    db.add_chat(user_id, "assistant", final_response)
                except Exception as db_err:
                    logger.error(f"Failed to save chat to history: {db_err}")

            return final_response

        except Exception as e:
            logger.error(f"Chat with user failed: {e}")
            return ""

    def analyze_expenses(self, transactions_list: List[Dict], period_label: str) -> str:
        """
        [Sync] Statistic calculation is fast enough for sync execution.
        If data grows large, move to pandas/async.
        """
        if not transactions_list:
            return f"Data {period_label} kosong."

        # ... (Logika analisis existing sudah cukup efisien untuk list kecil)
        total = 0
        cat_map = {}

        for t in transactions_list:
            try:
                # Robust extraction handling mixed types
                amt_val = t.get('Amount (IDR)') or t.get('amount') or 0
                cat_val = t.get('Category') or t.get('category') or 'Other'

                if isinstance(amt_val, str):
                    amt = int(''.join(filter(str.isdigit, amt_val)) or 0)
                else:
                    amt = int(amt_val)

                if str(cat_val).lower() in ['income', 'pemasukan']:
                    continue

                total += amt
                cat_map[cat_val] = int(cat_map.get(cat_val, 0)) + amt
            except Exception:
                continue

        if total == 0:
            return f"Belum ada pengeluaran valid di {period_label}."

        # Sorting & Formatting
        sorted_cats = sorted(cat_map.items(), key=lambda x: x[1], reverse=True)
        top_cat = sorted_cats[0]

        report = f"📊 Analisis {period_label}\n"
        report += f"💸 Total: Rp {total:,.0f}".replace(',', '.') + "\n\n"
        report += f"🚨 Terbesar: {top_cat[0]} (Rp {top_cat[1]:,.0f})".replace(',', '.') + "\n"

        return report

    async def summarize_expenses(
        self,
        transactions: List[Dict],
        period_label: str,
        user_query: str,
    ) -> str:
        """
        [ASYNC] Generate a smart AI summary of expenses for a given period.

        Returns a natural, conversational summary with:
        - Total spending
        - Breakdown by category
        - Spending patterns / insights
        """
        import json

        # Prepare compact data for prompt
        total = 0
        cat_map = {}
        tx_lines = []
        for t in transactions:
            amt = int(t.get('amount', 0))
            cat = t.get('category', 'Other')
            item = t.get('item_name', t.get('item', '?'))
            t.get('date', '')
            time_str = t.get('time', '')

            if str(cat).lower() in ['income', 'pemasukan', 'gaji']:
                continue

            total += amt
            cat_map[cat] = cat_map.get(cat, 0) + amt
            tx_lines.append({"waktu": time_str, "item": item, "jumlah": amt, "kategori": cat})

        if total == 0:
            return f"📂 Belum ada pengeluaran di periode {period_label} nih! 🎉"

        # Build category breakdown text
        sorted_cats = sorted(cat_map.items(), key=lambda x: x[1], reverse=True)
        cat_breakdown = "\n".join(
            f"- {cat}: Rp {amt:,}".replace(",", ".") for cat, amt in sorted_cats
        )

        total_str = f"Rp {total:,}".replace(",", ".")

        system_prompt = f"""Kamu adalah Benny, sahabat keuangan user yang santai dan akrab.

User bertanya tentang pengeluaran di periode: {period_label}

DATA PENGELUARAN:
Total: {total_str}
Jumlah transaksi: {len(tx_lines)}

Breakdown per kategori:
{cat_breakdown}

Daftar Transaksi (item dan waktu):
{json.dumps(tx_lines[max(0, len(tx_lines)-30):], indent=2)}

INSTRUKSI (SANGAT PENTING):
1. Rangkum pengeluaran dengan ANGKA YANG TEPAT (format Rp X.XXX).
2. Jika User menanyakan spesifik tentang transaksi, jam, atau waktu tertentu (misal: "jam 12 aku beli apa?"), JAWAB DENGAN TEPAT berdasarkan 'Daftar Transaksi' di atas. JANGAN MENEBAK-NEBAK dan HANYA GUNAKAN DATA TERSEBUT.
3. Jika ditanya hal umum, Sebutkan kategori terbesar jika user menanyakan ringkasan/laporan umum.
4. Gaya bahasa: asik, pintar, pakai emoji (2-4), kayak chat chat profesional (jangan terlalu kaku, tapi tidak usah terlalu gaul).
5. Singkat: 2-5 kalimat max. Jawab langsung ke intinya (to the point)."""

        try:
            chat_completion = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query},
                ],
                model=Config.GROQ_MODEL,
                temperature=0.6,
                max_tokens=350,
            )

            response = chat_completion.choices[0].message.content
            return response.strip() if response else self._fallback_summary(
                total_str, sorted_cats, period_label
            )

        except Exception as e:
            logger.error(f"Summarize expenses failed: {e}")
            return self._fallback_summary(total_str, sorted_cats, period_label)

    def _fallback_summary(self, total_str, sorted_cats, period_label):
        """Fallback non-AI summary when Groq is unavailable."""
        msg = f"📊 Pengeluaran {period_label}\n\n"
        msg += f"💸 Total: {total_str}\n\n"
        for cat, amt in sorted_cats:
            amt_str = f"Rp {amt:,}".replace(",", ".")
            msg += f"▪️ {cat}: {amt_str}\n"
        return msg

    async def generate_smart_recommendation(self, transactions: List[Dict], current_time: str, user_query: str) -> str:
        """
        [ASYNC] Generate context and time-aware recommendations based on history.
        """
        from config import Config
        import json

        # Prepare data for AI
        tx_data = []
        recent_tx = transactions[max(0, len(transactions)-100):]
        for t in recent_tx:  # Limit to recent 100 for context size
            # Clean up the dict to only essential info for the prompt
            item = t.get('item', t.get('Item Name', ''))
            cat = t.get('category', t.get('Category', ''))
            # Filter out income
            if str(cat).lower() in ['income', 'pemasukan', 'gaji']:
                continue

            tx_data.append({
                "time": t.get('time', ''),
                "date": t.get('date', t.get('Date', '')),
                "item": item,
                "category": cat
            })

        system_prompt = f"""Kamu adalah Benny, teman dekat user yang juga bisa kasih saran belanja pintar.
Kamu bukan robot, tapi sahabat yang kenal kebiasaan belanja si user karena kamu selalu bantu catat pengeluarannya.

Sekarang jam: {current_time}
Ini catatan belanja user yang pernah kamu bantu catat:
{json.dumps(tx_data, indent=2)}

CARA KASIH SARAN:
1. Pahami apa yang user tanya (mau makan? jajan? belanja? atau cuma bingung aja?)
2. Cek catatan di atas — kalo user sering beli Kopi jam 15, ya ingetin "eh biasanya jam segini kamu ngopi kan?" 😄
3. Kalo gak ada pola yang pas, kasih saran kreatif & relevan (siang → es kopi/makan siang, malam → martabak/gorengan)
4. Ngomongnya SANTAI BANGET kayak teman yang lagi chat biasa, pakai emoji secukupnya
5. Jangan bilang "Berdasarkan data..." atau "Berdasarkan histori...", tapi bilang aja "Eh biasanya kamu..." atau "Dari catatan kita..."
6. Singkat aja 2-3 kalimat, kayak bales chat temen"""

        try:
            logger.debug(f"🤖 Generating smart recommendation for query: '{user_query}' at {current_time}")
            chat_completion = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ],
                model=Config.GROQ_MODEL,
                temperature=0.7,
                max_tokens=250,
            )

            response = chat_completion.choices[0].message.content
            return response.strip() if response else "Hmm, aku lagi agak blank nih. Gimana kalau jajan yang seger-seger aja? 🍦"

        except Exception as e:
            logger.error(f"Failed to generate smart recommendation: {e}")
            return "Waduh, otak analisaku lagi ngadat bentar 🤯. Beli apa yang lagi kamu pengenin aja deh sekarang! 💙"
