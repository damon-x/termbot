# CLI 工具知识库设计文档

## 一、概述

### 1.1 目标

为 TermBot 添加 CLI 工具知识库功能，使 AI 能够：

1. **渐进式学习**：按需查询 CLI 工具的用法，而不是一开始就被所有信息淹没
2. **智能检索**：根据场景、关键词、功能描述搜索相关工具
3. **知识复用**：统一管理冷门 CLI 工具的文档和示例
4. **执行分离**：只负责知识的存储和检索，实际执行仍通过 `TerminalTool + PTYManager`

### 1.2 设计原则

1. **使用者友好**：每个工具的信息集中在一个地方，不需要跨文件编辑
2. **按需加载**：索引常驻内存，详细信息按需读取并缓存
3. **职责清晰**：知识库只管"教"AI 用工具，不管实际执行
4. **易于扩展**：添加新工具只需编辑 YAML，无需改代码

### 1.3 适用场景

| 场景 | 说明 | 示例 |
|------|------|------|
| 冷门工具 | 不常用的 CLI 工具，AI 训练数据中覆盖不足 | `jq`, `fzf`, `ripgrep` |
| 专业领域 | 特定领域的专业工具 | `imagemagick`, `ffmpeg` |
| 自定义命令 | 用户或团队内部的自定义脚本 | 内部部署脚本 |
| 最佳实践 | 工具的正确使用方式和常见陷阱 | jq 的过滤语法 |

---

## 二、系统架构

### 2.1 工作流程

```
┌─────────────────────────────────────────────────────────────────┐
│                         LLM 决策流程                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  用户: "帮我从 JSON 文件里提取所有用户的邮箱"                     │
│    ↓                                                            │
│  LLM: 需要处理 JSON → 调用 search_cli_tools("JSON 处理")      │
│    ↓                                                            │
│  CliKnowledgeTool: 返回索引                                      │
│    [{name: "jq", summary: "..."}, {name: "jp", summary: "..."}]│
│    ↓                                                            │
│  LLM: jq 看起来合适 → 调用 get_cli_tool_detail("jq")           │
│    ↓                                                            │
│  CliKnowledgeTool: 返回详细信息（示例、参数、注意事项）         │
│    ↓                                                            │
│  LLM: 生成命令 cat data.json | jq '.[].email'                   │
│    ↓                                                            │
│  LLM: 调用 terminal_tool.execute(cmd="...") 执行命令             │
│    ↓                                                            │
│  TerminalTool → PTYManager → bash 执行                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 职责划分

```
┌─────────────────────────────────────────────────────────────────┐
│                  CliKnowledgeTool (新增)                         │
│  职责: CLI 工具知识的存储和检索                                  │
│  - search_tools()     搜索工具（基于索引）                      │
│  - get_tool_detail()  获取详细信息（按需加载）                   │
│  - list_categories()  列出工具分类                              │
│  - get_random()       获取随机工具（学习推荐）                   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                   TerminalTool (现有)                             │
│  职责: 执行终端命令                                              │
│  - execute(cmd)      执行命令                                    │
│  - write()           写入 PTY                                    │
│  - read()            读取输出                                    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                      PTYManager (现有)                           │
│  职责: 管理伪终端                                                │
│  - fork_pty()        创建 PTY                                    │
│  - write_agent()     写入命令（带锁协调）                         │
│  - register_listener() 注册输出监听器                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、YAML 数据结构设计

### 3.1 文件组织

**推荐方案（单文件）**：
```
config/
└── cli_knowledge.yaml
```

**可选方案（多文件）**：
```
config/cli_knowledge/
├── index.yaml          # 索引文件（可选，可自动生成）
├── jq.yaml
├── fzf.yaml
├── ripgrep.yaml
└── ...
```

### 3.2 单文件结构（推荐）

