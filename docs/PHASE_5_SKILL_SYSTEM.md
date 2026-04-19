# Phase 5: Skill System & Sub-Agent Design

## 1. 目的 (Purpose)

扩展 TermBot 的能力边界，通过 **Skill 系统** 和 **子 Agent 机制** 实现：

1. **用户可扩展性**：用户可通过编写 SKILL.md 文件添加专业领域能力，无需修改代码
2. **上下文管理**：专业指令隔离在独立 Agent 中，避免污染主对话上下文
3. **LLM 驱动**：通过 LLM 匹配用户需求与 Skill，无需记忆 skill 名称
4. **代码复用**：主 Agent 和 skill Agent 共用同一套 Agent 代码，通过配置区分角色

## 2. 目标 (Goals)

### 功能目标

- [ ] **SKILL.md 格式支持**：YAML frontmatter + Markdown 内容
- [ ] **Skill 发现与加载**：扫描 `~/.termbot/skills/` 目录
- [ ] **热重载**：每次使用都从文件系统读取，支持实时修改
- [ ] **LLM 智能匹配**：用户自然语言描述需求，LLM 自动找到合适的 skill
- [ ] **子 Agent 执行**：skill 在独立 Agent 中运行，执行完自动清理上下文
- [ ] **共享 PTY**：skill Agent 可以执行命令，与主 Agent 共享 PTY
- [ ] **CLI/Web 统一**：两种接口都支持 skill 功能

### 质量目标

- **零破坏性**：现有功能（终端、笔记、快捷命令等）保持 100% 可用
- **性能无损**：skill 发现和加载不增加启动时间（懒加载）
- **可测试性**：每个阶段都可独立验证

## 3. 改造方案 (Solution)

### 3.1 核心设计

#### Skill 定义

```
~/.termbot/skills/
├── pdf-processing/
│   └── SKILL.md
├── git-workflow/
│   ├── SKILL.md
│   └── scripts/
│       └── setup.sh
└── data-analysis/
    ├── SKILL.md
    └── references/
        └── pandas-guide.md
```

**SKILL.md 格式**：

```markdown
---
name: pdf-processing
description: 从 PDF 中提取文本和表格，填写表单，并合并文档
---

# PDF 处理

## 使用场景
当需要对 PDF 文件进行操作时使用。

## 指令
- 使用 `pdfplumber` 提取文本型 PDF 内容
- 扫描版 PDF 需配合 OCR 工具
```

#### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                      Handler Layer                        │
│  ┌──────────────┐              ┌──────────────┐           │
│  │ CLI Handler  │              │ Web Handler  │           │
│  │  (1 PTY)    │              │ (1 PTY/session)│         │
│  └──────┬───────┘              └──────┬───────┘           │
└─────────┼──────────────────────────────┼───────────────────┘
          │                              │
          └──────────┬───────────────────┘
                     │
          ┌──────────▼─────────────────────┐
          │      AgentFactory              │
          │  - pty_manager (shared)       │
          │  - skill_manager             │
          │  - llm_client (shared)       │
          └──────────┬─────────────────────┘
                     │
         ┌───────────┴──────────┐
         │                      │
    ┌────▼─────┐          ┌────▼──────────┐
    │Main Agent│          │Skill Agent(s)  │
    │role=main│          │role=skill      │
    │Context A │          │Context B (独立) │
    │Tools:   │          │Tools:          │
    │ - term  │          │ - term (共享)  │
    │ - notes │          │ - notes        │
    │ - skill │          │                │
    └──────────┘          └───────────────┘
```

**关键决策**：

1. **代码复用**：Main Agent 和 Skill Agent 都是 `Agent` 类，通过 `role` + `tools` 区分
2. **共享 PTY**：同一次会话中的所有 Agent 共享 PTY（避免资源浪费）
3. **独立 Context**：每个 Agent 有独立的对话历史和状态
4. **热重载**：SkillManager 不缓存内容，每次都读文件

#### 工作流程

```
用户: "帮我从这份 PDF 中提取表格"

[主 Agent ReAct Loop]
  Step 1: LLM 思考 → 需要专业 PDF 处理能力
    Action: search_skill(query="PDF 提取表格")
    Observation: 找到 skill: /pdf-processing

  Step 2: LLM 决定使用 skill
    Action: use_skill(
      skill_name="pdf-processing",
      task="从 my-document.pdf 提取表格"
    )

[创建 Skill Agent]
  - 独立 Context (空对话历史)
  - system_prompt = skill.content
  - tools = [TerminalTool (共享 PTY), NoteTool, ...]
  - 执行 task

[Skill Agent 执行完成]
  - 返回结果
  - Context 自动销毁 (skill 信息不会污染主对话)

[主 Agent 继续]
  Step 3: LLM 收到结果 → 组装最终答案
    Final Answer: 已成功提取 3 个表格...
```

### 3.2 新增模块

```
agent/
├── skills/
│   ├── __init__.py
│   ├── manager.py          # SkillManager (无状态，纯文件操作)
│   ├── skill.py           # Skill 数据类
│   └── loader.py          # SKILL.md 解析器 (YAML + Markdown)
├── tools/
│   ├── skill_search.py    # SkillSearchTool (LLM 匹配)
│   ├── skill_executor.py   # SkillExecutorTool (创建 skill Agent)
│   └── toolsets.py        # 工具集定义 (role → tools)
└── factory.py             # AgentFactory (创建不同角色的 Agent)

infrastructure/
└── ... (无变化)

