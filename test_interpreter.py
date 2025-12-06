# 测试 Open Interpreter 的核心能力
from interpreter import interpreter
import json

# 配置使用本地 Ollama 模型
interpreter.llm.model = "ollama/qwen2.5:3b"
interpreter.llm.api_base = "http://localhost:11434"
interpreter.auto_run = True
interpreter.offline = True

print("=" * 60)
print("Open Interpreter 核心能力测试")
print("=" * 60)

# 测试 1: 直接执行 Shell 命令
print("\n【测试 1】直接执行 Shell 命令")
print("-" * 40)
result = interpreter.computer.run("shell", "echo Hello from Open Interpreter!")
for item in result:
    if item.get('type') == 'console':
        print(item.get('content', ''))

# 测试 2: 执行 Python 代码
print("\n【测试 2】执行 Python 代码")
print("-" * 40)
python_code = """
import os
files = os.listdir('.')
print(f"当前目录有 {len(files)} 个文件/文件夹:")
for f in files:
    print(f"  - {f}")
"""
result = interpreter.computer.run("python", python_code)
for item in result:
    if item.get('type') == 'console':
        print(item.get('content', ''))

# 测试 3: 文件读写
print("\n【测试 3】文件读写")
print("-" * 40)
write_code = """
# 写入文件
with open('test_file.txt', 'w', encoding='utf-8') as f:
    f.write('这是 Open Interpreter 创建的测试文件！\\n')
    f.write('时间: ' + __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
print('文件写入成功！')

# 读取文件
with open('test_file.txt', 'r', encoding='utf-8') as f:
    content = f.read()
print(f'文件内容:\\n{content}')
"""
result = interpreter.computer.run("python", write_code)
for item in result:
    if item.get('type') == 'console':
        print(item.get('content', ''))

# 测试 4: 让 LLM 决定如何执行任务
print("\n【测试 4】LLM 自主决策")
print("-" * 40)
print("发送任务: '计算 1+2+3+...+100 的结果'")
response = interpreter.chat("计算 1+2+3+...+100 的结果", display=False)
print(f"LLM 响应: {response}")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)

