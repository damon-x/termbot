"""
Web interface handler for Agent interaction.

Provides Web interface with multi-session support.
Each WebSocket connection gets its own Agent instance and PTY.

Architecture: 1 Web Session = 1 Agent Instance = 1 PTY Instance
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from flask import request
from flask_socketio import SocketIO, emit

from agent.factory import AgentFactory
from agent.profiles import AgentProfileManager
from agent.react import ReactResult
from agent.response_handler import ResponseHandler
from agent.skills import SkillManager
from infrastructure.terminal.pty_manager import PTYManager
from infrastructure.logging import get_logger, EventType, logger_context
from infrastructure.storage import create_conversation_logger

logger = get_logger("session.web")


class WebResponseHandler:
    """
    Response handler for Web sessions.
    
    Emits agent responses to the frontend via SocketIO.
    """
    
    def __init__(self, socketio: SocketIO, sid: str) -> None:
        """
        Initialize the handler.
        
        Args:
            socketio: SocketIO instance for emitting
            sid: Session ID (room) to emit to
        """
        self.socketio = socketio
        self.sid = sid
    
    def on_response(self, result: ReactResult) -> None:
        """
        Handle agent response by emitting to frontend.
        
        Args:
            result: The ReactResult from agent processing
        """
        if result.status == "paused":
            self.socketio.emit('chat_out', {
                'type': 'question',
                'message': result.response,
                'question': result.question,
                'options': result.options or []
            }, room=self.sid)
        else:
            self.socketio.emit('chat_out', {
                'type': 'response',
                'message': result.response
            }, room=self.sid)


class WebSession:
    """
    Represents a single web session with its own Agent and PTY.

    Each session is isolated from others:
    - Independent Agent instance (with its own Context)
    - Independent PTY Manager (separate terminal)
    - Independent conversation history
    """

    def __init__(
        self,
        sid: str,
        llm_client,
        system_prompt: str,
        socketio,
        agent_id: str = "default",
        allowed_tools: Optional[List[str]] = None,
        allowed_skills: Optional[List[str]] = None
    ) -> None:
        """
        Initialize a web session.

        Args:
            sid: SocketIO session ID
            llm_client: LLM client (shared across sessions)
            system_prompt: System prompt for agent
            socketio: SocketIO instance for emitting to clients
            allowed_tools: Optional list of allowed tool names (empty = all)
            allowed_skills: Optional list of allowed skill names (empty = all)
        """
        import random
        self.sid = sid
        self.session_id = str(random.randint(1_000_000_000, 9_999_999_999))
        self.socketio = socketio

        # Create independent PTY Manager for this session
        self.pty_manager = PTYManager(
            shell="/bin/bash",
            cols=80,
            rows=24,
            session_timeout=2.0
        )
        self.pty_manager.start()

        # Create Skill Manager for this session
        self.skill_manager = SkillManager()

        # Create Agent Factory (using this session's PTY)
        self.agent_factory = AgentFactory(
            self.pty_manager,
            self.skill_manager,
            llm_client
        )

        # Create response handler for this session
        self.response_handler = WebResponseHandler(socketio, sid)

        # Create main agent through factory with response handler and permissions
        try:
            self.agent = self.agent_factory.create_main_agent(
                system_prompt,
                response_handler=self.response_handler,
                allowed_tools=allowed_tools,
                allowed_skills=allowed_skills,
                agent_id=agent_id
            )
        except Exception as e:
            logger.error("Failed to create agent for session", sid=sid, error=str(e))
            raise

        # Store agent_id for logging context
        self.agent_id = agent_id

        # Propagate session_id to agent for worker thread logging
        self.agent.set_session_id(self.session_id)

        # Attach conversation logger to agent context
        self._conv_logger = create_conversation_logger(session_id=self.session_id, agent_id=agent_id)
        if self._conv_logger:
            self.agent.context.set_message_callback(self._conv_logger.log)
            logger.debug("Conversation logger attached", path=str(self._conv_logger.file_path))

        # Register PTY output listener for this session
        self.pty_manager.register_listener(
            lambda data: self._on_terminal_output(data)
        )

    def setup_logging_context(self) -> None:
        """Setup logging context for this session (call in each request thread)."""
        logger_context.set_session(session_id=self.session_id, mode="web")
        logger_context.set_agent(agent_id=self.agent_id)

    def _on_terminal_output(self, data: str) -> None:
        """
        Handle PTY output - send to this session's frontend.

        Args:
            data: Terminal output data
        """
        # Use socketio.emit() with room parameter (works outside request context)
        self.socketio.emit('terminal_output', {'data': data}, room=self.sid)

    def switch_conversation_log(self, session_id: str) -> None:
        """
        Redirect conversation logging to a different session file.

        Called when the user resumes a historical conversation, so that
        new messages are appended to the original session file instead of
        the current (new-connection) file.
        """
        if self._conv_logger:
            self._conv_logger.close()
        self.session_id = session_id
        self.agent.set_session_id(session_id)
        self._conv_logger = create_conversation_logger(session_id=session_id, agent_id=self.agent_id)
        if self._conv_logger:
            self.agent.context.set_message_callback(self._conv_logger.log)
            logger.debug("Conversation log switched", path=str(self._conv_logger.file_path))

    def cleanup(self) -> None:
        """Clean up session resources."""
        try:
            self.pty_manager.stop()
        except Exception:
            pass
        if self._conv_logger:
            self._conv_logger.close()


class WebHandler:
    """
    Web interface handler with multi-session support.

    Manages multiple user sessions, each with its own Agent and PTY.
    """

    # Default system prompt for web sessions
    DEFAULT_SYSTEM_PROMPT = """You are an intelligent terminal assistant.

