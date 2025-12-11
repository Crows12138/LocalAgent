"""
Centralized logging configuration for LocalAgent/Open Interpreter.
Provides a unified way to handle logging across all modules.
"""
import logging
import os
import sys
from typing import Optional


# Default log format
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
SIMPLE_FORMAT = "%(levelname)s: %(message)s"

# Environment variable to control log level
LOG_LEVEL_ENV = "INTERPRETER_LOG_LEVEL"


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Args:
        name: Logger name (typically __name__ of the calling module)
        level: Optional log level override

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        # Get level from environment or use default
        if level is None:
            env_level = os.environ.get(LOG_LEVEL_ENV, "WARNING").upper()
            level = getattr(logging, env_level, logging.WARNING)

        logger.setLevel(level)

        # Create console handler
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)

        # Use simple format for console output
        formatter = logging.Formatter(SIMPLE_FORMAT)
        handler.setFormatter(formatter)

        logger.addHandler(handler)

    return logger


def set_log_level(level: int) -> None:
    """
    Set the log level for all LocalAgent loggers.

    Args:
        level: Logging level (e.g., logging.DEBUG, logging.INFO)
    """
    # Update root interpreter logger and all children
    root_logger = logging.getLogger("interpreter_source")
    root_logger.setLevel(level)
    for handler in root_logger.handlers:
        handler.setLevel(level)


def enable_debug() -> None:
    """Enable debug logging for all LocalAgent modules."""
    set_log_level(logging.DEBUG)


def enable_verbose() -> None:
    """Enable verbose (INFO level) logging."""
    set_log_level(logging.INFO)


# Create package-level logger
logger = get_logger("interpreter_source")
