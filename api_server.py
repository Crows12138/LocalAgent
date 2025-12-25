"""
LocalAgent API Server - 完整版
支持所有 Agent 功能：聊天、代码执行、文件操作、网络搜索等

启动方式:
    python api_server.py

API 端点:
    POST /chat          - 自然语言对话 (可执行任意任务)
    POST /execute       - 执行代码
    POST /file/read     - 读取文件
    POST /file/write    - 写入文件
    POST /file/list     - 列出目录
    POST /search        - 网络搜索
    POST /browser/open  - 打开网页
    POST /shell         - 执行 Shell 命令
    GET  /health        - 健康检查
    GET  /models        - 获取模型列表
"""

import asyncio
import json
import os
import sys
import subprocess
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
from threading import Lock

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

# 导入 interpreter
from interpreter_source import interpreter

# 配置 interpreter
interpreter.llm.model = "ollama/qwen2.5-coder:14b"
interpreter.llm.api_base = "http://localhost:11434"
interpreter.llm.context_window = 32768
interpreter.llm.max_tokens = 4096
interpreter.llm.supports_functions = True
interpreter.auto_run = True  # 自动执行代码，无需确认
interpreter.offline = True

# 任务存储 (用于后台任务追踪)
task_storage: Dict[str, Dict[str, Any]] = {}
task_lock = Lock()

# 统一对话历史（Chat 和 Agent 共享）
# 格式: [{"role": "user"/"assistant", "content": "..."}]
conversation_history: List[Dict[str, str]] = []
HISTORY_LIMIT = 10  # 保留最近 10 轮对话（20条消息）

# 创建 FastAPI 应用
app = FastAPI(
    title="LocalAgent API",
    description="本地 AI Agent API - 支持聊天、代码执行、文件操作、网络搜索等",
    version="2.0.0"
)

# 添加 CORS 支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 数据模型 ============

class ChatRequest(BaseModel):
    """聊天请求 - 可以是任何自然语言指令"""
    message: str
    stream: bool = False
    auto_run: bool = True  # 是否自动执行生成的代码


class ExecuteRequest(BaseModel):
    """代码执行请求"""
    language: str = "python"
    code: str


class FileReadRequest(BaseModel):
    """文件读取请求"""
    path: str
    encoding: str = "utf-8"


class FileWriteRequest(BaseModel):
    """文件写入请求"""
    path: str
    content: str
    encoding: str = "utf-8"


class FileListRequest(BaseModel):
    """目录列表请求"""
    path: str = "."
    pattern: str = "*"


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str
    num_results: int = 5


class BrowserRequest(BaseModel):
    """浏览器请求"""
    url: str
    action: str = "open"  # open, screenshot, get_text


class ShellRequest(BaseModel):
    """Shell 命令请求"""
    command: str
    timeout: int = 60


# ============ 工具函数 ============

def needs_agent(message: str) -> tuple[bool, str]:
    """判断是否需要 Agent（有工具能力）

    返回: (需要Agent, 清理后的消息)

    规则：
    - @ 开头强制 Agent
    - 包含特定关键词 → Agent
    - 否则 → 纯聊天（直接用 Ollama）
    """
    # 提取用户消息（去掉 system prompt）
    user_msg = message
    if "用户:" in message:
        user_msg = message.split("用户:")[-1].strip()
    elif "用户：" in message:
        user_msg = message.split("用户：")[-1].strip()

    # 显式触发
    if user_msg.startswith('@'):
        return True, message.replace('@', '', 1)

    # 关键词触发
    agent_keywords = [
        '搜索', '搜一下', '查一下', '查询', '查找',
        '打开', '运行', '执行', '创建', '删除',
        '文件', '目录', '文件夹',
        '下载', '安装',
        '新闻', '股票', '汇率',
        '计算', '算一下',
    ]

    for kw in agent_keywords:
        if kw in user_msg:
            return True, message

    return False, message