```yaml
# config/cli_knowledge.yaml

# =====================================================================
# 数据处理工具
# =====================================================================

jq:
  # === 概要信息（会被索引，快速加载） ===
  summary: "命令行 JSON 处理器，用于查询、修改和格式化 JSON 数据"
  category: "data-processing"
  keywords: ["json", "parse", "filter", "transform", "query"]
  aliases: ["json-query"]

  # === 详细信息（按需加载） ===
  description: |
    jq 是一个轻量级且灵活的命令行 JSON 处理器。
    它可以解析 JSON 输入，通过过滤器和转换产生输出。
    类似于 JSON 版本的 sed，可以切片、过滤、映射和转换结构化数据。

  examples:
    - scenario: "提取 JSON 字段"
      command: 'cat data.json | jq ".users[0].name"'
      output: '"Alice"'
      explanation: "获取 JSON 中特定字段的值"

    - scenario: "格式化 JSON"
      command: 'echo ''{"a":1,"b":2}'' | jq "."'
      output: |
        {
          "a": 1,
          "b": 2
        }
      explanation: "美化输出 JSON，使其更易读"

    - scenario: "过滤数组元素"
      command: 'cat data.json | jq ".users[] | select(.age > 18)"'
      output: |
        {
          "name": "Bob",
          "age": 25
        }
      explanation: "只返回 age 大于 18 的用户"

    - scenario: "提取多个字段"
      command: 'cat data.json | jq ".users[] | {name, email}"'
      explanation: "只输出指定的字段，构建新对象"

    - scenario: "修改字段值"
      command: 'cat data.json | jq ".users[] | .age = 20"'
      explanation: "将所有用户的 age 字段改为 20"

    - scenario: "原始输出（无引号）"
      command: 'cat data.json | jq -r ".users[0].name"'
      output: "Alice"
      explanation: "使用 -r 参数输出原始字符串，不添加 JSON 引号"

  parameters:
    - name: "filter"
      description: "jq 查询表达式"
      required: true
      examples: ['".field"', ".array[]", ".array[] | select(.condition)"]

    - name: "--raw-output / -r"
      description: "输出原始字符串，不添加 JSON 引号"
      required: false
      examples: ["jq -r '.value'"]

    - name: "--compact-output / -c"
      description: "紧凑输出，不格式化"
      required: false

    - name: "--slurp / -s"
      description: "将所有输入读取到单个数组中"
      required: false

    - name: "--from-file / -f"
      description: "从文件读取 filter 表达式"
      required: false

  notes: |
    ## 学习建议
    - 学习曲线较陡，建议从简单查询开始
    - 语法类似 XPath，支持管道操作 `|`
    - 可以组合多个操作：`.[] | select(.age > 18) | .name`

    ## 常见陷阱
    - 键名包含特殊字符时需要用引号: `.["key-with-dash"]`
    - 注意 null 和 false 的区别
    - 数组索引从 0 开始，支持负数索引（-1 表示最后一个）
    - 字符串比较用 `==`，数字比较用 `>`

    ## 参考资源
    - 官方文档: https://stedolan.github.io/jq/manual/
    - 在线练习: https://jqplay.org/
    - 快速入门: https://devhints.io/jq

# =====================================================================
# 效率工具
# =====================================================================

fzf:
  summary: "交互式模糊查找器，用于快速筛选列表内容"
  category: "productivity"
  keywords: ["fuzzy", "search", "interactive", "filter", "finder"]

  description: |
    fzf 是一个通用的命令行模糊查找器。它可以与任何列表组合使用，
    提供交互式搜索界面，支持键盘快捷键和预览功能。

  examples:
    - scenario: "查找并打开文件"
      command: "fzf"
      input_from: "find . -type f |"
      explanation: "浏览当前目录的文件，回键打开选中项"

    - scenario: "搜索命令历史"
      command: "history | fzf"
      explanation: "交互式搜索并执行历史命令"

    - scenario: "查找进程并杀死"
      command: "ps aux | fzf | awk '{print $2}' | xargs kill"
      explanation: "交互式选择进程并杀死"

    - scenario: "多选文件"
      command: "find . -type f | fzf -m"
      explanation: "使用 -m 参数支持多选（Tab 键选择）"

    - scenario: "带预览的文件查找"
      command: "fzf --preview 'cat {}' --preview-window right:30%"
      explanation: "右侧预览文件内容"

  parameters:
    - name: "--multi / -m"
      description: "启用多选模式"
      required: false

    - name: "--preview"
      description: "预览命令，{} 会被替换为选中项"
      required: false
      examples: ["--preview 'cat {}'", "--preview 'bat --color=always {}'"]

    - name: "--height"
      description: "设置 fzf 窗口高度"
      required: false

    - name: "--filter"
      description: "非交互式过滤模式"
      required: false

  notes: |
    ## 快捷键
    - Ctrl-J / Ctrl-K: 上下移动
    - Enter: 确认选择
    - Esc: 取消
    - Tab: 多选模式下选择
    - Ctrl-T: 切换全选

    ## 常用组合
    - `find | fzf`: 文件查找
    - `git log | fzf`: Git 历史查找
    - `ps aux | fzf`: 进程查找
    - `history | fzf`: 命令历史查找

# =====================================================================
# 搜索工具
# =====================================================================

rg (ripgrep):
  summary: "超快速文本搜索工具，grep 的现代替代品"
  category: "search"
  keywords: ["search", "grep", "text", "regex", "ripgrep"]
  aliases: ["ripgrep"]

  description: |
    ripgrep (rg) 是一个递归正则表达式搜索工具。
    比 grep 更快，默认忽略 .gitignore 中的文件，支持自动颜色高亮。

  examples:
    - scenario: "搜索文本"
      command: 'rg "search_term" .'
      explanation: "在当前目录递归搜索"

    - scenario: "仅匹配文件名（不搜索内容）"
      command: 'rg -g "*.py" "pattern"'
      explanation: "只在 .py 文件中搜索"

    - scenario: "显示行号"
      command: 'rg -n "pattern"'
      explanation: "显示匹配行的行号"

    - scenario: "只显示匹配的文件名"
      command: 'rg -l "pattern"'
      explanation: "只输出包含匹配项的文件名"

    - scenario: "正则表达式搜索"
      command: 'rg "\b[A-Z]{2,}\b" .'
      explanation: "搜索两个或更多大写字母组成的单词"

    - scenario: "替换并输出"
      command: 'rg "old" -r "new"'
      explanation: "将匹配的 old 替换为 new 并输出（不修改文件）"

  parameters:
    - name: "pattern"
      description: "搜索模式（支持正则表达式）"
      required: true

    - name: "path"
      description: "搜索路径，默认为当前目录"
      required: false

    - name: "--ignore-case / -i"
      description: "忽略大小写"
      required: false

    - name: "--case-sensitive / -s"
      description: "区分大小写"
      required: false

    - name: "--files-with-matches / -l"
      description: "只显示包含匹配的文件名"
      required: false

    - name: "--glob / -g"
      description: "文件名模式过滤"
      required: false
      examples: ["-g '*.py'", "-g '!*.log'"]

    - name: "--replace / -r"
      description: "替换匹配的文本并输出"
      required: false

  notes: |
    ## 与 grep 的区别
    - 默认递归搜索
    - 默认忽略 .gitignore 文件
    - 自动颜色高亮
    - 比 grep 快很多

    ## 常用技巧
    - 搜索隐藏文件: `rg --hidden`
    - 搜索特定类型: `rg -t py "pattern"`
    - 排除文件: `rg -g '!*.log' "pattern"`
    - 统计匹配数: `rg --count-matches "pattern"`

# =====================================================================
# 其他工具...
# =====================================================================

# imagemagick:
#   summary: "强大的图像处理工具集"
#   category: "image"
#   keywords: ["image", "convert", "resize", "crop"]
#
#   examples:
#     - scenario: "调整图片大小"
#       command: "convert input.jpg -resize 800x600 output.jpg"
#
#     - scenario: "裁剪图片"
#       command: "convert input.jpg -crop 800x600+100+100 output.jpg"
#
#     - scenario: "格式转换"
#       command: "convert input.png output.jpg"
```

