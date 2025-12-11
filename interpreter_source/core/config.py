"""
Configuration dataclasses for OpenInterpreter.
Organizes the many configuration options into logical groups.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .constants import DEFAULT_MAX_OUTPUT_CHARS
from .prompts import default_system_message


@dataclass
class LoopConfig:
    """Configuration for the conversation loop behavior."""

    enabled: bool = False
    message: str = (
        "Proceed. You CAN run code on my machine. If the entire task I asked for is done, "
        "say exactly 'The task is done.' If you need some specific information (like username "
        "or password) say EXACTLY 'Please provide more information.' If it's impossible, say "
        "'The task is impossible.' (If I haven't provided a task, say exactly 'Let me know "
        "what you'd like to do next.') Otherwise keep going."
    )
    breakers: List[str] = field(default_factory=lambda: [
        "The task is done.",
        "The task is impossible.",
        "Let me know what you'd like to do next.",
        "Please provide more information.",
    ])


@dataclass
class ConversationConfig:
    """Configuration for conversation history management."""

    history_enabled: bool = True
    filename: Optional[str] = None
    history_path: Optional[str] = None  # Will be set from get_storage_path if None
    contribute: bool = False


@dataclass
class DisplayConfig:
    """Configuration for display and output settings."""

    max_output: int = DEFAULT_MAX_OUTPUT_CHARS
    shrink_images: bool = True
    plain_text: bool = False
    highlight_active_line: bool = True
    multi_line: bool = True
    speak_messages: bool = False


@dataclass
class SafetyConfig:
    """Configuration for safety and execution settings."""

    safe_mode: str = "off"  # "off", "ask", "auto"
    auto_run: bool = False


@dataclass
class LLMConfig:
    """Configuration for the language model."""

    system_message: str = default_system_message
    custom_instructions: str = ""
    user_message_template: str = "{content}"
    always_apply_user_message_template: bool = False
    code_output_template: str = (
        "Code output: {content}\n\n"
        "What does this output mean / what's next (if anything, or are we done)?"
    )
    empty_code_output_template: str = (
        "The code above was executed on my machine. It produced no text output. "
        "what's next (if anything, or are we done?)"
    )
    code_output_sender: str = "user"  # "user" or "assistant"


@dataclass
class ComputerConfig:
    """Configuration for the computer/execution environment."""

    sync_computer: bool = False
    import_computer_api: bool = False
    skills_path: Optional[str] = None
    import_skills: bool = False


@dataclass
class InterpreterConfig:
    """
    Complete configuration for OpenInterpreter.
    Groups related settings into logical categories.
    """

    # Behavior settings
    offline: bool = False
    verbose: bool = False
    debug: bool = False
    os_mode: bool = False
    disable_telemetry: bool = False
    in_terminal_interface: bool = False

    # Grouped configurations
    loop: LoopConfig = field(default_factory=LoopConfig)
    conversation: ConversationConfig = field(default_factory=ConversationConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    computer: ComputerConfig = field(default_factory=ComputerConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> InterpreterConfig:
        """
        Create an InterpreterConfig from a dictionary.
        Supports both flat and nested dictionary formats.

        Args:
            data: Configuration dictionary

        Returns:
            InterpreterConfig instance
        """
        config = cls()

        # Handle top-level settings
        if "offline" in data:
            config.offline = data["offline"]
        if "verbose" in data:
            config.verbose = data["verbose"]
        if "debug" in data:
            config.debug = data["debug"]
        if "os" in data:
            config.os_mode = data["os"]
        if "disable_telemetry" in data:
            config.disable_telemetry = data["disable_telemetry"]
        if "in_terminal_interface" in data:
            config.in_terminal_interface = data["in_terminal_interface"]

        # Handle loop settings (flat format)
        if "loop" in data:
            if isinstance(data["loop"], bool):
                config.loop.enabled = data["loop"]
            elif isinstance(data["loop"], dict):
                config.loop = LoopConfig(**data["loop"])
        if "loop_message" in data:
            config.loop.message = data["loop_message"]
        if "loop_breakers" in data:
            config.loop.breakers = data["loop_breakers"]

        # Handle conversation settings (flat format)
        if "conversation_history" in data:
            config.conversation.history_enabled = data["conversation_history"]
        if "conversation_filename" in data:
            config.conversation.filename = data["conversation_filename"]
        if "conversation_history_path" in data:
            config.conversation.history_path = data["conversation_history_path"]
        if "contribute_conversation" in data:
            config.conversation.contribute = data["contribute_conversation"]

        # Handle display settings (flat format)
        if "max_output" in data:
            config.display.max_output = data["max_output"]
        if "shrink_images" in data:
            config.display.shrink_images = data["shrink_images"]
        if "plain_text_display" in data:
            config.display.plain_text = data["plain_text_display"]
        if "multi_line" in data:
            config.display.multi_line = data["multi_line"]
        if "speak_messages" in data:
            config.display.speak_messages = data["speak_messages"]

        # Handle safety settings (flat format)
        if "safe_mode" in data:
            config.safety.safe_mode = data["safe_mode"]
        if "auto_run" in data:
            config.safety.auto_run = data["auto_run"]

        # Handle LLM settings (flat format)
        if "system_message" in data:
            config.llm.system_message = data["system_message"]
        if "custom_instructions" in data:
            config.llm.custom_instructions = data["custom_instructions"]
        if "user_message_template" in data:
            config.llm.user_message_template = data["user_message_template"]
        if "always_apply_user_message_template" in data:
            config.llm.always_apply_user_message_template = data["always_apply_user_message_template"]
        if "code_output_template" in data:
            config.llm.code_output_template = data["code_output_template"]
        if "empty_code_output_template" in data:
            config.llm.empty_code_output_template = data["empty_code_output_template"]
        if "code_output_sender" in data:
            config.llm.code_output_sender = data["code_output_sender"]

        # Handle computer settings (flat format)
        if "sync_computer" in data:
            config.computer.sync_computer = data["sync_computer"]
        if "import_computer_api" in data:
            config.computer.import_computer_api = data["import_computer_api"]
        if "skills_path" in data:
            config.computer.skills_path = data["skills_path"]
        if "import_skills" in data:
            config.computer.import_skills = data["import_skills"]

        return config

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the configuration to a flat dictionary.
        Compatible with the original OpenInterpreter parameter format.

        Returns:
            Flat configuration dictionary
        """
        return {
            # Top-level
            "offline": self.offline,
            "verbose": self.verbose,
            "debug": self.debug,
            "os": self.os_mode,
            "disable_telemetry": self.disable_telemetry,
            "in_terminal_interface": self.in_terminal_interface,
            # Loop
            "loop": self.loop.enabled,
            "loop_message": self.loop.message,
            "loop_breakers": self.loop.breakers,
            # Conversation
            "conversation_history": self.conversation.history_enabled,
            "conversation_filename": self.conversation.filename,
            "conversation_history_path": self.conversation.history_path,
            "contribute_conversation": self.conversation.contribute,
            # Display
            "max_output": self.display.max_output,
            "shrink_images": self.display.shrink_images,
            "plain_text_display": self.display.plain_text,
            "multi_line": self.display.multi_line,
            "speak_messages": self.display.speak_messages,
            # Safety
            "safe_mode": self.safety.safe_mode,
            "auto_run": self.safety.auto_run,
            # LLM
            "system_message": self.llm.system_message,
            "custom_instructions": self.llm.custom_instructions,
            "user_message_template": self.llm.user_message_template,
            "always_apply_user_message_template": self.llm.always_apply_user_message_template,
            "code_output_template": self.llm.code_output_template,
            "empty_code_output_template": self.llm.empty_code_output_template,
            "code_output_sender": self.llm.code_output_sender,
            # Computer
            "sync_computer": self.computer.sync_computer,
            "import_computer_api": self.computer.import_computer_api,
            "skills_path": self.computer.skills_path,
            "import_skills": self.computer.import_skills,
        }