def chat_with_ollama(user_msg: str, system_prompt: str = None) -> str:
    """直接用 Ollama 聊天（带对话历史）"""
    global conversation_history
    import requests

    if not system_prompt:
        system_prompt = "你是可爱的桌面宠物Io。回复简短（50字以内），轻松可爱。"

    # 构建消息列表：system + 历史 + 当前用户消息
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history)  # 加入对话历史
    messages.append({"role": "user", "content": user_msg})

    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "qwen2.5-coder:14b",
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 100}
            },
            timeout=30
        )
        if response.status_code == 200:
            result = response.json()
            assistant_reply = result.get("message", {}).get("content", "")

            # 保存到历史
            conversation_history.append({"role": "user", "content": user_msg})
            conversation_history.append({"role": "assistant", "content": assistant_reply})

            # 限制历史长度
            if len(conversation_history) > HISTORY_LIMIT * 2:
                conversation_history = conversation_history[-HISTORY_LIMIT * 2:]

            return assistant_reply
    except Exception as e:
        return f"聊天出错: {str(e)[:50]}"

    return "嗯...我不知道该说什么"


def collect_response(message: str, auto_run: bool = True) -> dict:
    """收集 interpreter 的完整响应

    返回:
        {
            "text": "响应文本",
            "pending_code": {"language": "python", "code": "..."} 或 None,
            "code_output": "执行结果" 或 None
        }
    """
    interpreter.auto_run = auto_run
    full_response = ""
    code_outputs = []
    pending_code = None  # 待确认的代码

    for chunk in interpreter.chat(message=message, stream=True, display=False):
        chunk_type = chunk.get("type", "")

        if chunk_type == "message" and chunk.get("role") == "assistant":
            content = chunk.get("content", "")
            if content:
                full_response += content

        # 捕获代码块 (当 auto_run=False 时，代码不会执行)
        if chunk_type == "code":
            code_content = chunk.get("content", "")
            code_lang = chunk.get("format", "python")
            if code_content and not auto_run:
                pending_code = {"language": code_lang, "code": code_content}

        # 收集代码执行结果 (当 auto_run=True 时)
        if chunk_type == "console" and chunk.get("format") == "output":
            output = chunk.get("content", "")
            if output:
                code_outputs.append(output)

    result = {"text": full_response.strip(), "pending_code": pending_code, "code_output": None}

    # 如果有代码输出，附加到响应
    if code_outputs:
        result["code_output"] = "\n".join(code_outputs)
        result["text"] += "\n\n### 执行结果:\n" + result["code_output"]

    return result


# ============ API 端点 ============

