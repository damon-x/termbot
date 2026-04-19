# TermBot 重构方案

## 一、项目现状分析

### 1.1 项目概述

TermBot (/Users/lixubo/work/termbot ) 是一个智能终端助手项目，核心功能是通过 PTY 操作和读取终端内容，实现不受本机环境束缚的远程终端操作（如 SSH 到远程机器）。

### 1.2 核心功能清单

| 功能模块 | 描述 | 实现位置 |
|---------|------|---------|
| Web终端 | 基于xterm.js的Web终端，支持多标签页 | app.py + static/index.html |
| AI助手对话 | 右侧聊天面板，与AI助手对话 | bot/agent.py |
| 智能任务执行 | 通过LLM理解用户意图并执行终端命令 | bot/ability/basic.py:LLMComponent |
| 笔记管理 | SQLite存储用户笔记，支持搜索 | bot/memary/long_memory.py |
| 快捷命令 | 预定义命令模板，支持嵌入向量检索 | bot/memary/quick_command.py |
| 经验学习 | 从任务执行中学习经验 | bot/memary/experience.py |
| PTY操作 | 通过pty.fork()创建伪终端 | app.py |
| 文本搜索 | Whoosh + jieba分词 | bot/common.py:TextSearch |
| 向量检索 | FAISS向量数据库 | bot/memary/embed_db.py |

### 1.3 现有问题分析

#### 1.3.1 代码规范问题
- 命名不规范（如`memary`应为`memory`，`satrtChat`拼写错误）
- 缺少类型注解
- 导入顺序混乱
- 注释和文档字符串不完整

#### 1.3.2 架构问题
- **Agent与交互层耦合严重**: `agent.py`直接依赖`SocketClient`和Flask相关代码
- **React循环逻辑混乱**: 多个Component循环调用LLM，逻辑分散
- **终端内容获取不合理**: 需要前端把xterm.js内容通过socket传回，后端被动等待
- **工具实现方式不统一**: `tools.py`和`ability/basic.py`都有工具定义

#### 1.3.3 功能缺失
- 无统一的配置管理
- 无CLI模式支持

## 二、重构目标

1. **代码规范**: 按PEP 8规范重构Python代码
2. **解耦架构**: Agent核心逻辑与交互层分离
3. **优化LLM调用**: 重构React循环，使用标准Function Calling
4. **模块化设计**: 统一工具抽象，清晰的模块边界
5. **优化终端获取**: 后端直接从pty读取，不依赖前端
6. **提示词优化**: 可选优化为英文，保持文件维护方式
7. **CLI支持**: Agent层可独立运行

## 三、架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Application Layer                         │
├───────────────┬─────────────────────────────────────────────────┤
│   Web Mode    │                  CLI Mode                        │
│  (Flask+WS)   │              (Interactive Shell)                │
└───────┬───────┴─────────────────────────────────────────────────┘
        │
┌───────▼─────────────────────────────────────────────────────────┐
│                     Presentation Layer                          │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │  WebHandler    │  │   CLIHandler   │  │  EventHandler  │   │
│  └────────┬───────┘  └────────┬───────┘  └────────┬───────┘   │
└───────────┼──────────────────┼──────────────────┼──────────────┘
            │                  │                  │
┌───────────▼──────────────────▼──────────────────▼──────────────┐
│                      Agent Core Layer                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    ReactAgent                             │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │  │
│  │  │  Planner   │  │  Executor  │  │  Observer  │        │  │
│  │  └────────────┘  └────────────┘  └────────────┘        │  │
│  └───────────────────────────┬──────────────────────────────┘  │
│                              │                                  │
│  ┌───────────────────────────▼──────────────────────────────┐  │
│  │                    Tool Registry                          │  │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌─────┐  │  │
│  │  │Note │ │Cmd  │ │Term │ │File │ │MCP  │ │User │  │  │
│  │  │Tool │ │Tool │ │Tool │ │Tool │ │Tool │ │Tool │  │  │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └─────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    Infrastructure Layer                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │   LLM    │  │ Terminal │  │  Memory  │  │  MCP Client   │  │
│  │  Client  │  │  Manager │  │  Manager │  │               │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.1.1 会话隔离原则

**核心设计原则：1 Web Session = 1 Agent 实例 = 1 PTY 实例**