Use tools (via function calling) to help users. Available tools will be provided with their descriptions.

When appropriate:
- Check notes if user asks about previously mentioned information
- Try alternative approaches if a tool fails
- Provide clear, helpful responses"""

    def __init__(
        self,
        socketio: SocketIO,
        llm_client,
        system_prompt: Optional[str] = None
    ) -> None:
        """
        Initialize Web handler.

        Args:
            socketio: Flask-SocketIO instance
            llm_client: Shared LLM client (stateless, safe to share)
            system_prompt: Optional custom system prompt
        """
        self.socketio = socketio
        self.shared_llm_client = llm_client
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        self.sessions: Dict[str, WebSession] = {}

        # Register event handlers
        self._register_event_handlers()

    def _register_event_handlers(self) -> None:
        """Register SocketIO event handlers."""

        @self.socketio.on('connect')
        def handle_connect():
            """New client connection - create independent Agent + PTY."""
            sid = request.sid

            # Set temporary logging context (updated after session is created)
            logger_context.set_session(session_id=sid, mode="web")

            # Resolve system prompt from agent_id query param
            agent_id = request.args.get('agent_id', 'default')
            logger.info("Client connected", sid=sid, agent_id=agent_id)

            profile = AgentProfileManager.get(agent_id) or {}
            system_prompt = profile.get('system_prompt', self.system_prompt)

            # Get allowed tools and skills from profile (empty list = all allowed)
            allowed_tools = profile.get('allowed_tools', [])
            allowed_skills = profile.get('allowed_skills', [])

            # Create new session with independent Agent and PTY
            try:
                session = WebSession(
                    sid,
                    self.shared_llm_client,
                    system_prompt,
                    self.socketio,
                    agent_id=agent_id,
                    allowed_tools=allowed_tools,
                    allowed_skills=allowed_skills
                )
                self.sessions[sid] = session
                # Update logging context to use the business session_id
                logger_context.set_session(session_id=session.session_id, mode="web")
                logger.info("Session created", session_id=session.session_id, agent_id=agent_id)
            except Exception as e:
                logger.error("Failed to create WebSession", sid=sid, error=str(e))
                raise

            # Notify client (compatible with original project)
            emit('start_conversation', {'id': ''})

        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Client disconnect - cleanup Agent and PTY."""
            sid = request.sid
            if sid in self.sessions:
                session = self.sessions[sid]
                session.cleanup()
                del self.sessions[sid]
            
            # Clear logging context
            logger_context.clear()

        @self.socketio.on('chat_in')
        def handle_chat_message(data):
            """Handle chat message from client (original project event name)."""
            sid = request.sid
            message = data.get('message', '').strip()

            if not message:
                return

            if sid not in self.sessions:
                self.socketio.emit('chat_out', {'message': 'Session not found. Please refresh.'}, room=sid)
                return

            session = self.sessions[sid]
            
            # Setup logging context for this request thread
            session.setup_logging_context()

            # Check if it's a command first (commands are not answers to questions)
            if message.startswith("/"):
                response = self._handle_command(message, session)
                self.socketio.emit('chat_out', {'message': response}, room=sid)
                return

            # Submit message to agent queue - returns immediately
            # Response will be delivered via WebResponseHandler
            session.agent.submit(message)

        @self.socketio.on('terminal_input')
        def handle_terminal_input(data):
            """Handle terminal input from client."""
            sid = request.sid
            user_input = data.get('input', data.get('data', ''))

            if sid not in self.sessions:
                return

            session = self.sessions[sid]

            # Write to this session's PTY
            result = session.pty_manager.write_web(user_input, sid)

            if not result.success:
                self.socketio.emit('terminal_error', {'message': result.message}, room=sid)

        @self.socketio.on('terminal_resize')
        def handle_terminal_resize(data):
            """Handle terminal resize from client."""
            sid = request.sid
            cols = data.get('cols', 80)
            rows = data.get('rows', 24)

            if sid in self.sessions:
                session = self.sessions[sid]
                session.pty_manager.resize(cols, rows)

        @self.socketio.on('load_history')
        def handle_load_history(data):
            """Load a historical conversation into the current agent context."""
            import json as _json
            from pathlib import Path as _Path
            from infrastructure.config.settings import settings

            sid = request.sid
            if sid not in self.sessions:
                return

            session = self.sessions[sid]
            session_id = data.get('session_id', '').strip()
            if not session_id:
                return

            conv_config = settings.get("conversations", {})
            base_dir = _Path(conv_config.get("base_dir", "~/.termbot/conversations")).expanduser()
            f = base_dir / session.agent_id / session_id / "chat.jsonl"

            if not f.exists():
                emit('history_load_error', {'message': '历史文件不存在'}, room=sid)
                return

            # Parse JSONL
            raw_messages = []
            try:
                with open(f, encoding='utf-8') as fp:
                    for line in fp:
                        line = line.strip()
                        if line:
                            try:
                                raw_messages.append(_json.loads(line))
                            except Exception:
                                pass
            except Exception as e:
                emit('history_load_error', {'message': str(e)}, room=sid)
                return

            # Load messages into agent context (replaces current conversation)
            checkpoint_messages = [
                {
                    "role": msg["role"],
                    "content": msg.get("content", ""),
                    "metadata": msg.get("metadata", {})
                }
                for msg in raw_messages
            ]
            session.agent.reset_conversation()
            session.agent.load_checkpoint({
                "messages": checkpoint_messages,
                "state": {},
                "status": "success",
                "chat_status": "running",
                "tasks": []
            })

            # Build display messages for frontend (user + non-empty assistant only)
            display_messages = []
            for msg in raw_messages:
                ts = msg.get("ts", "")[11:16]  # HH:MM from ISO timestamp
                if msg["role"] == "user":
                    display_messages.append({"type": "user", "text": msg.get("content", ""), "time": ts})
                elif msg["role"] == "assistant" and msg.get("content"):
                    display_messages.append({"type": "bot", "text": msg.get("content", ""), "time": ts})

            # Redirect logger to the original session file so new messages
            # are appended there, not written to a separate new-connection file.
            session.switch_conversation_log(session_id)

            emit('history_loaded', {'messages': display_messages}, room=sid)
            logger.info("History loaded into context", session_id=session_id, messages=len(raw_messages))

        @self.socketio.on('cmd_res')
        def handle_command_result(data):
            """Handle terminal content from frontend (original project feature)."""
            sid = request.sid
            terminal_content = data.get('terminal_content', data.get('cmd_res', ''))

            if sid in self.sessions and terminal_content:
                # Store terminal content in context for Agent to see
                session = self.sessions[sid]
                session.agent.get_context().set_terminal_content(terminal_content.strip())

    def _handle_command(self, command: str, session: WebSession) -> str:
        """
        Handle special commands.

        Args:
            command: Command string starting with /
            session: Web session

        Returns:
            Command response
        """
        cmd = command.lower().strip()

        if cmd == "/help":
            return """Available commands:
  /help - Show this help
  /tools - List available tools
  /mcp - Show MCP (Model Context Protocol) status
  /skills - List available skills
  /skill disable <name> - Disable a skill
  /skill enable <name> - Enable a skill
  /history - Show conversation history
  /reset - Reset conversation
  /stop - Stop current agent task
  /clear - Clear terminal screen"""
        elif cmd == "/tools":
            tools = session.agent.get_available_tools()
            return f"Available tools ({len(tools)}):\n" + "\n".join(f"  • {tool}" for tool in tools)
        elif cmd == "/mcp":
            return self._get_mcp_status(session)
        elif cmd == "/history":
            history = session.agent.get_conversation_history()
            return f"Conversation has {len(history)} messages"
        elif cmd == "/reset":
            session.agent.reset_conversation()
            return "Conversation reset."
        elif cmd == "/skills":
            skills = session.skill_manager.list_skill_basics()
            if not skills:
                return "No skills found in ~/.termbot/skills/"
            result = f"Available skills ({len(skills)}):\n"
            for skill in skills:
                result += f"\n  /{skill['name']}: {skill['description']}"
            return result
        elif cmd.startswith("/skill"):
            parts = cmd.split(None, 3)
            if len(parts) >= 3 and parts[1] == "skill":
                if parts[2] == "disable" and len(parts) >= 4:
                    return self._disable_skill(parts[3], session)
                elif parts[2] == "enable" and len(parts) >= 4:
                    return self._enable_skill(parts[3], session)
                else:
                    return "用法: /skill disable <name> 或 /skill enable <name>"
            else:
                return f"Unknown command: {command}"
        elif cmd == "/stop":
            session.agent.stop()
            return "已发送停止信号，Agent 将在当前步骤完成后停止。"
        elif cmd == "/clear":
            # Clear agent conversation history only
            session.agent.reset_conversation()
            return "Conversation cleared."
        else:
            return f"Unknown command: {command}"

    def _disable_skill(self, skill_name: str, session: 'WebSession') -> str:
        """Disable a skill by setting enabled=false in SKILL.md frontmatter."""
        import re
        import yaml
        from pathlib import Path

        skill_manager = session.skill_manager
        skill_path = Path(skill_manager.skills_dir) / skill_name
        skill_md = skill_path / "SKILL.md"

        if not skill_md.exists():
            return f"Skill '{skill_name}' not found."

        try:
            # Read current content
            content = skill_md.read_text(encoding='utf-8')

            # Parse frontmatter
            match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
            if not match:
                return f"Invalid SKILL.md format: missing frontmatter."

            # Parse YAML frontmatter
            frontmatter = yaml.safe_load(match.group(1))
            if not isinstance(frontmatter, dict):
                return f"Invalid SKILL.md format: frontmatter is not a dict."

            # Check current status
            current_enabled = frontmatter.get("enabled", True)
            if not current_enabled:
                return f"Skill '{skill_name}' is already disabled."

            # Set enabled to false
            frontmatter["enabled"] = False

            # Rebuild file content
            new_content = f"---\n{yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)}---\n{content[match.end():]}"
            skill_md.write_text(new_content, encoding='utf-8')

            return f"✓ Skill '{skill_name}' has been disabled.\n  Use '/skill enable {skill_name}' to re-enable it."
        except Exception as e:
            return f"Error disabling skill: {e}"

    def _enable_skill(self, skill_name: str, session: 'WebSession') -> str:
        """Enable a skill by setting enabled=true in SKILL.md frontmatter."""
        import re
        import yaml
        from pathlib import Path

        skill_manager = session.skill_manager
        skill_path = Path(skill_manager.skills_dir) / skill_name
        skill_md = skill_path / "SKILL.md"

        if not skill_md.exists():
            return f"Skill '{skill_name}' not found."

        try:
            # Read current content
            content = skill_md.read_text(encoding='utf-8')

            # Parse frontmatter
            match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
            if not match:
                return f"Invalid SKILL.md format: missing frontmatter."

            # Parse YAML frontmatter
            frontmatter = yaml.safe_load(match.group(1))
            if not isinstance(frontmatter, dict):
                return f"Invalid SKILL.md format: frontmatter is not a dict."

            # Check current status
            current_enabled = frontmatter.get("enabled", True)
            if current_enabled:
                return f"Skill '{skill_name}' is already enabled."

            # Set enabled to true
            frontmatter["enabled"] = True

            # Rebuild file content
            new_content = f"---\n{yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)}---\n{content[match.end():]}"
            skill_md.write_text(new_content, encoding='utf-8')

            return f"✓ Skill '{skill_name}' has been enabled.\n  Use '/skill disable {skill_name}' to disable it."
        except Exception as e:
            return f"Error enabling skill: {e}"

    def _get_mcp_status(self, session: 'WebSession') -> str:
        """Get MCP (Model Context Protocol) status."""
        from infrastructure.mcp import get_mcp_status_text, get_mcp_manager

        try:
            # Try to get MCP manager
            mcp_manager = get_mcp_manager()

            # Get status text
            status_text = get_mcp_status_text(mcp_manager)

            # Convert to HTML-friendly format (replace newlines with <br>)
            return status_text.replace("\n", "<br>")

        except Exception as e:
            return f"Error getting MCP status: {e}"

    def get_session_count(self) -> int:
        """Get number of active sessions."""
        return len(self.sessions)

    def get_session_info(self, sid: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a session.

        Args:
            sid: Session ID

        Returns:
            Session info dict or None
        """
        if sid not in self.sessions:
            return None

        session = self.sessions[sid]
        return {
            'sid': sid,
            'pty_pid': session.pty_manager.pid,
            'pty_running': session.pty_manager.is_running(),
            'lock_status': session.pty_manager.get_lock_status(),
            'message_count': session.agent.get_context().message_count
        }
