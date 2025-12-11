"""
Git integration module for LocalAgent.

Provides Git operations that can be used by the interpreter:
- Status, diff, log viewing
- Commit, branch management
- Simplified interface for LLM interaction
"""

from .git_manager import GitManager

__all__ = ["GitManager"]
