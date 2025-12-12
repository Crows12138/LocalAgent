# n8n Integration for LocalAgent

Use n8n workflow automation to orchestrate LocalAgent's AI capabilities.

## Quick Start

### 1. Start LocalAgent API Server

```bash
# From project root
python api_server.py
```

The API server will run at `http://localhost:8000`

### 2. Start n8n

```bash
cd n8n
docker compose up -d
```

Access n8n at: http://localhost:5678

### 3. Import Workflow

1. Open n8n in browser
2. Create a new workflow
3. Click menu (three dots) → Import from file
4. Select `workflow-localagent.json`

## API Endpoints

LocalAgent exposes these endpoints for n8n:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Natural language chat (can execute any task) |
| `/execute` | POST | Execute code directly |
| `/file/read` | POST | Read file content |
| `/file/write` | POST | Write file content |
| `/file/list` | POST | List directory contents |
| `/shell` | POST | Execute shell commands |
| `/health` | GET | Health check |

## Example n8n HTTP Request Configuration

**URL:** `http://host.docker.internal:8000/chat`

**Method:** POST

**Body (JSON):**
```json
{
  "message": "Your natural language instruction here"
}
```

## Example Tasks

Through the `/chat` endpoint, you can ask the agent to:

- Create, read, modify files
- Execute Python/JavaScript code
- Run shell commands
- Perform calculations
- Process data

## Architecture

```
┌─────────────┐     HTTP      ┌──────────────┐     ┌─────────┐
│    n8n      │ ───────────── │ LocalAgent   │ ──→ │  Ollama │
│  (Docker)   │               │ API Server   │     │   LLM   │
└─────────────┘               └──────────────┘     └─────────┘
     :5678                         :8000              :11434
```

## Troubleshooting

### Cannot connect to LocalAgent

Make sure:
1. `api_server.py` is running on the host machine
2. n8n uses `host.docker.internal:8000` (not `localhost`)

### Timeout errors

Increase timeout in HTTP Request node options (default: 120000ms)
