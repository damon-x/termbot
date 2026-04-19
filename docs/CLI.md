# CLI 模式使用指南

TermBot 的 CLI 模式提供交互式命令行界面，适合个人开发、快速调试等场景。

## 启动 CLI 模式

### 方式 1：快速启动脚本（推荐）

```bash
./start.sh
```

### 方式 2：直接运行 Python

```bash
python cli.py
```

### 方式 3：作为模块运行

```bash
python -m termbot.cli
```

## 启动流程

启动后你会看到：

```
Initializing PTY Manager...
PTY started (PID: 12345)
Initializing Agent...
Registering tools...
Registered 9 tools.
  ✅ exec_terminal_cmd - NOW WORKS with real PTY!

╔════════════════════════════════════════════════════════════╗
║           TermBot - AI Terminal Assistant               ║
╚════════════════════════════════════════════════════════════╝

Available commands:
  /help     - Show this help message
  /tools    - List available tools
  /history  - Show conversation history
  /reset    - Reset conversation
  /quit     - Exit the session

Just type your message and press Enter to chat!
──────────────────────────────────────────────────────────────

🧑 You:
```

## 基础使用

### 对话

直接输入问题或指令：

```
🧑 You: 查看当前目录
🤖 Agent: [执行命令]
```

```
🧑 You: 帮我记录一个笔记，服务器IP是192.168.1.100
🤖 Agent: [记录笔记]
```

### 命令执行

Agent 会自动理解你的意图并执行相应的命令：

```
🧑 You: 列出所有的Docker容器
🤖 Agent: [使用 exec_terminal_cmd 工具执行 docker ps]
```

## 可用命令

| 命令 | 功能 | 示例 |
|------|------|------|
| `/help` | 显示帮助信息 | `/help` |
| `/tools` | 列出所有可用工具 | `/tools` |
| `/history` | 显示对话历史 | `/history` |
| `/reset` | 重置对话历史 | `/reset` |
| `/quit` 或 `/exit` 或 `/q` | 退出程序 | `/quit` |

## 工具列表

Agent 内置了以下工具：

1. **exec_terminal_cmd** - 执行终端命令
   - 示例：`ls`, `pwd`, `cat file.txt`, `docker ps`

2. **add_note** - 记录笔记
   - 用于记住重要信息

3. **get_all_note** - 获取所有笔记
   - 查询之前记录的信息

4. **send_msg_to_user** - 发送消息
   - 通知用户重要信息

5. **create_quick_cmd** - 创建快捷命令
   - 保存常用命令模板

6. **get_all_quick_cmd** - 获取所有快捷命令
   - 列出已保存的命令

7. **search_weather** - 查询天气
   - 查询指定地点的天气

8. **send_email** - 发送邮件
   - 发送邮件通知

9. **send_file_user** - 发送文件
   - 向用户发送文件

## 使用技巧

### 1. 笔记功能

记录重要信息供后续查询：

```
🧑 You: 记录：生产环境数据库密码是 P@ssw0rd123
🤖 Agent: Note recorded successfully.

🧑 You: 数据库密码是什么？
🤖 Agent: [查询笔记]
根据笔记记录，数据库密码是 P@ssw0rd123
```

### 2. 多步骤任务

Agent 可以执行多步骤任务：

```
🧑 You: 检查项目的Python文件是否有语法错误
🤖 Agent: [执行 python -m py_compile ... 检查所有.py文件]
```

### 3. 命令链

可以连续执行多个相关命令：

```
🧑 You: 创建一个test目录，然后在里面创建一个README文件
🤖 Agent: [执行 mkdir test && cd test && touch README.md]
```

### 4. 历史查询

查看之前的对话：

```
🧑 You: /history
Conversation has 15 messages
  [USER] 查看当前目录
  [ASSISTANT] [命令执行结果]
  ...
```

### 5. 重置对话

如果对话太长或想要重新开始：

```
🧑 You: /reset
Conversation reset.
```

## 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+C` | 中断当前输入（不会退出） |
| `Ctrl+D` | 退出程序 |

## 退出

使用以下任一方式退出：

```
🧑 You: /quit
🧑 You: /exit
🧑 You: /q
🧑 You: (按 Ctrl+D)
```

## 故障排查

### 问题：PTY 启动失败

**错误信息**：
```
PTY started (PID: None)
```

**解决方案**：
- 检查系统是否支持 `/bin/bash`
- 尝试更改 shell：编辑 `cli.py` 中的 `shell` 参数

### 问题：API Key 未设置

**错误信息**：
```
⚠️  Warning: OPENAI_API_KEY not set!
```

**解决方案**：
1. 编辑 `.env` 文件
2. 添加：`OPENAI_API_KEY=your-api-key-here`
3. 重新启动 CLI

### 问题：命令执行超时

**错误信息**：
```
Failed to execute command: Lock acquisition timeout
```

**解决方案**：
- 可能是终端被占用（如正在运行 vim 等交互式程序）
- 等待当前命令完成或重启 CLI

## 高级用法

### 自定义系统提示词

编辑 `cli.py` 中的 `system_prompt` 参数来自定义 Agent 的行为：

```python
config = AgentConfig(
    llm_client=llm_client,
    max_iterations=20,
    enable_memory=False,
    enable_mcp=False,
    system_prompt="""You are a senior DevOps engineer..."""
)
```

### 添加自定义工具

在 `cli.py` 的工具注册部分添加：

```python
# 注册自定义工具
agent.register_tool(CustomTool())
```

## 相关文档

- [Web 模式使用指南](WEB.md)
- [项目 README](README.md)
- [架构设计文档](ARCHITECTURE.md)