@app.get("/")
async def root():
    """API 信息"""
    return {
        "name": "LocalAgent API",
        "version": "2.0.0",
        "capabilities": [
            "自然语言对话与任务执行",
            "多语言代码执行 (Python, JavaScript, Shell, etc.)",
            "文件读写操作",
            "网络搜索",
            "浏览器控制",
            "系统命令执行"
        ],
        "endpoints": {
            "/chat": "POST - 自然语言对话，可执行任意任务",
            "/execute": "POST - 执行代码",
            "/file/read": "POST - 读取文件",
            "/file/write": "POST - 写入文件",
            "/file/list": "POST - 列出目录",
            "/search": "POST - 网络搜索 (通过 Agent)",
            "/shell": "POST - 执行 Shell 命令",
            "/health": "GET - 健康检查",
            "/models": "GET - 获取模型列表",
            "/reset": "POST - 重置对话"
        }
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "model": interpreter.llm.model,
        "auto_run": interpreter.auto_run,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/context")
async def get_context():
    """获取当前窗口上下文（跨平台）"""
    try:
        from interpreter_source.core.computer.window import Window
        window = Window(interpreter.computer)
        active = window.get_active()
        if active:
            return {
                "success": True,
                "title": active.title,
                "app": active.app_name,
                "pid": active.pid,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        pass
    return {
        "success": False,
        "title": None,
        "app": None,
        "pid": None,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/models")
async def get_models():
    """获取 Ollama 模型列表"""
    import requests
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            return {"models": models, "current": interpreter.llm.model}
    except Exception as e:
        pass
    return {"models": [], "current": interpreter.llm.model, "error": "无法获取模型列表"}


# ============ 核心功能: 聊天 ============

@app.post("/chat")
async def chat(request: ChatRequest):
    """
    自然语言对话 - 核心端点（带智能路由 + 统一记忆）

    路由规则：
    - @ 开头或包含关键词 → Agent 模式（可执行代码）
    - 普通聊天 → 直接 Ollama 回复（更快）

    当 auto_run=False 时，返回 pending_code 供用户确认后执行
    """
    global conversation_history

    # 提取 system prompt 和 user message
    system_prompt = "你是可爱的桌面宠物Io。回复简短（50字以内），轻松可爱。"
    user_msg = request.message

    if "用户:" in request.message:
        parts = request.message.split("用户:")
        system_prompt = parts[0].strip()
        user_msg = parts[1].strip()
    elif "用户：" in request.message:
        parts = request.message.split("用户：")
        system_prompt = parts[0].strip()
        user_msg = parts[1].strip()

    try:
        # 智能路由：判断是否需要 Agent
        use_agent, _ = needs_agent(request.message)

        if use_agent:
            # Agent 模式：使用 interpreter
            result = collect_response(request.message, request.auto_run)

            # 记录到统一历史（保留有意义的信息）
            conversation_history.append({"role": "user", "content": user_msg})

            # 构建 Agent 回复摘要
            text_part = result["text"].split("### 执行结果:")[0].strip()
            code_output = result.get("code_output", "")

            if text_part:
                # 有文本回复，使用它
                agent_summary = text_part
            elif code_output:
                # 只有执行结果，取最后150字符作为摘要（关键信息通常在末尾）
                if len(code_output) > 150:
                    output_preview = "..." + code_output[-150:].strip()
                else:
                    output_preview = code_output.strip()
                agent_summary = f"执行完成。结果: {output_preview}"
            else:
                agent_summary = "好的，已完成。"

            conversation_history.append({"role": "assistant", "content": agent_summary})

            # 限制历史长度
            if len(conversation_history) > HISTORY_LIMIT * 2:
                conversation_history = conversation_history[-HISTORY_LIMIT * 2:]

            return {
                "success": True,
                "mode": "agent",
                "response": result["text"],
                "pending_code": result["pending_code"],
                "timestamp": datetime.now().isoformat()
            }
        else:
            # 聊天模式：直接用 Ollama（内部会记录历史）
            response_text = chat_with_ollama(user_msg, system_prompt)
            return {
                "success": True,
                "mode": "chat",
                "response": response_text,
                "pending_code": None,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式对话"""
    async def generate():
        interpreter.auto_run = request.auto_run
        try:
            for chunk in interpreter.chat(message=request.message, stream=True, display=False):
                if chunk.get("type") == "message" and chunk.get("role") == "assistant":
                    content = chunk.get("content", "")
                    if content:
                        yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
                elif chunk.get("type") == "console" and chunk.get("format") == "output":
                    output = chunk.get("content", "")
                    if output:
                        yield f"data: {json.dumps({'output': output}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ============ 代码执行 ============

@app.post("/execute")
async def execute_code(request: ExecuteRequest):
    """
    直接执行代码

    支持的语言: python, javascript, shell, powershell, html, r, ruby
    """
    try:
        result = interpreter.computer.run(request.language, request.code)
        return {
            "success": True,
            "language": request.language,
            "output": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ 文件操作 ============

@app.post("/file/read")
async def read_file(request: FileReadRequest):
    """
    读取文件内容

    n8n 配置:
    - Body: {"path": "C:/Users/xxx/test.txt"}
    """
    try:
        path = Path(request.path).expanduser().resolve()
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"文件不存在: {path}")

        content = path.read_text(encoding=request.encoding)
        return {
            "success": True,
            "path": str(path),
            "content": content,
            "size": path.stat().st_size,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/file/write")
async def write_file(request: FileWriteRequest):
    """
    写入文件

    n8n 配置:
    - Body: {"path": "C:/Users/xxx/output.txt", "content": "文件内容"}
    """
    try:
        path = Path(request.path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(request.content, encoding=request.encoding)
        return {
            "success": True,
            "path": str(path),
            "size": len(request.content),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/file/list")
async def list_files(request: FileListRequest):
    """
    列出目录内容

    n8n 配置:
    - Body: {"path": "C:/Users/xxx/Desktop", "pattern": "*.txt"}
    """
    try:
        path = Path(request.path).expanduser().resolve()
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"目录不存在: {path}")

        files = []
        for item in path.glob(request.pattern):
            stat = item.stat()
            files.append({
                "name": item.name,
                "path": str(item),
                "is_dir": item.is_dir(),
                "size": stat.st_size if item.is_file() else None,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })

        return {
            "success": True,
            "path": str(path),
            "pattern": request.pattern,
            "count": len(files),
            "files": files,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ 搜索功能 ============

@app.post("/search")
async def search(request: SearchRequest):
    """
    网络搜索 - 通过 Agent 执行

    Agent 会使用可用的搜索工具来获取信息

    n8n 配置:
    - Body: {"query": "Python 3.12 新特性", "num_results": 5}
    """
    try:
        # 构建搜索指令
        search_prompt = f"""请搜索以下内容并提供详细摘要:

搜索词: {request.query}

请提供:
1. 搜索到的主要信息
2. 关键要点总结
3. 相关来源 (如果有)

限制返回 {request.num_results} 条最相关的结果。"""

        response = collect_response(search_prompt)
        return {
            "success": True,
            "query": request.query,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Shell 命令 ============

@app.post("/shell")
async def run_shell(request: ShellRequest):
    """
    执行 Shell/PowerShell 命令

    n8n 配置:
    - Body: {"command": "dir", "timeout": 30}
    """
    try:
        # 在 Windows 上使用 PowerShell
        if sys.platform == "win32":
            result = subprocess.run(
                ["powershell", "-Command", request.command],
                capture_output=True,
                text=True,
                timeout=request.timeout
            )
        else:
            result = subprocess.run(
                request.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=request.timeout
            )

        return {
            "success": result.returncode == 0,
            "command": request.command,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
            "timestamp": datetime.now().isoformat()
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="命令执行超时")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ 对话管理 ============

@app.post("/reset")
async def reset_conversation():
    """重置对话历史（统一清空）"""
    global conversation_history
    interpreter.messages = []
    conversation_history = []
    return {
        "success": True,
        "message": "对话历史已清空",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/history")
async def get_history():
    """获取统一对话历史"""
    return {
        "messages": conversation_history,
        "count": len(conversation_history),
        "interpreter_messages": len(interpreter.messages),  # Agent 内部消息数
        "timestamp": datetime.now().isoformat()
    }


# ============ 高级功能 ============

def run_task_in_background(task_id: str, message: str, auto_run: bool):
    """后台执行任务的函数"""
    with task_lock:
        task_storage[task_id]["status"] = "running"
        task_storage[task_id]["started_at"] = datetime.now().isoformat()

    try:
        response = collect_response(message, auto_run)
        with task_lock:
            task_storage[task_id]["status"] = "completed"
            task_storage[task_id]["response"] = response
            task_storage[task_id]["completed_at"] = datetime.now().isoformat()
    except Exception as e:
        with task_lock:
            task_storage[task_id]["status"] = "failed"
            task_storage[task_id]["error"] = str(e)
            task_storage[task_id]["completed_at"] = datetime.now().isoformat()


@app.post("/task")
async def execute_task(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    执行复杂任务 (后台运行)

    立即返回任务 ID，任务在后台执行
    使用 GET /task/{task_id} 查询任务状态和结果
    """
    import uuid
    task_id = str(uuid.uuid4())[:8]

    # 初始化任务状态
    with task_lock:
        task_storage[task_id] = {
            "status": "pending",
            "message": request.message,
            "created_at": datetime.now().isoformat(),
            "response": None,
            "error": None
        }

    # 添加到后台任务队列
    background_tasks.add_task(run_task_in_background, task_id, request.message, request.auto_run)

    return {
        "success": True,
        "task_id": task_id,
        "status": "pending",
        "message": "任务已提交，使用 GET /task/{task_id} 查询结果",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """
    查询后台任务状态

    返回任务状态: pending, running, completed, failed
    """
    with task_lock:
        if task_id not in task_storage:
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

        task = task_storage[task_id].copy()

    return {
        "task_id": task_id,
        **task
    }


# ============ 启动服务 ============

if __name__ == "__main__":
    print("=" * 60)
    print("  LocalAgent API Server v2.0")
    print("=" * 60)
    print(f"  Model:    {interpreter.llm.model}")
    print(f"  API Base: {interpreter.llm.api_base}")
    print(f"  Auto Run: {interpreter.auto_run}")
    print("=" * 60)
    print("  Endpoints:")
    print("    POST /chat       - 自然语言对话")
    print("    POST /execute    - 执行代码")
    print("    POST /file/read  - 读取文件")
    print("    POST /file/write - 写入文件")
    print("    POST /file/list  - 列出目录")
    print("    POST /search     - 网络搜索")
    print("    POST /shell      - Shell 命令")
    print("    GET  /health     - 健康检查")
    print("=" * 60)
    print("  Server: http://localhost:8000")
    print("  Docs:   http://localhost:8000/docs")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8000)