interfaces/
├── cli.py                # 修改：使用 AgentFactory
└── web.py                # 修改：WebSession 使用 AgentFactory
```

## 4. 分阶段改造步骤 (Implementation Phases)

### Phase 5.1: Skill 基础设施 (3-4 天)

**目标**：建立 Skill 的发现、加载、解析能力

#### 实现内容

**新增文件**：

1. `agent/skills/skill.py` - Skill 数据类
2. `agent/skills/loader.py` - SKILL.md 解析器
3. `agent/skills/manager.py` - SkillManager（无状态，热重载）
4. `tests/unit/test_skill_manager.py` - 单元测试

**详细设计**：

```python
# agent/skills/skill.py
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List

@dataclass
class Skill:
    """Skill 数据类"""
    name: str                          # 从 frontmatter
    description: str                    # 从 frontmatter
    content: str                       # Markdown 内容 (不含 frontmatter)
    path: Path                         # Skill 目录路径
    scripts_dir: Optional[Path] = None  # scripts/ 目录
    references_dir: Optional[Path] = None  # references/ 目录
    assets_dir: Optional[Path] = None   # assets/ 目录
```

```python
# agent/skills/loader.py
import re
import yaml
from pathlib import Path
from typing import Optional

class SkillLoader:
    """SKILL.md 文件加载器"""

    @staticmethod
    def parse_frontmatter(skill_md_path: Path) -> Optional[Dict]:
        """解析 YAML frontmatter"""
        try:
            content = skill_md_path.read_text(encoding='utf-8')
            match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
            if not match:
                return None
            return yaml.safe_load(match.group(1))
        except Exception:
            return None

    @staticmethod
    def load_skill(skill_path: Path) -> Optional[Skill]:
        """加载完整 Skill"""
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            return None

        try:
            content = skill_md.read_text(encoding='utf-8')

            # 解析 frontmatter
            match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
            if not match:
                return None

            frontmatter = yaml.safe_load(match.group(1))

            # 验证必需字段
            if "name" not in frontmatter or "description" not in frontmatter:
                return None

            # 提取 markdown 内容
            markdown_content = content[match.end():].strip()

            return Skill(
                name=frontmatter["name"],
                description=frontmatter["description"],
                content=markdown_content,
                path=skill_path,
                scripts_dir=skill_path / "scripts" if (skill_path / "scripts").exists() else None,
                references_dir=skill_path / "references" if (skill_path / "references").exists() else None,
                assets_dir=skill_path / "assets" if (skill_path / "assets").exists() else None,
            )
        except Exception:
            return None
```

```python
# agent/skills/manager.py
from pathlib import Path
from typing import List, Dict, Optional

class SkillManager:
    """
    无状态的 Skill 管理器。

    热重载策略：每次操作都从文件系统读取，不缓存内容。
    """

    DEFAULT_SKILLS_DIR = Path.home() / ".termbot" / "skills"

    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or self.DEFAULT_SKILLS_DIR

    def list_skill_basics(self) -> List[Dict]:
        """
        扫描所有 skills，只返回基本信息 (name + description)

        Returns:
            [{"name": str, "description": str, "path": str}, ...]
        """
        if not self.skills_dir.exists():
            return []

        skills = []
        for skill_path in self.skills_dir.iterdir():
            if not skill_path.is_dir():
                continue

            skill_md = skill_path / "SKILL.md"
            if not skill_md.exists():
                continue

            from agent.skills.loader import SkillLoader
            frontmatter = SkillLoader.parse_frontmatter(skill_md)
            if frontmatter and "name" in frontmatter and "description" in frontmatter:
                skills.append({
                    "name": frontmatter["name"],
                    "description": frontmatter["description"],
                    "path": str(skill_path)
                })

        return skills

    def get_skill_by_name(self, name: str) -> Optional[Skill]:
        """
        根据名称获取 skill（包含完整内容）

        热重载：每次都重新读取文件
        """
        skills_basics = self.list_skill_basics()
        for basic in skills_basics:
            if basic["name"] == name:
                from agent.skills.loader import SkillLoader
                skill_path = Path(basic["path"])
                return SkillLoader.load_skill(skill_path)
        return None
```

#### 验证点

**单元测试** (`tests/unit/test_skill_manager.py`)：

```python
import tempfile
from pathlib import Path
from agent.skills import SkillManager

def test_skill_manager_empty_dir():
    """测试空目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SkillManager(Path(tmpdir))
        assert manager.list_skill_basics() == []

def test_skill_manager_load():
    """测试加载 skill"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试 skill
        skill_dir = Path(tmpdir) / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: test
description: Test skill
---

# Test

This is a test skill.
""")

        manager = SkillManager(Path(tmpdir))

        # 测试 list_skill_basics
        basics = manager.list_skill_basics()
        assert len(basics) == 1
        assert basics[0]["name"] == "test"
        assert basics[0]["description"] == "Test skill"

        # 测试 get_skill_by_name
        skill = manager.get_skill_by_name("test")
        assert skill is not None
        assert skill.content == "# Test\n\nThis is a test skill."

def test_skill_manager_hot_reload():
    """测试热重载"""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / "test-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"

        # 初始内容
        skill_md.write_text("""---
name: test
description: Original
---

Original content
""")

        manager = SkillManager(Path(tmpdir))

        # 第一次加载
        skill1 = manager.get_skill_by_name("test")
        assert skill1.description == "Original"
        assert skill1.content == "Original content"

        # 修改文件
        skill_md.write_text("""---
name: test
description: Modified
---

