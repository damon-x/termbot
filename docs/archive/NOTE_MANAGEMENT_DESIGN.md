# 笔记管理系统设计文档

## 1. 概述

### 1.1 设计目标

为 TermBot 添加笔记管理能力，用户通过自然语言与 Agent 交互，实现对笔记的查询、修改和删除。

**核心原则**：
- 自然语言驱动，不需要用户学习命令
- Tool 层控制数据量和业务逻辑
- Agent 层保持通用，不包含笔记相关逻辑
- 支持分页，避免 token 浪费
- 软删除，可恢复

### 1.2 设计约束

| 约束项 | 说明 |
|--------|------|
| **数据量控制** | Tool 返回数据必须有硬编码上限，不由 LLM 决定截断 |
| **逻辑位置** | Tool 的调用条件写在 Tool description，不写在 Agent prompt |
| **Agent 不动** | 改造不涉及 Agent 核心代码和 system prompt |
| **分页支持** | 超过阈值时使用分页，工具层处理 |
| **删除方式** | 软删除（disable），不实现多版本 |

---

## 2. 功能范围

### 2.1 用户交互场景

```
场景 1：查看笔记列表
用户: "有哪些笔记？"
🤖: 显示前 5 条笔记，并说明总数

场景 2：搜索笔记
用户: "有没有关于 docker 的笔记？"
🤖: 搜索相关笔记，显示前 5 条，说明总数

场景 3：分页查看
用户: "再看看其他的"
🤖: 调用分页，显示下一页

场景 4：修改笔记（直接）
用户: "把第 3 条笔记里的 docker 改成 podman"
🤖: 理解意图，调用修改工具

场景 5：修改笔记（交互式）
用户: "我要编辑第 3 条笔记"
🤖: "好的，请告诉我新的内容："
用户: "..."
🤖: 调用修改工具

场景 6：删除笔记
用户: "删除第 3 条笔记"
🤖: 调用删除工具（软删除）

场景 7：删除笔记（内容指代）
用户: "删除关于 docker 容器配置的那条笔记"
🤖: 如果唯一，直接删除；如果不唯一，询问用户

场景 8：删除笔记（不清晰）
用户: "删除那条笔记"
🤖: "请问要删除哪一条笔记？请提供笔记 ID 或描述内容"
```

---

## 3. 架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                       用户                               │
└────────────────────────┬────────────────────────────────┘
                         │ 自然语言
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    Agent Layer                          │
│  • ReAct Loop                                           │
│  • Function Calling (Tool 选择)                         │
│  • 自然语言理解                                         │
└────────────────────────┬────────────────────────────────┘
                         │ Tool 调用
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    Tool Layer (新增)                    │
│  ┌─────────────────┐  ┌─────────────────┐              │
│  │ ListNotesTool   │  │ DeleteNoteTool  │              │
│  │ (复用/改造)      │  │ (新增)          │              │
│  └─────────────────┘  └─────────────────┘              │
│  ┌─────────────────┐  ┌─────────────────┐              │
│  │ EditNoteTool    │  │ SearchMemoryTool│              │
│  │ (新增)          │  │ (优化返回)       │              │
│  └─────────────────┘  └─────────────────┘              │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                 MemoryManager (扩展)                    │
│  • list_memories()   - 分页查询                         │
│  • update_memory()   - 更新内容/标签                    │
│  • disable_memory()  - 软删除（已有）                   │
└─────────────────────────────────────────────────────────┘
```

### 3.2 数据流

```
用户输入
  │
  ▼
Agent 理解意图
  │
  ├─ 需要查询？ → ListNotesTool / SearchMemoryTool
  │                 │
  │                 ▼
  │              MemoryManager.list_memories(limit=5)
  │                 │
  │                 ▼
  │              返回最多 5 条笔记
  │                 │
  ▼                 ▼
Agent 组织自然语言回复 → 用户

用户指定操作
  │
  ▼
Agent 解析参数（ID 或 内容描述）
  │
  ├─ 修改？ → EditNoteTool
  │            │
  │            ▼
  │         MemoryManager.update_memory()
  │            │
  ▼            ▼
Agent 反馈结果 → 用户
```

---

## 4. Tool 规范

### 4.1 Tool Description 设计原则

**关键原则**：Tool 的调用条件、参数要求必须写在 description 里，让 LLM 通过 Function Calling 自行判断。

**Description 模板**：
```
"{工具功能描述}

