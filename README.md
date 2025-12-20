# LocalAgent

A fork of [Open Interpreter](https://github.com/OpenInterpreter/open-interpreter) optimized for local language models, with specific support for **Qwen 2.5-Coder** models via Ollama.

## Features

- **Qwen 2.5-Coder Optimization**: Dedicated profile with bilingual system prompts (English/Chinese)
- **Smart Function Calling**: Automatic detection of models that support native tool calling
- **Local Model Support**: Optimized for running with local LLMs through Ollama
- **Multi-language Code Execution**: Python, JavaScript, Shell, PowerShell, and more
- **Computer Control**: File operations, display, keyboard, mouse automation
- **Conversation History**: Automatic saving and loading of conversations
- **Improved Code Parsing**: Better markdown code block parsing with multi-block support

## Installation

```bash
# Clone the repository
git clone https://github.com/Crows12138/LocalAgent.git
cd LocalAgent

# Install dependencies
pip install -r requirements.txt

# Install Ollama (for local models)
# Visit https://ollama.com for installation instructions

# Pull Qwen 2.5-Coder model
ollama pull qwen2.5-coder:14b
```

## Quick Start

### API Server (Recommended for Integration)

```bash
# Start the API server
python api_server.py
```

Server runs at `http://localhost:8000`. See [API Endpoints](#api-endpoints) below.

### Using Qwen 2.5-Coder (Recommended)

```bash
# Start with the optimized Qwen profile
interpreter --profile qwen25-coder.py
```

Or programmatically:

```python
from interpreter_source import interpreter

# Configure for Qwen 2.5-Coder
interpreter.llm.model = "ollama/qwen2.5-coder:14b"
interpreter.llm.api_base = "http://localhost:11434"
interpreter.llm.context_window = 32768
interpreter.llm.max_tokens = 4096
interpreter.llm.supports_functions = True  # Qwen 2.5 supports tool calling
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
interpreter.llm.supports_functions = True  # Enable for Qwen 2.5
interpreter.llm.temperature = 0.1  # Lower for deterministic code
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `INTERPRETER_LOG_LEVEL` | Set logging level (DEBUG, INFO, WARNING, ERROR) |

## Supported Models

### Qwen 2.5-Coder (Optimized)

| Model | Size | Context | Best For |
|-------|------|---------|----------|
| `qwen2.5-coder:7b` | ~4GB | 32K | Quick tasks, limited RAM |
| `qwen2.5-coder:14b` | ~8GB | 32K | **Recommended** - best balance |
| `qwen2.5-coder:32b` | ~18GB | 32K | Complex tasks, high accuracy |

### Other Supported Models

- Llama 3.1/3.2
- Codestral
- Mistral-Nemo
- Gemma 2
- Any Ollama-compatible model

## Project Structure

```
LocalAgent/
├── interpreter_source/
│   ├── core/
│   │   ├── core.py           # Main OpenInterpreter class
│   │   ├── respond.py        # Response handling
│   │   ├── llm/              # LLM integration
│   │   │   ├── llm.py        # LLM class with model detection
│   │   │   ├── run_text_llm.py      # Markdown parsing (improved)
│   │   │   └── run_tool_calling_llm.py  # Native tool calling
│   │   ├── computer/         # Computer control modules
│   │   ├── config.py         # Configuration dataclasses
│   │   ├── config_validator.py  # Configuration validation
│   │   ├── constants.py      # Centralized constants
│   │   └── logger.py         # Logging system
│   └── terminal_interface/
│       └── profiles/defaults/
│           └── qwen25-coder.py  # Qwen-optimized profile
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

## Differences from Open Interpreter

1. **Qwen 2.5-Coder Support**:
   - Dedicated profile with optimized settings
   - Bilingual system prompts (English/Chinese)
   - Automatic function calling detection

2. **Improved Model Detection**:
   - Known models list for function calling support
   - Better handling of Ollama models

3. **Enhanced Code Parsing**:
   - Multi-block support in `run_text_llm`
   - More robust markdown parsing

4. **Code Quality Improvements**:
   - Fixed logic errors
   - Improved exception handling
   - Added type annotations
   - Centralized constants

5. **Configuration System**:
   - New dataclass-based configuration
   - Configuration validation

## API Endpoints

The `api_server.py` provides a RESTful API with smart routing:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Smart chat (auto-routes to Chat or Agent mode) |
| `/execute` | POST | Execute code directly |
| `/file/read` | POST | Read file |
| `/file/write` | POST | Write file |
| `/shell` | POST | Run shell command |
| `/reset` | POST | Clear conversation history |
| `/history` | GET | Get unified conversation history |
| `/health` | GET | Health check |

### Smart Routing

- **Chat mode**: Simple conversations go directly to Ollama (fast, uses `qwen2.5:1.5b`)
- **Agent mode**: Requests with `@` prefix or keywords trigger code execution (uses `qwen2.5-coder:14b`)

```bash
# Chat mode (fast)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello", "auto_run": false}'

# Agent mode (prefix with @)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "@list files on desktop", "auto_run": false}'
```

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

## License

This project is a fork of Open Interpreter. Please refer to the original project for licensing information.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## Acknowledgments

- [Open Interpreter](https://github.com/OpenInterpreter/open-interpreter) - The original project
- [Ollama](https://ollama.com) - Local model serving
- [Qwen](https://github.com/QwenLM/Qwen) - Qwen 2.5-Coder language models