Modified content
""")

        # 第二次加载（热重载）
        skill2 = manager.get_skill_by_name("test")
        assert skill2.description == "Modified"
        assert skill2.content == "Modified content"
```

**手动验证**：

```bash
# 1. 创建测试 skill 目录
mkdir -p ~/.termbot/skills/pdf-processing

# 2. 创建 SKILL.md
cat > ~/.termbot/skills/pdf-processing/SKILL.md << 'EOF'
---
name: pdf-processing
description: 从 PDF 中提取文本和表格
---

# PDF 处理

这是一个测试 skill。
EOF

# 3. 运行测试
.venv/bin/python3 -m pytest tests/unit/test_skill_manager.py -v

# 4. 预期输出：所有测试通过
```

#### 回归测试

- [ ] 启动 CLI/Web，确认无报错
- [ ] 现有功能（终端、笔记）正常工作

---

### Phase 5.2: 工具集配置化 (2-3 天)

**目标**：将工具注册从硬编码改为配置驱动，支持不同角色

#### 实现内容

**新增文件**：

1. `agent/tools/toolsets.py` - 工具集定义
2. `tests/unit/test_toolsets.py` - 单元测试

**详细设计**：

```python
# agent/tools/toolsets.py
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from agent.tools.base import Tool

def get_toolset_for_role(role: str, **dependencies) -> List['Tool']:
    """
    根据角色获取工具集（不包含 TerminalTool）

    Args:
        role: Agent 角色 (main, skill)
        **dependencies: 工具需要的依赖

    Returns:
        工具列表
    """
    if role == "skill":
        return _create_skill_toolset(**dependencies)
    elif role == "main":
        return _create_main_toolset(**dependencies)
    else:
        return []

def _create_skill_toolset(**deps) -> List['Tool']:
    """创建 skill Agent 的工具集"""
    from agent.tools.impl import (
        NoteTool, GetAllNotesTool,
        SendMessageTool, SendFileTool
    )

    return [
        NoteTool(),
        GetAllNotesTool(),
        SendMessageTool(),
        SendFileTool(),
    ]

def _create_main_toolset(**deps) -> List['Tool']:
    """创建主 Agent 的工具集"""
    from agent.tools.impl import (
        NoteTool, GetAllNotesTool,
        SendMessageTool, SendFileTool
    )

    tools = _create_skill_toolset(**deps)

    # 主 Agent 额外的工具（在 5.3 添加 skill_search, skill_executor）
    # 暂时为空

    return tools
```

**修改文件**：

`agent/tools/impl.py` - 添加 `__all__` 导出

```python
# 在文件末尾添加
__all__ = [
    'NoteTool',
    'GetAllNotesTool',
    'SendMessageTool',
    'SendFileTool',
    # ... 其他工具
]
```

#### 验证点

**单元测试** (`tests/unit/test_toolsets.py`)：

```python
from agent.tools.toolsets import get_toolset_for_role

def test_skill_toolset():
    """测试 skill 工具集"""
    tools = get_toolset_for_role("skill")
    tool_names = {t.schema.name for t in tools}

    assert "add_note" in tool_names
    assert "get_all_note" in tool_names
    assert "send_msg_to_user" in tool_names
    assert "send_file_user" in tool_names

def test_main_toolset():
    """测试主 Agent 工具集"""
    tools = get_toolset_for_role("main")
    tool_names = {t.schema.name for t in tools}

    # 主 Agent 至少包含 skill 的工具
    assert "add_note" in tool_names
```

**手动验证**：

```python
# 创建测试脚本 test_toolsets.py
from agent.tools.toolsets import get_toolset_for_role

skill_tools = get_toolset_for_role("skill")
print(f"Skill tools: {[t.schema.name for t in skill_tools]}")

main_tools = get_toolset_for_role("main")
print(f"Main tools: {[t.schema.name for t in main_tools]}")

# 预期输出：工具列表正常显示
```

#### 回归测试

- [ ] CLI 启动，`/tools` 命令显示工具列表
- [ ] Web 启动，创建 session，工具正常注册

---

### Phase 5.3: Agent 工厂 (3-4 天)

**目标**：实现 AgentFactory，统一创建不同角色的 Agent

#### 实现内容

**新增文件**：

1. `agent/factory.py` - AgentFactory
2. `agent/core.py` 修改 - AgentConfig 添加 pty_manager 和 tools
3. `tests/unit/test_agent_factory.py` - 单元测试

**详细设计**：

```python
# agent/core.py 修改

@dataclass
class AgentConfig:
    """Agent 配置"""
    llm_client: OpenAIClient
    max_iterations: int = 20
    enable_memory: bool = True
    system_prompt: Optional[str] = None
    role: Optional[str] = None              # NEW: Agent 角色
    pty_manager: Optional[Any] = None       # NEW: 共享的 PTY Manager
    tools: Optional[List[Tool]] = None      # NEW: 预注册工具列表

class Agent:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.context = Context()
        self.react_loop = ReactLoop(
            llm_client=config.llm_client,
            context=self.context,
            max_iterations=config.max_iterations,
            system_prompt=config.system_prompt or self.DEFAULT_SYSTEM_PROMPT
        )

        # 注册预配置的工具
        if config.tools:
            for tool in config.tools:
                self.register_tool(tool)
```

```python
# agent/factory.py
from agent.core import Agent, AgentConfig
from agent.tools.toolsets import get_toolset_for_role
from agent.tools.terminal import TerminalTool

class AgentFactory:
    """
    Agent 工厂类。

    PTY 共享：所有 Agent（主 Agent + skill Agent）使用同一个 PTY。
    上下文隔离：每个 Agent 有独立的 Context。
    """

    def __init__(self, pty_manager, skill_manager, llm_client):
        """
        初始化工厂。

        Args:
            pty_manager: 共享的 PTY Manager
            skill_manager: Skill Manager
            llm_client: LLM Client
        """
        self.pty_manager = pty_manager
        self.skill_manager = skill_manager
        self.llm_client = llm_client

    def create_main_agent(self, system_prompt: Optional[str] = None) -> Agent:
        """创建主 Agent（使用共享 PTY）"""
        config = AgentConfig(
            llm_client=self.llm_client,
            max_iterations=20,
            enable_memory=True,
            role="main",
            system_prompt=system_prompt,
            pty_manager=self.pty_manager,
            tools=get_toolset_for_role(
                "main",
                skill_manager=self.skill_manager,
                llm_client=self.llm_client
            )
        )
        return self._create_agent(config, agent_id="main")

    def create_skill_agent(self, skill: 'Skill') -> Agent:
        """创建 skill Agent（使用共享 PTY）"""
        # 构建 skill 的 system prompt
        skill_system_prompt = f"""# Skill: {skill.name}

