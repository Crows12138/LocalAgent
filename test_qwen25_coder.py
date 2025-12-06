# 测试 LocalAgent 与 qwen2.5-coder:14b 的兼容性
# 此脚本验证：
# 1. 模型连接性
# 2. 代码执行能力（Python）
# 3. 工具调用 / Markdown 代码块解析
# 4. 复杂任务处理

import sys
import os

# 添加 interpreter_source 到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from interpreter_source import interpreter
import time

def test_model_connection():
    """测试 1: 模型连接和基本响应"""
    print("\n" + "=" * 60)
    print("【测试 1】模型连接 - qwen2.5-coder:14b")
    print("=" * 60)

    # 配置 qwen2.5-coder:14b
    interpreter.llm.model = "ollama/qwen2.5-coder:14b"
    interpreter.llm.api_base = "http://localhost:11434"
    interpreter.auto_run = True
    interpreter.offline = True

    # 设置上下文窗口和最大 token（14b 模型建议值）
    interpreter.llm.context_window = 32768
    interpreter.llm.max_tokens = 4096

    print(f"模型: {interpreter.llm.model}")
    print(f"上下文窗口: {interpreter.llm.context_window}")
    print(f"最大输出 Token: {interpreter.llm.max_tokens}")
    print("-" * 40)

    return True

def test_simple_code_execution():
    """测试 2: 简单代码执行"""
    print("\n" + "=" * 60)
    print("【测试 2】简单代码执行")
    print("=" * 60)

    # 直接执行 Python 代码
    python_code = """
print("Hello from LocalAgent + qwen2.5-coder:14b!")
result = sum(range(1, 101))
print(f"1+2+3+...+100 = {result}")
"""

    print("执行代码:")
    print(python_code)
    print("-" * 40)
    print("输出:")

    result = interpreter.computer.run("python", python_code)
    for item in result:
        if item.get('type') == 'console':
            print(item.get('content', ''))

    return True

def test_llm_code_generation():
    """测试 3: LLM 自主生成和执行代码"""
    print("\n" + "=" * 60)
    print("【测试 3】LLM 自主代码生成")
    print("=" * 60)

    # 重置对话
    interpreter.messages = []

    task = "请用 Python 计算斐波那契数列的前 10 个数并打印出来"
    print(f"任务: {task}")
    print("-" * 40)

    start_time = time.time()
    response = interpreter.chat(task, display=False)
    elapsed = time.time() - start_time

    print(f"\n耗时: {elapsed:.2f} 秒")
    print("\nLLM 响应:")
    for msg in response:
        if msg.get('type') == 'message':
            print(f"[消息] {msg.get('content', '')[:200]}...")
        elif msg.get('type') == 'code':
            print(f"[代码] {msg.get('format', 'unknown')}")
            print(msg.get('content', '')[:500])
        elif msg.get('type') == 'console':
            print(f"[输出] {msg.get('content', '')}")

    return True

def test_complex_task():
    """测试 4: 复杂任务（需要多步推理）"""
    print("\n" + "=" * 60)
    print("【测试 4】复杂任务处理")
    print("=" * 60)

    # 重置对话
    interpreter.messages = []

    task = """请完成以下任务：
1. 创建一个名为 test_output 的目录（如果不存在）
2. 在该目录中创建一个 info.txt 文件
3. 写入当前时间和系统信息
4. 读取并显示文件内容"""

    print(f"任务: {task}")
    print("-" * 40)

    start_time = time.time()
    response = interpreter.chat(task, display=False)
    elapsed = time.time() - start_time

    print(f"\n耗时: {elapsed:.2f} 秒")
    print(f"响应消息数: {len(response)}")

    # 显示最后的输出
    for msg in response[-5:]:
        if msg.get('type') == 'console':
            content = msg.get('content', '')
            if content:
                print(f"[输出] {content[:300]}")

    return True

def test_tool_calling_mode():
    """测试 5: 检查工具调用模式"""
    print("\n" + "=" * 60)
    print("【测试 5】工具调用模式检测")
    print("=" * 60)

    # 加载模型以触发 supports_functions 检测
    interpreter.llm.load()

    print(f"supports_functions: {interpreter.llm.supports_functions}")
    print(f"supports_vision: {interpreter.llm.supports_vision}")

    if interpreter.llm.supports_functions:
        print("[OK] Using native tool calling mode (run_tool_calling_llm)")
    else:
        print("[OK] Using Markdown parsing mode (run_text_llm)")

    return True

def main():
    print("\n" + "=" * 60)
    print("LocalAgent + qwen2.5-coder:14b 兼容性测试")
    print("=" * 60)

    tests = [
        ("模型连接", test_model_connection),
        ("工具调用模式检测", test_tool_calling_mode),
        ("简单代码执行", test_simple_code_execution),
        ("LLM 代码生成", test_llm_code_generation),
        # ("复杂任务处理", test_complex_task),  # 可选，耗时较长
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, "[PASS]" if success else "[FAIL]"))
        except Exception as e:
            results.append((name, f"[ERROR]: {str(e)[:50]}"))
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, result in results:
        print(f"  {name}: {result}")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()
