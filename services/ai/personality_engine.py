"""
Personality Engine
Provides consistent friendly and supportive personality to AI responses.
"""

import random
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
import os

logger = logging.getLogger(__name__)


class PersonalityEngine:
    """Manages AI personality for natural, friendly responses."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize Personality Engine.
        
        Args:
            config_path: Path to personality config JSON file
        """
        self.config = self._load_config(config_path)
        self.name = self.config.get('name', 'TeleBuddy')
        self.personality_type = self.config.get('personality_type', 'supportive_friend')
        
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load personality configuration."""
        default_config = {
            "name": "TeleBuddy",
            "personality_type": "supportive_friend",
            "tone": "friendly_casual",
            "language": "id",
            "emoji_usage": "moderate",
            "response_style": {
                "greeting": "warm_personal",
                "encouragement": "high",
                "humor": "light",
                "formality": "low"
            }
        }
        
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    default_config.update(loaded)
            except Exception as e:
                logger.warning(f"Failed to load config, using defaults: {e}")
        
        return default_config
    
    def generate_greeting(
        self, 
        user_name: Optional[str] = None,
        time_of_day: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> str:
        """
        Generate contextual greeting.
        
        Args:
            user_name: User's name
            time_of_day: Time period (morning, afternoon, evening, night)
            context: Additional context (last_seen, achievements, etc)
            
        Returns:
            Greeting message
        """
        if not time_of_day:
            hour = datetime.now().hour
            if 5 <= hour < 11:
                time_of_day = 'morning'
            elif 11 <= hour < 15:
                time_of_day = 'afternoon'
            elif 15 <= hour < 19:
                time_of_day = 'evening'
            else:
                time_of_day = 'night'
        
        greetings = {
            'morning': [
                f"Pagi {user_name or 'kak'}! ☀️ Semangat pagi!",
                f"Selamat pagi! 🌅 Gimana tidurnya?",
                f"Morning {user_name or 'bestie'}! 😊 Siap nabung hari ini?",
            ],
            'afternoon': [
                f"Siang {user_name or 'kak'}! 🌤️ Lagi istirahat makan siang?",
                f"Halo! Semangat siang ya! 💪",
                f"Siang-siang gini enaknya cek budget ya kan? 😄",
            ],
            'evening': [
                f"Sore {user_name or 'kak'}! 🌇 Gimana harinya?",
                f"Halloo! Udah mau pulang nih? 😊",
                f"Sore! Waktunya review pengeluaran hari ini nih 📊",
            ],
            'night': [
                f"Malam {user_name or 'kak'}! 🌙 Masih melek nih?",
                f"Malem! Jangan begadang terus ya 😴",
                f"Halo! Sempet mau cek keuangan sebelum tidur? 💤",
            ]
        }
        
        options = greetings.get(time_of_day, greetings['afternoon'])
        return random.choice(options)
    
    def add_encouragement(
        self,
        context_type: str = 'general',
        achievement: Optional[str] = None
    ) -> str:
        """
        Generate encouragement message.
        
        Args:
            context_type: Type of encouragement (saving, spending, goal, general)
            achievement: Specific achievement to celebrate
            
        Returns:
            Encouragement message
        """
        encouragements = {
            'saving': [
                "Keren banget! Konsisten nabung tuh kuncinya! 💪",
                "Yeay! Makin deket sama goal nih! 🎯",
                "Mantap! Keep it up! 🌟",
                "Wihh, disiplin banget! Salut deh! 👏",
            ],
            'spending': [
                "Bagus! Pengeluarannya terkontrol nih! 👍",
                "Nice! Bijak manage uangnya! 💯",
                "Oke banget! Tetap mindful ya! ✨",
            ],
            'goal': [
                "Wohooo! Goal tercapai! Proud of you! 🎉",
                "Selamat yaaa! Kerja keras terbayar! 🏆",
                "Sukses! Next goal yuk! 🚀",
                "Amazing! Kamu keren! ⭐",
            ],
            'general': [
                "Semangat terus ya! Aku support kamu! 💪",
                "Kamu pasti bisa! Fighting! 🔥",
                "Yuk tetap konsisten! 😊",
            ]
        }
        
        options = encouragements.get(context_type, encouragements['general'])
        return random.choice(options)
    
    def format_response(
        self,
        message: str,
        add_emoji: bool = True,
        tone: str = 'casual'
    ) -> str:
        """
        Format response with personality.
        
        Args:
            message: Raw message
            add_emoji: Whether to add emoji
            tone: Response tone (casual, supportive, playful)
            
        Returns:
            Formatted message
        """
        # Add personality touches based on tone
        if tone == 'supportive':
            if not any(emoji in message for emoji in ['😊', '💪', '🌟', '✨']):
                if add_emoji:
                    supportive_emojis = ['😊', '💪', '🌟', '✨', '👍']
                    message += ' ' + random.choice(supportive_emojis)
        
        elif tone == 'playful':
            if add_emoji:
                playful_emojis = ['😄', '🎉', '🎊', '🚀', '⭐']
                if random.random() > 0.7:  # 30% chance
                    message += ' ' + random.choice(playful_emojis)
        
        return message
    
    def contextualize_message(
        self,
        base_message: str,
        user_context: Optional[Dict] = None,
        personalization: bool = True
    ) -> str:
        """
        Add context and personalization to message.
        
        Args:
            base_message: Base message content
            user_context: User context data
            personalization: Whether to add personal touches
            
        Returns:
            Contextualized message
        """
        if not personalization or not user_context:
            return base_message
        
        # Add personal touches based on context
        prefixes = []
        
        # Check for achievements
        if user_context.get('recent_achievement'):
            prefixes.append(f"Btw, congrats lagi ya! {self.add_encouragement('goal')}\n\n")
        
        # Check for active goals near completion
        if user_context.get('goal_near_completion'):
            goal = user_context['goal_near_completion']
            prefixes.append(f"Psstt, {goal} udah dekat loh! Semangat! 💪\n\n")
        
        # Combine prefix with message
        if prefixes:
            return random.choice(prefixes) + base_message
        
        return base_message
    
    def generate_reminder(
        self,
        reminder_type: str,
        details: Optional[Dict] = None
    ) -> str:
        """
        Generate friendly reminder message.
        
        Args:
            reminder_type: Type of reminder (budget, goal, spending, etc)
            details: Additional details for the reminder
            
        Returns:
            Reminder message
        """
        reminders = {
            'budget_limit': [
                "Hei! Budget bulan ini udah {percent}% nih. Keep track ya! 📊",
                "Reminder: Budget tinggal {remaining}! Jaga pengeluaran yaa 💰",
                "Psst, budget alert! Udah {percent}% kepake. Stay mindful! ✨",
            ],
            'goal_deadline': [
                "Goal '{goal}' deadline-nya tinggal {days} hari lagi! Semangat! 🎯",
                "Jangan lupa, target '{goal}' bentar lagi ya! Yuk push! 💪",
            ],
            'daily_check': [
                "Udah catet pengeluaran hari ini belum? 📝",
                "Waktunya update keuangan harian nih! 😊",
            ],
            'weekly_review': [
                "Hai! Yuk review pengeluaran minggu ini! 📈",
                "Weekend nih, sempet cek ringkasan mingguan ga? ✨",
            ]
        }
        
        templates = reminders.get(reminder_type, reminders['daily_check'])
        template = random.choice(templates)
        
        # Format with details if provided
        if details:
            try:
                return template.format(**details)
            except KeyError:
                return template
        
        return template
    
    def handle_sentiment(
        self,
        user_sentiment: str,
        message: str
    ) -> str:
        """
        Adjust response based on user sentiment.
        
        Args:
            user_sentiment: Detected sentiment (positive, negative, neutral, frustrated)
            message: Original message
            
        Returns:
            Sentiment-aware message
        """
        if user_sentiment == 'negative' or user_sentiment == 'frustrated':
            supportive_intros = [
                "Aku tau ini mungkin challenging, tapi ",
                "Gapapa, santai aja ya! ",
                "Aku ngerti kok, tapi ingat: ",
                "Hey, everything's gonna be okay! ",
            ]
            return random.choice(supportive_intros) + message
        
        elif user_sentiment == 'positive':
            positive_intros = [
                "Yes! ",
                "Seneng deh liat semangatnya! ",
                "Mantap! ",
                "Love the energy! ",
            ]
            return random.choice(positive_intros) + message
        
        return message
    
    def get_conversation_starter(self) -> str:
        """
        Generate random conversation starter.
        
        Returns:
            Conversation starter message
        """
        starters = [
            "Gimana kabar finansialnya hari ini? 😊",
            "Ada yang bisa aku bantu hari ini? 💬",
            "Yuk mulai atur keuangan hari ini! ✨",
            "Siap bantu kamu manage budget! 💪",
            "Halo! Mau cek pengeluaran atau set goal? 🎯",
        ]
        return random.choice(starters)
    
    def create_system_prompt(
        self,
        context: Optional[Dict] = None
    ) -> str:
        """
        Create system prompt for LLM with personality definition.
        
        Args:
            context: Additional context to include
            
        Returns:
            System prompt string
        """
        base_prompt = f"""Kamu adalah {self.name}, asisten keuangan AI yang ramah dan supportive.

Personality:
- Kamu berbicara dengan bahasa Indonesia casual dan friendly
- Kamu seperti teman yang care dan selalu support user
- Kamu pakai emoji secara moderate untuk ekspresif tapi ga berlebihan
- Kamu kasih motivasi dan encouragement tanpa terdengar menggurui
- Kamu honest tapi tetap gentle kalau ada yang perlu dikritik

Gaya komunikasi:
- Gunakan "kamu" bukan "Anda"
- Pakai kontraksi: "udah", "gimana", "ga"
- Natural dan conversational
- Hindari jargon yang terlalu teknis
- Berikan saran dengan cara yang supportive

Fokus utama:
- Bantu user manage keuangan dengan cara yang fun dan ga stressful
- Kasih insight yang actionable dan relevan
- Celebrate achievements sekecil apapun
- Ingatkan dengan gentle tanpa judgmental

Ingat: Kamu bukan robot, kamu teman yang peduli! 💙"""

        if context:
            base_prompt += f"\n\nKonteks tambahan:\n{json.dumps(context, indent=2, ensure_ascii=False)}"
        
        return base_prompt
