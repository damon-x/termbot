# 阶段四：CLI模式与Web集成

## 目标

实现CLI模式和Web界面，完成集成测试

## 任务清单

1. 实现CLI交互层（`interfaces/cli.py`）
2. 实现命令行界面
3. 完成Web模式迁移
4. 集成测试
5. 文档编写

## 验证标准（测试用例）

| 编号 | 测试名称 | 前置步骤 | 操作 | 期望结果 |
|------|---------|---------|------|---------|
| TC-5-1 | CLI模式启动 | CLIHandler已实现 | 运行 `python -m termbot.cli` | 进入CLI交互模式，显示提示符 |
| TC-5-2 | CLI基础对话 | CLI已启动 | 输入 `你好` | 返回AI回复 |
| TC-5-3 | CLI命令执行 | CLI已启动 | 输入 `查看当前目录` | 执行ls命令，显示结果 |
| TC-5-4 | CLI命令模式 | CLI已启动 | 输入 `/help` | 显示帮助信息 |
| TC-5-5 | CLI退出 | CLI已启动 | 输入 `/exit` 或 `Ctrl+D` | 程序正常退出 |
| TC-5-6 | Web模式启动 | Web模式已迁移 | 运行 `python -m termbot.web` | Flask服务器启动，无报错 |
| TC-5-7 | Web终端连接 | Web服务器已启动 | 访问 `http://localhost:5000` | 页面加载，终端显示 |
| TC-5-8 | Web Socket连接 | Web页面已打开 | 浏览器连接WebSocket | 连接成功，终端bash启动 |
| TC-5-9 | Web聊天功能 | Web已连接 | 发送消息 `你好` | 返回AI回复 |
| TC-5-10 | Web终端操作 | Web已连接 | 在终端输入 `ls` | 显示目录列表 |
| TC-5-11 | 集成测试-基础任务 | 系统已启动 | 输入 `查看当前目录有哪些Python文件` | 执行ls *.py，返回结果 |
| TC-5-12 | 集成测试-笔记 | 系统已启动 | 输入 `/note 记录：测试环境IP是10.0.0.1` | 笔记保存成功 |
| TC-5-13 | 集成测试-多轮对话 | 系统已启动 | 依次输入：`SSH到192.168.1.1` → `密码123456` → `查看日志` | 正确执行多步操作 |
| TC-5-14 | 集成测试-终端读取 | 系统已启动 | 在终端执行命令后输入 `解释上面的输出` | AI正确读取并解释 |
| TC-5-15 | 文档完整性 | 所有功能已实现 | 检查 `docs/` 目录 | 存在README.md, API.md, CLI.md, WEB.md |
| TC-5-16 | 快速开始文档 | 文档已编写 | 按照README.md中的快速开始操作 | 可以成功运行项目 |

## 核心设计

### 5.1 CLI交互层

```python
# interfaces/cli.py
import sys
import readline  # 支持命令历史和编辑
from typing import Optional

from interfaces.base import BaseHandler
from agent.core import Agent
from agent.commands import CommandParser


class CLIHandler(BaseHandler):
    """CLI交互层"""

    def __init__(self, agent: Agent):
        super().__init__(agent)
        self.command_parser = CommandParser()
        self.running = False

    def start(self):
        """启动CLI交互"""
        self.running = True
        print("╔════════════════════════════════════════════════════════════╗")
        print("║           TermBot - Intelligent Terminal Assistant       ║")
        print("╚════════════════════════════════════════════════════════════╝")
        print("\n输入 /help 查看可用命令\n")

        while self.running:
            try:
                user_input = input(">>> ").strip()

                if not user_input:
                    continue

                # 检查是否是命令
                if user_input.startswith("/"):
                    result = await self.command_parser.execute(user_input, self.agent.context)
                    print(result.message)

                    # 检查是否需要退出
                    if result.data and result.data.get("action") == "exit":
                        self.stop()
                        break
                else:
                    # 普通消息，发送给Agent
                    response = self.send_message(user_input)
                    print(f"\n{response}\n")

            except KeyboardInterrupt:
                print("\n使用 /exit 或 Ctrl+D 退出")
            except EOFError:
                print("\n再见！")
                self.stop()

    def stop(self):
        """停止CLI交互"""
        self.running = False

    def send_message(self, message: str) -> str:
        """发送消息并获取响应"""
        return self.agent.process_message(message)

    def on_agent_response(self, response: str):
        """Agent响应回调（CLI模式下同步处理，不需要此方法）"""
        pass
```

### 5.2 CLI入口