REQUIREMENTS（调用条件）:
- 条件 1
- 条件 2

PARAMETER RULES（参数规则）:
- 参数 1 的要求
- 参数 2 的要求

BEHAVIOR（行为说明）:
- 执行后的效果
- 注意事项"
```

### 4.2 ListNotesTool

```python
class ListNotesTool(Tool):
    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="list_notes",
            description=(
                "List all notes with pagination support. "
                "Each call returns at most 5 notes to avoid token waste. "
                ""
                "REQUIREMENTS:"
                "- Call this tool when user asks to see notes, view notes, "
                "  list notes, or check what notes exist."
                "- If user asks to continue or see more notes, call with "
                "  increased offset parameter."
                ""
                "PARAMETER RULES:"
                "- offset: Number of notes to skip (default 0 for first page)"
                ""
                "BEHAVIOR:"
                "- Returns a formatted list of notes with ID, content preview, "
                "  tags, and creation time"
                "- Total count is included so user knows how many notes exist"
            ),
            parameters=[
                ToolParameter(
                    name="offset",
                    type=ToolParameterType.INTEGER,
                    description="Number of results to skip. Use 0 for first page, 5 for second page, etc.",
                    required=False,
                    default=0
                )
            ]
        )

    def execute(self, offset: int = 0) -> str:
        limit = 5  # 硬编码上限
        memories, total = memory_manager.list_memories(
            offset=offset,
            limit=limit,
            sort_by="created_at",
            sort_order="desc"
        )

        # 格式化输出
        lines = [f"📝 共有 {total} 条笔记，显示第 {offset+1}-{min(offset+limit, total)} 条:\n"]
        for m in memories:
            tags = json.loads(m.tags) if m.tags else []
            preview = m.content[:60].replace('\n', ' ')
            lines.append(f"[{m.id}] {preview}... | 标签: {', '.join(tags)} | 创建: {m.created_at}")

        if offset + limit < total:
            lines.append(f"\n💡 还有 {total - offset - limit} 条笔记，说"继续"或"下一页"查看更多")

        return "\n".join(lines)
```

### 4.3 SearchMemoryTool（优化）

```python
class SearchMemoryTool(Tool):
    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="search_memory",
            description=(
                "Search notes using keywords or semantic similarity. "
                "Each query returns at most 5 results. "
                ""
                "REQUIREMENTS:"
                "- Call when user asks to find notes about a specific topic, "
                "  keyword, or concept"
                "- Supports both exact keyword matching and semantic understanding"
                "- If user says 'continue' or 'more results', call with offset parameter"
                ""
                "PARAMETER RULES:"
                "- queries: List of search terms or questions (e.g., ['docker', 'container'])"
                "- offset: For pagination, use 5 for second page, 10 for third, etc."
                ""
                "BEHAVIOR:"
                "- Uses hybrid search (keyword + semantic) for best results"
                "- Returns notes with relevance scores"
                "- Total matching count is included"
            ),
            parameters=[
                ToolParameter(
                    name="queries",
                    type=ToolParameterType.ARRAY,
                    description="Search queries (list of strings)",
                    required=True
                ),
                ToolParameter(
                    name="offset",
                    type=ToolParameterType.INTEGER,
                    description="Number of results to skip",
                    required=False,
                    default=0
                )
            ]
        )

    def execute(self, queries: list, offset: int = 0) -> str:
        limit = 5
        results = ltm.get(queries=queries, limit=limit, offset=offset)

        output = []
        for result in results:
            output.append(f"查询: {result.query} (共 {result.total} 条相关)")

            if len(result.memories) == 0:
                output.append("  未找到相关笔记")
            else:
                for mem in result.memories[:limit]:
                    tags_str = ', '.join(mem.get('tags', []))
                    score_str = f" (相关度: {mem.get('score', 0):.2f})"
                    output.append(f"  [{mem['id']}] {mem['content'][:80]}... | 标签: {tags_str}{score_str}")

            if result.total > limit:
                output.append(f"  💡 还有 {result.total - limit} 条结果，说"更多"查看")

        return "\n".join(output)