### 3.3 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `summary` | string | ✅ | 一句话描述，用于搜索结果展示 |
| `category` | string | ✅ | 分类 |
| `keywords` | string[] | ✅ | 搜索关键词 |
| `aliases` | string[] | ❌ | 别名（如 rg 的别名 ripgrep） |
| `description` | string | ❌ | 详细描述（支持 Markdown） |
| `examples` | object[] | ❌ | 使用示例 |
| `parameters` | object[] | ❌ | 参数说明 |
| `notes` | string | ❌ | 注意事项、学习建议、参考链接 |

### 3.4 分类标准

| 分类 | 说明 | 示例工具 |
|------|------|----------|
| `data-processing` | 数据处理、转换 | jq, sed, awk, miller |
| `search` | 文本/文件搜索 | ripgrep, ag, fzf |
| `productivity` | 效率工具 | fzf, tmux, htop |
| `system` | 系统管理 | systemd, strace, lsof |
| `network` | 网络工具 | curl, wget, tcpdump, wireshark-cli |
| `devops` | DevOps 工具 | docker, kubectl, ansible |
| `image` | 图像处理 | imagemagick, ffmpeg |
| `git` | Git 相关工具 | git, gh, lazygit |
| `database` | 数据库工具 | psql, redis-cli, mongosh |