{skill.description}

## 指令

{skill.content}

请严格按照上述指令执行任务。"""

        config = AgentConfig(
            llm_client=self.llm_client,
            max_iterations=20,
            enable_memory=False,
            role="skill",
            system_prompt=skill_system_prompt,
            pty_manager=self.pty_manager,
            tools=get_toolset_for_role(
                "skill",
                llm_client=self.llm_client
            )
        )
        return self._create_agent(config, agent_id=f"skill_{skill.name}")

    def _create_agent(self, config: AgentConfig, agent_id: str) -> Agent:
        """创建 Agent 并注册工具"""
        agent = Agent(config)

        # 注册 TerminalTool（使用共享 PTY）
        terminal_tool = TerminalTool(
            config.pty_manager,
            agent_id=agent_id
        )
        agent.register_tool(terminal_tool)

        return agent
```

#### 验证点

**单元测试** (`tests/unit/test_agent_factory.py`)：

```python
import tempfile
from pathlib import Path
from unittest.mock import Mock
from agent.factory import AgentFactory

def test_create_main_agent():
    """测试创建主 Agent"""
    mock_pty = Mock()
    mock_skill_manager = Mock()
    mock_llm = Mock()

    factory = AgentFactory(mock_pty, mock_skill_manager, mock_llm)
    agent = factory.create_main_agent()

    assert agent is not None
    assert agent.config.role == "main"
    assert agent.config.pty_manager == mock_pty
    assert len(agent.get_available_tools()) > 0

def test_create_skill_agent():
    """测试创建 skill Agent"""
    from agent.skills.skill import Skill

    mock_pty = Mock()
    mock_skill_manager = Mock()
    mock_llm = Mock()

    factory = AgentFactory(mock_pty, mock_skill_manager, mock_llm)

    # 创建测试 skill
    skill = Skill(
        name="test",
        description="Test skill",
        content="# Test\n\nDo something",
        path=Path("/tmp/test")
    )

    agent = factory.create_skill_agent(skill)

    assert agent is not None
    assert agent.config.role == "skill"
    assert "Test skill" in agent.config.system_prompt
    assert len(agent.get_available_tools()) > 0
```

**手动验证**：

```python
# 创建测试脚本 test_factory.py
from infrastructure.terminal.pty_manager import PTYManager
from infrastructure.llm.client import OpenAIClient
from agent.skills import SkillManager
from agent.factory import AgentFactory

# 创建依赖
pty = PTYManager(shell="/bin/bash", cols=80, rows=24)
pty.start()

llm = OpenAIClient(api_key="test")
skill_mgr = SkillManager()

# 创建工厂
factory = AgentFactory(pty, skill_mgr, llm)

# 测试创建主 Agent
main_agent = factory.create_main_agent()
print(f"Main agent tools: {main_agent.get_available_tools()}")

# 清理
pty.stop()

# 预期输出：工具列表正常显示
```

#### 回归测试

- [ ] 所有现有单元测试通过
- [ ] 启动 CLI，确认无报错

---

### Phase 5.4: CLI 集成 (2 天)

**目标**：CLI Handler 使用 AgentFactory 创建 Agent

#### 实现内容

**修改文件**：

1. `cli.py` - 使用 AgentFactory
2. `interfaces/cli.py` - 构造 AgentFactory 并传入 Handler

**详细设计**：

```python
# cli.py 修改

from infrastructure.terminal.pty_manager import PTYManager
from infrastructure.llm.client import OpenAIClient
from agent.skills import SkillManager
from interfaces.cli import CLIHandler
from agent.factory import AgentFactory

def main():
    # ... 配置加载代码 ...

    # 创建共享的 PTY Manager
    pty_manager = PTYManager(
        shell=shell_config.get("shell", "/bin/bash"),
        cols=shell_config.get("cols", 80),
        rows=shell_config.get("rows", 24)
    )
    pty_manager.start()

    # 创建 LLM 客户端
    llm_client = OpenAIClient(api_key=config.get("openai_api_key"))

    # 创建 Skill Manager
    skill_manager = SkillManager()

    # 创建 Agent Factory
    agent_factory = AgentFactory(pty_manager, skill_manager, llm_client)

    try:
        # 创建 CLI Handler
        handler = CLIHandler(agent_factory)

        # 运行会话
        handler.run_session()
    finally:
        pty_manager.stop()
```

```python
# interfaces/cli.py 修改

class CLIHandler(BaseHandler):
    """CLI interface handler with skill support."""

    def __init__(self, agent_factory: AgentFactory) -> None:
        """
        Initialize the CLI handler.

        Args:
            agent_factory: Agent factory for creating agents
        """
        self.agent_factory = agent_factory

        # 创建主 Agent
        agent = agent_factory.create_main_agent()

        super().__init__(agent)
```

#### 验证点

**手动验证**：

```bash
# 1. 启动 CLI
.venv/bin/python3 cli.py

# 2. 测试基础功能
/tools
# 预期：显示工具列表（add_note, get_all_note, ...）

# 3. 测试笔记功能
请帮我记录：今天要买牛奶
# 预期：正常记录

查看笔记
# 预期：显示刚才的笔记

# 4. 测试终端功能
执行 ls -la
# (在终端输入)
# 预期：正常执行

# 5. 测试 /skills 命令（新增）
/skills
# 预期：显示可用 skill 列表
```

#### 回归测试

- [ ] `/tools` 命令正常
- [ ] 笔记功能正常
- [ ] 终端功能正常
- [ ] `/help` 命令正常
- [ ] `/history` 命令正常
- [ ] `/reset` 命令正常

---

### Phase 5.5: Web 集成 (2 天)

**目标**：Web Handler 使用 AgentFactory，支持多 session

#### 实现内容

**修改文件**：

1. `interfaces/web.py` - WebSession 使用 AgentFactory
2. `web.py` - 修改初始化逻辑

**详细设计**：

```python
# interfaces/web.py 修改

from agent.factory import AgentFactory

class WebSession:
    """
    单个 Web session，有独立的 PTY。
    该 session 内的所有 Agent（主 Agent + skill Agent）共享这个 PTY。
    """

    def __init__(self, sid: str, llm_client, system_prompt: str, socketio) -> None:
        self.sid = sid
        self.socketio = socketio

        # 创建独立的 PTY Manager（这个 session 专用）
        self.pty_manager = PTYManager(
            shell="/bin/bash",
            cols=80,
            rows=24,
            session_timeout=2.0
        )
        self.pty_manager.start()

        # 创建工厂（使用这个 session 的 PTY）
        skill_manager = SkillManager()
        self.agent_factory = AgentFactory(self.pty_manager, skill_manager, llm_client)

        # 创建主 Agent
        self.agent = self.agent_factory.create_main_agent(system_prompt)

        # 注册 PTY 输出监听
        self.pty_manager.register_listener(
            lambda data: self._on_terminal_output(data)
        )

    def _on_terminal_output(self, data: str) -> None:
        """PTY 输出 → 发送到前端"""
        self.socketio.emit('terminal_output', {'data': data}, room=self.sid)

    def cleanup(self) -> None:
        """清理 session 资源"""
        try:
            self.pty_manager.stop()
        except Exception:
            pass
```

#### 验证点

**手动验证**：

```bash
# 1. 启动 Web
.venv/bin/python3 web.py

# 2. 打开浏览器，打开开发者工具 Console

# 3. 测试连接
# 预期：终端显示 "Client connected: <sid>"

# 4. 测试聊天
# 发送消息：请帮我记录：测试笔记
# 预期：收到 chat_out 响应

# 5. 测试 /skills 命令
# 发送消息：/skills
# 预期：显示可用 skill 列表
```

#### 回归测试

- [ ] Web 连接正常
- [ ] 聊天功能正常
- [ ] 终端功能正常
- [ ] 多 session 隔离正常（打开两个浏览器窗口，独立操作）

---

### Phase 5.6: Skill 搜索与执行工具 (3-4 天)

**目标**：实现 SkillSearchTool 和 SkillExecutorTool

#### 实现内容

**新增文件**：

1. `agent/tools/skill_search.py` - SkillSearchTool
2. `agent/tools/skill_executor.py` - SkillExecutorTool
3. `tests/unit/test_skill_tools.py` - 单元测试

**修改文件**：

1. `agent/tools/toolsets.py` - 主 Agent 工具集添加 skill 工具

**详细设计**：

```python
# agent/tools/skill_search.py
from agent.tools.base import Tool, ToolSchema, ToolParameterType

class SkillSearchTool(Tool):
    """
    使用 LLM 搜索匹配的 skill。
    主 Agent 在 ReAct 循环中调用此工具来找到合适的 skill。
    """

    def __init__(self, skill_manager, llm_client):
        self.skill_manager = skill_manager
        self.llm_client = llm_client
        self._schema = ToolSchema(
            name="search_skill",
            description="当需要特定领域的专业知识或工具时，搜索匹配的 skill。例如：PDF 处理、Git 工作流、数据分析等。",
            parameters=[
                ToolParameter(
                    name="query",
                    type=ToolParameterType.STRING,
                    description="需要什么类型的技能或功能",
                    required=True
                )
            ]
        )

    @property
    def schema(self) -> ToolSchema:
        return self._schema

    def execute(self, query: str) -> str:
        """搜索匹配的 skills"""
        matched = self.skill_manager.search_skill_by_llm(
            self.llm_client,
            query
        )

        if not matched:
            return f"未找到与 '{query}' 相关的 skill"

        result = f"找到 {len(matched)} 个相关 skill:\n"
        for skill in matched:
            result += f"\n- /{skill['name']}: {skill['description']}"

        return result
```

```python
# agent/tools/skill_executor.py
from agent.tools.base import Tool, ToolSchema, ToolParameterType

class SkillExecutorTool(Tool):
    """
    使用指定的 skill 执行子任务。
    创建子 Agent，skill 内容作为 system_prompt，
    执行完成后自动清理上下文。
    """

    def __init__(self, agent_factory):
        self.agent_factory = agent_factory
        self._schema = ToolSchema(
            name="use_skill",
            description="使用指定的 skill 执行子任务。skill 会提供专业领域的指令。",
            parameters=[
                ToolParameter(
                    name="skill_name",
                    type=ToolParameterType.STRING,
                    description="skill 名称 (不需要 / 前缀)",
                    required=True
                ),
                ToolParameter(
                    name="task",
                    type=ToolParameterType.STRING,
                    description="需要执行的具体任务",
                    required=True
                )
            ]
        )

    @property
    def schema(self) -> ToolSchema:
        return self._schema

    def execute(self, skill_name: str, task: str) -> str:
        """使用 skill 执行任务"""
        # 热重载：每次都从文件系统读取
        skill = self.agent_factory.skill_manager.get_skill_by_name(skill_name)

        if not skill:
            return f"Skill '{skill_name}' 未找到"

        # 创建 skill Agent
        skill_agent = self.agent_factory.create_skill_agent(skill)

        try:
            result = skill_agent.process_message_with_result(task)

            if result.success:
                return result.response
            else:
                return f"执行失败: {result.error or '未知错误'}"
        except Exception as e:
            return f"执行出错: {e}"
```

```python
# agent/skills/manager.py 添加

    def search_skill_by_llm(self, llm_client, user_query: str, top_k: int = 3) -> List[Dict]:
        """
        使用 LLM 匹配用户需求与 skill 描述

        Args:
            llm_client: LLM 客户端
            user_query: 用户需求描述
            top_k: 返回前 K 个最相关的

        Returns:
            匹配的 skill 列表 (按相关性排序)
        """
        skills_basics = self.list_skill_basics()

        if not skills_basics:
            return []

        # 构建 LLM prompt
        skill_list = "\n".join([
            f"- {s['name']}: {s['description']}"
            for s in skills_basics
        ])

        prompt = f"""你是一个 skill 匹配助手。根据用户需求，从可用的 skills 中选择最合适的。