```

### 4.4 EditNoteTool

```python
class EditNoteTool(Tool):
    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="edit_note",
            description=(
                "Edit note content and/or tags. "
                ""
                "REQUIREMENTS:"
                "- User MUST clearly specify which note to edit:"
                "  1. By ID (preferred): 'edit note 5' or 'change note 5'"
                "  2. By content description: 'edit the note about docker restart' "
                "     ONLY IF the description uniquely identifies one note"
                "- DO NOT call this tool if user says ambiguous things like "
                "  'edit that note', 'change this one', 'edit the second one' "
                "  WITHOUT prior context showing note IDs."
                "- If unclear, ask user to specify the note ID."
                ""
                "PARAMETER RULES:"
                "- note_id: Required. The numeric ID of the note to edit"
                "- content: Optional. New note content. If not provided, only tags are updated"
                "- tags: Optional. List of new tags to replace existing tags"
                ""
                "BEHAVIOR:"
                "- Updates the note with new content and/or tags"
                "- Preserves creation time, updates 'updated_at' timestamp"
                "- Returns success confirmation"
            ),
            parameters=[
                ToolParameter(
                    name="note_id",
                    type=ToolParameterType.INTEGER,
                    description="The numeric ID of the note to edit. User must provide this.",
                    required=True
                ),
                ToolParameter(
                    name="content",
                    type=ToolParameterType.STRING,
                    description="New note content (optional)",
                    required=False
                ),
                ToolParameter(
                    name="tags",
                    type=ToolParameterType.ARRAY,
                    description="New list of tags to replace existing tags (optional)",
                    required=False
                )
            ]
        )

    def execute(self, note_id: int, content: str = None, tags: list = None) -> str:
        if content is None and tags is None:
            return "❌ 请提供要修改的内容或标签"

        success = memory_manager.update_memory(note_id, content, tags)

        if success:
            return f"✅ 笔记 {note_id} 已更新"
        else:
            return f"❌ 笔记 {note_id} 不存在"
```

### 4.5 DeleteNoteTool

```python
class DeleteNoteTool(Tool):
    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="delete_note",
            description=(
                "Delete a note (soft delete, can be recovered). "
                ""
                "REQUIREMENTS:"
                "- User MUST clearly specify which note to delete:"
                "  1. By ID (preferred): 'delete note 5' or 'remove note 5'"
                "  2. By content description: 'delete the note about docker restart' "
                "     ONLY IF the description uniquely identifies one note"
                "- DO NOT call this tool if user says ambiguous things like "
                "  'delete that note', 'remove this one', 'delete the second one' "
                "  WITHOUT prior context showing note IDs."
                "- If user's description is not unique (e.g., 'delete docker note' "
                "  when there are multiple docker notes), ask user to specify the ID."
                "- If unclear, ask user to specify the note ID or describe the content."
                ""
                "PARAMETER RULES:"
                "- note_id: Required. The numeric ID of the note to delete"
                ""
                "BEHAVIOR:"
                "- Performs soft delete (note is marked as disabled but not removed)"
                "- Note can be recovered later if needed"
                "- Returns success confirmation with note ID"
            ),
            parameters=[
                ToolParameter(
                    name="note_id",
                    type=ToolParameterType.INTEGER,
                    description="The numeric ID of the note to delete. User must provide this.",
                    required=True
                )
            ]
        )

    def execute(self, note_id: int) -> str:
        success = memory_manager.disable_memory(note_id)

        if success:
            return f"✅ 笔记 {note_id} 已删除（软删除，可恢复）"
        else:
            return f"❌ 笔记 {note_id} 不存在"
```

---

## 5. MemoryManager 扩展

### 5.1 新增方法

```python
# agent/memory/models.py

