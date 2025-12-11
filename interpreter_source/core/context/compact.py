"""
Conversation compaction module for LocalAgent.

Implements Claude Code-style /compact functionality to compress
conversation history using LLM summarization.
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class CompactConfig:
    """Configuration for conversation compaction."""
    # Auto-compact when context usage exceeds this percentage
    auto_compact_threshold: float = 0.8
    # Maximum tokens for the summary
    summary_max_tokens: int = 2000
    # Keep recent N messages uncompressed
    keep_recent_messages: int = 4
    # Enable auto-compact
    auto_compact_enabled: bool = True


class ConversationCompactor:
    """
    Compacts conversation history by summarizing older messages.

    Features:
    - Manual /compact command support
    - Auto-compact when context approaches limit
    - Preserves key information (code changes, decisions, errors)
    - Keeps recent messages intact

    Usage:
        compactor = ConversationCompactor(interpreter)

        # Manual compact
        compactor.compact()

        # Check if auto-compact needed
        if compactor.should_auto_compact():
            compactor.compact()
    """

    def __init__(self, interpreter: Any):
        """
        Initialize conversation compactor.

        Args:
            interpreter: OpenInterpreter instance
        """
        self.interpreter = interpreter
        self.config = CompactConfig()
        self._last_summary: Optional[str] = None
        self._compacted_count: int = 0

    def configure(
        self,
        auto_compact_threshold: float = None,
        summary_max_tokens: int = None,
        keep_recent_messages: int = None,
        auto_compact_enabled: bool = None,
    ) -> "ConversationCompactor":
        """
        Configure compactor settings.

        Args:
            auto_compact_threshold: Trigger auto-compact at this usage %
            summary_max_tokens: Max tokens for summary
            keep_recent_messages: Keep N recent messages uncompressed
            auto_compact_enabled: Enable/disable auto-compact

        Returns:
            self for chaining
        """
        if auto_compact_threshold is not None:
            self.config.auto_compact_threshold = auto_compact_threshold
        if summary_max_tokens is not None:
            self.config.summary_max_tokens = summary_max_tokens
        if keep_recent_messages is not None:
            self.config.keep_recent_messages = keep_recent_messages
        if auto_compact_enabled is not None:
            self.config.auto_compact_enabled = auto_compact_enabled
        return self

    def estimate_tokens(self, messages: List[Dict]) -> int:
        """
        Estimate token count for messages.

        Args:
            messages: List of message dicts

        Returns:
            Estimated token count
        """
        try:
            from ..terminal_interface.utils.count_tokens import count_tokens

            total = 0
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, str):
                    total += count_tokens(content)
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            total += count_tokens(item["text"])
            return total
        except:
            # Fallback: estimate ~4 chars per token
            total_chars = sum(
                len(str(msg.get("content", "")))
                for msg in messages
            )
            return total_chars // 4

    def get_context_usage(self) -> Tuple[int, int, float]:
        """
        Get current context window usage.

        Returns:
            Tuple of (used_tokens, max_tokens, usage_percentage)
        """
        messages = self.interpreter.messages
        used = self.estimate_tokens(messages)

        # Get max context from model config or default
        max_tokens = getattr(self.interpreter.llm, 'context_window', None)
        if max_tokens is None or max_tokens <= 0:
            max_tokens = 8192

        percentage = used / max_tokens if max_tokens > 0 else 0

        return used, max_tokens, percentage

    def should_auto_compact(self) -> bool:
        """
        Check if auto-compact should be triggered.

        Returns:
            True if should compact
        """
        if not self.config.auto_compact_enabled:
            return False

        _, _, usage = self.get_context_usage()
        return usage >= self.config.auto_compact_threshold

    def _extract_key_info(self, messages: List[Dict]) -> Dict[str, List[str]]:
        """
        Extract key information from messages for summarization.

        Args:
            messages: Messages to analyze

        Returns:
            Dict with categorized key info
        """
        key_info = {
            "code_executed": [],
            "files_modified": [],
            "errors": [],
            "decisions": [],
            "user_requests": [],
        }

        for msg in messages:
            role = msg.get("role", "")
            msg_type = msg.get("type", "")
            content = str(msg.get("content", ""))

            # Track code execution
            if msg_type == "code":
                lang = msg.get("format", "unknown")
                code_preview = content[:200] + "..." if len(content) > 200 else content
                key_info["code_executed"].append(f"[{lang}] {code_preview}")

            # Track errors
            if "error" in content.lower() or "exception" in content.lower():
                if len(content) < 500:
                    key_info["errors"].append(content[:200])

            # Track user requests
            if role == "user" and msg_type == "message":
                key_info["user_requests"].append(content[:300])

            # Track file modifications (look for common patterns)
            if "created" in content.lower() or "modified" in content.lower():
                # Extract potential file paths
                import re
                files = re.findall(r'["\']?([a-zA-Z0-9_\-./\\]+\.(py|js|ts|json|yaml|md))["\']?', content)
                for f in files:
                    if isinstance(f, tuple):
                        key_info["files_modified"].append(f[0])
                    else:
                        key_info["files_modified"].append(f)

        # Deduplicate
        key_info["files_modified"] = list(set(key_info["files_modified"]))

        return key_info

    def _create_summary_prompt(self, messages: List[Dict], key_info: Dict) -> str:
        """
        Create a prompt for the LLM to summarize conversation.

        Args:
            messages: Messages to summarize
            key_info: Extracted key information

        Returns:
            Summary prompt string
        """
        # Build conversation text
        conversation_parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            msg_type = msg.get("type", "message")
            content = str(msg.get("content", ""))

            if msg_type == "code":
                lang = msg.get("format", "")
                conversation_parts.append(f"[{role}] Code ({lang}):\n{content[:500]}")
            else:
                conversation_parts.append(f"[{role}] {content[:500]}")

        conversation_text = "\n\n".join(conversation_parts[-20:])  # Last 20 messages max

        # Build key info section
        key_info_text = ""
        if key_info["user_requests"]:
            key_info_text += "User Requests:\n" + "\n".join(f"- {r[:100]}" for r in key_info["user_requests"][-5:]) + "\n\n"
        if key_info["code_executed"]:
            key_info_text += f"Code Executed: {len(key_info['code_executed'])} blocks\n\n"
        if key_info["files_modified"]:
            key_info_text += "Files Modified:\n" + "\n".join(f"- {f}" for f in key_info["files_modified"][:10]) + "\n\n"
        if key_info["errors"]:
            key_info_text += "Errors Encountered:\n" + "\n".join(f"- {e[:100]}" for e in key_info["errors"][-3:]) + "\n\n"

        prompt = f"""Summarize this conversation history concisely. Focus on:
