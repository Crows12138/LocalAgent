"""
Context manager for automatic context injection into conversations.
"""

import re
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field

from .context_builder import ContextBuilder


@dataclass
class ContextConfig:
    """Configuration for context management."""
    enabled: bool = True
    max_tokens: int = 8000
    auto_inject_files: bool = True  # Auto-add mentioned files
    auto_inject_codebase: bool = True  # Auto-add relevant code
    auto_inject_git: bool = False  # Auto-add git status
    file_mention_pattern: str = r'["\']?([a-zA-Z0-9_\-./\\]+\.(py|js|ts|tsx|jsx|java|go|rs|c|cpp|h|hpp|rb|php|swift|kt|scala|sh|yaml|yml|json|toml|md|txt))["\']?'


class ContextManager:
    """
    Manages context injection for conversations.

    Features:
    - Auto-detect file mentions in messages
    - Auto-inject relevant codebase context
    - Manage context window limits
    - Track what context has been added

    Usage:
        manager = ContextManager(interpreter)
        manager.enable()

        # Context is auto-injected when user sends messages
        # Or manually:
        context = manager.prepare_context("fix the login bug in auth.py")
    """

    def __init__(self, interpreter: Any):
        """
        Initialize context manager.

        Args:
            interpreter: OpenInterpreter instance
        """
        self.interpreter = interpreter
        self.config = ContextConfig()
        self._injected_files: Set[str] = set()
        self._last_query: Optional[str] = None

    def configure(
        self,
        enabled: bool = None,
        max_tokens: int = None,
        auto_inject_files: bool = None,
        auto_inject_codebase: bool = None,
        auto_inject_git: bool = None,
    ) -> "ContextManager":
        """
        Configure context manager.

        Args:
            enabled: Enable/disable context injection
            max_tokens: Maximum context tokens
            auto_inject_files: Auto-add mentioned files
            auto_inject_codebase: Auto-add relevant code
            auto_inject_git: Auto-add git status

        Returns:
            self for chaining
        """
        if enabled is not None:
            self.config.enabled = enabled
        if max_tokens is not None:
            self.config.max_tokens = max_tokens
        if auto_inject_files is not None:
            self.config.auto_inject_files = auto_inject_files
        if auto_inject_codebase is not None:
            self.config.auto_inject_codebase = auto_inject_codebase
        if auto_inject_git is not None:
            self.config.auto_inject_git = auto_inject_git
        return self

    def enable(self) -> "ContextManager":
        """Enable context injection."""
        self.config.enabled = True
        return self

    def disable(self) -> "ContextManager":
        """Disable context injection."""
        self.config.enabled = False
        return self

    def extract_file_mentions(self, message: str) -> List[str]:
        """
        Extract file paths mentioned in a message.

        Args:
            message: User message

        Returns:
            List of file paths
        """
        pattern = self.config.file_mention_pattern
        matches = re.findall(pattern, message, re.IGNORECASE)

        files = []
        for match in matches:
            if isinstance(match, tuple):
                path = match[0]
            else:
                path = match

            # Clean up the path
            path = path.strip("'\"")

            # Skip very short paths or common words
            if len(path) > 3 and not path.startswith("http"):
                files.append(path)

        return list(set(files))

    def extract_keywords(self, message: str) -> List[str]:
        """
        Extract keywords for codebase search.

        Args:
            message: User message

        Returns:
            List of keywords
        """
        # Remove common words
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below",
            "between", "under", "again", "further", "then", "once",
            "here", "there", "when", "where", "why", "how", "all",
            "each", "few", "more", "most", "other", "some", "such",
            "no", "nor", "not", "only", "own", "same", "so", "than",
            "too", "very", "just", "and", "but", "if", "or", "because",
            "until", "while", "this", "that", "these", "those", "what",
            "which", "who", "whom", "it", "its", "i", "me", "my", "we",
            "our", "you", "your", "he", "him", "his", "she", "her",
            "they", "them", "their", "fix", "bug", "error", "issue",
            "problem", "add", "create", "make", "change", "update",
            "modify", "delete", "remove", "help", "please", "want",
            "need", "like", "code", "file", "function", "class",
        }

        # Extract words
        words = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b", message.lower())

        # Filter
        keywords = [w for w in words if w not in stopwords]

        return keywords[:10]  # Limit to top 10

    def prepare_context(self, message: str) -> str:
        """
        Prepare context for a message.

        Args:
            message: User message

        Returns:
            Context string to prepend to conversation
        """
        if not self.config.enabled:
            return ""

        builder = ContextBuilder(max_tokens=self.config.max_tokens)

        # Auto-inject mentioned files
        if self.config.auto_inject_files:
            files = self.extract_file_mentions(message)
            for f in files:
                if f not in self._injected_files:
                    builder.add_file(f, priority=8)
                    self._injected_files.add(f)

        # Auto-inject relevant codebase context
        if self.config.auto_inject_codebase and self.interpreter._codebase_indexer:
            keywords = self.extract_keywords(message)
            if keywords:
                query = " ".join(keywords)
                if query != self._last_query:
                    builder.add_codebase_context(
                        self.interpreter._codebase_indexer,
                        query,
                        max_files=3,
                        priority=6,
                    )
                    self._last_query = query

        # Auto-inject git context
        if self.config.auto_inject_git and self.interpreter._git_manager:
            builder.add_git_context(
                self.interpreter._git_manager,
                include_diff=True,
                priority=5,
            )

        context = builder.build()

        if context:
            return f"## Context\n\n{context}\n\n---\n\n"

        return ""

    def inject_context(self, message: str) -> str:
        """
        Inject context into a message.

        Args:
            message: Original user message

        Returns:
            Message with context prepended
        """
        context = self.prepare_context(message)
        if context:
            return f"{context}## User Request\n\n{message}"
        return message

    def reset(self) -> "ContextManager":
        """Reset context tracking."""
        self._injected_files.clear()
        self._last_query = None
        return self

    def get_stats(self) -> Dict[str, Any]:
        """Get context manager statistics."""
        return {
            "enabled": self.config.enabled,
            "max_tokens": self.config.max_tokens,
            "injected_files": list(self._injected_files),
            "last_query": self._last_query,
            "auto_inject_files": self.config.auto_inject_files,
            "auto_inject_codebase": self.config.auto_inject_codebase,
            "auto_inject_git": self.config.auto_inject_git,
        }