```python
# cli.py (项目根目录)
import asyncio
from infrastructure.config.settings import Settings
from infrastructure.llm.client import LLMClient
from agent.core import Agent, AgentConfig
from interfaces.cli import CLIHandler


def main():
    """CLI主入口"""
    # 加载配置
    settings = Settings(env="development")

    # 创建LLM客户端
    llm_client = LLMClient(settings)

    # 创建Agent
    agent_config = AgentConfig(
        llm_client=llm_client,
        max_iterations=settings.agent.get("max_iterations", 20),
        enable_memory=settings.agent.get("enable_memory", True),
        enable_mcp=settings.agent.get("enable_mcp", True)
    )
    agent = Agent(agent_config)

    # 启动CLI
    cli = CLIHandler(agent)
    cli.start()


if __name__ == "__main__":
    main()
```

### 5.3 Web交互层（迁移后）

**重要架构原则：1 Web Session = 1 Agent 实例 = 1 PTY 实例**

每个 WebSocket 连接（用户浏览器窗口）都有独立的：
- Agent 实例（独立的 Context 和对话历史）
- PTY Manager（独立的终端）
- 会话状态

```python
# interfaces/web.py
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from interfaces.base import BaseHandler
from agent.core import Agent
from agent.commands import CommandParser
from infrastructure.terminal.pty_manager import PTYManager


class WebHandler:
    """Web交互层 - 管理多个用户会话"""

    def __init__(self, socketio: SocketIO, llm_client):
        """初始化Web处理器

        注意：这里只共享 LLM Client（无状态）
        每个 Session 会创建独立的 Agent 和 PTY
        """
        self.socketio = socketio
        self.shared_llm_client = llm_client  # 共享LLM客户端
        self.sessions = {}  # sid -> {agent, pty, ...}
        self._register_routes()

    def _register_routes(self):
        """注册路由和事件处理器"""

        @self.socketio.on('connect')
        def handle_connect():
            """新客户端连接 - 创建独立的 Agent + PTY"""
            sid = request.sid
            print(f"Client connected: {sid}")

            # 1. 创建独立的 PTY Manager
            pty_manager = PTYManager(shell="/bin/bash", cols=80, rows=24)
            pty_manager.start()

            # 2. 创建独立的 Agent 实例
            agent_config = AgentConfig(
                llm_client=self.shared_llm_client,  # 共享LLM
                max_iterations=20,
                enable_memory=True,
                enable_mcp=False  # MCP在阶段五
            )
            agent = ReactAgent(agent_config)

            # 3. Agent 绑定这个 PTY
            terminal_tool = TerminalTool(pty_manager, agent_id=f"web_{sid}")
            agent.register_tool(terminal_tool)

            # 4. 注册 PTY 输出监听器（推送到前端）
            pty_manager.register_listener(
                lambda data: self._on_terminal_output(sid, data)
            )

            # 5. 保存会话
            self.sessions[sid] = {
                'agent': agent,
                'pty_manager': pty_manager,
                'terminal_tool': terminal_tool
            }

            emit('connected', {'message': 'Terminal started'})

        @self.socketio.on('disconnect')
        def handle_disconnect():
            """客户端断开 - 清理 Agent 和 PTY"""
            sid = request.sid
            print(f"Client disconnected: {sid}")

            if sid in self.sessions:
                session = self.sessions[sid]

                # 停止 PTY
                session['pty_manager'].stop()

                # 清理会话
                del self.sessions[sid]

        @self.socketio.on('chat_message')
        def handle_chat_message(data):
            """处理聊天消息"""
            sid = request.sid
            message = data.get('message', '')

            if sid not in self.sessions:
                emit('chat_response', {'message': 'Session not found'})
                return

            agent = self.sessions[sid]['agent']

            # 发送给该会话的 Agent
            response = agent.process_message(message)
            emit('chat_response', {'message': response})

        @self.socketio.on('terminal_input')
        def handle_terminal_input(data):
            """处理终端输入"""
            sid = request.sid
            user_input = data.get('data', '')

            if sid not in self.sessions:
                return

            pty_manager = self.sessions[sid]['pty_manager']

            # 写入该会话的 PTY
            result = pty_manager.write_web(user_input, sid)

            if not result.success:
                emit('terminal_error', {'message': result.message})

    def _on_terminal_output(self, sid: str, data: str):
        """PTY输出回调 - 推送到指定会话的前端"""
        self.socketio.emit('terminal_output', {'data': data}, room=sid)
```

### 5.4 Web入口（迁移后）