1. What the user wanted to accomplish
2. What actions were taken (code executed, files modified)
3. Current state and any pending tasks
4. Important decisions or errors

Keep the summary under 500 words. Be specific about file names and code changes.

Key Information:
{key_info_text}

Conversation:
{conversation_text}

Summary:"""

        return prompt

    def compact(self, verbose: bool = True) -> Dict[str, Any]:
        """
        Compact the conversation history.

        Args:
            verbose: Print status messages

        Returns:
            Dict with compact results
        """
        messages = self.interpreter.messages

        if len(messages) <= self.config.keep_recent_messages:
            return {
                "success": False,
                "reason": "Not enough messages to compact",
                "messages_before": len(messages),
                "messages_after": len(messages),
            }

        # Split messages: older ones to summarize, recent ones to keep
        keep_count = self.config.keep_recent_messages
        messages_to_summarize = messages[:-keep_count]
        messages_to_keep = messages[-keep_count:]

        if verbose:
            print(f"Compacting {len(messages_to_summarize)} messages...")

        # Extract key information
        key_info = self._extract_key_info(messages_to_summarize)

        # Create summary prompt
        summary_prompt = self._create_summary_prompt(messages_to_summarize, key_info)

        # Generate summary using the interpreter's LLM
        try:
            # Use a simple completion to generate summary
            summary_messages = [
                {"role": "user", "type": "message", "content": summary_prompt}
            ]

            summary = ""
            for chunk in self.interpreter.llm.run(summary_messages):
                if chunk.get("type") == "message":
                    summary += chunk.get("content", "")

            if not summary:
                summary = self._create_fallback_summary(messages_to_summarize, key_info)

        except Exception as e:
            if verbose:
                print(f"LLM summarization failed: {e}, using fallback")
            summary = self._create_fallback_summary(messages_to_summarize, key_info)

        # Create the compacted message
        compacted_message = {
            "role": "system",
            "type": "message",
            "content": f"""[Conversation History Summary]

{summary}

---
(Previous {len(messages_to_summarize)} messages have been compacted into this summary)
""",
        }

        # Update interpreter messages
        self.interpreter.messages = [compacted_message] + messages_to_keep

        # Track stats
        self._last_summary = summary
        self._compacted_count += len(messages_to_summarize)

        # Calculate token savings
        tokens_before = self.estimate_tokens(messages)
        tokens_after = self.estimate_tokens(self.interpreter.messages)
        tokens_saved = tokens_before - tokens_after

        result = {
            "success": True,
            "messages_before": len(messages),
            "messages_after": len(self.interpreter.messages),
            "messages_compacted": len(messages_to_summarize),
            "tokens_before": tokens_before,
            "tokens_after": tokens_after,
            "tokens_saved": tokens_saved,
            "summary_preview": summary[:200] + "..." if len(summary) > 200 else summary,
        }

        if verbose:
            print(f"Compacted {result['messages_compacted']} messages")
            print(f"Tokens: {tokens_before} -> {tokens_after} (saved {tokens_saved})")

        return result

    def _create_fallback_summary(self, messages: List[Dict], key_info: Dict) -> str:
        """
        Create a simple summary without LLM when summarization fails.

        Args:
            messages: Messages that were compacted
            key_info: Extracted key information

        Returns:
            Fallback summary string
        """
        parts = []

        if key_info["user_requests"]:
            parts.append("User Requests:")
            for req in key_info["user_requests"][-5:]:
                parts.append(f"  - {req[:150]}")

        if key_info["files_modified"]:
            parts.append(f"\nFiles Modified: {', '.join(key_info['files_modified'][:10])}")

        if key_info["code_executed"]:
            parts.append(f"\nCode Blocks Executed: {len(key_info['code_executed'])}")

        if key_info["errors"]:
            parts.append("\nErrors:")
            for err in key_info["errors"][-3:]:
                parts.append(f"  - {err[:100]}")

        parts.append(f"\n\nTotal messages compacted: {len(messages)}")

        return "\n".join(parts)

    def get_stats(self) -> Dict[str, Any]:
        """Get compactor statistics."""
        used, max_tokens, usage = self.get_context_usage()
        return {
            "context_used": used,
            "context_max": max_tokens,
            "context_usage_percent": round(usage * 100, 1),
            "total_compacted_messages": self._compacted_count,
            "auto_compact_enabled": self.config.auto_compact_enabled,
            "auto_compact_threshold": self.config.auto_compact_threshold,
            "last_summary_preview": self._last_summary[:100] if self._last_summary else None,
        }