---

## 四、核心设计

### 4.1 CliKnowledgeTool 实现

```python
# agent/tools/cli_knowledge.py
from typing import List, Dict, Any, Optional
import yaml
from pathlib import Path

from agent.tools.base import Tool, ToolSchema, ToolParameter, ToolParameterType


class CliKnowledgeTool(Tool):
    """CLI 工具知识库查询工具"""

    def __init__(self, yaml_path: str = "config/cli_knowledge.yaml"):
        self.yaml_path = Path(yaml_path)
        self._data: Optional[Dict[str, Any]] = None
        self._index: Optional[Dict[str, Dict[str, Any]]] = None

    def _load_data(self) -> Dict[str, Any]:
        """加载 YAML 数据（懒加载）"""
        if self._data is None:
            with open(self.yaml_path, 'r', encoding='utf-8') as f:
                self._data = yaml.safe_load(f)
        return self._data

    def _build_index(self) -> Dict[str, Dict[str, Any]]:
        """构建工具索引"""
        if self._index is not None:
            return self._index

        data = self._load_data()
        self._index = {}

        for tool_name, tool_data in data.items():
            self._index[tool_name] = {
                "name": tool_name,
                "summary": tool_data.get("summary", ""),
                "category": tool_data.get("category", "other"),
                "keywords": tool_data.get("keywords", []),
                "aliases": tool_data.get("aliases", [])
            }

        return self._index

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="cli_knowledge",
            description="查询 CLI 工具的使用方法和最佳实践。支持搜索工具、获取详细用法、查看分类。",
            parameters=[
                ToolParameter(
                    name="action",
                    type=ToolParameterType.STRING,
                    description="操作类型: search/detail/list_categories/list_tools",
                    required=True
                ),
                ToolParameter(
                    name="query",
                    type=ToolParameterType.STRING,
                    description="搜索关键词、工具名称或分类名称"
                ),
                ToolParameter(
                    name="limit",
                    type=ToolParameterType.INTEGER,
                    description="返回结果数量限制（仅用于 search）",
                    required=False
                ),
                ToolParameter(
                    name="sections",
                    type=ToolParameterType.ARRAY,
                    description="需要的详细信息部分（仅用于 detail），如 ['description', 'examples']",
                    required=False
                )
            ]
        )

    def execute(self, **kwargs) -> Any:
        action = kwargs.get("action")

        if action == "search":
            return self._search_tools(
                query=kwargs.get("query", ""),
                limit=kwargs.get("limit", 5)
            )
        elif action == "detail":
            return self._get_tool_detail(
                tool_name=kwargs.get("query", ""),
                sections=kwargs.get("sections")
            )
        elif action == "list_categories":
            return self._list_categories()
        elif action == "list_tools":
            return self._list_tools(kwargs.get("query"))
        else:
            return f"Unknown action: {action}"

    # ==================== 实现方法 ====================

    def _search_tools(self, query: str, limit: int = 5) -> str:
        """搜索工具

        Args:
            query: 搜索关键词
            limit: 返回结果数量

        Returns:
            格式化的搜索结果
        """
        index = self._build_index()
        query_lower = query.lower()

        # 计算相关性分数
        scored_tools = []
        for tool_name, tool_info in index.items():
            score = 0.0

            # 名称匹配
            if query_lower in tool_name.lower():
                score += 1.0

            # 别名匹配
            for alias in tool_info.get("aliases", []):
                if query_lower in alias.lower():
                    score += 0.9

            # 关键词匹配
            for keyword in tool_info.get("keywords", []):
                if query_lower in keyword.lower():
                    score += 0.7

            # 分类匹配
            if query_lower in tool_info.get("category", "").lower():
                score += 0.5

            # 概要匹配
            summary = tool_info.get("summary", "").lower()
            if query_lower in summary:
                score += 0.3

            if score > 0:
                scored_tools.append((tool_name, score, tool_info))

        # 排序并限制数量
        scored_tools.sort(key=lambda x: x[1], reverse=True)
        scored_tools = scored_tools[:limit]

        if not scored_tools:
            return f"未找到与 '{query}' 相关的工具"

        # 格式化输出
        result = [f"找到 {len(scored_tools)} 个相关工具:\n"]

        for tool_name, score, tool_info in scored_tools:
            result.append(f"**{tool_name}**")
            result.append(f"  分类: {tool_info.get('category', 'N/A')}")
            result.append(f"  说明: {tool_info.get('summary', 'N/A')}")
            result.append("")

        return "\n".join(result)

    def _get_tool_detail(
        self,
        tool_name: str,
        sections: Optional[List[str]] = None
    ) -> str:
        """获取工具详细信息

        Args:
            tool_name: 工具名称
            sections: 需要的部分，如 ['description', 'examples']

        Returns:
            格式化的详细信息
        """
        data = self._load_data()

        # 查找工具（支持别名）
        tool_data = None
        for name, info in data.items():
            if name.lower() == tool_name.lower():
                tool_data = info
                break
            # 检查别名
            if tool_name.lower() in [a.lower() for a in info.get("aliases", [])]:
                tool_data = info
                break

        if not tool_data:
            return f"未找到工具: {tool_name}"

        # 构建结果
        result = [f"# {tool_name}\n"]

        if sections is None:
            sections = ["description", "examples", "parameters", "notes"]

        if "description" in sections and "description" in tool_data:
            result.append(f"## 描述\n{tool_data['description']}\n")

        if "examples" in sections and "examples" in tool_data:
            result.append("## 使用示例")
            for i, example in enumerate(tool_data["examples"], 1):
                result.append(f"\n### {i}. {example.get('scenario', '示例')}")
                if "command" in example:
                    result.append(f"**命令:** `{example['command']}`")
                if "input_from" in example:
                    result.append(f"**输入:** `{example['input_from']}`")
                if "output" in example:
                    result.append(f"**输出:**\n```\n{example['output']}\n```")
                if "explanation" in example:
                    result.append(f"**说明:** {example['explanation']}")
            result.append("")

        if "parameters" in sections and "parameters" in tool_data:
            result.append("## 参数说明")
            for param in tool_data["parameters"]:
                required = "（必填）" if param.get("required") else "（可选）"
                result.append(f"- **{param['name']}** {required}")
                result.append(f"  - {param.get('description', 'N/A')}")
                if "examples" in param:
                    result.append(f"  - 示例: {', '.join(param['examples'])}")
            result.append("")

        if "notes" in sections and "notes" in tool_data:
            result.append(f"## 注意事项\n{tool_data['notes']}\n")

        return "\n".join(result)

    def _list_categories(self) -> str:
        """列出所有分类"""
        index = self._build_index()
        categories = {}

        for tool_info in index.values():
            category = tool_info.get("category", "other")
            if category not in categories:
                categories[category] = 0
            categories[category] += 1

        result = ["工具分类:\n"]
        for category, count in sorted(categories.items()):
            result.append(f"- **{category}**: {count} 个工具")

        return "\n".join(result)

    def _list_tools(self, category: Optional[str] = None) -> str:
        """列出工具

        Args:
            category: 分类过滤，不指定则列出所有工具
        """
        index = self._build_index()

        if category:
            tools = [
                (name, info) for name, info in index.items()
                if info.get("category", "").lower() == category.lower()
            ]
            if not tools:
                return f"分类 '{category}' 下没有工具"
            result = [f"分类 '{category}' 下的工具:\n"]
        else:
            tools = list(index.items())
            result = [f"所有工具 (共 {len(tools)} 个):\n"]

        for tool_name, tool_info in sorted(tools):
            result.append(f"- **{tool_name}**: {tool_info.get('summary', 'N/A')}")

        return "\n".join(result)
```