```python
# web.py (项目根目录)
from flask import Flask
from flask_socketio import SocketIO
from infrastructure.config.settings import Settings
from infrastructure.llm.client import LLMClient
from interfaces.web import WebHandler


def create_app():
    """创建Flask应用"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your-secret-key'

    # 创建SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

    # 加载配置
    settings = Settings(env="development")

    # 创建共享的 LLM 客户端（无状态，可共享）
    llm_client = LLMClient(settings)

    # 创建Web处理器（不创建Agent，等连接时再创建）
    web_handler = WebHandler(socketio, llm_client)
    web_handler.app = app

    return app, socketio


if __name__ == "__main__":
    app, socketio = create_app()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
```

### 5.5 集成测试

```python
# tests/integration/test_cli.py
import pytest
from interfaces.cli import CLIHandler
from agent.core import Agent, AgentConfig
from infrastructure.llm.client import LLMClient


class TestCLIIntegration:
    """CLI集成测试"""

    @pytest.fixture
    def agent(self):
        """创建测试Agent"""
        # 使用mock LLM客户端
        llm_client = MockLLMClient()
        config = AgentConfig(llm_client=llm_client)
        return Agent(config)

    def test_cli_start(self, agent):
        """测试CLI启动"""
        cli = CLIHandler(agent)
        assert cli.running == False

    def test_basic_conversation(self, agent):
        """测试基础对话"""
        response = agent.process_message("你好")
        assert isinstance(response, str)
        assert len(response) > 0

    def test_command_execution(self, agent):
        """测试命令执行"""
        response = agent.process_message("查看当前目录")
        assert isinstance(response, str)


# tests/integration/test_web.py
class TestWebIntegration:
    """Web集成测试"""

    def test_web_start(self):
        """测试Web启动"""
        app, socketio = create_app()
        assert app is not None
        assert socketio is not None

    def test_terminal_connection(self):
        """测试终端连接"""
        # 测试WebSocket连接和PTY启动
        pass
```

### 5.6 文档结构

```
docs/
├── README.md              # 项目概述和快速开始
├── API.md                 # API文档
├── CLI.md                 # CLI模式使用指南
├── WEB.md                 # Web模式使用指南
├── ARCHITECTURE.md        # 架构设计文档
├── REFACTOR_PLAN.md       # 重构计划总览
├── PHASE_1_BASIC_REFACTOR.md
├── PHASE_2_AGENT_CORE.md
├── PHASE_3_LLM_TERMINAL.md
├── PHASE_4_CLI_INTEGRATION.md
└── PHASE_5_MCP_COMMANDS.md
```

### 5.7 README示例

```markdown
# TermBot

智能终端助手 - 通过AI理解你的意图并执行终端命令

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置

1. 复制配置文件模板
```bash
cp config/default.json config/development.json
```

2. 配置LLM API密钥
```bash
export OPENAI_API_KEY="your-api-key"
```

### CLI模式

```bash
python -m termbot.cli
```

### Web模式

```bash
python -m termbot.web
```

然后访问 http://localhost:5000

## 功能特性

- 🤖 **AI智能理解**: 通过LLM理解自然语言指令
- 💻 **终端操作**: 自动执行终端命令
- 📝 **笔记管理**: 记录和查询重要信息
- 🔧 **MCP支持**: 集成第三方MCP服务
- 🎯 **命令模式**: 支持快捷命令
- 🖥️ **双模式**: CLI和Web两种使用方式

## 命令参考

| 命令 | 说明 |
|------|------|
| /help | 显示帮助信息 |
| /clear | 清空对话历史 |
| /tools | 列出可用工具 |
| /note | 添加笔记 |
| /config | 查看配置 |
| /exit | 退出程序 |

更多文档请查看 [docs/](docs/)
```

## 详细步骤

### Step 5.1: 实现CLIHandler
创建 `interfaces/cli.py`

### Step 5.2: 创建CLI入口
创建 `cli.py`

### Step 5.3: 迁移Web模式
将现有Web代码迁移到新架构

### Step 5.4: 实现WebHandler
重构 `interfaces/web.py`

### Step 5.5: 创建Web入口
创建 `web.py`

### Step 5.6: 编写集成测试
创建完整的集成测试套件

### Step 5.7: 编写文档
编写所有文档

### Step 5.8: 端到端测试
执行所有验证测试用例

## 验收检查表

- [ ] CLI模式实现完成
- [ ] Web模式迁移完成
- [ ] 集成测试通过
- [ ] 文档编写完成
- [ ] 功能验证通过
- [ ] 所有TC-5-x测试用例通过

## 估计工作量

3-4天
