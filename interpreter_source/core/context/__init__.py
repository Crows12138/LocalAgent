"""
Context management module for LocalAgent.

Provides intelligent context management:
- Auto-inject relevant code files into conversations
- Manage context window limits
- Track conversation context
"""

from .context_manager import ContextManager
from .context_builder import ContextBuilder

__all__ = ["ContextManager", "ContextBuilder"]
