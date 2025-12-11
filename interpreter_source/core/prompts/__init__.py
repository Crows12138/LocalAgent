"""
Prompts module for LocalAgent.

Manages system messages, templates, and prompt engineering.
"""

from .system_message import default_system_message, get_system_message

__all__ = ["default_system_message", "get_system_message"]
