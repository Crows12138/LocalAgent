"""
Context builder for constructing LLM context from various sources.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class ContextItem:
    """A single item of context."""
    type: str  # "file", "git", "codebase", "custom"
    source: str  # Path or identifier
    content: str
    priority: int = 0  # Higher = more important
    tokens_estimate: int = 0

    def __post_init__(self):
        # Rough token estimate (4 chars per token)
        if not self.tokens_estimate:
            self.tokens_estimate = len(self.content) // 4


class ContextBuilder:
    """
    Builds context strings for LLM from various sources.

    Usage:
        builder = ContextBuilder(max_tokens=8000)
        builder.add_file("src/main.py")
        builder.add_codebase_context(indexer, "login function")
        builder.add_git_context(git_manager)
        context = builder.build()
    """

    def __init__(self, max_tokens: int = 8000):
        """
        Initialize context builder.

        Args:
            max_tokens: Maximum tokens for context
        """
        self.max_tokens = max_tokens
        self.items: List[ContextItem] = []

    def add_file(
        self,
        path: str,
        priority: int = 5,
        max_lines: int = 500,
    ) -> "ContextBuilder":
        """
        Add a file to context.

        Args:
            path: Path to file
            priority: Priority (higher = more important)
            max_lines: Maximum lines to include

        Returns:
            self for chaining
        """
        try:
            file_path = Path(path)
            if not file_path.exists():
                return self

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            if len(lines) > max_lines:
                # Take first and last portions
                half = max_lines // 2
                content = "".join(lines[:half])
                content += f"\n... ({len(lines) - max_lines} lines omitted) ...\n"
                content += "".join(lines[-half:])
            else:
                content = "".join(lines)

            # Determine language for syntax highlighting
            ext = file_path.suffix[1:] if file_path.suffix else "txt"

            formatted = f"### File: {path}\n```{ext}\n{content}\n```"

            self.items.append(ContextItem(
                type="file",
                source=path,
                content=formatted,
                priority=priority,
            ))

        except Exception:
            pass

        return self

    def add_files(
        self,
        paths: List[str],
        priority: int = 5,
    ) -> "ContextBuilder":
        """Add multiple files to context."""
        for path in paths:
            self.add_file(path, priority=priority)
        return self

    def add_codebase_context(
        self,
        indexer: Any,  # CodebaseIndexer
        query: str,
        max_files: int = 3,
        priority: int = 7,
    ) -> "ContextBuilder":
        """
        Add relevant codebase context.

        Args:
            indexer: CodebaseIndexer instance
            query: Query to find relevant files
            max_files: Maximum files to include
            priority: Priority

        Returns:
            self for chaining
        """
        if not indexer:
            return self

        try:
            context = indexer.get_context_for_query(query, max_files=max_files)
            self.items.append(ContextItem(
                type="codebase",
                source=f"query:{query}",
                content=context,
                priority=priority,
            ))
        except Exception:
            pass

        return self

    def add_git_context(
        self,
        git_manager: Any,  # GitManager
        include_diff: bool = True,
        priority: int = 6,
    ) -> "ContextBuilder":
        """
        Add Git context.

        Args:
            git_manager: GitManager instance
            include_diff: Include current diff
            priority: Priority

        Returns:
            self for chaining
        """
        if not git_manager:
            return self

        try:
            summary = git_manager.get_summary()

            if include_diff:
                diff = git_manager.diff()
                if diff:
                    summary += f"\n\n### Current Changes:\n```diff\n{diff[:2000]}\n```"

            self.items.append(ContextItem(
                type="git",
                source="git_status",
                content=summary,
                priority=priority,
            ))
        except Exception:
            pass

        return self

    def add_custom(
        self,
        content: str,
        source: str = "custom",
        priority: int = 5,
    ) -> "ContextBuilder":
        """
        Add custom context.

        Args:
            content: Context content
            source: Source identifier
            priority: Priority

        Returns:
            self for chaining
        """
        self.items.append(ContextItem(
            type="custom",
            source=source,
            content=content,
            priority=priority,
        ))
        return self

    def add_project_overview(
        self,
        indexer: Any,
        priority: int = 4,
    ) -> "ContextBuilder":
        """Add project overview from codebase indexer."""
        if not indexer:
            return self

        try:
            overview = indexer.get_project_overview()
            self.items.append(ContextItem(
                type="codebase",
                source="project_overview",
                content=overview,
                priority=priority,
            ))
        except Exception:
            pass

        return self

    def build(self) -> str:
        """
        Build the final context string.

        Returns:
            Context string within token limits
        """
        if not self.items:
            return ""

        # Sort by priority (highest first)
        sorted_items = sorted(self.items, key=lambda x: -x.priority)

        # Build context within token limit
        parts = []
        total_tokens = 0

        for item in sorted_items:
            if total_tokens + item.tokens_estimate > self.max_tokens:
                # Try to fit partial content
                remaining = self.max_tokens - total_tokens
                if remaining > 500:  # Worth adding partial
                    char_limit = remaining * 4
                    truncated = item.content[:char_limit] + "\n... (truncated)"
                    parts.append(truncated)
                break

            parts.append(item.content)
            total_tokens += item.tokens_estimate

        return "\n\n---\n\n".join(parts)

    def clear(self) -> "ContextBuilder":
        """Clear all context items."""
        self.items.clear()
        return self

    def get_stats(self) -> Dict[str, Any]:
        """Get context statistics."""
        return {
            "item_count": len(self.items),
            "total_tokens": sum(i.tokens_estimate for i in self.items),
            "max_tokens": self.max_tokens,
            "by_type": {
                t: len([i for i in self.items if i.type == t])
                for t in set(i.type for i in self.items)
            },
        }
