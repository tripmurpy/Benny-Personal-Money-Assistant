"""
Benny's Personality Response Engine
Generates supportive, encouraging responses for different contexts.

This module provides contextual, personality-driven responses that make
Benny feel like a supportive friend rather than a generic bot.
"""

import random
from typing import List, Optional


class PersonalityResponses:
    """
    Benny's personality engine for generating warm, supportive responses.
    
    Benny is designed to be:
    - Supportive: Always encouraging, never judgmental
    - Friendly: Casual, warm, personal tone
    - Motivating: Celebrates wins, encourages during challenges
    - Helpful: Provides actionable insights with care
    
    Example:
        >>> personality = PersonalityResponses()
        >>> response = personality.get_transaction_response(25000, "Food")
        >>> print(response)
        "✅ Tercatat! Makan enak nih? Semoga kenyang! 🍽️"
    """
    
    def __init__(self):
        """Initialize personality responses with various templates."""
        
        # Transaction confirmation responses (cheerful & supportive)
        self.transaction_confirmations = {
            'Food': [
                "✅ Tercatat! Makan enak nih? Semoga kenyang! 🍽️",
                "✅ Oke! Jajan lagi ya? Nikmatin! 🍔",
                "✅ Sip! Semoga makanannya enak banget! 😋",
                "✅ Noted! Treat yourself, you deserve it! ☕"
            ],
            'Transport': [
                "✅ Tercatat! Hati-hati di jalan ya! 🚗",
                "✅ Oke! Perjalanan aman! 🛵",
                "✅ Sip! Semoga lancar perjalanannya! 🚌"
            ],
            'Shopping': [
                "✅ Tercatat! Belanja apa nih? Pasti seru! 🛍️",
                "✅ Oke! Dapet barang bagus? 🎁",
                "✅ Sip! Semoga belanjaan berguna ya! 🛒"
            ],
            'Bills': [
                "✅ Tercatat! Good job bayar tagihan tepat waktu! 💳",
                "✅ Oke! Mantap, tanggungan berkurang! ⚡",
                "✅ Sip! Responsibility level: 100! 📱"
            ],
            'Income': [
                "💵 Yeayyy! Pemasukan nih! Congrats! 🎉",
                "💰 Wohooo! Rezeki datang! Alhamdulillah! ✨",
                "💸 Mantap! Semoga makin lancar rezekinya! 🚀"
            ],
            'default': [
                "✅ Tercatat! Semoga bermanfaat ya! 👍",
                "✅ Oke! Noted with care! 📝",
                "✅ Sip! Aku catat ya! ✨"
            ]
        }
        
        # Budget warning responses (gentle & motivating)
        self.budget_warnings = {
            'low': [  # 50-70%
                "💡 Psst, budget {category} udah {percentage}% nih. Masih aman, tapi mulai hati-hati ya! 😊",
                "📊 Hey! {category} udah {percentage}% dari budget. Pelan-pelan ya spending-nya! 💪",
                "⚡ FYI: Budget {category} udah {percentage}%. Kamu pasti bisa manage sisanya! 🎯"
            ],
            'medium': [  # 70-90%
                "⚠️ Budget {category} udah {percentage}% nih! Yuk, coba hemat sedikit buat sisanya! 💛",
                "🔔 {category} udah {percentage}%! Semangat ya, tinggal dikit lagi! Kamu bisa! 🌟",
                "💛 Hati-hati, {category} udah {percentage}%! Ayo kita jaga biar ga over! 💪"
            ],
            'high': [  # 90%+
                "🚨 Budget {category} udah {percentage}%! Udah di ujung nih. Pelan-pelan ya! Kamu pasti bisa ngatur! 💙",
                "⚠️ Wah! {category} tinggal {remaining}% lagi! Yuk, sama-sama jaga biar ga tembus! 🛡️",
                "🔴 {category} udah hampir habis ({percentage}%)! Tenang, masih ada waktu buat adjust! 🎯"
            ]
        }
        
        # Goal progress responses (celebratory!)
        self.goal_progress = {
            'started': [  # 0-25%
                "🎯 Target {goal_name} dimulai! {percentage}% - Langkah pertama sudah diambil! Semangat! 💪",
                "🌱 {goal_name}: {percentage}% - Small steps, big dreams! Ayo lanjut! ✨"
            ],
            'good': [  # 25-50%
                "📈 {goal_name}: {percentage}% - Wih progress bagus! Setengah jalan nih! Keep going! 🚀",
                "🎉 Udah {percentage}% nih {goal_name}! Mantap banget! Lanjutkan! 💪"
            ],
            'great': [  # 50-75%
                "🔥 {goal_name}: {percentage}% - Hebat! Lebih dari setengah! Goal makin deket! 🎯",
                "⭐ Wow {percentage}%! {goal_name} hampir tercapai! Keren banget! 💫"
            ],
            'almost': [  # 75-99%
                "🚀 {goal_name}: {percentage}% - TINGGAL DIKIT LAGI! You got this! 🔥",
                "💪 {percentage}%! {goal_name} hampir selesai! Final push! 🏁"
            ],
            'achieved': [  # 100%+
                "🎊 YEAAAY! {goal_name} TERCAPAI! {percentage}%! YOU DID IT! 🏆✨",
                "🏆 TARGET ACHIEVED! {goal_name} {percentage}%! Luar biasa! 🎉🎉🎉"
            ]
        }
        
        # Weekly report intros (warm greetings)
        self.weekly_intros = [
            "Halo! Ini laporan minggu ini. Yuk kita lihat progress kamu! 📊",
            "Hey! Udah seminggu nih. Aku rangkumin spending kamu ya! ✨",
            "Halo teman! Weekly report ready! Let's check it out! 🎯",
            "Hai! Seminggu berlalu nih. Gimana keuangan kamu? Aku analisis ya! 💡"
        ]
        
        # Savings encouragement
        self.savings_encouragement = [
            "Keren! Minggu ini kamu hemat {amount}! Keep it up! 💪",
            "Mantap! Saving {amount} minggu ini! Proud of you! ✨",
            "Wih! Berhasil hemat {amount}! Lanjutkan! 🎯"
        ]
        
        # Overspending gentle reminders
        self.overspending_reminders = [
            "Minggu ini spending naik {amount}. Yuk, coba hemat minggu depan! Kamu pasti bisa! 💛",
            "Spending naik {amount} nih. Ga apa, next week kita balance lagi ya! 💪",
            "Pengeluaran naik {amount}. It's okay! Minggu depan kita adjust! Semangat! 🌟"
        ]

    def get_transaction_response(self, amount: int, category: str) -> str:
        """
        Get a supportive response for a transaction confirmation.
        
        Args:
            amount: Transaction amount in IDR
            category: Transaction category (Food, Transport, etc.)
        
        Returns:
            Friendly confirmation message with personality
            
        Example:
            >>> get_transaction_response(25000, "Food")
            "✅ Tercatat! Makan enak nih? Semoga kenyang! 🍽️"
        """
        responses = self.transaction_confirmations.get(
            category, 
            self.transaction_confirmations['default']
        )
        return random.choice(responses)
    
    def get_budget_warning(self, category: str, percentage: float) -> str:
        """
        Get a gentle budget warning based on usage percentage.
        
        Args:
            category: Budget category name
            percentage: Percentage of budget used (0-100+)
        
        Returns:
            Motivating warning message (never harsh!)
            
        Example:
            >>> get_budget_warning("Food", 85)
            "⚠️ Budget Food udah 85% nih! Yuk, coba hemat sedikit..."
        """
        # Determine severity level
        if percentage < 70:
            level = 'low'
        elif percentage < 90:
            level = 'medium'
        else:
            level = 'high'
        
        template = random.choice(self.budget_warnings[level])
        remaining = 100 - percentage
        
        return template.format(
            category=category,
            percentage=int(percentage),
            remaining=int(remaining)
        )
    
    def get_goal_progress_message(self, goal_name: str, percentage: float) -> str:
        """
        Get a celebratory message for goal progress.
        
        Args:
            goal_name: Name of the goal
            percentage: Progress percentage (0-100+)
        
        Returns:
            Encouraging progress message
            
        Example:
            >>> get_goal_progress_message("MacBook", 75)
            "🚀 MacBook: 75% - TINGGAL DIKIT LAGI! You got this! 🔥"
        """
        # Determine progress level
        if percentage >= 100:
            level = 'achieved'
        elif percentage >= 75:
            level = 'almost'
        elif percentage >= 50:
            level = 'great'
        elif percentage >= 25:
            level = 'good'
        else:
            level = 'started'
        
        template = random.choice(self.goal_progress[level])
        return template.format(goal_name=goal_name, percentage=int(percentage))
    
    def get_weekly_intro(self) -> str:
        """
        Get a warm intro for weekly reports.
        
        Returns:
            Friendly weekly report greeting
            
        Example:
            >>> get_weekly_intro()
            "Halo! Ini laporan minggu ini. Yuk kita lihat progress kamu! 📊"
        """
        return random.choice(self.weekly_intros)
    
    def get_savings_message(self, amount: int) -> str:
        """
        Get an encouraging message for savings achievement.
        
        Args:
            amount: Amount saved compared to previous period
        
        Returns:
            Celebratory savings message
            
        Example:
            >>> get_savings_message(50000)
            "Keren! Minggu ini kamu hemat Rp 50.000! Keep it up! 💪"
        """
        formatted_amount = f"Rp {amount:,}".replace(',', '.')
        template = random.choice(self.savings_encouragement)
        return template.format(amount=formatted_amount)
    
    def get_overspending_message(self, amount: int) -> str:
        """
        Get a gentle reminder for increased spending (never harsh!).
        
        Args:
            amount: Amount of increased spending
        
        Returns:
            Motivating (not discouraging) reminder
            
        Example:
            >>> get_overspending_message(30000)
            "Spending naik Rp 30.000 nih. Ga apa, next week kita balance..."
        """
        formatted_amount = f"Rp {amount:,}".replace(',', '.')
        template = random.choice(self.overspending_reminders)
        return template.format(amount=formatted_amount)


# Singleton instance
_personality = None

def get_personality() -> PersonalityResponses:
    """
    Get singleton personality engine instance.
    
    Returns:
        PersonalityResponses instance
    """
    global _personality
    if _personality is None:
        _personality = PersonalityResponses()
    return _personality
