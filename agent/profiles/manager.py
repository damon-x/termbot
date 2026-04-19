"""
Agent profile management.

An AgentProfile defines a named agent configuration:
  - system_prompt: the agent's role and behavior
  - allowed_tools:  hard constraint on which tools it may call (empty = all)
  - allowed_skills: hard constraint on which skills it may invoke (empty = all)

Profiles are stored as JSON files under ~/.termbot/agents/ and are
interface-agnostic (used by both Web and CLI modes).
"""
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional


DEFAULT_SYSTEM_PROMPT = """You are an intelligent terminal assistant.

Use tools (via function calling) to help users. Available tools will be provided with their descriptions.

When appropriate:
- Check notes if user asks about previously mentioned information
- Try alternative approaches if a tool fails
- Provide clear, helpful responses"""

# Full registry of tools that can be assigned to an agent profile.
# Used by the UI to present a selection list when creating/editing a profile.
AVAILABLE_TOOLS = [
    {
        "name": "search_weather",
        "description": "查询天气信息",
        "parameters": [
            {"name": "location", "type": "string", "description": "要查询的城市名称", "required": True}
        ]
    },
    {
        "name": "send_email",
        "description": "发送邮件",
        "parameters": [
            {"name": "to", "type": "string", "description": "收件人邮箱地址", "required": True},
            {"name": "subject", "type": "string", "description": "邮件主题", "required": True},
            {"name": "body", "type": "string", "description": "邮件正文", "required": True}
        ]
    },
    {
        "name": "send_file_user",
        "description": "发送文件给用户",
        "parameters": [
            {"name": "file_path", "type": "string", "description": "文件路径", "required": True}
        ]
    },
    {
        "name": "get_system_info",
        "description": "获取系统信息",
        "parameters": []
    },
    {
        "name": "add_memory",
        "description": "添加笔记到长期记忆",
        "parameters": [
            {"name": "content", "type": "string", "description": "笔记内容", "required": True},
            {"name": "tags", "type": "array", "description": "标签列表", "required": False}
        ]
    },
    {
        "name": "list_notes",
        "description": "列出所有笔记",
        "parameters": []
    },
    {
        "name": "edit_note",
        "description": "编辑已有笔记",
        "parameters": [
            {"name": "note_id", "type": "string", "description": "笔记ID", "required": True},
            {"name": "new_content", "type": "string", "description": "新的笔记内容", "required": True}
        ]
    },
    {
        "name": "delete_note",
        "description": "删除笔记",
        "parameters": [
            {"name": "note_id", "type": "string", "description": "笔记ID", "required": True}
        ]
    },
    {
        "name": "search_memory",
        "description": "搜索笔记",
        "parameters": [
            {"name": "query", "type": "string", "description": "搜索关键词", "required": True}
        ]
    },
    {
        "name": "exec_terminal_cmd",
        "description": "执行终端命令",
        "parameters": [
            {"name": "command", "type": "string", "description": "要执行的命令", "required": True}
        ]
    },
    {
        "name": "use_skill",
        "description": "执行技能",
        "parameters": [
            {"name": "skill_name", "type": "string", "description": "技能名称", "required": True},
            {"name": "task", "type": "string", "description": "任务描述", "required": False}
        ]
    },
    {
        "name": "delegate_task",
        "description": "异步子Agent",
        "parameters": [
            {"name": "tasks", "type": "array", "description": "任务列表", "required": True}
        ]
    },
    {
        "name": "read_file",
        "description": "读取文件内容",
        "parameters": [
            {"name": "file_path", "type": "string", "description": "文件路径", "required": True}
        ]
    },
    {
        "name": "write_file",
        "description": "写入文件内容",
        "parameters": [
            {"name": "file_path", "type": "string", "description": "文件路径", "required": True},
            {"name": "content", "type": "string", "description": "文件内容", "required": True}
        ]
    },
    {
        "name": "edit_file",
        "description": "编辑文件",
        "parameters": [
            {"name": "file_path", "type": "string", "description": "文件路径", "required": True},
            {"name": "old_string", "type": "string", "description": "要替换的旧内容", "required": True},
            {"name": "new_string", "type": "string", "description": "新内容", "required": True}
        ]
    }
]

