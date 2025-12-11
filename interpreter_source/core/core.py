"""
This file defines the Interpreter class.
It's the main file. `from interpreter import interpreter` will import an instance of this class.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Union

from ..terminal_interface.local_setup import local_setup
from ..terminal_interface.terminal_interface import terminal_interface
from ..terminal_interface.utils.display_markdown_message import display_markdown_message
from ..terminal_interface.utils.local_storage_path import get_storage_path
from ..terminal_interface.utils.oi_dir import oi_dir
from .codebase import CodebaseIndexer
from .computer.computer import Computer
from .context import ContextManager, ContextBuilder
from .git import GitManager
from .config import InterpreterConfig
from .default_system_message import default_system_message
from .llm.llm import Llm
from .respond import respond
from .constants import DEFAULT_MAX_OUTPUT_CHARS
from .utils.telemetry import send_telemetry
from .utils.truncate_output import truncate_output


class OpenInterpreter:
    """
    This class (one instance is called an `interpreter`) is the "grand central station" of this project.

    Its responsibilities are to:

    1. Given some user input, prompt the language model.
    2. Parse the language models responses, converting them into LMC Messages.
    3. Send code to the computer.
    4. Parse the computer's response (which will already be LMC Messages).
    5. Send the computer's response back to the language model.
    ...

    The above process should repeat—going back and forth between the language model and the computer— until:

    6. Decide when the process is finished based on the language model's response.
    """

    def __init__(
        self,
        messages=None,
        offline=False,
        auto_run=False,
        verbose=False,
        debug=False,
        max_output=DEFAULT_MAX_OUTPUT_CHARS,
        safe_mode="off",
        shrink_images=True,
        loop=False,
        loop_message="""Proceed. You CAN run code on my machine. If the entire task I asked for is done, say exactly 'The task is done.' If you need some specific information (like username or password) say EXACTLY 'Please provide more information.' If it's impossible, say 'The task is impossible.' (If I haven't provided a task, say exactly 'Let me know what you'd like to do next.') Otherwise keep going.""",
        loop_breakers=[
            "The task is done.",
            "The task is impossible.",
            "Let me know what you'd like to do next.",
            "Please provide more information.",
        ],
        disable_telemetry=False,
        in_terminal_interface=False,
        conversation_history=True,
        conversation_filename=None,
        conversation_history_path=get_storage_path("conversations"),
        os=False,
        speak_messages=False,
        llm=None,
        system_message=default_system_message,
        custom_instructions="",
        user_message_template="{content}",
        always_apply_user_message_template=False,
        code_output_template="Code output: {content}\n\nWhat does this output mean / what's next (if anything, or are we done)?",
        empty_code_output_template="The code above was executed on my machine. It produced no text output. what's next (if anything, or are we done?)",
        code_output_sender="user",
        computer=None,
        sync_computer=False,
        import_computer_api=False,
        skills_path=None,
        import_skills=False,
        multi_line=True,
        contribute_conversation=False,
        plain_text_display=False,
        # LocalAgent extension: easy local model setup
        local_model=None,  # e.g., "qwen2.5-coder:14b" or "llama3.1:8b"
    ):
        # State
        self.messages = [] if messages is None else messages
        self.responding = False
        self.last_messages_count = 0

        # Settings
        self.offline = offline
        self.auto_run = auto_run
        self.verbose = verbose
        self.debug = debug
        self.max_output = max_output
        self.safe_mode = safe_mode
        self.shrink_images = shrink_images
        self.disable_telemetry = disable_telemetry
        self.in_terminal_interface = in_terminal_interface
        self.multi_line = multi_line
        self.contribute_conversation = contribute_conversation
        self.plain_text_display = plain_text_display
        self.highlight_active_line = True  # additional setting to toggle active line highlighting. Defaults to True

        # Loop messages
        self.loop = loop
        self.loop_message = loop_message
        self.loop_breakers = loop_breakers

        # Conversation history
        self.conversation_history = conversation_history
        self.conversation_filename = conversation_filename
        self.conversation_history_path = conversation_history_path

        # OS control mode related attributes
        self.os = os
        self.speak_messages = speak_messages

        # Computer
        self.computer = Computer(self) if computer is None else computer
        self.sync_computer = sync_computer
        self.computer.import_computer_api = import_computer_api

        # Skills
        if skills_path:
            self.computer.skills.path = skills_path

        self.computer.import_skills = import_skills

        # LLM
        self.llm = Llm(self) if llm is None else llm

        # LocalAgent extension: easy local model configuration
        # If local_model is specified, auto-configure for Ollama
        if local_model:
            self.offline = True
            self.llm.model = f"ollama/{local_model}" if not local_model.startswith("ollama/") else local_model
            self.llm.api_base = "http://localhost:11434"
            self.llm.context_window = 32768
            self.llm.max_tokens = 4096

        # These are LLM related
        self.system_message = system_message
        self.custom_instructions = custom_instructions
        self.user_message_template = user_message_template
        self.always_apply_user_message_template = always_apply_user_message_template
        self.code_output_template = code_output_template
        self.empty_code_output_template = empty_code_output_template
        self.code_output_sender = code_output_sender

        # LocalAgent extension: Codebase indexing
        self._codebase_indexer: Optional[CodebaseIndexer] = None

        # LocalAgent extension: Git integration
        self._git_manager: Optional[GitManager] = None

        # LocalAgent extension: Context management
        self._context_manager: Optional[ContextManager] = None

    def local_setup(self):
        """
        Opens a wizard that lets terminal users pick a local model.
        """
        self = local_setup(self)

    def wait(self) -> List[Dict[str, Any]]:
        """Wait for the interpreter to finish responding and return new messages."""
        while self.responding:
            time.sleep(0.2)
        # Return new messages
        return self.messages[self.last_messages_count :]

    @property
    def anonymous_telemetry(self) -> bool:
        return not self.disable_telemetry and not self.offline

    @property
    def will_contribute(self) -> bool:
        overrides = (
            self.offline or not self.conversation_history or self.disable_telemetry
        )
        return self.contribute_conversation and not overrides

    def chat(
        self,
        message: Optional[Union[str, Dict[str, Any], List[Dict[str, Any]]]] = None,
        display: bool = True,
        stream: bool = False,
        blocking: bool = True,
    ) -> Optional[Union[List[Dict[str, Any]], Generator[Dict[str, Any], None, None]]]:
        try:
            self.responding = True
            if self.anonymous_telemetry:
                message_type = type(
                    message
                ).__name__  # Only send message type, no content
                send_telemetry(
                    "started_chat",
                    properties={
                        "in_terminal_interface": self.in_terminal_interface,
                        "message_type": message_type,
                        "os_mode": self.os,
                    },
                )

            if not blocking:
                chat_thread = threading.Thread(
                    target=self.chat, args=(message, display, stream, True)
                )  # True as in blocking = True
                chat_thread.start()
                return

            if stream:
                return self._streaming_chat(message=message, display=display)

            # If stream=False, *pull* from the stream.
            for _ in self._streaming_chat(message=message, display=display):
                pass

            # Return new messages
            self.responding = False
            return self.messages[self.last_messages_count :]

        except GeneratorExit:
            self.responding = False
            # It's fine
        except Exception as e:
            self.responding = False
            if self.anonymous_telemetry:
                message_type = type(message).__name__
                send_telemetry(
                    "errored",
                    properties={
                        "error": str(e),
                        "in_terminal_interface": self.in_terminal_interface,
                        "message_type": message_type,
                        "os_mode": self.os,
                    },
                )

            raise

    def _streaming_chat(
        self,
        message: Optional[Union[str, Dict[str, Any], List[Dict[str, Any]]]] = None,
        display: bool = True,
    ) -> Generator[Dict[str, Any], None, None]:
        # Sometimes a little more code -> a much better experience!
        # Display mode actually runs interpreter.chat(display=False, stream=True) from within the terminal_interface.
        # wraps the vanilla .chat(display=False) generator in a display.
        # Quite different from the plain generator stuff. So redirect to that
        if display:
            yield from terminal_interface(self, message)
            return

        # One-off message
        if message or message == "":
            ## We support multiple formats for the incoming message:
            # Dict (these are passed directly in)
            if isinstance(message, dict):
                if "role" not in message:
                    message["role"] = "user"
                self.messages.append(message)
            # String (we construct a user message dict)
            elif isinstance(message, str):
                self.messages.append(
                    {"role": "user", "type": "message", "content": message}
                )
            # List (this is like the OpenAI API)
            elif isinstance(message, list):
                self.messages = message

            # Now that the user's messages have been added, we set last_messages_count.
            # This way we will only return the messages after what they added.
            self.last_messages_count = len(self.messages)

            # DISABLED because I think we should just not transmit images to non-multimodal models?
            # REENABLE this when multimodal becomes more common:

            # Make sure we're using a model that can handle this
            # if not self.llm.supports_vision:
            #     for message in self.messages:
            #         if message["type"] == "image":
            #             raise Exception(
            #                 "Use a multimodal model and set `interpreter.llm.supports_vision` to True to handle image messages."
            #             )

            # This is where it all happens!
            yield from self._respond_and_store()

            # Save conversation if we've turned conversation_history on
            if self.conversation_history:
                # If it's the first message, set the conversation name
                if not self.conversation_filename:
                    first_few_words_list = self.messages[0]["content"][:25].split(" ")
                    if (
                        len(first_few_words_list) >= 2
                    ):  # for languages like English with blank between words
                        first_few_words = "_".join(first_few_words_list[:-1])
                    else:  # for languages like Chinese without blank between words
                        first_few_words = self.messages[0]["content"][:15]
                    for char in '<>:"/\\|?*!\n':  # Invalid characters for filenames
                        first_few_words = first_few_words.replace(char, "")

                    date = datetime.now().strftime("%B_%d_%Y_%H-%M-%S")
                    self.conversation_filename = (
                        "__".join([first_few_words, date]) + ".json"
                    )

                # Check if the directory exists, if not, create it
                if not os.path.exists(self.conversation_history_path):
                    os.makedirs(self.conversation_history_path)
                # Write or overwrite the file
                with open(
                    os.path.join(
                        self.conversation_history_path, self.conversation_filename
                    ),
                    "w",
                ) as f:
                    json.dump(self.messages, f)
            return

        raise Exception(
            "`interpreter.chat()` requires a display. Set `display=True` or pass a message into `interpreter.chat(message)`."
        )

    def _respond_and_store(self) -> Generator[Dict[str, Any], None, None]:
        """
        Pulls from the respond stream, adding delimiters. Some things, like active_line, console, confirmation... these act specially.
        Also assembles new messages and adds them to `self.messages`.
        """
        self.verbose = False

        # Utility function
        def is_ephemeral(chunk):
            """
            Ephemeral = this chunk doesn't contribute to a message we want to save.
            """
            if "format" in chunk and chunk["format"] == "active_line":
                return True
            if chunk["type"] == "review":
                return True
            return False

        last_flag_base = None

        try:
            for chunk in respond(self):
                # For async usage
                if hasattr(self, "stop_event") and self.stop_event.is_set():
                    print("Open Interpreter stopping.")
                    break

                if chunk["content"] == "":
                    continue

                # If active_line is None, we finished running code.
                if (
                    chunk.get("format") == "active_line"
                    and chunk.get("content", "") == None
                ):
                    # If output wasn't yet produced, add an empty output
                    if self.messages[-1]["role"] != "computer":
                        self.messages.append(
                            {
                                "role": "computer",
                                "type": "console",
                                "format": "output",
                                "content": "",
                            }
                        )

                # Handle the special "confirmation" chunk, which neither triggers a flag or creates a message
                if chunk["type"] == "confirmation":
                    # Emit a end flag for the last message type, and reset last_flag_base
                    if last_flag_base:
                        yield {**last_flag_base, "end": True}
                        last_flag_base = None

                    if self.auto_run == False:
                        yield chunk

                    # We want to append this now, so even if content is never filled, we know that the execution didn't produce output.
                    # ... rethink this though.
                    # self.messages.append(
                    #     {
                    #         "role": "computer",
                    #         "type": "console",
                    #         "format": "output",
                    #         "content": "",
                    #     }
                    # )
                    continue

                # Check if the chunk's role, type, and format (if present) match the last_flag_base
                if (
                    last_flag_base
                    and "role" in chunk
                    and "type" in chunk
                    and last_flag_base["role"] == chunk["role"]
                    and last_flag_base["type"] == chunk["type"]
                    and (
                        "format" not in last_flag_base
                        or (
                            "format" in chunk
                            and chunk["format"] == last_flag_base["format"]
                        )
                    )
                ):
                    # If they match, append the chunk's content to the current message's content
                    # (Except active_line, which shouldn't be stored)
                    if not is_ephemeral(chunk):
                        if any(
                            [
                                (property in self.messages[-1])
                                and (
                                    self.messages[-1].get(property)
                                    != chunk.get(property)
                                )
                                for property in ["role", "type", "format"]
                            ]
                        ):
                            self.messages.append(chunk)
                        else:
                            self.messages[-1]["content"] += chunk["content"]
                else:
                    # If they don't match, yield a end message for the last message type and a start message for the new one
                    if last_flag_base:
                        yield {**last_flag_base, "end": True}

                    last_flag_base = {"role": chunk["role"], "type": chunk["type"]}

                    # Don't add format to type: "console" flags, to accommodate active_line AND output formats
                    if "format" in chunk and chunk["type"] != "console":
                        last_flag_base["format"] = chunk["format"]

                    yield {**last_flag_base, "start": True}

                    # Add the chunk as a new message
                    if not is_ephemeral(chunk):
                        self.messages.append(chunk)

                # Yield the chunk itself
                yield chunk

                # Truncate output if it's console output
                if chunk["type"] == "console" and chunk["format"] == "output":
                    self.messages[-1]["content"] = truncate_output(
                        self.messages[-1]["content"],
                        self.max_output,
                        add_scrollbars=self.computer.import_computer_api,  # I consider scrollbars to be a computer API thing
                    )

            # Yield a final end flag
            if last_flag_base:
                yield {**last_flag_base, "end": True}
        except GeneratorExit:
            raise  # gotta pass this up!

    def reset(self) -> None:
        """Reset the interpreter state, terminating all running processes."""
        self.computer.terminate()  # Terminates all languages
        self.computer._has_imported_computer_api = False  # Flag reset
        self.messages = []
        self.last_messages_count = 0

    def display_message(self, markdown: str) -> None:
        """Display a markdown message to the user."""
        if self.plain_text_display:
            print(markdown)
        else:
            display_markdown_message(markdown)

    def get_oi_dir(self) -> str:
        """Get the Open Interpreter directory path."""
        return oi_dir

    # =========================================================================
    # LocalAgent Extension: Codebase Indexing
    # =========================================================================

    def index_codebase(self, path: str = ".", max_file_size: int = 500_000) -> str:
        """
        Index a codebase for intelligent context retrieval.

        This scans the directory, extracts symbols and keywords from code files,
        and enables relevant file retrieval for queries.

        Args:
            path: Path to the directory to index (default: current directory)
            max_file_size: Maximum file size in bytes to index (default: 500KB)

        Returns:
            Project overview string

        Example:
            interpreter.index_codebase("./my_project")
            interpreter.chat("What does the login function do?")
        """
        self._codebase_indexer = CodebaseIndexer()
        self._codebase_indexer.index_directory(path, max_file_size=max_file_size)
        return self._codebase_indexer.get_project_overview()

    def get_relevant_context(self, query: str, max_files: int = 5) -> str:
        """
        Get relevant code context for a query.

        Args:
            query: The query to search for
            max_files: Maximum number of files to include

        Returns:
            Context string with relevant file contents
        """
        if not self._codebase_indexer:
            return "No codebase indexed. Call index_codebase() first."
        return self._codebase_indexer.get_context_for_query(query, max_files=max_files)

    def search_codebase(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search the indexed codebase.

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            List of matching files with scores
        """
        if not self._codebase_indexer:
            return []

        results = self._codebase_indexer.get_relevant_files(query, max_results=max_results)
        return [
            {
                "path": path,
                "score": score,
                "summary": entry.summary,
                "symbols": entry.symbols[:10],  # First 10 symbols
            }
            for path, score, entry in results
        ]

    @property
    def codebase(self) -> Optional[CodebaseIndexer]:
        """Access the codebase indexer directly."""
        return self._codebase_indexer

    # =========================================================================
    # LocalAgent Extension: Git Integration
    # =========================================================================

    def init_git(self, path: str = ".") -> str:
        """
        Initialize Git integration for a repository.

        Args:
            path: Path to the Git repository

        Returns:
            Git status summary

        Example:
            interpreter.init_git("./my_project")
            interpreter.git_status()
        """
        self._git_manager = GitManager(path)
        return self._git_manager.get_summary()

    def git_status(self) -> Dict[str, Any]:
        """
        Get Git repository status.

        Returns:
            Status dict with branch, changes, etc.
        """
        if not self._git_manager:
            return {"error": "Git not initialized. Call init_git() first."}

        status = self._git_manager.status()
        return {
            "branch": status.branch,
            "is_clean": status.is_clean,
            "staged": status.staged,
            "modified": status.modified,
            "untracked": status.untracked,
            "deleted": status.deleted,
            "ahead": status.ahead,
            "behind": status.behind,
        }

    def git_diff(self, staged: bool = False, file: Optional[str] = None) -> str:
        """
        Get diff of changes.

        Args:
            staged: Show staged changes
            file: Specific file to diff

        Returns:
            Diff string
        """
        if not self._git_manager:
            return "Git not initialized. Call init_git() first."
        return self._git_manager.diff(staged=staged, file=file)

    def git_log(self, count: int = 10) -> List[Dict[str, str]]:
        """
        Get commit history.

        Args:
            count: Number of commits

        Returns:
            List of commit dicts
        """
        if not self._git_manager:
            return []

        commits = self._git_manager.log(count=count)
        return [
            {
                "hash": c.short_hash,
                "author": c.author,
                "date": c.date,
                "message": c.message,
            }
            for c in commits
        ]

    def git_commit(self, message: str, add_all: bool = False) -> Dict[str, Any]:
        """
        Create a Git commit.

        Args:
            message: Commit message
            add_all: Stage all changes first

        Returns:
            Commit info dict
        """
        if not self._git_manager:
            return {"error": "Git not initialized. Call init_git() first."}

        try:
            commit = self._git_manager.commit(message, add_all=add_all)
            return {
                "success": True,
                "hash": commit.short_hash,
                "message": commit.message,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def git_add(self, files: Optional[List[str]] = None, all: bool = False) -> bool:
        """
        Stage files for commit.

        Args:
            files: Files to stage
            all: Stage all changes

        Returns:
            Success status
        """
        if not self._git_manager:
            return False

        try:
            self._git_manager.add(files=files, all=all)
            return True
        except Exception:
            return False

    def git_branch(self, name: Optional[str] = None, checkout: bool = True) -> str:
        """
        Create or list branches.

        Args:
            name: Branch name to create (None = list branches)
            checkout: Switch to new branch

        Returns:
            Current branch or list of branches
        """
        if not self._git_manager:
            return "Git not initialized"

        if name:
            self._git_manager.create_branch(name, checkout=checkout)
            return f"Created and switched to branch: {name}" if checkout else f"Created branch: {name}"
        else:
            branches = self._git_manager.branches()
            current = self._git_manager.current_branch()
            return f"Current: {current}\nBranches: {', '.join(branches)}"

    def git_checkout(self, branch: str) -> bool:
        """
        Switch to a branch.

        Args:
            branch: Branch name

        Returns:
            Success status
        """
        if not self._git_manager:
            return False

        try:
            self._git_manager.checkout(branch)
            return True
        except Exception:
            return False

    def git_push(self, remote: str = "origin", set_upstream: bool = False) -> str:
        """
        Push to remote.

        Args:
            remote: Remote name
            set_upstream: Set upstream tracking

        Returns:
            Push output
        """
        if not self._git_manager:
            return "Git not initialized"

        try:
            return self._git_manager.push(remote=remote, set_upstream=set_upstream)
        except Exception as e:
            return f"Push failed: {e}"

    def git_pull(self, remote: str = "origin") -> str:
        """
        Pull from remote.

        Args:
            remote: Remote name

        Returns:
            Pull output
        """
        if not self._git_manager:
            return "Git not initialized"

        try:
            return self._git_manager.pull(remote=remote)
        except Exception as e:
            return f"Pull failed: {e}"

    @property
    def git(self) -> Optional[GitManager]:
        """Access the Git manager directly."""
        return self._git_manager

    # =========================================================================
    # LocalAgent Extension: Context Management
    # =========================================================================

    def enable_context(
        self,
        max_tokens: int = 8000,
        auto_files: bool = True,
        auto_codebase: bool = True,
        auto_git: bool = False,
    ) -> "OpenInterpreter":
        """
        Enable intelligent context management.

        When enabled, the interpreter will automatically inject relevant
        context (files, codebase, git) into conversations.

        Args:
            max_tokens: Maximum tokens for context
            auto_files: Auto-inject mentioned files
            auto_codebase: Auto-inject relevant code from indexed codebase
            auto_git: Auto-inject git status

        Returns:
            self for chaining

        Example:
            interpreter.index_codebase("./my_project")
            interpreter.enable_context()
            interpreter.chat("fix the bug in auth.py")  # auth.py auto-loaded
        """
        self._context_manager = ContextManager(self)
        self._context_manager.configure(
            enabled=True,
            max_tokens=max_tokens,
            auto_inject_files=auto_files,
            auto_inject_codebase=auto_codebase,
            auto_inject_git=auto_git,
        )
        return self

    def disable_context(self) -> "OpenInterpreter":
        """Disable context management."""
        if self._context_manager:
            self._context_manager.disable()
        return self

    def build_context(self) -> ContextBuilder:
        """
        Get a context builder for manual context construction.

        Returns:
            New ContextBuilder instance

        Example:
            ctx = interpreter.build_context()
            ctx.add_file("src/main.py")
            ctx.add_custom("Important: use async functions")
            context_str = ctx.build()
        """
        return ContextBuilder(max_tokens=8000)

    def prepare_context(self, message: str) -> str:
        """
        Prepare context for a message.

        Args:
            message: User message

        Returns:
            Context string
        """
        if self._context_manager and self._context_manager.config.enabled:
            return self._context_manager.prepare_context(message)
        return ""

    def inject_context(self, message: str) -> str:
        """
        Inject context into a message.

        Args:
            message: User message

        Returns:
            Message with context prepended
        """
        if self._context_manager and self._context_manager.config.enabled:
            return self._context_manager.inject_context(message)
        return message

    @property
    def context(self) -> Optional[ContextManager]:
        """Access the context manager directly."""
        return self._context_manager

    @property
    def config(self) -> InterpreterConfig:
        """
        Get the current configuration as an InterpreterConfig object.

        Returns:
            InterpreterConfig with current settings
        """
        cfg = InterpreterConfig()

        # Top-level settings
        cfg.offline = self.offline
        cfg.verbose = self.verbose
        cfg.debug = self.debug
        cfg.os_mode = self.os
        cfg.disable_telemetry = self.disable_telemetry
        cfg.in_terminal_interface = self.in_terminal_interface

        # Loop settings
        cfg.loop.enabled = self.loop
        cfg.loop.message = self.loop_message
        cfg.loop.breakers = self.loop_breakers

        # Conversation settings
        cfg.conversation.history_enabled = self.conversation_history
        cfg.conversation.filename = self.conversation_filename
        cfg.conversation.history_path = self.conversation_history_path
        cfg.conversation.contribute = self.contribute_conversation

        # Display settings
        cfg.display.max_output = self.max_output
        cfg.display.shrink_images = self.shrink_images
        cfg.display.plain_text = self.plain_text_display
        cfg.display.highlight_active_line = self.highlight_active_line
        cfg.display.multi_line = self.multi_line
        cfg.display.speak_messages = self.speak_messages

        # Safety settings
        cfg.safety.safe_mode = self.safe_mode
        cfg.safety.auto_run = self.auto_run

        # LLM settings
        cfg.llm.system_message = self.system_message
        cfg.llm.custom_instructions = self.custom_instructions
        cfg.llm.user_message_template = self.user_message_template
        cfg.llm.always_apply_user_message_template = self.always_apply_user_message_template
        cfg.llm.code_output_template = self.code_output_template
        cfg.llm.empty_code_output_template = self.empty_code_output_template
        cfg.llm.code_output_sender = self.code_output_sender

        # Computer settings
        cfg.computer.sync_computer = self.sync_computer
        cfg.computer.import_computer_api = self.computer.import_computer_api
        cfg.computer.skills_path = getattr(self.computer.skills, 'path', None)
        cfg.computer.import_skills = self.computer.import_skills

        return cfg

    @classmethod
    def from_config(cls, config: InterpreterConfig) -> "OpenInterpreter":
        """
        Create an OpenInterpreter instance from an InterpreterConfig.

        Args:
            config: InterpreterConfig object with settings

        Returns:
            New OpenInterpreter instance
        """
        return cls(
            offline=config.offline,
            verbose=config.verbose,
            debug=config.debug,
            os=config.os_mode,
            disable_telemetry=config.disable_telemetry,
            in_terminal_interface=config.in_terminal_interface,
            loop=config.loop.enabled,
            loop_message=config.loop.message,
            loop_breakers=config.loop.breakers,
            conversation_history=config.conversation.history_enabled,
            conversation_filename=config.conversation.filename,
            conversation_history_path=config.conversation.history_path or get_storage_path("conversations"),
            contribute_conversation=config.conversation.contribute,
            max_output=config.display.max_output,
            shrink_images=config.display.shrink_images,
            plain_text_display=config.display.plain_text,
            multi_line=config.display.multi_line,
            speak_messages=config.display.speak_messages,
            safe_mode=config.safety.safe_mode,
            auto_run=config.safety.auto_run,
            system_message=config.llm.system_message,
            custom_instructions=config.llm.custom_instructions,
            user_message_template=config.llm.user_message_template,
            always_apply_user_message_template=config.llm.always_apply_user_message_template,
            code_output_template=config.llm.code_output_template,
            empty_code_output_template=config.llm.empty_code_output_template,
            code_output_sender=config.llm.code_output_sender,
            sync_computer=config.computer.sync_computer,
            import_computer_api=config.computer.import_computer_api,
            skills_path=config.computer.skills_path,
            import_skills=config.computer.import_skills,
        )

    def apply_config(self, config: InterpreterConfig) -> None:
        """
        Apply an InterpreterConfig to this instance.

        Args:
            config: InterpreterConfig object with settings to apply
        """
        # Top-level settings
        self.offline = config.offline
        self.verbose = config.verbose
        self.debug = config.debug
        self.os = config.os_mode
        self.disable_telemetry = config.disable_telemetry
        self.in_terminal_interface = config.in_terminal_interface

        # Loop settings
        self.loop = config.loop.enabled
        self.loop_message = config.loop.message
        self.loop_breakers = config.loop.breakers

        # Conversation settings
        self.conversation_history = config.conversation.history_enabled
        self.conversation_filename = config.conversation.filename
        if config.conversation.history_path:
            self.conversation_history_path = config.conversation.history_path
        self.contribute_conversation = config.conversation.contribute

        # Display settings
        self.max_output = config.display.max_output
        self.shrink_images = config.display.shrink_images
        self.plain_text_display = config.display.plain_text
        self.highlight_active_line = config.display.highlight_active_line
        self.multi_line = config.display.multi_line
        self.speak_messages = config.display.speak_messages

        # Safety settings
        self.safe_mode = config.safety.safe_mode
        self.auto_run = config.safety.auto_run

        # LLM settings
        self.system_message = config.llm.system_message
        self.custom_instructions = config.llm.custom_instructions
        self.user_message_template = config.llm.user_message_template
        self.always_apply_user_message_template = config.llm.always_apply_user_message_template
        self.code_output_template = config.llm.code_output_template
        self.empty_code_output_template = config.llm.empty_code_output_template
        self.code_output_sender = config.llm.code_output_sender

        # Computer settings
        self.sync_computer = config.computer.sync_computer
        self.computer.import_computer_api = config.computer.import_computer_api
        if config.computer.skills_path:
            self.computer.skills.path = config.computer.skills_path
        self.computer.import_skills = config.computer.import_skills
