"""
AI System Package
Provides natural AI capabilities with memory, personality, context awareness, and coaching.
"""

from .chat_memory import ChatMemory
from .personality_engine import PersonalityEngine
from .context_processor import ContextProcessor
from .prompts import PromptTemplates
from .coaching_engine import CoachingEngine, get_coaching_engine

__all__ = [
    'ChatMemory',
    'PersonalityEngine', 
    'ContextProcessor',
    'PromptTemplates',
    'CoachingEngine',
    'get_coaching_engine'
]
