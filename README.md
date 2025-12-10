# LocalAgent

A fork of [Open Interpreter](https://github.com/OpenInterpreter/open-interpreter) optimized for local language models, particularly Qwen 2.5-Coder models via Ollama.

## Features

- **Local Model Support**: Optimized for running with local LLMs through Ollama
- **Multi-language Code Execution**: Python, JavaScript, Shell, PowerShell, and more
- **Computer Control**: File operations, display, keyboard, mouse automation
- **Conversation History**: Automatic saving and loading of conversations
- **Configurable Safety**: Multiple safety modes for code execution

## Installation

```bash
# Clone the repository
git clone https://github.com/Crows12138/LocalAgent.git
cd LocalAgent

# Install dependencies
pip install -r requirements.txt

# Install Ollama (for local models)
# Visit https://ollama.com for installation instructions
```

## Quick Start

### With Ollama (Recommended)

```python
from interpreter_source import interpreter

# Configure for local Ollama model
interpreter.llm.model = "ollama/qwen2.5-coder:14b"
interpreter.llm.api_base = "http://localhost:11434"
interpreter.auto_run = True
interpreter.offline = True

# Start chatting
interpreter.chat("Create a Python script that lists all files in the current directory")
```

### Basic Usage

```python
from interpreter_source import interpreter

# Simple code execution
result = interpreter.computer.run("python", "print('Hello, World!')")

# Shell commands
result = interpreter.computer.run("shell", "echo Hello from shell")
```

## Configuration

### Main Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `auto_run` | `False` | Automatically run generated code |
| `offline` | `False` | Disable internet features |
| `safe_mode` | `"off"` | Safety mode: "off", "ask", or "auto" |
| `max_output` | `2800` | Maximum output characters |
| `verbose` | `False` | Enable verbose logging |

### LLM Settings

```python
interpreter.llm.model = "ollama/qwen2.5-coder:14b"
interpreter.llm.api_base = "http://localhost:11434"
interpreter.llm.context_window = 32768
interpreter.llm.max_tokens = 4096
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `INTERPRETER_LOG_LEVEL` | Set logging level (DEBUG, INFO, WARNING, ERROR) |

## Project Structure

```
LocalAgent/
├── interpreter_source/
│   ├── core/
│   │   ├── core.py           # Main OpenInterpreter class
│   │   ├── respond.py        # Response handling
│   │   ├── llm/              # LLM integration
│   │   ├── computer/         # Computer control modules
│   │   ├── config.py         # Configuration dataclasses
│   │   ├── constants.py      # Centralized constants
│   │   └── logger.py         # Logging system
│   └── terminal_interface/   # CLI interface
├── requirements.txt
└── README.md
```

## Development

### Running Tests

```bash
python test_qwen25_coder.py
```

### Code Quality

The project includes:
- Type annotations for core modules
- Centralized configuration constants
- Unified logging system
- Configuration validation

## Supported Languages

- Python
- JavaScript
- Shell (bash)
- PowerShell
- HTML
- Java
- R
- Ruby
- AppleScript (macOS)

## Differences from Open Interpreter

1. **Local Model Focus**: Optimized configuration for Ollama and local models
2. **Code Quality Improvements**:
   - Fixed logic errors
   - Improved exception handling
   - Added type annotations
   - Centralized constants
3. **Configuration System**: New dataclass-based configuration

## License

This project is a fork of Open Interpreter. Please refer to the original project for licensing information.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## Acknowledgments

- [Open Interpreter](https://github.com/OpenInterpreter/open-interpreter) - The original project
- [Ollama](https://ollama.com) - Local model serving
- [Qwen](https://github.com/QwenLM/Qwen) - Language models