### 4.2 系统提示词集成

```python
# agent/prompts/system.py
# 在现有的 system prompt 中添加

CLI_KNOWLEDGE_HINT = """
你可以访问一个 CLI 工具知识库，里面包含各种命令行工具的使用方法。

**使用流程：**
1. 当用户需要某个功能时，先调用 `cli_knowledge` 工具的 `search` 操作搜索相关工具
2. 找到合适的工具后，调用 `detail` 操作获取详细用法
3. 根据用法生成正确的命令，通过 `terminal_tool` 执行
4. 如果命令执行失败，可以查看详细的 examples 和 notes

**可用操作：**
- `action="search"` + `query="关键词"`: 搜索工具
- `action="detail"` + `query="工具名"`: 获取详细用法
- `action="list_categories"`: 列出所有分类
- `action="list_tools"` + `query="分类名"`: 列出某个分类下的工具

**注意事项：**
- 不要假设用户知道冷门工具的用法
- 对于不确定的工具，先查询再使用
- 优先参考 examples 中的实际用例
"""
```

### 4.3 配置管理

```python
# infrastructure/config/settings.py
# 在配置文件中添加

# config/default.json
{
  "cli_knowledge": {
    "enabled": true,
    "path": "config/cli_knowledge.yaml",
    "auto_reload": false,
    "cache_enabled": true
  }
}
```