class MemoryManager:
    # ... 现有方法 ...

    def list_memories(
        self,
        enabled_only: bool = True,
        tag_filter: str = None,
        search_query: str = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        offset: int = 0,
        limit: int = 5
    ) -> tuple[List[MemoryItem], int]:
        """
        获取笔记列表（分页）

        Args:
            enabled_only: 只返回启用的笔记
            tag_filter: 按标签筛选
            search_query: 在内容中搜索关键词
            sort_by: 排序字段 (created_at | updated_at | access_count)
            sort_order: 排序方向 (desc | asc)
            offset: 跳过前 N 条（分页用）
            limit: 最多返回 N 条

        Returns:
            (笔记列表, 总数)
        """
        session = self.get_session()
        try:
            query = session.query(MemoryItem)

            # 筛选
            if enabled_only:
                query = query.filter(MemoryItem.enabled == True)

            if tag_filter:
                query = query.filter(MemoryItem.tags.contains(tag_filter))

            if search_query:
                query = query.filter(MemoryItem.content.contains(search_query))

            # 总数（分页前）
            total = query.count()

            # 排序
            order_column = {
                "created_at": MemoryItem.created_at,
                "updated_at": MemoryItem.updated_at,
                "access_count": MemoryItem.access_count
            }.get(sort_by, MemoryItem.created_at)

            if sort_order == "desc":
                query = query.order_by(order_column.desc())
            else:
                query = query.order_by(order_column.asc())

            # 分页
            memories = query.offset(offset).limit(limit).all()

            return memories, total

        finally:
            session.close()

    def update_memory(
        self,
        memory_id: int,
        content: str = None,
        tags: List[str] = None
    ) -> bool:
        """
        更新笔记

        Args:
            memory_id: 笔记 ID
            content: 新内容（可选）
            tags: 新标签列表（可选）

        Returns:
            是否更新成功
        """
        session = self.get_session()
        try:
            memory = session.query(MemoryItem).filter_by(id=memory_id).first()
            if not memory:
                return False

            if content is not None:
                memory.content = content

            if tags is not None:
                import json
                memory.tags = json.dumps(tags, ensure_ascii=False)

            memory.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            session.commit()
            return True

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
```

### 5.2 LongTermMemory 分页支持

```python
# agent/memory/long_term_memory.py

class LongTermMemory:
    # ... 现有代码 ...

    def get(
        self,
        queries: List[str],
        limit: int = 5,
        offset: int = 0,
        use_rerank: bool = False
    ) -> List[MemoryResult]:
        """
        批量检索（支持分页）

        Args:
            queries: 查询列表
            limit: 每个查询最多返回条数
            offset: 跳过前 N 条
            use_rerank: 是否使用重排序

        Returns:
            MemoryResult 列表，每个 result 包含 total 字段
        """
        # ... 现有搜索逻辑 ...

        # 在 MemoryResult 中添加 total 字段
        return MemoryResult(
            query=query,
            memories=memories,
            total=len(all_memories_for_query),  # 总数
            retrieval_time=retrieval_time
        )
```

---

## 6. 实现计划

### Phase 1: MemoryManager 扩展（基础层）

**目标**：扩展数据层能力，支持分页和更新

**任务**：
1. ✅ `MemoryManager.list_memories()` - 分页查询
2. ✅ `MemoryManager.update_memory()` - 更新笔记
3. ✅ 测试：单元测试 MemoryManager 新方法

**验收标准**：
- [ ] 可以分页获取笔记列表
- [ ] 可以更新笔记内容和标签
- [ ] 单元测试覆盖率 ≥ 80%

**预计时间**：1-2 天

---

### Phase 2: Tool 实现（工具层）

**目标**：实现新的 Tool，优化现有 Tool

**任务**：
1. ✅ `ListNotesTool` - 列表工具
2. ✅ `EditNoteTool` - 编辑工具
3. ✅ `DeleteNoteTool` - 删除工具
4. ✅ `SearchMemoryTool` - 优化返回格式，支持分页
5. ✅ 注册新 Tool 到 ToolRegistry

**验收标准**：
- [ ] 所有 Tool 符合 description 规范
- [ ] Tool 返回格式清晰，包含分页信息
- [ ] LLM 能正确理解 Tool 调用条件

**预计时间**：2-3 天

---

### Phase 3: 集成测试（端到端）

**目标**：测试 Agent + Tool 的端到端交互

**任务**：
1. ✅ 编写集成测试用例
2. ✅ 测试各种用户输入场景
3. ✅ 验证 LLM 的 Tool 选择逻辑

**测试用例**：

| # | 用户输入 | 预期行为 | 预期输出 |
|---|---------|---------|---------|
| 1 | "有哪些笔记" | 调用 ListNotesTool | 显示前 5 条笔记 |
| 2 | "docker 相关的笔记" | 调用 SearchMemoryTool | 显示相关笔记 |
| 3 | "再看看其他的" | 调用 Tool(offset=5) | 显示下一页 |
| 4 | "删除第 3 条笔记" | 调用 DeleteNoteTool(id=3) | 确认删除 |
| 5 | "把第 3 条改成 ..." | 调用 EditNoteTool | 确认修改 |
| 6 | "删除关于 docker 的笔记" | 如果唯一则删除，否则询问 | 符合预期的响应 |
| 7 | "删除那条笔记"（无上下文） | 不调用 Tool，询问用户 | "请问要删除哪条笔记" |

**验收标准**：
- [ ] 所有测试用例通过
- [ ] LLM 正确判断 Tool 调用条件
- [ ] 分页功能正常工作

**预计时间**：2-3 天

---

### Phase 4: CLI/Web 适配（可选）

**目标**：为 CLI 和 Web 添加便捷命令

**任务**：
1. ✅ CLI: `/notes` 命令（可选，用户也可直接对话）
2. ✅ Web: REST API 端点（可选，用于管理界面）

**验收标准**：
- [ ] CLI 命令能正常工作
- [ ] REST API 返回正确的数据格式

**预计时间**：1-2 天（可选）

---

## 7. 测试策略

### 7.1 单元测试

```python
# tests/unit/test_memory_manager.py