```
WebHandler (多会话管理)
    │
    ├── Session A (sid="abc123")
    │   ├── Agent A (独立Context、独立对话历史)
    │   │   └── TerminalTool → PTY A (独立终端)
    │   └── 用户A的浏览器窗口
    │
    ├── Session B (sid="def456")
    │   ├── Agent B (独立Context、独立对话历史)
    │   │   └── TerminalTool → PTY B (独立终端)
    │   └── 用户B的浏览器窗口
    │
    └── Session C (sid="ghi789")
        ├── Agent C (独立Context、独立对话历史)
        │   └── TerminalTool → PTY C (独立终端)
        └── 用户C的多标签页2
```

**为什么每个会话需要独立的 Agent？**

| 问题 | 共享 Agent 的后果 |
|------|------------------|
| 📝 **对话历史混乱** | 用户A的对话混到用户B的回复中 |
| 🧠 **笔记查询错误** | 用户A问"王总怎么过来"，查到用户B的笔记 |
| ⚡ **任务冲突** | 多用户同时下达命令，Agent不知道执行谁的 |
| 🔒 **状态污染** | Context 状态完全混乱 |

**共享 vs 独立：**

| 组件 | 多会话策略 | 原因 |
|------|-----------|------|
| LLM Client | ✅ 共享 | 无状态，只是调用API |
| Agent 实例 | ❌ 独立 | 有状态（Context、对话历史） |
| PTY Manager | ❌ 独立 | 每个会话独立终端 |
| Memory/笔记 | ❌ 独立 | 用户数据隔离 |

### 3.2 核心模块设计

#### 3.2.1 Agent核心模块 (`agent/`)

```
agent/
├── __init__.py
├── core.py              # Agent核心类，与交互层解耦
├── react.py             # React循环实现
├── context.py           # 执行上下文
├── tools/               # 工具定义
│   ├── __init__.py
│   ├── base.py          # 工具基类
│   ├── terminal.py      # 终端操作工具
│   ├── note.py          # 笔记工具
│   ├── file.py          # 文件操作工具
│   └── mcp.py           # MCP工具适配器
├── memory/              # 记忆模块
│   ├── __init__.py
│   ├── base.py          # 记忆基类
│   ├── short_term.py    # 短期记忆
│   ├── long_term.py     # 长期记忆（笔记）
│   └── experience.py    # 经验记忆
└── prompts/             # 提示词管理
    ├── __init__.py
    └── templates.txt    # 提示词模板
```

#### 3.2.2 交互层 (`interfaces/`)

```
interfaces/
├── __init__.py
├── base.py              # 交互层基类
├── web.py               # Web交互实现
├── cli.py               # CLI交互实现
└── terminal.py          # 终端管理器
```

#### 3.2.3 基础设施层 (`infrastructure/`)

```
infrastructure/
├── __init__.py
├── llm/
│   ├── __init__.py
│   ├── client.py        # LLM客户端
│   └── function_calling.py # Function Calling支持
├── terminal/
│   ├── __init__.py
│   ├── pty_manager.py   # PTY管理
│   └── buffer.py        # 终端缓冲区
├── memory/
│   ├── __init__.py
│   ├── database.py      # 数据库管理
│   └── vector.py        # 向量存储
└── config/
    ├── __init__.py
    └── settings.py      # 配置管理
```

## 四、重构阶段概览

本重构分为4个阶段，预计需要14-18个工作日完成：

| 阶段 | 名称 | 工作量 | 文档 |
|------|------|--------|------|
| 阶段一 | 基础重构（代码规范与模块拆分） | 3-4天 | [PHASE_1_BASIC_REFACTOR.md](PHASE_1_BASIC_REFACTOR.md) |
| 阶段二 | Agent核心解耦 | 4-5天 | [PHASE_2_AGENT_CORE.md](PHASE_2_AGENT_CORE.md) |
| 阶段三 | LLM调用优化与终端管理 | 4-5天 | [PHASE_3_LLM_TERMINAL.md](PHASE_3_LLM_TERMINAL.md) |
| 阶段四 | CLI模式与Web集成 | 3-4天 | [PHASE_4_CLI_INTEGRATION.md](PHASE_4_CLI_INTEGRATION.md) |

各阶段的详细内容请查看对应文档。