---

## 五、实现步骤

### Step 5.1: 创建 YAML 配置文件

创建 `config/cli_knowledge.yaml`，添加 10-20 个常用工具

### Step 5.2: 实现 CliKnowledgeTool

创建 `agent/tools/cli_knowledge.py`

### Step 5.3: 注册工具

修改 `agent/core.py` 或工具注册逻辑

### Step 5.4: 更新系统提示词

在 agent/prompts 中添加 CLI 知识库的使用说明

### Step 5.5: 编写测试

创建 `tests/test_cli_knowledge.py`

### Step 5.6: 手动测试

通过 CLI 或 Web 界面测试实际效果

---

## 六、验证标准（测试用例）

| 编号 | 测试名称 | 操作 | 期望结果 |
|------|---------|------|---------|
| TC-CK-1 | 搜索工具 | `cli_knowledge(action="search", query="json")` | 返回包含 jq 等工具的列表 |
| TC-CK-2 | 获取详情 | `cli_knowledge(action="detail", query="jq")` | 返回 jq 的完整用法 |
| TC-CK-3 | 别名查找 | `cli_knowledge(action="detail", query="ripgrep")` | 返回 rg 的用法 |
| TC-CK-4 | 分类列表 | `cli_knowledge(action="list_categories")` | 返回所有分类 |
| TC-CK-5 | 按分类列出 | `cli_knowledge(action="list_tools", query="search")` | 返回搜索类工具 |
| TC-CK-6 | 部分加载 | `cli_knowledge(action="detail", query="jq", sections=["examples"])` | 只返回示例部分 |
| TC-CK-7 | 无结果搜索 | `cli_knowledge(action="search", query="不存在")` | 返回友好提示 |
| TC-CK-8 | YAML 格式错误 | 提供格式错误的 YAML | 优雅降级或报错提示 |
| TC-CK-9 | 集成测试 | 用户: "用 jq 提取 JSON" | LLM 先查询再执行 |
| TC-CK-10 | 缓存测试 | 多次查询同一工具 | 第二次从缓存读取 |