class TestMemoryManager:
    def test_list_memories_pagination(self):
        """测试分页功能"""
        # 添加测试数据
        for i in range(10):
            memory_manager.add_memory(f"Note {i}")

        # 第一页
        memories, total = memory_manager.list_memories(offset=0, limit=5)
        assert total == 10
        assert len(memories) == 5

        # 第二页
        memories, total = memory_manager.list_memories(offset=5, limit=5)
        assert len(memories) == 5

    def test_update_memory(self):
        """测试更新功能"""
        note_id = memory_manager.add_memory("Original content")
        success = memory_manager.update_memory(note_id, content="Updated content")

        assert success is True
        note = memory_manager.get_memory(note_id)
        assert note.content == "Updated content"
```

### 7.2 Tool 测试

```python
# tests/unit/test_note_tools.py

class TestNoteTools:
    def test_list_notes_tool(self):
        """测试列表工具"""
        tool = ListNotesTool()
        result = tool.execute(offset=0)

        assert "共有" in result
        assert "笔记" in result

    def test_edit_note_tool_validation(self):
        """测试编辑工具参数验证"""
        tool = EditNoteTool()

        # 无参数应返回错误
        result = tool.execute(note_id=1)
        assert "请提供" in result or "不存在" in result
```

### 7.3 集成测试

```python
# tests/integration/test_note_management.py

class TestNoteManagementIntegration:
    def test_user_flow_list_and_delete(self):
        """测试用户查看并删除笔记的流程"""
        # 准备数据
        note_id = memory_manager.add_memory("Test note")

        # 模拟用户输入
        result = agent.process("有哪些笔记？")
        assert "Test note" in result

        result = agent.process(f"删除第 {note_id} 条笔记")
        assert "已删除" in result

        # 验证软删除
        note = memory_manager.get_memory(note_id)
        assert note.enabled is False
```

---

## 8. 风险与注意事项

### 8.1 LLM 理解偏差

**风险**：LLM 可能误解 Tool 的调用条件

**缓解措施**：
- Tool description 写得足够详细
- 在集成测试中覆盖各种边界情况
- 必要时调整 description

### 8.2 分页状态丢失

**风险**：用户说"继续"时，LLM 忘记了上一页的 offset

**缓解措施**：
- Tool 返回值中包含明确的 offset 提示
- 对话历史自动保存上下文

### 8.3 Token 消耗

**风险**：即使有分页，长对话仍可能消耗大量 token

**监控指标**：
- 平均每次查询的 token 数
- Tool 返回的平均字符数

---

## 9. 附录

### 9.1 相关文件

```
agent/memory/models.py          - MemoryManager 扩展
agent/memory/long_term_memory.py - LongTermMemory 分页支持
agent/tools/impl.py             - 新增 Tool
agent/tools/base.py             - Tool 基类（可能需要微调）
tests/unit/test_memory_manager.py - 单元测试
tests/integration/test_note_management.py - 集成测试
```

### 9.2 环境变量

无需新增环境变量

### 9.3 数据库变更

无需数据库 schema 变更（使用现有表）

---

## 文档版本

- **版本**: 1.0
- **日期**: 2025-03-01
- **状态**: 设计完成，待评审