_DEFAULT_ALLOWED_TOOLS = [
    "search_weather", "send_email", "send_file_user", "get_system_info",
    "add_memory", "list_notes", "edit_note", "delete_note", "search_memory",
    "exec_terminal_cmd", "skill_executor", "async_sub_agent",
]


class AgentProfileManager:
    """
    Manages custom agent profiles stored in ~/.termbot/agents/.

    Each profile is a JSON file containing:
      - id:             unique identifier
      - name:           display name
      - system_prompt:  defines the agent's role and behavior
      - allowed_tools:  hard constraint — only these tools may be called
                        (empty list means all tools are allowed)
      - allowed_skills: hard constraint — only these skills may be invoked
                        (empty list means all skills are allowed)
      - is_default:     True only for the built-in default profile

    The built-in default profile (id='default') is never written to disk.
    """

    PROFILES_DIR = Path.home() / ".termbot" / "agents"

    @classmethod
    def _ensure_dir(cls) -> None:
        cls.PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _default_profile(cls) -> Dict:
        return {
            "id": "default",
            "name": "TERMBOT",
            "system_prompt": DEFAULT_SYSTEM_PROMPT,
            "allowed_skills": [],
            "allowed_tools": _DEFAULT_ALLOWED_TOOLS,
            "is_default": True,
        }

    @classmethod
    def get_all(cls) -> List[Dict]:
        """Return all profiles: built-in default first, then custom ones sorted by filename."""
        profiles = [cls._default_profile()]
        cls._ensure_dir()
        for path in sorted(cls.PROFILES_DIR.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                profiles.append(data)
            except Exception:
                pass
        return profiles

    @classmethod
    def get(cls, profile_id: str) -> Optional[Dict]:
        """Return a single profile by id, or None if not found."""
        if profile_id == "default":
            return cls._default_profile()
        cls._ensure_dir()
        path = cls.PROFILES_DIR / f"{profile_id}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    @classmethod
    def create(cls, name: str, system_prompt: str,
               allowed_skills: Optional[List] = None,
               allowed_tools: Optional[List] = None) -> Dict:
        """Create and persist a new custom profile. Returns the created profile."""
        cls._ensure_dir()
        profile_id = uuid.uuid4().hex[:8]
        profile = {
            "id": profile_id,
            "name": name,
            "system_prompt": system_prompt,
            "allowed_skills": allowed_skills or [],
            "allowed_tools": allowed_tools or [],
            "is_default": False,
        }
        (cls.PROFILES_DIR / f"{profile_id}.json").write_text(
            json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return profile

    @classmethod
    def update(cls, profile_id: str, name: str, system_prompt: str,
               allowed_skills: Optional[List] = None,
               allowed_tools: Optional[List] = None) -> Optional[Dict]:
        """Update an existing custom profile. Returns updated profile, or None if not found."""
        if profile_id == "default":
            return None
        cls._ensure_dir()
        path = cls.PROFILES_DIR / f"{profile_id}.json"
        if not path.exists():
            return None
        profile = {
            "id": profile_id,
            "name": name,
            "system_prompt": system_prompt,
            "allowed_skills": allowed_skills or [],
            "allowed_tools": allowed_tools or [],
            "is_default": False,
        }
        path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        return profile

    @classmethod
    def delete(cls, profile_id: str) -> bool:
        """Delete a custom profile. Returns True on success, False if not found or protected."""
        if profile_id == "default":
            return False
        cls._ensure_dir()
        path = cls.PROFILES_DIR / f"{profile_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    @classmethod
    def available_tools(cls) -> List[Dict]:
        """Return the full tool registry, used by the UI to populate the tool selector."""
        return AVAILABLE_TOOLS