用户需求: {user_query}

可用的 skills:
{skill_list}

请返回最相关的 {min(top_k, len(skills_basics))} 个 skill 名称，用逗号分隔。
只返回 skill 名称，不要其他内容。"""

        try:
            response = llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                tools=None
            )

            # 解析 LLM 返回的 skill 名称
            result = response.content or ""
            names = [n.strip().lstrip("/") for n in result.split(",")]

            # 匹配并返回完整的 skill 基本信息
            matched = []
            for name in names:
                for skill in skills_basics:
                    if skill["name"] == name:
                        matched.append(skill)
                        break

            return matched
        except Exception as e:
            # LLM 调用失败，返回空列表
            return []
```

```python
# agent/tools/toolsets.py 修改

def _create_main_toolset(**deps) -> List['Tool']:
    """创建主 Agent 的工具集"""
    from agent.tools.impl import (
        NoteTool, GetAllNotesTool,
        SendMessageTool, SendFileTool
    )
    from agent.tools.skill_search import SkillSearchTool
    from agent.tools.skill_executor import SkillExecutorTool

    tools = _create_skill_toolset(**deps)

    # 主 Agent 额外的工具
    skill_manager = deps.get('skill_manager')
    llm_client = deps.get('llm_client')

    if skill_manager and llm_client:
        # 需要 agent_factory，暂时传入 None
        # （这里需要调整，见下文）
        pass

    return tools
```

**问题**：`_create_main_toolset` 需要 `agent_factory` 来创建 `SkillExecutorTool`

**解决方案**：调整 `get_toolset_for_role` 接口

```python
# agent/tools/toolsets.py 修改

def get_toolset_for_role(role: str, agent_factory=None, **dependencies) -> List['Tool']:
    """
    根据角色获取工具集（不包含 TerminalTool）

    Args:
        role: Agent 角色 (main, skill)
        agent_factory: AgentFactory (可选，用于创建 skill_executor)
        **dependencies: 其他依赖
    """
    if role == "skill":
        return _create_skill_toolset(**dependencies)
    elif role == "main":
        return _create_main_toolset(agent_factory, **dependencies)
    else:
        return []

def _create_main_toolset(agent_factory=None, **deps) -> List['Tool']:
    """创建主 Agent 的工具集"""
    from agent.tools.impl import (
        NoteTool, GetAllNotesTool,
        SendMessageTool, SendFileTool
    )
    from agent.tools.skill_search import SkillSearchTool
    from agent.tools.skill_executor import SkillExecutorTool

    tools = _create_skill_toolset(**deps)

    skill_manager = deps.get('skill_manager')
    llm_client = deps.get('llm_client')

    if skill_manager and llm_client:
        tools.append(SkillSearchTool(skill_manager, llm_client))

    if agent_factory:
        tools.append(SkillExecutorTool(agent_factory))

    return tools
```

```python
# agent/factory.py 修改

    def _create_agent(self, config: AgentConfig, agent_id: str) -> Agent:
        """创建 Agent 并注册工具"""
        agent = Agent(config)

        # 注册 TerminalTool
        terminal_tool = TerminalTool(
            config.pty_manager,
            agent_id=agent_id
        )
        agent.register_tool(terminal_tool)

        # 注册配置中的其他工具
        # 注意：这里传入 self (agent_factory)，以便 skill_executor 使用
        if config.tools:
            for tool in config.tools:
                agent.register_tool(tool)

        return agent

    def create_main_agent(self, system_prompt: Optional[str] = None) -> Agent:
        """创建主 Agent（使用共享 PTY）"""
        config = AgentConfig(
            llm_client=self.llm_client,
            max_iterations=20,
            enable_memory=True,
            role="main",
            system_prompt=system_prompt,
            pty_manager=self.pty_manager,
            tools=get_toolset_for_role(
                "main",
                agent_factory=self,  # 传入 factory
                skill_manager=self.skill_manager,
                llm_client=self.llm_client
            )
        )
        return self._create_agent(config, agent_id="main")
```

#### 验证点

**单元测试** (`tests/unit/test_skill_tools.py`)：

```python
from unittest.mock import Mock, patch
from agent.tools.skill_search import SkillSearchTool
from agent.tools.skill_executor import SkillExecutorTool

def test_skill_search_tool():
    """测试 skill 搜索工具"""
    mock_skill_manager = Mock()
    mock_llm = Mock()

    # Mock 返回
    mock_skill_manager.list_skill_basics.return_value = [
        {"name": "pdf", "description": "PDF processing"}
    ]
    mock_llm.chat.return_value = Mock(content="pdf")

    tool = SkillSearchTool(mock_skill_manager, mock_llm)
    result = tool.execute(query="PDF 处理")

    assert "找到" in result
    assert "pdf" in result

def test_skill_executor_tool():
    """测试 skill 执行工具"""
    from agent.skills.skill import Skill

    mock_factory = Mock()
    mock_skill = Skill(
        name="test",
        description="Test",
        content="Do test",
        path=Mock()
    )

    # Mock 返回
    mock_factory.skill_manager.get_skill_by_name.return_value = mock_skill

    mock_agent = Mock()
    mock_agent.process_message_with_result.return_value = Mock(
        success=True,
        response="Test result"
    )
    mock_factory.create_skill_agent.return_value = mock_agent

    tool = SkillExecutorTool(mock_factory)
    result = tool.execute(skill_name="test", task="do something")

    assert result == "Test result"
    mock_factory.create_skill_agent.assert_called_once_with(mock_skill)
```

**手动验证**：

```bash
# 1. 创建测试 skill
mkdir -p ~/.termbot/skills/test-skill
cat > ~/.termbot/skills/test-skill/SKILL.md << 'EOF'
---
name: test-skill
description: 测试 skill
---

# 测试

这是一个测试 skill。你只需要简单回复 "Test skill executed" 即可。
EOF

# 2. 启动 CLI
.venv/bin/python3 cli.py

# 3. 测试 search_skill
# （通过聊天触发）
我需要测试功能

# 预期：Agent 调用 search_skill，找到 test-skill

# 4. 测试 use_skill
# （通过聊天触发）
使用 test-skill 执行测试任务

# 预期：Agent 创建 skill Agent，返回 "Test skill executed"
```

#### 回归测试

- [ ] 基础工具（笔记等）正常
- [ ] search_skill 和 use_skill 可用
- [ ] `/skills` 命令显示新创建的 skill

---

### Phase 5.7: 增强功能与优化 (2-3 天)

**目标**：完善细节，添加辅助功能

#### 实现内容

1. **CLI 命令增强**
   - `/skills` - 列出所有 skills
   - `/skill info <name>` - 显示 skill 详情
   - `/skill reload <name>` - 热重载 skill

2. **错误处理**
   - Skill 加载失败友好提示
   - LLM 匹配失败降级到关键词匹配

3. **性能优化**
   - Skill 搜索缓存（5 分钟 TTL）
   - LLM 匹配超时控制

**详细设计**：

```python
# interfaces/cli.py 添加

    def _handle_command(self, command: str) -> None:
        cmd = command.lower().strip()

        # ... 现有命令 ...

        elif cmd == "/skills":
            self._show_skills()
        elif cmd.startswith("/skill "):
            parts = cmd.split(None, 3)
            if len(parts) >= 3:
                if parts[1] == "info":
                    self._show_skill_info(parts[2])
                elif parts[1] == "reload":
                    self._reload_skill(parts[2])
            else:
                print("用法: /skill info <name> 或 /skill reload <name>")
        else:
            print(f"Unknown command: {command}")

    def _show_skills(self) -> None:
        """显示所有可用的 skills"""
        skills = self.agent.skill_manager.list_skill_basics()

        print()
        print(f"Available skills ({len(skills)}):")
        for skill in skills:
            print(f"  /{skill['name']:<20} {skill['description']}")

    def _show_skill_info(self, skill_name: str) -> None:
        """显示 skill 详细信息"""
        skill = self.agent.skill_manager.get_skill_by_name(skill_name)
        if not skill:
            print(f"Skill '{skill_name}' 未找到")
            return

        print()
        print(f"Skill: /{skill.name}")
        print(f"Description: {skill.description}")
        print(f"Path: {skill.path}")
        if skill.scripts_dir:
            print(f"Scripts: {skill.scripts_dir}")
        if skill.references_dir:
            print(f"References: {skill.references_dir}")

    def _reload_skill(self, skill_name: str) -> None:
        """热重载 skill"""
        # 热重载就是重新读取，无需额外操作
        skill = self.agent.skill_manager.get_skill_by_name(skill_name)
        if skill:
            print(f"Skill '{skill_name}' 已重载")
        else:
            print(f"Skill '{skill_name}' 未找到")
```

#### 验证点

**手动验证**：

```bash
# 1. 创建 skill
mkdir -p ~/.termbot/skills/test-skill
cat > ~/.termbot/skills/test-skill/SKILL.md << 'EOF'
---
name: test-skill
description: 初始描述
---

# 测试
EOF

# 2. 启动 CLI
.venv/bin/python3 cli.py

# 3. 测试 /skills
/skills
# 预期：显示 test-skill

# 4. 测试 /skill info
/skill info test-skill
# 预期：显示详情

# 5. 修改 skill
cat > ~/.termbot/skills/test-skill/SKILL.md << 'EOF'
---
name: test-skill
description: 修改后的描述
---

# 测试
EOF

# 6. 测试热重载
/skill info test-skill
# 预期：显示新描述

/skill reload test-skill
# 预期：确认重载

/skill info test-skill
# 预期：仍是新描述（热重载）
```

#### 回归测试

- [ ] 所有命令正常
- [ ] 基础功能正常

---

## 5. 总体验证 (Final Validation)

### 完整流程测试

**场景 1：PDF 处理**

```bash
# 1. 创建 PDF skill
mkdir -p ~/.termbot/skills/pdf-processing
cat > ~/.termbot/skills/pdf-processing/SKILL.md << 'EOF'
---
name: pdf-processing
description: 从 PDF 中提取文本和表格，填写表单，并合并文档
---

# PDF 处理 Skill

## 使用场景
当需要对 PDF 文件进行操作时使用。

## 指令
1. 使用 `pdfplumber` 提取文本型 PDF 内容
2. 使用 `pdftotext` 处理扫描版 PDF
3. 始终提供清晰的步骤说明
EOF

# 2. 启动 CLI
.venv/bin/python3 cli.py

# 3. 测试完整流程
🧑 You: 帮我从这份 PDF report.pdf 中提取表格

# 预期流程：
# Step 1: Agent 调用 search_skill("PDF 提取表格")
# Step 2: Agent 调用 use_skill("pdf-processing", "从 report.pdf 提取表格")
# Step 3: skill Agent 按照 SKILL.md 指令执行
# Step 4: 返回结果
```

**场景 2：多 session Web**

```bash
# 1. 启动 Web
.venv/bin/python3 web.py

# 2. 打开两个浏览器窗口

# 窗口 1
发送消息：帮我记录：用户A的笔记
# 预期：记录成功

发送消息：查看笔记
# 预期：显示 "用户A的笔记"

# 窗口 2
发送消息：查看笔记
# 预期：不显示用户A的笔记（session 隔离）

发送消息：帮我记录：用户B的笔记
# 预期：记录成功

发送消息：查看笔记
# 预期：显示 "用户B的笔记"
```

### 性能验证

```bash
# 1. 测试启动时间
time .venv/bin/python3 cli.py
# 预期：启动时间无明显增加

# 2. 测试 skill 加载
/skills
# 预期：响应时间 < 100ms

# 3. 测试 LLM 匹配
# （通过聊天触发搜索）
# 预期：搜索响应时间 < 2s
```

### 边界条件测试

- [ ] Skill 目录不存在
- [ ] SKILL.md 格式错误
- [ ] Skill 名称重复
- [ ] LLM 匹配失败（网络问题）
- [ ] Skill 执行失败
- [ ] PTY 锁竞争（主 Agent 和 skill Agent 同时执行命令）

## 6. 风险与缓解 (Risks & Mitigations)

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| PTY 锁竞争导致命令混乱 | 高 | 中 | 1. 监控锁等待时间<br>2. 考虑为 skill Agent 添加独立 PTY |
| LLM 匹配不准确 | 中 | 中 | 1. 添加关键词匹配降级<br>2. 用户可手动指定 skill |
| Skill 编写不当导致死循环 | 中 | 低 | 1. 限制 skill Agent max_iterations<br>2. 添加超时机制 |
| 热重载频繁读取文件影响性能 | 低 | 低 | 1. 监控文件系统调用<br>2. 如需要，添加短时缓存 |

## 7. 时间线 (Timeline)

| 阶段 | 工作量 | 依赖 |
|------|--------|------|
| 5.1 Skill 基础设施 | 3-4 天 | 无 |
| 5.2 工具集配置化 | 2-3 天 | 5.1 |
| 5.3 Agent 工厂 | 3-4 天 | 5.2 |
| 5.4 CLI 集成 | 2 天 | 5.3 |
| 5.5 Web 集成 | 2 天 | 5.3 |
| 5.6 Skill 搜索与执行 | 3-4 天 | 5.3 |
| 5.7 增强功能 | 2-3 天 | 5.6 |
| **总计** | **17-22 天** | |

## 8. 验收标准 (Acceptance Criteria)

### 功能验收

- [ ] 用户可以创建自定义 skill（SKILL.md）
- [ ] 用户通过自然语言描述需求，Agent 自动匹配 skill
- [ ] skill 在独立 Agent 中执行，不污染主对话上下文
- [ ] skill Agent 可以执行终端命令
- [ ] 修改 SKILL.md 后立即生效（热重载）
- [ ] CLI 和 Web 都支持 skill 功能

### 质量验收

- [ ] 所有现有单元测试通过
- [ ] 代码覆盖率 ≥ 80%（新增代码）
- [ ] Pylint 分数 ≥ 8.0
- [ ] 无已知 bug

### 性能验收

- [ ] 启动时间增加 < 10%
- [ ] `/skills` 命令响应 < 100ms
- [ ] skill 搜索响应 < 2s

---

**文档版本**: v1.0
**最后更新**: 2025-02-13
**状态**: 待评审
