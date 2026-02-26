import json
import re
import base64
import logging
import io
import asyncio
from typing import List, Dict, Any, Optional

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
            # logger.info("✅ AI Service Initialized (Async Mode)") # Silenced for clean output
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
            content = content[start:end+1]
            
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
      "category": "Food/Transport/Bills/Shopping/Income/Other", 
      "amount": integer, 
      "location": "string"
    }}
  ]
}}

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
   - 'dapat' (got/received) -> "Hari ini dapat 100rb" (Item: Dapat uang, Amount: 100000, Category: Income)
   - 'dapet' 
   - 'terima'
   - 'gaji' / 'salary'
   - 'masuk' -> "Ada transfer masuk 500rb"
   - 'dikasih' -> "Dikasih tante 200rb" (Item: Dikasih tante, Amount: 200000, Category: Income)
   - 'bonus', 'THR', 'hadiah'
   
   For income, the amount is often the MAIN focus. E.g., "dapat 100rb" means the User RECEIVED 100000 IDR.

OTHER RULES:
7. Default missing values to reasonable defaults or empty string.
8. OUTPUT JSON ONLY. NO MARKDOWN."""

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
            return [] # Return empty list gracefully only after logging

    async def parse_receipt_image(self, image_bytes: bytes) -> List[Dict]:
        """[ASYNC] OCR Struk -> JSON using Groq Vision (Llama 3.2)"""
        try:
            # 1. Optimize Image (Blocking CPU operation, keep it minimal or run in executor if heavy)
            processed_image = self._optimize_image(image_bytes)
            
            # 2. Call Groq Vision
            prompt = "Extract all purchased items, prices, and total date from this receipt. Return JSON format: {items: [{item, category, amount, date}]}. Convert IDR currency (e.g. 50.000 -> 50000)."
            
            logger.debug("🔍 Sending image to Groq Vision...")
            chat_completion = await self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{processed_image}",
                                },
                            },
                        ],
                    }
                ],
                model="llama-3.2-90b-vision-preview",
                temperature=0.1,
                max_tokens=1024,
            )
            
            result_text = chat_completion.choices[0].message.content
            result = self._clean_json_output(result_text)
            return result.get("items", [])
            
        except Exception as e:
            logger.error(f"FAILED Groq Vision OCR: {e}")
            # Fallback to HuggingFace Florence-2
            logger.info("🔄 Falling back to HF Florence-2...")
            return await self._ocr_fallback_hf(image_bytes)

    async def _ocr_fallback_hf(self, image_bytes: bytes) -> List[Dict]:
        """Fallback OCR using HuggingFace API (Async)"""
        # Encode implementation again as we need raw base64 for HF
        encoded_image = base64.b64encode(image_bytes).decode('utf-8')
        
        payload = {
            "inputs": "Extract all items and prices from this receipt image.",
            "parameters": {"image": encoded_image}
        }
        
        try:
            async with httpx.AsyncClient() as http_client:
                response = await http_client.post(
                    "https://api-inference.huggingface.co/models/microsoft/Florence-2-large",
                    headers=self.hf_headers,
                    json=payload,
                    timeout=45.0
                )
                
                if response.status_code != 200:
                    logger.error(f"HF Fallback Error: {response.status_code} - {response.text}")
                    return []
                
                # Florence returns generated text, need to parse carefully or pipe to LLM
                # For simplicity in this '10x' fix, we return empty or try to parse if structure is known.
                # Usually Florence needs a second pass to structure data unless prompted perfectly.
                # We return empty here to avoid garbage data.
                return [] 
                
        except Exception as e:
            logger.error(f"HF Fallback Exception: {e}")
            return []

    async def transcribe_audio(self, audio_bytes: bytes) -> str:
        """[ASYNC] Voice -> Text using Groq Whisper (Fastest & Reliable)"""
        import tempfile
        import os
        
        try:
            # Groq Whisper is extremely fast (LPU Inference)
            # We need to save bytes to a temp file first because Groq SDK needs a file-like object with name
            
            # Use .ogg extension as it mimics the original Telegram voice format
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_audio:
                temp_audio.write(audio_bytes)
                temp_path = temp_audio.name

            try:
                logger.debug("🎤 Transcribing with Groq Whisper...")
                with open(temp_path, 'rb') as audio_file:
                    transcription = await self.client.audio.transcriptions.create(
                        model="whisper-large-v3",
                        file=audio_file,
                        language="id" # Optimize for Indonesian
                    )
                return transcription.text
                
            finally:
                # Cleanup temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except Exception as e:
            logger.error(f"❌ Groq Whisper Error: {e}")
            return ""

    def _optimize_image(self, image_bytes: bytes) -> str:
        """Resize and encode image to base64 (CPU Bound)"""
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        image.thumbnail((1024, 1024))
        
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=85)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    async def chat_with_user(self, user_text: str, reply_context: str = "") -> str:
        """
        [ASYNC] Conversational chat using Groq with warm personality.
        
        Unlike parse_expense (which extracts JSON), this returns natural
        friendly text responses for casual conversation.
        
        Args:
            user_text: User's message
            reply_context: Optional text from the message user is replying to
        """
        from services.ai.prompts import PromptTemplates
        from config import Config
        
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
- Kalau user balas (reply) pesan sebelumnya, PAHAMI konteks pesan yang dibalas dan jawab relevan"""

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        
        # If user is replying to a bot message, add it as context
        if reply_context:
            messages.append({"role": "assistant", "content": reply_context})
        
        messages.append({"role": "user", "content": user_text})

        try:
            chat_completion = await self.client.chat.completions.create(
                messages=messages,
                model=Config.GROQ_MODEL,
                temperature=0.7,
                max_tokens=256,
            )
            
            response = chat_completion.choices[0].message.content
            return response.strip() if response else ""
            
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
                cat_map[cat_val] = cat_map.get(cat_val, 0) + amt
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

    async def generate_smart_recommendation(self, transactions: List[Dict], current_time: str, user_query: str) -> str:
        """
        [ASYNC] Generate context and time-aware recommendations based on history.
        """
        from config import Config
        from services.ai.prompts import PromptTemplates
        import json
        
        # Prepare data for AI
        tx_data = []
        for t in transactions[-100:]: # Limit to recent 100 for context size
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