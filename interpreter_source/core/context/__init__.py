"""
Context management module for LocalAgent.

Provides intelligent context management:
- Auto-inject relevant code files into conversations
- Manage context window limits
- Track conversation context
- Compact conversation history (Claude Code-style /compact)
"""

from .context_manager import ContextManager
from .context_builder import ContextBuilder
from .compact import ConversationCompactor

__all__ = ["ContextManager", "ContextBuilder", "ConversationCompactor"]
