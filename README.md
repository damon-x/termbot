# TermBot

**智能终端助手** —— 用自然语言控制你的终端

TermBot 是一个基于 AI 的终端助手，能够理解你的自然语言指令并直接在真实终端中执行操作。提供多用户 Web 界面，内置长期记忆管理和可扩展的工具系统。

![Web 界面](markdown-test.jpg)

---

## ✨ 特性

- **自然语言控制终端** —— 直接用中文或英文描述你想做的事，Agent 会自动分析并执行
- **真实 PTY 终端** —— 基于伪终端（PTY）在真实 shell 中执行命令
- **ReAct 推理模式** —— 先思考再行动，每步骤均可见，结果可追踪
- **长期记忆管理** —— 支持笔记、经验、快捷命令的持久化存储和语义搜索
- **Skills 技能系统** —— 可插拔的专项能力模块，按需启用
- **双模式运行** —— Web 多用户模式（会话完全隔离）+ CLI 单用户交互模式
- **兼容主流 LLM** —— 支持任意 OpenAI 兼容 API（OpenAI、DeepSeek、通义千问、GLM 等）


---

## 📸 截图

| Web 界面（终端 + 对话） | Markdown 渲染 |
|---|---|
| ![Web](markdown-test.jpg) | ![Markdown](markdown-render-success.jpg) |

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- 支持 PTY 的系统（Linux / macOS；Windows 需要 WSL）

### 安装

```bash
git clone https://github.com/your-username/termbot.git
cd termbot
pip install -r requirements.txt
```

### 配置

复制环境变量模板并填写你的 API 信息：

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 LLM API 配置：

```bash
# 选择 Provider: openai（OpenAI 兼容接口）或 anthropic（Anthropic 原生接口）
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
```

#### OpenAI 兼容接口（`LLM_PROVIDER=openai`）

支持任意兼容 OpenAI 格式的服务：

| 服务 | `LLM_BASE_URL` | 参考模型 |
|------|----------------|---------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 通义千问（DashScope） | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-max` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4` |

#### Anthropic 原生接口（`LLM_PROVIDER=anthropic`）

```bash
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-your-api-key
LLM_BASE_URL=https://api.anthropic.com
LLM_MODEL=claude-sonnet-4-5
```

#### 可选：语义记忆搜索

配置 Embedding API 后，记忆系统将支持语义搜索（当前仅支持 DashScope）。不配置时自动降级为关键词搜索。

```bash
EMBEDDING_API_KEY=sk-your-dashscope-key
RERANK_API_KEY=sk-your-dashscope-key
```

---

## 💻 使用方式

### Web 模式（推荐）

```bash
python web.py
# 或自定义地址
TERMBOT_HOST=127.0.0.1 TERMBOT_PORT=8080 python web.py
```

访问 `http://localhost:5000`，界面包含：
- **左侧**：真实终端（xterm.js），可直接操作
- **右侧**：AI 对话面板，支持 Markdown 渲染

支持多用户同时使用，每个连接会话完全隔离（独立 Agent + 独立终端进程）。

#### 自定义 Agent

Web 界面支持创建多个自定义 Agent，每个 Agent 运行在独立的标签页中：

1. 点击界面顶部的 **「+ 添加 Agent」** 按钮
2. 填写 Agent 名称和系统提示词（定义 Agent 的角色和专长）
3. 可选限定该 Agent 允许使用的**工具**和 **Skills**（留空表示允许全部）
4. 创建后即可在标签页间自由切换

自定义 Agent 配置持久化存储在 `~/.termbot/agents/`，重启后自动恢复。

**应用场景举例：**

| Agent 名称 | 系统提示词方向 | 限定工具 |
|------------|----------------|----------|
| Python 专家 | 专注 Python 开发，代码风格严格 | 终端、文件读写 |
| 运维助手 | 专注服务器运维，谨慎操作生产环境 | 仅终端命令 |
| 文档助手 | 专注文档整理，不执行命令 | 仅笔记、文件 |

**Web 界面命令：**

```
/tools                  列出可用工具
/skills                 列出技能
/skill enable <名称>    启用技能
/skill disable <名称>   禁用技能
/history                查看消息历史数量
/reset                  清空对话上下文
/stop                   中断 AI 任务
/clear                  清空上下文
```

### CLI 模式

```bash
python cli.py
```

启动后进入交互界面，直接输入自然语言即可：

```
You: 帮我查看当前目录下最大的10个文件
You: 把 /tmp/logs 下所有超过7天的日志文件压缩打包
You: 监控 CPU 使用率，超过 80% 告诉我
```

**CLI 内置命令：**

```
/help     查看帮助
/tools    列出可用工具
/skills   查看技能列表
/history  查看对话历史
/reset    清空当前对话
/stop     中断正在运行的任务
/quit     退出程序
```

---

## 🛠️ 内置工具

| 工具 | 说明 |
|------|------|
| `exec_terminal_cmd` | 在 PTY 终端中执行 shell 命令 |
| `add_memory` | 添加笔记、经验或命令到长期记忆 |
| `search_memory` | 混合搜索（关键词 + 语义），支持标签过滤 |
| `list_notes` | 列出所有笔记（支持分页） |
| `edit_note` | 编辑笔记内容和标签 |
| `delete_note` | 删除笔记 |
| `send_msg_to_user` | 向用户发送消息，支持等待回复 |
| `ask_user` | 向用户提问并暂停执行等待回答 |
| `send_file_user` | 发送文件给用户 |
| `get_system_info` | 获取系统信息（CPU、内存、OS） |
| `search_weather` | 查询天气（示例实现） |
| `send_email` | 发送邮件（示例实现） |