---

## 七、验收检查表

- [ ] YAML 配置文件创建
- [ ] CliKnowledgeTool 实现完成
- [ ] 搜索功能正常
- [ ] 详情获取正常
- [ ] 分类列表正常
- [ ] 支持别名查找
- [ ] 支持部分加载
- [ ] 工具已注册到 Agent
- [ ] 系统提示词已更新
- [ ] 单元测试通过
- [ ] 手动集成测试通过
- [ ] Pylint 评分 ≥ 8.0
- [ ] 文档完整

---

## 八、初始工具列表建议

### 优先添加（高优先级）

| 工具 | 分类 | 说明 |
|------|------|------|
| jq | data-processing | JSON 处理器 |
| fzf | productivity | 交互式模糊查找 |
| ripgrep (rg) | search | 超快文本搜索 |
| fd | search | 快速文件查找 |
| bat | productivity | cat 的增强版 |
| exa / eza | productivity | ls 的增强版 |
| tldr | productivity | 简化版 man |
| htop | system | 交互式进程监控 |
| tmux | productivity | 终端复用器 |
| zoxide | productivity | 智能目录跳转 |

### 后续添加（中优先级）

| 工具 | 分类 | 说明 |
|------|------|------|
| sed | data-processing | 流编辑器 |
| awk | data-processing | 文本处理 |
| curl | network | HTTP 客户端 |
| wget | network | 下载工具 |
| git | git | 版本控制 |
| docker | devops | 容器管理 |
| jqplay | productivity | jq 在线工具（文档链接） |

---

## 九、估计工作量

| 任务 | 工作量 |
|------|--------|
| YAML 配置文件（20 个工具） | 4-6 小时 |
| CliKnowledgeTool 实现 | 3-4 小时 |
| 单元测试 | 2-3 小时 |
| 集成测试 | 2-3 小时 |
| 文档完善 | 1-2 小时 |
| **总计** | **12-18 小时** |

---

## 十、后续扩展

### 10.1 缓存优化

添加内存缓存，避免重复 YAML 解析：

```python
class CliKnowledgeCache:
    def __init__(self):
        self._index_cache: Optional[Dict] = None
        self._detail_cache: Dict[str, Any] = {}

    def get_index(self) -> Dict:
        if self._index_cache is None:
            self._index_cache = self._load_index()
        return self._index_cache

    def get_detail(self, tool_name: str) -> Dict:
        if tool_name not in self._detail_cache:
            self._detail_cache[tool_name] = self._load_detail(tool_name)
        return self._detail_cache[tool_name]
```

### 10.2 智能推荐

根据用户历史命令推荐相关工具：

```python
def recommend_tool(self, context: str, last_command: str) -> List[str]:
    """根据上下文推荐工具"""
    # 分析 last_command，推荐相关工具
    pass
```

### 10.3 多文件支持

当工具数量超过 50 个时，拆分为多文件：

```
config/cli_knowledge/
├── index.yaml
├── jq.yaml
├── fzf.yaml
└── ...
```

### 10.4 MCP 外部知识源

通过 MCP 协议连接在线知识库：

```python
class MCPKnowledgeSource:
    """通过 MCP 获取工具知识"""

    async def fetch_tool_info(self, tool_name: str) -> Dict:
        """从 MCP 服务器获取工具信息"""
        pass
```

---

## 十一、参考资源

- jq 官方文档: https://stedolan.github.io/jq/manual/
- fzf GitHub: https://github.com/junegunn/fzf
- ripgrep GitHub: https://github.com/BurntSushi/ripgrep
- tldr 项目: https://tldr.sh/

---

*文档版本: v1.0*
*创建日期: 2026-02-12*
