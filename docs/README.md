# TermBot

智能终端助手 - 通过AI理解你的意图并执行终端命令

> 采用现代化的架构设计，实现 Agent 核心与交互层的完全解耦。

## ✨ 特性

- 🤖 **AI智能理解**: 通过 LLM 理解自然语言指令
- 💻 **真实终端执行**: 基于 PTY 的真实终端命令执行
- 📝 **笔记管理**: 记录和查询重要信息
- 🎯 **多工具支持**: 内置9种工具，可扩展
- 🖥️ **双模式**: CLI 和 Web 两种使用方式
- 🔒 **会话隔离**: 每个会话独立的 Agent 和终端

## 🚀 快速开始

### 1. 安装依赖

```bash
# 激活虚拟环境
source .venv/bin/activate

# 安装依赖（如果还没有）
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
# 复制并编辑 .env 文件
cp .env.example .env

# 编辑 .env 文件，设置你的 API Key
# OPENAI_API_KEY=your-api-key-here
```

### 3. 运行模式

#### CLI 模式

```bash
# 方式1：使用快速启动脚本
./start.sh

# 方式2：直接运行 Python
python cli.py

# 方式3：作为模块运行
python -m termbot.cli
```

#### Web 模式

```bash
# 启动 Web 服务器
python web.py

# 然后访问 http://localhost:5000
```

## 📖 使用指南

### CLI 模式

CLI 模式提供交互式命令行界面：

```bash
$ ./start.sh

╔════════════════════════════════════════════════════════════╗
║           TermBot - AI Terminal Assistant                 ║
╚════════════════════════════════════════════════════════════╝

Available commands:
  /help     - Show this help message
  /tools    - List available tools
  /history  - Show conversation history
  /reset    - Reset conversation
  /quit     - Exit the session

🧑 You: 查看当前目录的Python文件
🤖 Agent: [执行 exec_terminal_cmd]
```

### Web 模式

Web 模式提供浏览器界面：

- **左侧**: Web 终端（基于 xterm.js）
- **右侧**: AI 助手对话面板
- **支持**: 多用户同时使用，每个用户独立的会话

## 🛠️ 可用工具

| 工具 | 功能 |
|------|------|
| `exec_terminal_cmd` | 执行终端命令（真实执行） |
| `add_note` | 记录笔记 |
| `get_all_note` | 获取所有笔记 |
| `send_msg_to_user` | 发送消息给用户 |
| `create_quick_cmd` | 创建快捷命令 |
| `get_all_quick_cmd` | 获取所有快捷命令 |
| `search_weather` | 查询天气 |
| `send_email` | 发送邮件 |
| `send_file_user` | 发送文件给用户 |

## 📁 项目结构

```
termbot/
├── agent/              # Agent 核心逻辑
│   ├── core.py         # Agent 主类
│   ├── react.py        # ReAct 循环实现
│   ├── context.py      # 执行上下文
│   ├── tools/          # 工具实现
│   └── prompts/        # 提示词管理
├── infrastructure/     # 基础设施
│   ├── llm/           # LLM 客户端
│   ├── terminal/      # PTY 管理
│   └── config/        # 配置管理
├── interfaces/        # 交互层
│   ├── base.py        # 基类
│   ├── cli.py         # CLI 交互
│   └── web.py         # Web 交互
├── tests/             # 测试
│   ├── unit/          # 单元测试
│   └── integration/   # 集成测试
├── docs/              # 文档
├── config/            # 配置文件
├── cli.py             # CLI 入口
├── web.py             # Web 入口
└── start.py           # 快速启动脚本
```

## 🔧 架构设计

### 核心原则

**1 Web Session = 1 Agent 实例 = 1 PTY 实例**

每个用户会话都有独立的：
- Agent 实例（独立的 Context 和对话历史）
- PTY Manager（独立的终端）
- 会话状态

```
WebHandler (多会话管理)
    ├── Session A → Agent A + PTY A → 用户A的窗口
    ├── Session B → Agent B + PTY B → 用户B的窗口
    └── Session C → Agent C + PTY C → 用户C的多标签页
```

### 共享 vs 独立

| 组件 | 多会话策略 | 原因 |
|------|-----------|------|
| LLM Client | ✅ 共享 | 无状态，只是调用 API |
| Agent 实例 | ❌ 独立 | 有状态（Context、对话历史） |
| PTY Manager | ❌ 独立 | 每个会话独立终端 |
| Memory/笔记 | ❌ 独立 | 用户数据隔离 |

## 📚 详细文档

- [CLI 模式使用指南](docs/CLI.md)
- [Web 模式使用指南](docs/WEB.md)
- [架构设计文档](docs/ARCHITECTURE.md)
- [重构计划](docs/REFACTOR_PLAN.md)

## 🧪 运行测试

```bash
# 单元测试
pytest tests/unit/

# 集成测试
pytest tests/integration/

# 带覆盖率报告
pytest --cov=agent --cov=infrastructure tests/
```

## 🗺️ 开发路线图

- [x] **阶段一**: 基础重构（代码规范与模块拆分）
- [x] **阶段二**: Agent 核心解耦
- [x] **阶段三**: LLM 调用优化与终端管理
- [x] **阶段四**: CLI 模式与 Web 集成
- [ ] **阶段五**: MCP 支持与命令模式

## 🤝 贡献

欢迎贡献！请查看 [重构计划](docs/REFACTOR_PLAN.md) 了解当前进度。

## 📄 许可证

MIT License

## 🙏 致谢

本项目基于原 [TermBot](https://github.com/yourusername/termbot) 项目重构而来。
