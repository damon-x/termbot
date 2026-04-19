# Web 模式使用指南

TermBot 的 Web 模式提供浏览器界面，支持多用户同时使用，适合团队协作、远程访问等场景。

## 启动 Web 服务器

```bash
python web.py
```

启动后会看到：

```
╔════════════════════════════════════════════════════════════╗
║           TermBot - Web Server                          ║
╚════════════════════════════════════════════════════════════╝

Starting server on http://0.0.0.0:5000
Debug mode: False

Press Ctrl+C to stop the server
──────────────────────────────────────────────────────────────

 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.x.x:5000
```

## 访问 Web 界面

在浏览器中打开：

```
http://localhost:5000
```

## 界面布局

Web 界面分为两部分：

```
┌─────────────────────────────────────────────────────────────┐
│  ┌─────────────────┐  ┌─────────────────────────────────┐  │
│  │                 │  │                                 │  │
│  │   Web Terminal  │  │      AI Assistant Chat          │  │
│  │   (xterm.js)     │  │                                 │  │
│  │                 │  │  🧑 你好                      │  │
│  │  $ ls -la        │  │  🤖 你好！我是智能终端助手    │  │
│  │                 │  │                                 │  │
│  │                 │  │  [命令执行结果]                │  │
│  │                 │  │                                 │  │
│  └─────────────────┘  └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 左侧：Web 终端

- 基于 xterm.js 的完整终端模拟
- 支持颜色、光标移动、交互式程序
- 每个用户独立的终端会话

### 右侧：AI 助手对话

- 自然语言交互界面
- 支持多轮对话
- 自动理解意图并执行命令

## 多用户支持

### 架构原则

**1 Web Session = 1 Agent 实例 = 1 PTY 实例**

每个用户（或每个浏览器标签页）都有：
- 独立的 Agent（独立的对话历史和笔记）
- 独立的 PTY（独立的终端会话）
- 完全隔离的状态

### 多用户场景

```
用户A (浏览器标签1)
    └── Session A → Agent A + PTY A → 独立的终端和对话

用户A (浏览器标签2)
    └── Session B → Agent B + PTY B → 另一个独立终端

用户B (另一台电脑)
    └── Session C → Agent C + PTY C → 完全独立的会话
```

### 数据隔离

| 数据类型 | 是否隔离 | 说明 |
|---------|---------|------|
| 对话历史 | ✅ 隔离 | 每个会话独立记录 |
| 笔记 | ✅ 隔离 | 每个会话独立笔记 |
| 终端状态 | ✅ 隔离 | 每个会话独立 PTY |
| LLM Client | ❌ 共享 | 无状态，可共享 |

## WebSocket 事件

### 客户端发送

| 事件 | 参数 | 说明 |
|------|------|------|
| `chat_message` | `{message: "..."}` | 发送聊天消息 |
| `terminal_input` | `{data: "..."}` | 发送终端输入 |
| `terminal_resize` | `{cols: 80, rows: 24}` | 调整终端大小 |

### 服务器推送

| 事件 | 参数 | 说明 |
|------|------|------|
| `connected` | `{message: "...", pty_pid: ...}` | 连接成功 |
| `chat_response` | `{message: "..."}` | AI 回复 |
| `terminal_output` | `{data: "..."}` | 终端输出 |
| `terminal_error` | `{message: "..."}` | 终端错误 |
| `clear_terminal` | - | 清空终端 |

## 使用示例

### 示例 1：基本对话

```
🧑: 你好
🤖: 你好！我是智能终端助手，有什么可以帮助你的吗？

🧑: 查看当前目录
🤖: [执行 exec_terminal_cmd]
```

### 示例 2：直接操作终端

在左侧 Web 终端中直接输入命令：

```
$ ls -la
total 16
drwxr-xr-x  5 user  staff  160 Feb  9 16:30 .
drwxr-xr-x  20 user  staff  640 Feb  9 13:47 ..
...
```

### 示例 3：混合使用

```
🧑: 创建一个test目录
🤖: [执行 mkdir test]

🧑: [在终端中输入] cd test && ls -la
🤖: [读取终端输出]
```

### 示例 4：笔记管理

```
🧑: 记录：王总下午3点开会
🤖: [调用 add_note] 笔记已保存

🧑: 王总什么时候来？
🤖: [调用 get_all_note] 根据笔记，王总下午3点开会
```

## 命令支持

在聊天输入框中输入以下命令：

| 命令 | 功能 |
|------|------|
| `/help` | 显示帮助信息 |
| `/tools` | 列出可用工具 |
| `/history` | 显示对话历史 |
| `/reset` | 重置对话 |
| `/clear` | 清空终端屏幕 |

## API 端点

### HTTP 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 主页 |
| `/health` | GET | 健康检查 |
| `/sessions` | GET | 列出活动会话 |

### 健康检查

```bash
$ curl http://localhost:5000/health
{
  "status": "healthy",
  "sessions": 2
}
```

### 会话列表

```bash
$ curl http://localhost:5000/sessions
{
  "count": 2,
  "sessions": {
    "abc123": {
      "sid": "abc123",
      "pty_pid": 12345,
      "pty_running": true,
      "lock_status": {...},
      "message_count": 5
    }
  }
}
```

## 配置

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_API_KEY` | - | OpenAI API 密钥（必需） |
| `TERMBOT_HOST` | `0.0.0.0` | 监听地址 |
| `TERMBOT_PORT` | `5000` | 监听端口 |
| `TERMBOT_DEBUG` | `false` | 调试模式 |
| `SECRET_KEY` | `termbot-secret-key` | Flask 密钥 |

### 自定义配置

创建 `.env` 文件：

```bash
# API 配置
OPENAI_API_KEY=your-api-key-here

# 服务器配置
TERMBOT_HOST=0.0.0.0
TERMBOT_PORT=5000
TERMBOT_DEBUG=false

# Flask 配置
SECRET_KEY=your-secret-key-here
```

## 故障排查

### 问题：无法连接到服务器

**检查**：
1. 服务器是否正在运行
2. 防火墙是否阻止了连接
3. 端口是否被占用

**解决方案**：
```bash
# 检查端口占用
lsof -i :5000

# 更换端口
TERMBOT_PORT=5001 python web.py
```

### 问题：终端不响应

**可能原因**：
1. PTY 进程崩溃
2. Agent 正在执行命令（锁等待）
3. 网络连接问题

**解决方案**：
1. 刷新页面重新连接
2. 检查服务器日志

### 问题：AI 不回复

**可能原因**：
1. API Key 未设置或无效
2. 网络连接问题
3. API 配额用尽

**解决方案**：
1. 检查 `.env` 文件中的 API Key
2. 查看 `/health` 端点状态
3. 检查 OpenAI 账户状态

### 问题：多用户冲突

**检查**：
- 理论上不会冲突（每个会话独立）
- 如果出现问题，请确认是否使用同一浏览器标签

## 部署

### 生产环境部署

使用 Gunicorn 或 uWSGI：

```bash
# 安装 gunicorn
pip install gunicorn

# 启动
gunicorn -k gevent --worker-connections 1000 --bind 0.0.0.0:5000 web:create_app()
```

### Docker 部署

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt

EXPOSE 5000

CMD ["python", "web.py"]
```

## 相关文档

- [CLI 模式使用指南](CLI.md)
- [项目 README](README.md)
- [架构设计文档](ARCHITECTURE.md)
