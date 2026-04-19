"""
Tool implementations for new architecture.

Migrated tools from old toolbox to new Tool base class.

Phase 5 Complete:
- New unified memory tools only (AddMemoryTool, SearchMemoryTool)
- Legacy tools removed (NoteTool, GetAllNotesTool, QuickCommandTool, etc.)
"""
import json
import platform
import subprocess
from typing import Any, Optional

from agent.context import Context
from agent.memory.long_term_memory import get_long_term_memory
from agent.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSchema,
)
from infrastructure.config.utils import get_tmp_file



class WeatherTool(Tool):
    """Tool for querying weather information."""

    @property
    def schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name="search_weather",
            description="Query weather for a location on a specific date.",
            parameters=[
                ToolParameter(
                    name="location",
                    type=ToolParameterType.STRING,
                    description="Location name to query weather for",
                    required=True
                ),
                ToolParameter(
                    name="date",
                    type=ToolParameterType.STRING,
                    description="Date in yyyy-MM-dd format, e.g., 2023-05-11",
                    required=True
                )
            ]
        )

    def execute(self, **kwargs: Any) -> Any:
        """Execute weather query."""
        location = kwargs.get("location", "")
        date = kwargs.get("date", "")
        # This is a mock implementation
        return f"Weather for {location} on {date}: Cloudy with temperatures 15-25°C"


class EmailTool(Tool):
    """Tool for sending emails."""

    @property
    def schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name="send_email",
            description="Send email with subject to address. Message content should be polished.",
            parameters=[
                ToolParameter(
                    name="to_address",
                    type=ToolParameterType.STRING,
                    description="Recipient email address",
                    required=True
                ),
                ToolParameter(
                    name="subject",
                    type=ToolParameterType.STRING,
                    description="Email subject",
                    required=True
                ),
                ToolParameter(
                    name="msg",
                    type=ToolParameterType.STRING,
                    description="Email message content",
                    required=True
                )
            ]
        )

    def execute(self, **kwargs: Any) -> Any:
        """Execute email sending."""
        to_address = kwargs.get("to_address", "")
        subject = kwargs.get("subject", "")
        # This is a mock implementation
        return f"Email sent to {to_address} with subject '{subject}'"


class SendMessageTool(Tool):
    """Tool for sending messages to user."""

    def __init__(self) -> None:
        self._context: Optional[Context] = None

    def set_context(self, context: Context) -> None:
        self._context = context

    @property
    def schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name="send_msg_to_user",
            description="Send message to user.",
            parameters=[
                ToolParameter(
                    name="msg",
                    type=ToolParameterType.STRING,
                    description="Message to send",
                    required=True
                ),
                ToolParameter(
                    name="wait_for_res",
                    type=ToolParameterType.STRING,
                    description=(
                        "Y or N, whether to wait for user response. Only Y when there's a "
                        "clear task that requires user reply to continue, otherwise N"
                    ),
                    required=False,
                    default="N"
                )
            ]
        )

    def execute(self, **kwargs: Any) -> Any:
        """Execute message sending."""
        msg = kwargs.get("msg", "")
        wait_for_res = kwargs.get("wait_for_res", "N")
        context = self._context

        if not context:
            return f"Message sent: {msg}"

        context.add_message("assistant", msg)

        if wait_for_res == "N":
            return f"Message sent: {msg}"

        context.set_waiting_user_answer(True)
        return f"Message sent and waiting for response: {msg}"


class SendFileTool(Tool):
    """Tool for sending files to user."""

    def __init__(self) -> None:
        self._context: Optional[Context] = None

    def set_context(self, context: Context) -> None:
        self._context = context

    @property
    def schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name="send_file_user",
            description="Send file to user.",
            parameters=[
                ToolParameter(
                    name="file_name",
                    type=ToolParameterType.STRING,
                    description="Filename to send",
                    required=True
                )
            ]
        )

    def execute(self, **kwargs: Any) -> Any:
        """Execute file sending."""
        file_name = kwargs.get("file_name", "")
        context = self._context

        data = get_tmp_file(file_name)
        if context:
            context.add_message("system", f"File content: {data}")

        return f"File '{file_name}' sent to user"


