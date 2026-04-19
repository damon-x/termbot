# TermBot 产品说明书

## 产品简介

TermBot 是一个基于 AI 的智能终端助手，通过自然语言理解和执行终端命令，让用户以对话方式操作系统、管理文件、查询信息和自动化任务。

产品提供 **Web 界面**，支持多用户同时使用，每个用户拥有完全独立的 AI 助手实例和终端环境。

---

## 核心能力

### 终端操作
用自然语言描述任务，AI 自动生成并执行命令。

- 执行 Shell 命令，实时输出结果
- 跨平台支持（Linux / macOS / Windows）
- 内置完整的 PTY（伪终端），支持交互式程序
- 终端尺寸自适应

**示例**：
> "查看当前目录下最大的 10 个文件"
> "安装 Python 依赖 requests"
> "统计日志文件里 ERROR 出现的次数"

---

### 文件管理
- 读取文件内容（支持大文件分页）
- 写入 / 创建文件
- 按字符串替换编辑文件

---

### 长期记忆（Notes）
AI 助手可以记住用户提供的信息，在后续对话中调用。

- 添加笔记，支持标签分类
- 混合检索：语义搜索 + 关键词匹配
- 编辑、删除笔记
- 软删除（可恢复）

**示例**：
> "记住我们的测试服务器地址是 192.168.1.100"
> "把这次排查思路记下来"

---

### Skills（技能插件）
Skills 是可扩展的专项能力模块，每个 Skill 是一个独立目录，通过 Markdown 文件描述其功能和执行逻辑。

**执行模式**：
- **Agent 模式**：启动独立子 Agent 处理任务
- **Inject 模式**：将技能指令注入当前 Agent 执行

**特性**：
- 热更新：文件修改立即生效
- 可动态启用 / 禁用
- AI 自动匹配用户需求并选择合适的 Skill

---

### 异步任务（Sub-Agent）
支持创建异步子 Agent，在后台并行执行任务，不阻塞当前对话。

---

## Web 界面

### 启动方式

```bash
.venv/bin/python web.py
```

默认监听 `0.0.0.0:5000`，通过浏览器访问。

可通过环境变量自定义：
```bash
TERMBOT_HOST=127.0.0.1 TERMBOT_PORT=8080 .venv/bin/python web.py
```

---

### 界面布局

Web 界面分为两个面板：
- **左侧：对话面板** — 与 AI 助手对话，查看任务进展
- **右侧：终端面板** — 实时显示命令执行输出，支持直接输入

两个面板之间的分隔线可拖动调整宽度。

---

### 对话操作

在对话输入框中输入自然语言，AI 会自动规划并执行任务。

AI 在执行过程中会实时反馈进展（ReAct 模式：思考 → 行动 → 观察 → 继续）。

---

### 斜杠命令

在对话输入框中输入以下命令进行控制：

| 命令 | 说明 |
|------|------|
| `/help` | 查看所有可用命令 |
| `/tools` | 列出当前可用工具 |
| `/skills` | 列出当前已启用的技能 |
| `/skill enable <名称>` | 启用某个技能 |
| `/skill disable <名称>` | 禁用某个技能 |
| `/history` | 查看当前会话消息数量 |
| `/reset` | 清空当前对话历史，开始新对话 |
| `/stop` | 中断正在执行的 AI 任务 |
| `/clear` | 清空当前对话上下文 |

---

### Agent 配置

系统支持多个 Agent 配置文件，不同配置可赋予 AI 不同的角色、权限和工具集。

**内置默认 Agent**：
- 名称：`TERMBOT`
- 默认开放全部工具

**自定义 Agent**：
- 可设置自定义系统提示词
- 可限定允许使用的工具列表
- 可限定允许使用的技能列表
- 通过 REST API 管理（创建 / 修改 / 删除）
- 连接时通过 URL 参数 `?agent_id=<id>` 指定使用哪个 Agent

---

### 会话历史

每次对话自动持久化存储（JSONL 格式），支持：
- 查看历史对话列表（按 Agent 分类，按时间倒序）
- 加载历史对话，恢复上下文继续工作
- 新消息追加至原始会话文件

存储路径：`~/.termbot/conversations/<agent_id>/<session_id>/chat.jsonl`

---

## 多用户会话隔离

每个 WebSocket 连接对应完全独立的运行环境：

| 组件 | 隔离方式 | 说明 |
|------|---------|------|
| AI Agent 实例 | 每会话独立 | 独立的对话历史和上下文 |
| PTY 终端 | 每会话独立 | 独立的 Shell 进程 |
| 笔记 / 记忆 | 每会话独立 | 用户数据相互隔离 |
| LLM 客户端 | 共享 | 无状态，仅负责 API 调用 |

---

## REST API

| 路径 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查，返回当前会话数 |
| `/sessions` | GET | 列出所有活跃会话 |
| `/api/agents` | GET | 获取所有 Agent 配置 |
| `/api/agents` | POST | 创建新 Agent 配置 |
| `/api/agents/<id>` | PUT | 更新 Agent 配置 |
| `/api/agents/<id>` | DELETE | 删除 Agent 配置 |
| `/api/skills` | GET | 获取已启用技能列表 |
| `/api/tools` | GET | 获取完整工具注册表 |
| `/api/conversations/<agent_id>` | GET | 列出历史会话 |
| `/api/conversations/<agent_id>/<session_id>` | GET | 获取某次会话所有消息 |

---

## 环境配置

在项目根目录创建 `.env` 文件：

```bash
OPENAI_API_KEY=your-api-key-here   # 必填，LLM API 密钥
SECRET_KEY=your-secret-key          # Flask Session 密钥（可选，自动生成）
TERMBOT_HOST=0.0.0.0               # 监听地址（默认 0.0.0.0）
TERMBOT_PORT=5000                   # 监听端口（默认 5000）
TERMBOT_DEBUG=false                 # Debug 模式（默认 false）
```

---

## 数据存储路径

| 数据类型 | 路径 |
|--------|------|
| 对话记录 | `~/.termbot/conversations/` |
| Agent 配置 | `~/.termbot/agents/` |
| 技能插件 | `~/.termbot/skills/` |
| 笔记数据库 | `data/termbot.db` |
| 向量索引 | `data/faiss/` |

---

## 技术栈

| 层次 | 技术 |
|------|------|
| 后端框架 | Flask + Flask-SocketIO |
| AI 推理 | OpenAI 兼容 API（支持多种模型） |
| 终端模拟 | PTY（伪终端） |
| 向量搜索 | FAISS + Dashscope Embedding |
| 全文检索 | Whoosh + jieba 中文分词 |
| 持久化 | SQLite + JSONL |

---

*文档生成日期：2026-04-14*
