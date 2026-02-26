"""
Context Processor
Analyzes user context and generates intelligent, personalized responses.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ContextProcessor:
    """Processes user context for intelligent AI responses."""
    
    def __init__(self, chat_memory, personality_engine):
        """
        Initialize Context Processor.
        
        Args:
            chat_memory: ChatMemory instance
            personality_engine: PersonalityEngine instance
        """
        self.memory = chat_memory
        self.personality = personality_engine
    
    def analyze_context(self, user_id: int) -> Dict[str, Any]:
        """
        Analyze complete user context.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Comprehensive context dictionary
        """
        try:
            # Get all user data
            profile = self.memory.get_user_profile(user_id)
            history = self.memory.get_conversation_history(user_id, limit=5)
            context = self.memory.get_user_context(user_id)
            knowledge = self.memory.get_user_knowledge(user_id)
            
            # Analyze patterns
            sentiment = self._detect_sentiment(history)
            engagement_level = self._analyze_engagement(history)
            time_context = self._get_time_context()
            
            return {
                'profile': profile,
                'recent_conversations': history,
                'user_context': context,
                'knowledge_items': knowledge,
                'sentiment': sentiment,
                'engagement_level': engagement_level,
                'time_context': time_context,
                'analyzed_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze context: {e}")
            return {}
    
    def detect_sentiment(self, messages: List[str]) -> str:
        """
        Detect sentiment from messages.
        
        Args:
            messages: List of user messages
            
        Returns:
            Sentiment: positive, negative, neutral, frustrated
        """
        return self._detect_sentiment(messages)
    
    def _detect_sentiment(self, conversation_history: List[Dict]) -> str:
        """
        Detect user sentiment from conversation history.
        
        Args:
            conversation_history: Recent conversation data
            
        Returns:
            Sentiment string
        """
        if not conversation_history:
            return 'neutral'
        
        # Simple keyword-based sentiment analysis
        positive_keywords = [
            'senang', 'happy', 'bagus', 'mantap', 'keren', 'berhasil',
            'sukses', 'yes', 'yay', 'alhamdulillah', 'syukur', 'thanks',
            'terima kasih', '😊', '😄', '🎉', '👍', '💪'
        ]
        
        negative_keywords = [
            'susah', 'sulit', 'gagal', 'bingung', 'stress', 'boros',
            'habis', 'over', 'tidak bisa', 'ga bisa', 'males', 'capek',
            'frustasi', 'kesel', '😔', '😢', '😞', '😤'
        ]
        
        frustrated_keywords = [
            'kenapa', 'gimana sih', 'udah coba', 'tetep ga', 'masih error',
            'ga jalan', 'error terus', 'ribet'
        ]
        
        # Analyze recent messages
        recent_messages = []
        for conv in conversation_history[-3:]:  # Last 3 messages
            msg = conv.get('user_message', '').lower()
            recent_messages.append(msg)
        
        combined = ' '.join(recent_messages)
        
        # Check for frustrated
        frustrated_count = sum(1 for kw in frustrated_keywords if kw in combined)
        if frustrated_count >= 2:
            return 'frustrated'
        
        # Check positive vs negative
        positive_count = sum(1 for kw in positive_keywords if kw in combined)
        negative_count = sum(1 for kw in negative_keywords if kw in combined)
        
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        
        return 'neutral'
    
    def _analyze_engagement(self, conversation_history: List[Dict]) -> str:
        """
        Analyze user engagement level.
        
        Args:
            conversation_history: Recent conversation data
            
        Returns:
            Engagement level: high, medium, low
        """
        if not conversation_history:
            return 'low'
        
        # Check frequency of interactions
        if len(conversation_history) >= 5:
            # Check if within last 24 hours
            try:
                latest = datetime.fromisoformat(conversation_history[-1].get('timestamp', ''))
                oldest = datetime.fromisoformat(conversation_history[0].get('timestamp', ''))
                
                time_diff = latest - oldest
                if time_diff < timedelta(hours=24):
                    return 'high'
                elif time_diff < timedelta(days=3):
                    return 'medium'
            except:
                pass
        
        return 'low' if len(conversation_history) < 3 else 'medium'
    
    def _get_time_context(self) -> Dict[str, Any]:
        """
        Get current time context.
        
        Returns:
            Time context dictionary
        """
        now = datetime.now()
        hour = now.hour
        
        if 5 <= hour < 11:
            period = 'morning'
        elif 11 <= hour < 15:
            period = 'afternoon'
        elif 15 <= hour < 19:
            period = 'evening'
        else:
            period = 'night'
        
        return {
            'current_time': now.isoformat(),
            'hour': hour,
            'period': period,
            'day_of_week': now.strftime('%A'),
            'is_weekend': now.weekday() >= 5
        }
    
    def get_relevant_insights(
        self,
        user_id: int,
        query_type: Optional[str] = None
    ) -> List[str]:
        """
        Get relevant insights based on query type.
        
        Args:
            user_id: Telegram user ID
            query_type: Type of query (spending, saving, goal, etc)
            
        Returns:
            List of relevant insight strings
        """
        insights = []
        
        try:
            # Get user knowledge
            knowledge_items = self.memory.get_user_knowledge(user_id)
            
            if query_type:
                # Filter by type
                relevant = [k for k in knowledge_items 
                           if k.get('knowledge_type') == query_type]
            else:
                relevant = knowledge_items[:5]  # Recent 5
            
            for item in relevant:
                insights.append(item.get('knowledge_item', ''))
            
        except Exception as e:
            logger.error(f"Failed to get insights: {e}")
        
        return insights
    
    def generate_personalized_response(
        self,
        user_id: int,
        base_response: str,
        include_greeting: bool = False
    ) -> str:
        """
        Generate personalized response with context.
        
        Args:
            user_id: Telegram user ID
            base_response: Base response text
            include_greeting: Whether to include greeting
            
        Returns:
            Personalized response
        """
        try:
            # Analyze context
            full_context = self.analyze_context(user_id)
            
            # Get user name
            profile = full_context.get('profile', {})
            user_name = profile.get('name') if profile else None
            
            # Build response
            parts = []
            
            # Add greeting if requested
            if include_greeting:
                time_context = full_context.get('time_context', {})
                greeting = self.personality.generate_greeting(
                    user_name=user_name,
                    time_of_day=time_context.get('period')
                )
                parts.append(greeting)
            
            # Adjust for sentiment
            sentiment = full_context.get('sentiment', 'neutral')
            adjusted_response = self.personality.handle_sentiment(
                sentiment, 
                base_response
            )
            
            # Contextualize
            user_context_data = full_context.get('user_context', {})
            contextualized = self.personality.contextualize_message(
                adjusted_response,
                user_context_data
            )
            
            parts.append(contextualized)
            
            return '\n\n'.join(parts)
            
        except Exception as e:
            logger.error(f"Failed to personalize response: {e}")
            return base_response
    
    def should_remind_user(
        self,
        user_id: int,
        reminder_type: str
    ) -> tuple[bool, Optional[Dict]]:
        """
        Check if user should be reminded about something.
        
        Args:
            user_id: Telegram user ID
            reminder_type: Type of reminder to check
            
        Returns:
            Tuple of (should_remind, reminder_details)
        """
        try:
            context = self.memory.get_user_context(user_id)
            
            if not context:
                return False, None
            
            # Check different reminder types
            if reminder_type == 'budget_limit':
                # Check if approaching budget limit
                spending = context.get('total_spending_pattern', '')
                if 'high' in spending.lower():
                    return True, {'pattern': 'high'}
            
            elif reminder_type == 'goal_deadline':
                # Check for goals with approaching deadlines
                goals = context.get('active_goals', '[]')
                try:
                    goals_list = json.loads(goals) if isinstance(goals, str) else goals
                    if goals_list:
                        return True, {'goals': goals_list}
                except:
                    pass
            
            elif reminder_type == 'daily_check':
                # Check last interaction time
                history = self.memory.get_conversation_history(user_id, limit=1)
                if history:
                    try:
                        last_time = datetime.fromisoformat(history[-1].get('timestamp', ''))
                        if datetime.now() - last_time > timedelta(hours=24):
                            return True, {}
                    except:
                        pass
            
        except Exception as e:
            logger.error(f"Failed to check reminder: {e}")
        
        return False, None
    
    def extract_user_intent(self, message: str) -> Dict[str, Any]:
        """
        Extract user intent from message.
        
        Args:
            message: User message
            
        Returns:
            Intent dictionary with type and entities
        """
        message_lower = message.lower()
        
        # Define intent patterns
        intents = {
            'add_expense': ['beli', 'bayar', 'keluar', 'habis', 'spend'],
            'check_budget': ['budget', 'anggaran', 'sisa', 'cek', 'check'],
            'set_goal': ['goal', 'target', 'nabung', 'saving'],
            'analyze': ['analisis', 'analyze', 'laporan', 'report', 'summary'],
            'help': ['help', 'bantuan', 'gimana', 'cara', 'how'],
        }
        
        detected_intent = 'unknown'
        confidence = 0.0
        
        for intent, keywords in intents.items():
            matches = sum(1 for kw in keywords if kw in message_lower)
            score = matches / len(keywords)
            
            if score > confidence:
                confidence = score
                detected_intent = intent
        
        return {
            'intent': detected_intent,
            'confidence': confidence,
            'raw_message': message
        }
    
    def build_context_for_llm(
        self,
        user_id: int,
        current_message: str
    ) -> str:
        """
        Build context string for LLM prompt.
        
        Args:
            user_id: Telegram user ID
            current_message: Current user message
            
        Returns:
            Context string formatted for LLM
        """
        try:
            full_context = self.analyze_context(user_id)
            
            # Extract relevant info
            profile = full_context.get('profile', {})
            user_name = profile.get('name', 'User')
            
            recent_conv = full_context.get('recent_conversations', [])
            conv_summary = []
            for conv in recent_conv[-3:]:
                user_msg = conv.get('user_message', '')
                bot_msg = conv.get('bot_response', '')
                conv_summary.append(f"User: {user_msg}\nBot: {bot_msg}")
            
            context_data = full_context.get('user_context', {})
            top_categories = context_data.get('top_categories', '[]')
            active_goals = context_data.get('active_goals', '[]')
            
            # Build context string
            context_parts = [
                f"User Name: {user_name}",
                f"Current Sentiment: {full_context.get('sentiment', 'neutral')}",
                f"Time: {full_context.get('time_context', {}).get('period', 'day')}",
            ]
            
            if conv_summary:
                context_parts.append(f"\nRecent Conversation:\n" + "\n---\n".join(conv_summary))
            
            if top_categories != '[]':
                context_parts.append(f"Top Spending Categories: {top_categories}")
            
            if active_goals != '[]':
                context_parts.append(f"Active Goals: {active_goals}")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Failed to build LLM context: {e}")
            return f"Current message: {current_message}"
