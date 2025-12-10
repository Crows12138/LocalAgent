"""
Constants used throughout the LocalAgent/Open Interpreter codebase.
Centralizing magic numbers and configuration defaults for better maintainability.
"""

# Output truncation settings
DEFAULT_MAX_OUTPUT_CHARS = 2800  # Maximum characters to show in truncated output

# Timeout settings (in seconds)
TERMINAL_INPUT_PATIENCE = 15  # Seconds to wait before prompting for input
LONG_RUNNING_THRESHOLD = 500  # Seconds before suggesting CTRL-C for frozen processes

# Context window defaults
DEFAULT_CONTEXT_WINDOW = 8000  # Fallback context window when model info unavailable
CONTEXT_WINDOW_BUFFER = 25  # Token buffer when trimming messages

# LLM retry settings
LLM_MAX_RETRY_ATTEMPTS = 4  # Number of retry attempts for LLM calls
SUBPROCESS_MAX_RETRIES = 3  # Max retries for subprocess language execution

# Image processing
MAX_IMAGE_SIZE_MB = 5  # Maximum image size before compression
TARGET_IMAGE_SIZE_MB = 4.9  # Target size after compression
IMAGE_RESIZE_MAX_ITERATIONS = 10  # Max iterations for image resizing loop

# Jupyter/Kernel settings
KERNEL_STARTUP_WAIT = 0.5  # Seconds to wait after kernel starts
KERNEL_CHECK_INTERVAL = 0.1  # Interval for checking kernel status
MESSAGE_QUEUE_TIMEOUT = 0.3  # Timeout for message queue operations
KERNEL_MAX_RETRIES = 100  # Max retries for kernel message listener

# Response wait settings
RESPONSE_WAIT_INTERVAL = 0.2  # Interval for checking response completion
OUTPUT_CAPTURE_INTERVAL = 0.1  # Interval for capturing output

# Conversation filename settings
FILENAME_MAX_CHARS = 25  # Max characters for conversation filename prefix
FILENAME_NON_ENGLISH_CHARS = 15  # Max characters for non-English filenames
