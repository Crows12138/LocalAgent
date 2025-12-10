"""
Configuration validation for OpenInterpreter.
Provides validation functions to ensure configuration values are valid before use.
"""
from typing import Any, Dict, List, Optional, Union


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


def validate_safe_mode(value: str) -> str:
    """
    Validate safe_mode setting.

    Args:
        value: The safe_mode value to validate

    Returns:
        The validated value

    Raises:
        ConfigValidationError: If value is invalid
    """
    valid_modes = ["off", "ask", "auto"]
    if value not in valid_modes:
        raise ConfigValidationError(
            f"Invalid safe_mode '{value}'. Must be one of: {valid_modes}"
        )
    return value


def validate_max_output(value: int) -> int:
    """
    Validate max_output setting.

    Args:
        value: Maximum output characters

    Returns:
        The validated value

    Raises:
        ConfigValidationError: If value is invalid
    """
    if not isinstance(value, int):
        raise ConfigValidationError(
            f"max_output must be an integer, got {type(value).__name__}"
        )
    if value < 100:
        raise ConfigValidationError(
            f"max_output must be at least 100, got {value}"
        )
    if value > 100000:
        raise ConfigValidationError(
            f"max_output must be at most 100000, got {value}"
        )
    return value


def validate_code_output_sender(value: str) -> str:
    """
    Validate code_output_sender setting.

    Args:
        value: The code_output_sender value

    Returns:
        The validated value

    Raises:
        ConfigValidationError: If value is invalid
    """
    valid_senders = ["user", "assistant"]
    if value not in valid_senders:
        raise ConfigValidationError(
            f"Invalid code_output_sender '{value}'. Must be one of: {valid_senders}"
        )
    return value


def validate_llm_model(model: Optional[str]) -> Optional[str]:
    """
    Validate LLM model string format.

    Args:
        model: The model identifier string

    Returns:
        The validated model string

    Raises:
        ConfigValidationError: If model format is invalid
    """
    if model is None:
        return None

    if not isinstance(model, str):
        raise ConfigValidationError(
            f"model must be a string, got {type(model).__name__}"
        )

    if len(model.strip()) == 0:
        raise ConfigValidationError("model cannot be an empty string")

    return model.strip()


def validate_api_base(api_base: Optional[str]) -> Optional[str]:
    """
    Validate API base URL.

    Args:
        api_base: The API base URL

    Returns:
        The validated URL

    Raises:
        ConfigValidationError: If URL format is invalid
    """
    if api_base is None:
        return None

    if not isinstance(api_base, str):
        raise ConfigValidationError(
            f"api_base must be a string, got {type(api_base).__name__}"
        )

    api_base = api_base.strip()

    if not api_base.startswith(("http://", "https://")):
        raise ConfigValidationError(
            f"api_base must start with http:// or https://, got '{api_base}'"
        )

    return api_base.rstrip("/")


def validate_context_window(value: Optional[int]) -> Optional[int]:
    """
    Validate context window size.

    Args:
        value: Context window token count

    Returns:
        The validated value

    Raises:
        ConfigValidationError: If value is invalid
    """
    if value is None:
        return None

    if not isinstance(value, int):
        raise ConfigValidationError(
            f"context_window must be an integer, got {type(value).__name__}"
        )

    if value < 1000:
        raise ConfigValidationError(
            f"context_window must be at least 1000, got {value}"
        )

    return value


def validate_max_tokens(value: Optional[int]) -> Optional[int]:
    """
    Validate max tokens per response.

    Args:
        value: Maximum tokens per response

    Returns:
        The validated value

    Raises:
        ConfigValidationError: If value is invalid
    """
    if value is None:
        return None

    if not isinstance(value, int):
        raise ConfigValidationError(
            f"max_tokens must be an integer, got {type(value).__name__}"
        )

    if value < 1:
        raise ConfigValidationError(
            f"max_tokens must be at least 1, got {value}"
        )

    return value


def validate_temperature(value: Optional[float]) -> Optional[float]:
    """
    Validate LLM temperature setting.

    Args:
        value: Temperature value (0.0 to 2.0)

    Returns:
        The validated value

    Raises:
        ConfigValidationError: If value is invalid
    """
    if value is None:
        return None

    if not isinstance(value, (int, float)):
        raise ConfigValidationError(
            f"temperature must be a number, got {type(value).__name__}"
        )

    if value < 0.0 or value > 2.0:
        raise ConfigValidationError(
            f"temperature must be between 0.0 and 2.0, got {value}"
        )

    return float(value)


def validate_interpreter_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a complete interpreter configuration dictionary.

    Args:
        config: Configuration dictionary

    Returns:
        Validated configuration dictionary

    Raises:
        ConfigValidationError: If any validation fails
    """
    validated = {}

    # Validate each known key
    if "safe_mode" in config:
        validated["safe_mode"] = validate_safe_mode(config["safe_mode"])

    if "max_output" in config:
        validated["max_output"] = validate_max_output(config["max_output"])

    if "code_output_sender" in config:
        validated["code_output_sender"] = validate_code_output_sender(
            config["code_output_sender"]
        )

    # Copy through other values without validation
    for key, value in config.items():
        if key not in validated:
            validated[key] = value

    return validated


def validate_llm_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate LLM-specific configuration.

    Args:
        config: LLM configuration dictionary

    Returns:
        Validated configuration dictionary

    Raises:
        ConfigValidationError: If any validation fails
    """
    validated = {}

    if "model" in config:
        validated["model"] = validate_llm_model(config["model"])

    if "api_base" in config:
        validated["api_base"] = validate_api_base(config["api_base"])

    if "context_window" in config:
        validated["context_window"] = validate_context_window(config["context_window"])

    if "max_tokens" in config:
        validated["max_tokens"] = validate_max_tokens(config["max_tokens"])

    if "temperature" in config:
        validated["temperature"] = validate_temperature(config["temperature"])

    # Copy through other values
    for key, value in config.items():
        if key not in validated:
            validated[key] = value

    return validated
