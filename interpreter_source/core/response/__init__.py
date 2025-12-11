"""
Response handling module for LocalAgent.

Manages the conversation loop, code execution, and response generation.
"""

from .respond import respond
from .render import render_message

__all__ = ["respond", "render_message"]
