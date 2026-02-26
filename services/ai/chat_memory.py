"""
Chat Memory Manager
Handles user memory, conversation history, and context storage in Google Sheets.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ChatMemory:
    """Manages AI memory system using Google Sheets as persistent storage."""
    
    def __init__(self, sheets_service):
        """
        Initialize Chat Memory Manager.
        
        Args:
            sheets_service: Instance of SheetsService for data persistence
        """
        self.sheets = sheets_service
        self.sheet_names = {
            'profiles': 'UserProfiles',
            'history': 'ChatHistory',
            'context': 'UserContext',
            'knowledge': 'KnowledgeBase'
        }
        
    def save_conversation(
        self, 
        user_id: int, 
        user_message: str, 
        bot_response: str,
        message_type: str = 'text',
        context_used: Optional[Dict] = None
    ) -> bool:
        """
        Save conversation to history.
        
        Args:
            user_id: Telegram user ID
            user_message: User's message
            bot_response: Bot's response
            message_type: Type of message (text, command, etc)
            context_used: Context data used for response
            
        Returns:
            True if saved successfully
        """
        try:
            timestamp = datetime.now().isoformat()
            context_str = json.dumps(context_used) if context_used else ""
            
            row_data = [
                timestamp,
                str(user_id),
                message_type,
                user_message,
                bot_response,
                context_str
            ]
            
            self.sheets.append_row(self.sheet_names['history'], row_data)
            logger.info(f"Saved conversation for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")
            return False
    
    def get_conversation_history(
        self, 
        user_id: int, 
        limit: int = 10,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get recent conversation history for a user.
        
        Args:
            user_id: Telegram user ID
            limit: Maximum number of messages to retrieve
            days: Only get messages from last N days
            
        Returns:
            List of conversation dictionaries
        """
        try:
            all_data = self.sheets.get_all_data(self.sheet_names['history'])
            if not all_data or len(all_data) < 2:
                return []
            
            headers = all_data[0]
            cutoff_date = datetime.now() - timedelta(days=days)
            
            conversations = []
            for row in reversed(all_data[1:]):  # Start from most recent
                if len(row) < len(headers):
                    continue
                    
                row_dict = dict(zip(headers, row))
                
                # Filter by user_id
                if str(row_dict.get('user_id', '')) != str(user_id):
                    continue
                
                # Filter by date
                try:
                    msg_date = datetime.fromisoformat(row_dict.get('timestamp', ''))
                    if msg_date < cutoff_date:
                        continue
                except:
                    continue
                
                conversations.append(row_dict)
                
                if len(conversations) >= limit:
                    break
            
            return list(reversed(conversations))  # Chronological order
            
        except Exception as e:
            logger.error(f"Failed to get conversation history: {e}")
            return []
    
    def get_user_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user profile data.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            User profile dictionary or None
        """
        try:
            all_data = self.sheets.get_all_data(self.sheet_names['profiles'])
            if not all_data or len(all_data) < 2:
                return None
            
            headers = all_data[0]
            for row in all_data[1:]:
                if len(row) < len(headers):
                    continue
                    
                row_dict = dict(zip(headers, row))
                if str(row_dict.get('user_id', '')) == str(user_id):
                    return row_dict
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user profile: {e}")
            return None
    
    def update_user_profile(
        self, 
        user_id: int,
        name: Optional[str] = None,
        timezone: Optional[str] = None,
        preferences: Optional[Dict] = None,
        communication_style: Optional[str] = None
    ) -> bool:
        """
        Update or create user profile.
        
        Args:
            user_id: Telegram user ID
            name: User's name
            timezone: User's timezone
            preferences: User preferences dict
            communication_style: Preferred communication style
            
        Returns:
            True if updated successfully
        """
        try:
            existing = self.get_user_profile(user_id)
            now = datetime.now().isoformat()
            
            if existing:
                # Update existing profile
                # TODO: Implement update logic
                logger.info(f"Profile exists for user {user_id}, update not implemented yet")
                return True
            else:
                # Create new profile
                preferences_str = json.dumps(preferences) if preferences else "{}"
                
                row_data = [
                    str(user_id),
                    name or "User",
                    timezone or "Asia/Jakarta",
                    now,  # join_date
                    now,  # last_active
                    preferences_str,
                    communication_style or "casual"
                ]
                
                self.sheets.append_row(self.sheet_names['profiles'], row_data)
                logger.info(f"Created profile for user {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update user profile: {e}")
            return False
    
    def get_user_context(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive user context (spending patterns, goals, etc).
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            User context dictionary or None
        """
        try:
            all_data = self.sheets.get_all_data(self.sheet_names['context'])
            if not all_data or len(all_data) < 2:
                return None
            
            headers = all_data[0]
            for row in all_data[1:]:
                if len(row) < len(headers):
                    continue
                    
                row_dict = dict(zip(headers, row))
                if str(row_dict.get('user_id', '')) == str(user_id):
                    return row_dict
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user context: {e}")
            return None
    
    def update_user_context(
        self,
        user_id: int,
        spending_pattern: Optional[str] = None,
        top_categories: Optional[List[str]] = None,
        active_goals: Optional[List[str]] = None,
        achievements: Optional[List[str]] = None,
        sentiment_trend: Optional[str] = None
    ) -> bool:
        """
        Update user context with latest insights.
        
        Args:
            user_id: Telegram user ID
            spending_pattern: Summary of spending patterns
            top_categories: List of top spending categories
            active_goals: List of active goal names
            achievements: List of achievements
            sentiment_trend: Recent sentiment trend
            
        Returns:
            True if updated successfully
        """
        try:
            existing = self.get_user_context(user_id)
            now = datetime.now().isoformat()
            
            # Prepare data
            top_cat_str = json.dumps(top_categories) if top_categories else "[]"
            goals_str = json.dumps(active_goals) if active_goals else "[]"
            achieve_str = json.dumps(achievements) if achievements else "[]"
            
            if existing:
                # TODO: Implement update logic
                logger.info(f"Context exists for user {user_id}, update not implemented yet")
                return True
            else:
                # Create new context
                row_data = [
                    str(user_id),
                    spending_pattern or "",
                    top_cat_str,
                    goals_str,
                    achieve_str,
                    sentiment_trend or "neutral",
                    now  # last_updated
                ]
                
                self.sheets.append_row(self.sheet_names['context'], row_data)
                logger.info(f"Created context for user {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update user context: {e}")
            return False
    
    def learn_about_user(
        self,
        user_id: int,
        knowledge_type: str,
        knowledge_item: str,
        confidence: float = 0.8
    ) -> bool:
        """
        Store learned insights about user.
        
        Args:
            user_id: Telegram user ID
            knowledge_type: Type of knowledge (preference, habit, goal, etc)
            knowledge_item: The actual knowledge content
            confidence: Confidence level (0.0 to 1.0)
            
        Returns:
            True if saved successfully
        """
        try:
            now = datetime.now().isoformat()
            
            row_data = [
                str(user_id),
                knowledge_type,
                knowledge_item,
                str(confidence),
                now,  # learned_date
                now   # last_referenced
            ]
            
            self.sheets.append_row(self.sheet_names['knowledge'], row_data)
            logger.info(f"Learned about user {user_id}: {knowledge_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to learn about user: {e}")
            return False
    
    def get_user_knowledge(
        self, 
        user_id: int,
        knowledge_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get learned knowledge about user.
        
        Args:
            user_id: Telegram user ID
            knowledge_type: Optional filter by knowledge type
            
        Returns:
            List of knowledge items
        """
        try:
            all_data = self.sheets.get_all_data(self.sheet_names['knowledge'])
            if not all_data or len(all_data) < 2:
                return []
            
            headers = all_data[0]
            knowledge_items = []
            
            for row in all_data[1:]:
                if len(row) < len(headers):
                    continue
                    
                row_dict = dict(zip(headers, row))
                
                # Filter by user_id
                if str(row_dict.get('user_id', '')) != str(user_id):
                    continue
                
                # Filter by type if specified
                if knowledge_type and row_dict.get('knowledge_type') != knowledge_type:
                    continue
                
                knowledge_items.append(row_dict)
            
            return knowledge_items
            
        except Exception as e:
            logger.error(f"Failed to get user knowledge: {e}")
            return []
    
    def initialize_sheets(self) -> bool:
        """
        Initialize all required sheets with headers if they don't exist.
        
        Returns:
            True if initialized successfully
        """
        try:
            # UserProfiles sheet
            profile_headers = [
                'user_id', 'name', 'timezone', 'join_date', 
                'last_active', 'preferences', 'communication_style'
            ]
            
            # ChatHistory sheet
            history_headers = [
                'timestamp', 'user_id', 'message_type', 
                'user_message', 'bot_response', 'context_used'
            ]
            
            # UserContext sheet
            context_headers = [
                'user_id', 'total_spending_pattern', 'top_categories',
                'active_goals', 'achievements', 'sentiment_trend', 'last_updated'
            ]
            
            # KnowledgeBase sheet
            knowledge_headers = [
                'user_id', 'knowledge_type', 'knowledge_item',
                'confidence', 'learned_date', 'last_referenced'
            ]
            
            # TODO: Implement sheet initialization
            # This would require adding create_sheet() method to sheets_service
            logger.info("Sheet initialization not fully implemented yet")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize sheets: {e}")
            return False