class AskUserTool(Tool):
    """Tool for asking user questions and pausing execution."""

    def __init__(self) -> None:
        self._context: Optional[Context] = None

    def set_context(self, context: Context) -> None:
        self._context = context

    @property
    def schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name="ask_user",
            description=(
                "Ask user a question and pause execution. "
                "Use this when you need user confirmation, additional information, "
                "or a choice between options before proceeding."
            ),
            parameters=[
                ToolParameter(
                    name="question",
                    type=ToolParameterType.STRING,
                    description="Question to ask user",
                    required=True
                ),
                ToolParameter(
                    name="options",
                    type=ToolParameterType.ARRAY,
                    description=(
                        "Optional list of answer choices (e.g., ['yes', 'no']). "
                        "If provided, user should select from these options."
                    ),
                    required=False
                )
            ]
        )

    def execute(self, **kwargs: Any) -> Any:
        """Execute asking user question."""
        question = kwargs.get("question", "")
        options = kwargs.get("options")
        context = self._context

        # Store question in context for Interface layer to read
        if context:
            context.set_state("pending_question", {
                "question": question,
                "options": options
            })
            context.set_waiting_user_answer(True)

        # Return special marker to trigger pause
        return "__ASK_USER_PENDING__"


class SystemInfoTool(Tool):
    """
    Tool for getting cross-platform system information.

    Provides reliable system information across different operating systems.
    """

    @property
    def schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name="get_system_info",
            description=(
                "Get cross-platform system information (CPU count, memory, OS, etc.). "
                "Use this when you need to know system specifications like CPU cores "
                "to explain load averages, memory usage, etc. Works on macOS, Linux, Windows."
            ),
            parameters=[
                ToolParameter(
                    name="info_type",
                    type=ToolParameterType.STRING,
                    description=(
                        "Type of information to retrieve. Options: "
                        "'cpu_count' (number of CPU cores), "
                        "'memory' (total and available memory), "
                        "'os' (operating system info), "
                        "'all' (all information)"
                    ),
                    required=False,
                    default="all"
                )
            ]
        )

    def execute(self, **kwargs: Any) -> Any:
        """Execute getting system information."""
        info_type = kwargs.get("info_type", "all")

        try:
            result = {}

            if info_type in ["all", "cpu_count"]:
                result["cpu_count"] = self._get_cpu_count()

            if info_type in ["all", "memory"]:
                result["memory"] = self._get_memory_info()

            if info_type in ["all", "os"]:
                result["os"] = self._get_os_info()

            # Format output nicely
            if info_type == "all":
                output = []
                output.append("=== System Information ===")
                if "os" in result:
                    output.append(f"\nOS: {result['os']}")
                if "cpu_count" in result:
                    output.append(f"CPU Cores: {result['cpu_count']}")
                if "memory" in result:
                    output.append(f"Memory: {result['memory']}")
                return "\n".join(output)
            else:
                # Return just the requested info
                return result.get(info_type.replace("all", ""), "Unknown")

        except Exception as e:
            return f"Failed to get system info: {str(e)}"

    def _get_cpu_count(self) -> int:
        """Get CPU count (cross-platform)."""
        return platform.processor() or str(os.cpu_count())

    def _get_memory_info(self) -> str:
        """Get memory information (cross-platform)."""
        system = platform.system()

        try:
            if system == "Darwin":  # macOS
                # Use vm_stat
                result = subprocess.run(
                    ["vm_stat"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                # Parse vm_stat output
                pages = 0
                for line in result.stdout.split('\n'):
                    if "Pages free" in line:
                        pages = int(line.split(':')[1].strip().replace('.', ''))
                # Page size on macOS is 4096 bytes
                return f"Free: {pages * 4096 / 1024 / 1024:.0f} MB"
            elif system == "Linux":
                # Use free command
                result = subprocess.run(
                    ["free", "-h"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return result.stdout.strip().split('\n')[1]  # Memory line
            else:
                return "Memory info not available"
        except Exception:
            return "Memory info unavailable"

    def _get_os_info(self) -> str:
        """Get OS information."""
        return f"{platform.system()} {platform.release()}"


# Import os after platform for cpu_count
import os


# ========== Unified Memory Tools (Phase 4-5) ==========


class AddMemoryTool(Tool):
    """
    Tool for adding unified long-term memory.

    Supports: Notes, experiences, commands, preferences, etc.
    Replaces: Old NoteTool, QuickCommandTool
    """

    @property
    def schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name="add_memory",
            description=(
                "添加新笔记（不是修改现有笔记）。"
                ""
                "【使用场景】"
                "✅ 用户说：'记住这个' / 'save this' / 'add a note'"
                "✅ 用户说：'添加一条笔记' / 'create a new note'"
                "❌ 用户说：'修改笔记' / 'change this' / 'update that' → 用 edit_note"
                ""
                "【关键区分】"
                "- 如果用户提到'修改'、'改'、'更新'、'fix'，用edit_note"
                "- 如果用户提到'添加'、'新建'、'记住'，用add_memory"
                ""
                "【参数】"
                "- content: 笔记内容（必填）"
                "- tags: 标签列表（可选，如['docker', 'devops']）"
                "- source_type: 来源类型（可选，'用户' 或 '自动记录'，默认'用户'）"
            ),
            parameters=[
                ToolParameter(
                    name="content",
                    type=ToolParameterType.STRING,
                    description="Content to save to memory",
                    required=True
                ),
                ToolParameter(
                    name="tags",
                    type=ToolParameterType.ARRAY,
                    description=(
                        "Optional list of tags for categorization "
                        "(e.g., ['docker', 'devops'])"
                    ),
                    required=False
                ),
                ToolParameter(
                    name="source_type",
                    type=ToolParameterType.STRING,
                    description=(
                        "Source type of the note: '用户' (user) or '自动记录' (auto-recorded). "
                        "Default is '用户'."
                    ),
                    required=False,
                    default="用户"
                )
            ]
        )

    def execute(self, **kwargs: Any) -> Any:
        """Execute adding memory."""
        content = kwargs.get("content", "")
        tags = kwargs.get("tags")
        source_type = kwargs.get("source_type", "用户")

        if not content or not content.strip():
            return "Content cannot be empty"

        try:
            ltm = get_long_term_memory()
            result = ltm.set(content=content, tags=tags, source_type=source_type)
            return result.message
        except Exception as e:
            return f"Failed to save memory: {str(e)}"


class ListNotesTool(Tool):
    """
    Tool for listing notes with pagination.

    Lists all notes with pagination support.
    """

    @property
    def schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name="list_notes",
            description=(
                "查看所有笔记列表（不分页时最多5条）。"
                ""
                "【使用场景】"
                "✅ 用户说：'有哪些笔记' / '查看所有笔记' / 'show all notes' / 'list notes'"
                "✅ 用户说：'看看笔记' / '查看笔记'（无特定关键词）"
                "❌ 用户说：'关于docker的笔记' / '查找电视相关' → 用 search_memory"
                ""
                "【功能说明】"
                "- 返回所有笔记的ID、内容预览、标签"
                "- 支持分页（offset参数）"
                "- 格式：📌 笔记 #ID\\n   内容: ...\\n   标签: ..."
            ),
            parameters=[
                ToolParameter(
                    name="offset",
                    type=ToolParameterType.INTEGER,
                    description=(
                        "Number of results to skip. Use 0 for first page, "
                        "5 for second page, etc."
                    ),
                    required=False,
                    default=0
                )
            ]
        )

    def execute(self, **kwargs: Any) -> Any:
        """Execute listing notes."""
        from agent.memory.models import memory_manager

        offset = kwargs.get("offset", 0)
        limit = 5  # Hardcoded limit

        try:
            memories, total = memory_manager.list_memories(
                enabled_only=True,
                offset=offset,
                limit=limit,
                sort_by="created_at",
                sort_order="desc"
            )

            # Format output with clear ID display
            lines = [f"📝 共有 {total} 条笔记，显示第 {offset+1}-{min(offset+limit, total)} 条:\n"]

            if not memories:
                lines.append("  暂无笔记")
            else:
                for m in memories:
                    tags = json.loads(m.tags) if m.tags else []
                    preview = m.content[:60].replace('\n', ' ')
                    source_type = getattr(m, 'source_type', '用户')
                    # Make ID more prominent
                    lines.append(
                        f"📌 笔记 #{m.id}\n"
                        f"   内容: {preview}...\n"
                        f"   标签: {', '.join(tags)}\n"
                        f"   来源: {source_type}\n"
                    )

            if offset + limit < total:
                lines.append(f"\n💡 还有 {total - offset - limit} 条笔记，说\"继续\"查看更多")

            return "\n".join(lines)

        except Exception as e:
            return f"Failed to list notes: {str(e)}"


class EditNoteTool(Tool):
    """
    Tool for editing note content and/or tags.
    """

    @property
    def schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name="edit_note",
            description=(
                "修改已有笔记的内容或标签（不创建新笔记）。"
                ""
                "【使用场景】"
                "✅ 用户说：'修改笔记5' / 'edit note 5' / 'change note 5'"
                "✅ 用户说：'修改这一条' / 'edit that note'（从上下文提取ID）"
                "❌ 用户说：'添加一条笔记' / 'save a note' → 用 add_memory"
                ""
                "【关键规则】"
                "- 必须提供note_id参数"
                "- 从对话历史中查找笔记ID（格式：📌 笔记 #ID）"
                "- 如果用户说'修改电视那条笔记'，历史显示'📌 笔记 #5 电视'，则note_id=5"
                "- 如果用户描述不明确（多条匹配），请询问用户具体ID"
                ""
                "【参数】"
                "- note_id: 笔记ID（必填）"
                "- content: 新内容（可选）"
                "- tags: 新标签列表（可选）"
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

    def execute(self, **kwargs: Any) -> Any:
        """Execute editing note."""
        from agent.memory.models import memory_manager

        note_id = kwargs.get("note_id")
        content = kwargs.get("content")
        tags = kwargs.get("tags")

        if note_id is None:
            return "❌ 请提供笔记 ID"

        if content is None and tags is None:
            return "❌ 请提供要修改的内容或标签"

        try:
            success = memory_manager.update_memory(note_id, content, tags)

            if success:
                return f"✅ 笔记 {note_id} 已更新"
            else:
                return f"❌ 笔记 {note_id} 不存在"

        except Exception as e:
            return f"Failed to edit note: {str(e)}"


class DeleteNoteTool(Tool):
    """
    Tool for deleting a note (soft delete, can be recovered).
    """

    @property
    def schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name="delete_note",
            description=(
                "删除已有笔记（软删除，可恢复）。"
                ""
                "【使用场景】"
                "✅ 用户说：'删除笔记5' / 'delete note 5' / 'remove note 5'"
                "✅ 用户说：'删除这一条' / 'delete that note'（从上下文提取ID）"
                ""
                "【关键规则】"
                "- 必须提供note_id参数"
                "- 从对话历史中查找笔记ID（格式：📌 笔记 #ID）"
                "- 如果用户说'删除电视那条笔记'，历史显示'📌 笔记 #5 电视'，则note_id=5"
                "- 如果用户描述不明确（多条匹配），请询问用户具体ID"
                ""
                "【参数】"
                "- note_id: 要删除的笔记ID（必填）"
                ""
                "【说明】"
                "- 软删除：笔记被标记为删除，但可以恢复"
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

    def execute(self, **kwargs: Any) -> Any:
        """Execute deleting note."""
        from agent.memory.models import memory_manager

        note_id = kwargs.get("note_id")

        if note_id is None:
            return "❌ 请提供笔记 ID"

        try:
            success = memory_manager.disable_memory(note_id)

            if success:
                return f"✅ 笔记 {note_id} 已删除（软删除，可恢复）"
            else:
                return f"❌ 笔记 {note_id} 不存在"

        except Exception as e:
            return f"Failed to delete note: {str(e)}"


class SearchMemoryTool(Tool):
    """
    Tool for searching unified long-term memory.

    Supports: Keyword search, semantic search, hybrid search
    Replaces: Old GetAllNotesTool, GetAllQuickCommandsTool
    """

    @property
    def schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name="search_memory",
            description=(
                "搜索特定关键词或主题的笔记（语义+关键词混合搜索）。"
                ""
                "【使用场景】"
                "✅ 用户说：'关于docker的笔记' / '查找电视相关' / 'search for TV'"
                "✅ 用户说：'有没有关于xxx的笔记' / 'find notes about...'"
                "❌ 用户说：'查看所有笔记' / '有哪些笔记'（无关键词）→ 用 list_notes"
                ""
                "【重要】"
                "- 此工具需要queries参数，不能为空"
                "- 如果用户没提供搜索词，请询问用户要搜索什么"
                ""
                "【功能说明】"
                "- 支持语义搜索和关键词搜索"
                "- 返回相关度分数"
                "- 格式：📌 笔记 #ID\\n   内容: ...\\n   相关度: ..."
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

    def execute(self, **kwargs: Any) -> Any:
        """Execute searching memory."""
        queries = kwargs.get("queries", [])
        offset = kwargs.get("offset", 0)
        limit = 5  # Hardcoded limit

        if not queries:
            return "Queries cannot be empty"

        try:
            ltm = get_long_term_memory()
            results = ltm.get(queries=queries, limit=limit, use_rerank=False)

            # Format results with clear ID display
            output = []
            for result in results:
                total = len(result.memories)  # Total available for this query
                showing = min(total, limit)

                output.append(f"查询: {result.query} (找到 {total} 条相关)")

                if total == 0:
                    output.append("  未找到相关笔记")
                else:
                    for mem in result.memories[:showing]:
                        tags_str = ", ".join(mem.get("tags", []))
                        score = mem.get("score", 0)
                        source_type = mem.get("source_type", "用户")
                        # Make ID more prominent
                        output.append(
                            f"  📌 笔记 #{mem['id']}\n"
                            f"     内容: {mem['content'][:80]}...\n"
                            f"     标签: {tags_str}\n"
                            f"     来源: {source_type}\n"
                            f"     相关度: {score:.2f}"
                        )

                    if total > showing:
                        output.append(f"  💡 还有 {total - showing} 条结果，说\"更多\"查看")

                output.append("")

            return "\n".join(output)

        except Exception as e:
            return f"Failed to search memory: {str(e)}"


def create_default_tools() -> list[Tool]:
    """
    Create list of default tool instances.

    Phase 5: Only unified memory tools, legacy tools removed.

    Returns:
        List of default tools
    """
    return [
        WeatherTool(),
        EmailTool(),
        # SendMessageTool(),  # Disabled - not needed
        SendFileTool(),
        # AskUserTool(),  # Disabled - not needed
        SystemInfoTool(),  # Add cross-platform system info tool
        # Unified memory tools
        AddMemoryTool(),
        ListNotesTool(),
        EditNoteTool(),
        DeleteNoteTool(),
        SearchMemoryTool(),
    ]


__all__ = [
    'WeatherTool',
    'EmailTool',
    'SendMessageTool',
    'SendFileTool',
    'AskUserTool',
    'SystemInfoTool',
    # Unified memory tools
    'AddMemoryTool',
    'ListNotesTool',
    'EditNoteTool',
    'DeleteNoteTool',
    'SearchMemoryTool',
    'create_default_tools',
]
