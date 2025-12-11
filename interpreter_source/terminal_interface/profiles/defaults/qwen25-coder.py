"""
Qwen 2.5-Coder Profile for LocalAgent

This profile is specifically optimized for Qwen 2.5-Coder models (7B/14B/32B) running via Ollama.
It includes:
- Bilingual system prompt (English/Chinese)
- Optimized context window and token settings
- Code-focused instruction format
- Function calling support (Qwen 2.5 supports tool use)
"""

from interpreter import interpreter
import platform
import getpass

# Detect user's language preference based on system locale
import locale
try:
    system_lang = locale.getdefaultlocale()[0] or "en_US"
    is_chinese = system_lang.startswith("zh")
except:
    is_chinese = False

# Bilingual system prompt optimized for Qwen 2.5-Coder
SYSTEM_PROMPT_EN = """You are a skilled programmer assistant powered by Qwen 2.5-Coder. Your task is to help users by writing and executing code.

Core Principles:
1. Write clean, efficient, working code
2. Use markdown code blocks with language specified
3. Execute code step by step, verify results before proceeding
4. Handle errors gracefully and explain solutions
5. Use cross-platform compatible paths and methods

When writing code:
- Always specify the programming language after ```
- Never use placeholder paths like "path/to/file" - use actual paths
- For file operations, use pathlib for cross-platform compatibility
- Print meaningful output so results can be verified

Current Environment:
- User: {username}
- OS: {os_name}
- Platform: {platform}

Start by understanding the task, then write code to solve it."""

SYSTEM_PROMPT_ZH = """你是一个由 Qwen 2.5-Coder 驱动的专业编程助手。你的任务是通过编写和执行代码来帮助用户。

核心原则：
1. 编写简洁、高效、可运行的代码
2. 使用带语言标识的 markdown 代码块
3. 分步执行代码，验证结果后再继续
4. 优雅地处理错误并解释解决方案
5. 使用跨平台兼容的路径和方法

编写代码时：
- 始终在 ``` 后指定编程语言
- 不要使用占位符路径如 "path/to/file" - 使用实际路径
- 文件操作使用 pathlib 以确保跨平台兼容
- 打印有意义的输出以便验证结果

当前环境：
- 用户: {username}
- 操作系统: {os_name}
- 平台: {platform}

首先理解任务，然后编写代码解决它。"""

# Choose system prompt based on locale
base_prompt = SYSTEM_PROMPT_ZH if is_chinese else SYSTEM_PROMPT_EN

# Format with environment info
interpreter.system_message = base_prompt.format(
    username=getpass.getuser(),
    os_name=platform.system(),
    platform=platform.platform()
)

# Code output templates (bilingual)
if is_chinese:
    interpreter.code_output_template = '''代码已执行。输出如下："""{content}"""

请解释输出含义，并告诉我下一步（如果需要）或确认任务完成。'''
    interpreter.empty_code_output_template = "代码已执行，没有文本输出。请继续下一步或确认完成。"
else:
    interpreter.code_output_template = '''Code executed. Output: """{content}"""

What does this mean / what's next (if anything)?'''
    interpreter.empty_code_output_template = "Code executed with no output. What's next (or are we done)?"

interpreter.code_output_sender = "user"

# =============================================================================
# Qwen 2.5-Coder LLM Settings
# =============================================================================

# Model selection - default to 14b, can be overridden
# Available: qwen2.5-coder:7b, qwen2.5-coder:14b, qwen2.5-coder:32b
interpreter.llm.model = "ollama/qwen2.5-coder:14b"

# Qwen 2.5-Coder supports function calling!
# This is a key optimization - we enable native tool calling
interpreter.llm.supports_functions = True

# Context window settings optimized for Qwen 2.5
# Qwen 2.5-Coder supports up to 128K context, but we set conservative defaults
# for better performance with local inference
interpreter.llm.context_window = 32768  # 32K - good balance
interpreter.llm.max_tokens = 4096       # Enough for complex code

# Temperature - lower for more deterministic code generation
interpreter.llm.temperature = 0.1

# Disable text-based execution instructions since we use function calling
interpreter.llm.execution_instructions = False

# =============================================================================
# Performance Optimizations for Local Inference
# =============================================================================

# Computer API settings
interpreter.computer.import_computer_api = False  # Reduces prompt size

# Output settings - optimized for code responses
interpreter.max_output = 2000  # Reasonable limit for code output

# Auto-run disabled by default for safety
interpreter.auto_run = False

# Offline mode - essential for local models
interpreter.offline = True

# =============================================================================
# Load the model
# =============================================================================

# This will:
# 1. Check if the model is downloaded
# 2. Download if necessary
# 3. Load the model into memory
interpreter.llm.load()

# =============================================================================
# Welcome message
# =============================================================================

if is_chinese:
    welcome_msg = """> 模型已设置为 `qwen2.5-coder:14b`

**LocalAgent** 将在运行代码前请求确认。

使用 `interpreter -y` 跳过确认。

按 `CTRL-C` 退出。
"""
else:
    welcome_msg = """> Model set to `qwen2.5-coder:14b`

**LocalAgent** will require approval before running code.

Use `interpreter -y` to bypass this.

Press `CTRL-C` to exit.
"""

interpreter.display_message(welcome_msg)