---

## 🧠 工作原理

TermBot 采用 **ReAct（Reasoning + Acting）** 模式：

```
用户输入
   ↓
[Think]  LLM 分析请求，选择合适的工具
   ↓
[Act]    调用工具执行（终端命令、记忆查询等）
   ↓
[Observe] 获取执行结果，加入对话上下文
   ↓
重复循环，直到任务完成
```

每一步的思考过程和操作结果都会实时显示，过程完全透明可追踪。

---

## 📁 项目结构

```
termbot/
├── agent/                  # Agent 核心（与界面无关）
│   ├── core.py             # Agent 主类
│   ├── react.py            # ReAct 循环实现
│   ├── context.py          # 对话上下文管理
│   └── tools/              # 工具系统
│       ├── base.py         # 工具基类和注册表
│       ├── terminal.py     # 终端工具
│       └── impl.py         # 内置工具实现
├── infrastructure/         # 基础设施层
│   ├── llm/                # LLM 客户端（OpenAI 兼容）
│   ├── terminal/           # PTY 管理器
│   ├── memory/             # 向量数据库 + 全文检索
│   └── config/             # 配置管理
├── interfaces/             # 界面层
│   ├── cli.py              # CLI 交互处理
│   └── web.py              # Web/SocketIO 处理
├── config/                 # 配置文件
│   ├── default.json        # 默认配置
│   └── development.json    # 开发环境配置
├── static/                 # Web 前端静态资源
├── templates/              # HTML 模板
├── cli.py                  # CLI 入口
└── web.py                  # Web 入口
```

---

## ⚙️ 高级配置

### Skills 技能系统

Skills 是可插拔的自定义 Agent 模块，让你无需修改代码即可扩展 TermBot 的专项能力。

#### 创建 Skill

在 `~/.termbot/skills/` 下新建一个目录，放入 `SKILL.md` 文件：

```
~/.termbot/skills/
├── pdf-processing/
│   ├── SKILL.md
│   └── scripts/       # 可选：脚本文件
├── git-workflow/
│   ├── SKILL.md
│   └── references/    # 可选：参考文档
└── data-analysis/
    └── SKILL.md
```

**SKILL.md 格式**（YAML frontmatter + Markdown 内容）：

```markdown
---
name: pdf-processing
description: 从 PDF 中提取文本和表格，填写表单，并合并文档
enabled: true
execution_mode: agent
---

# PDF 处理

## 使用场景
当用户需要对 PDF 文件进行操作时使用本技能。

## 操作指南
- 使用 pdfplumber 提取文本型 PDF 内容
- 扫描版 PDF 需配合 OCR 工具（tesseract）
- 合并多个 PDF 使用 pypdf
```

**frontmatter 字段说明：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | ✅ | Skill 唯一名称 |
| `description` | ✅ | 能力描述，LLM 根据此字段匹配用户需求 |
| `enabled` | 否 | 是否启用，默认 `true` |
| `execution_mode` | 否 | `agent`（子 Agent 执行，默认）或 `inject`（注入主 Agent 上下文） |
| `use_independent_pty` | 否 | 是否使用独立终端进程，默认 `false` |

**在 SKILL.md 中引用 Skill 目录**

SKILL.md 内容中可以使用 `${SKILL_DIR}` 变量，加载时会自动替换为该 Skill 所在目录的绝对路径。适合在说明中引用 Skill 附带的脚本：

```markdown
## 使用方式

运行以下命令开始分析：

```bash
${SKILL_DIR}/scripts/run.sh
```
```

#### 使用 Skill

```
/skills                  列出所有已加载的 Skills
/skill enable <名称>     启用某个 Skill
/skill disable <名称>    禁用某个 Skill
```

启用后，Agent 会根据你的自然语言描述自动匹配并调用合适的 Skill，无需手动指定名称。

### 数据存储路径

所有持久化数据存放于用户目录下，不污染项目目录：

| 数据 | 路径 |
|------|------|
| 笔记数据库 | `~/.termbot/memory/termbot.db` |
| 向量索引（FAISS） | `~/.termbot/memory/faiss/` |
| 全文索引（Whoosh） | `~/.termbot/memory/whoosh_index/` |
| 对话记录 | `~/.termbot/conversations/` |
| 日志 | `logs/termbot.log` |

首次启动时以上目录会自动创建，无需手动操作。

---

## 🔧 开发

```bash
# 代码检查
.venv/bin/python3 -m pylint agent/ infrastructure/ interfaces/
.venv/bin/python3 -m mypy agent/ infrastructure/ interfaces/ --ignore-missing-imports

# 运行测试
.venv/bin/python3 -m pytest tests/

# 带覆盖率的测试
.venv/bin/python3 -m pytest --cov=agent --cov=infrastructure tests/
```

---

## 📄 许可证

[MIT License](LICENSE)

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

在贡献代码前，请确保：
- Pylint 分数 ≥ 8.0
- 有相应的测试用例
- 遵循 PEP 8 代码风格
