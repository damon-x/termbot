"""
Agent core module - main agent implementation.

Provides the core Agent class that orchestrates the ReAct loop,
tool management, and context handling.
"""
import queue
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from agent.context import Context
from agent.react import ReactLoop, ReactResult
from agent.response_handler import ResponseHandler
from agent.tools.base import Tool, ToolRegistry
from infrastructure.llm.client import OpenAIClient
from infrastructure.logging import get_logger

if TYPE_CHECKING:
    from agent.skills.manager import SkillManager

logger = get_logger("agent.core")


@dataclass
class AgentConfig:
    """
    Configuration for the Agent.

    Attributes:
        llm_client: LLM client for generating responses
        max_iterations: Maximum iterations for ReAct loop
        enable_memory: Whether to enable memory features
        system_prompt: Optional custom system prompt
        role: Optional Agent role (e.g., 'main', 'skill')
        pty_manager: Optional shared PTY Manager
        tools: Optional list of pre-registered tools
        skill_manager: Optional SkillManager for injecting available skills
        response_handler: Optional handler for async responses
        enable_mcp: Whether to enable MCP (Model Context Protocol) tools
        mcp_config_path: Optional path to MCP configuration file
        mcp_auto_start: Whether to auto-start MCP servers on initialization
        allowed_skills: Optional list of allowed skill names
        allowed_tools: Optional list of allowed tool names
    """
    llm_client: OpenAIClient
    max_iterations: int = 20
    enable_memory: bool = True
    system_prompt: Optional[str] = None
    role: Optional[str] = None
    pty_manager: Optional[Any] = None
    tools: Optional[List[Tool]] = None
    enable_mcp: bool = True
    mcp_config_path: Optional[str] = None
    mcp_auto_start: bool = True
    skill_manager: Optional['SkillManager'] = None
    response_handler: Optional[ResponseHandler] = field(default=None, repr=False)
    allowed_skills: Optional[List[str]] = None  # 允许的技能名称列表
    allowed_tools: Optional[List[str]] = None  # 允许的工具名称列表


class Agent:
    """
    Core Agent class - decoupled from any interface layer.

    The agent processes user messages through a ReAct loop,
    using available tools to complete tasks.
    
    Supports both synchronous (process_message_with_result) and 
    asynchronous (submit) message processing.
    """

    def __init__(self, config: AgentConfig) -> None:
        """
        Initialize the Agent.

        Args:
            config: Agent configuration
        """
        self.config = config
        self.context = Context()
        self._instance_id: Optional[str] = None  # Set by factory
        self._session_id: Optional[str] = None  # Set by web layer
        self._agent_id: Optional[str] = None  # Set by web layer
        self.react_loop = ReactLoop(
            llm_client=config.llm_client,
            context=self.context,
            max_iterations=config.max_iterations,
            system_prompt=config.system_prompt,
            skill_manager=config.skill_manager,
            allowed_skills=config.allowed_skills,
            allowed_tools=config.allowed_tools
        )

        # Register pre-configured tools
        if config.tools:
            for tool in config.tools:
                self.register_tool(tool)

        # Async message queue
        self._message_queue: queue.Queue[str] = queue.Queue()
        self._processing = False
        self._processing_lock = threading.Lock()
        self._response_handler = config.response_handler

    def set_instance_id(self, instance_id: str) -> None:
        """
        Set the runtime instance ID for logging and PTY locking.

        Called by AgentFactory after creating the agent.

        Args:
            instance_id: Runtime identifier, e.g. "main", "skill_lark", "sub_abc"
        """
        self._instance_id = instance_id
        self.react_loop.instance_id = instance_id

    def set_agent_id(self, agent_id: str) -> None:
        """
        Set the agent ID for context injection.

        Called by the web layer to identify which Agent Profile is in use.

        Args:
            agent_id: Agent Profile identifier, e.g. "default" or 8-char hex
        """
        self._agent_id = agent_id
        self.react_loop.agent_id = agent_id

    def set_session_id(self, session_id: str) -> None:
        """
        Set the session ID for logging context.

        Called by the web layer when a session is established or switched.

        Args:
            session_id: Business session identifier (10-digit)
        """
        self._session_id = session_id
        self.react_loop.session_id = session_id

    def _setup_tools(self) -> None:
        """Set up available tools for the agent."""
        # Import and register built-in tools
        # Note: These will be migrated from the existing toolbox
        pass

    def register_tool(self, tool: Tool) -> None:
        """
        Register a built-in tool with the agent.

        Subject to the allowed_tools whitelist defined in the agent profile.

        Args:
            tool: Tool instance to register
        """
        if hasattr(tool, 'set_agent'):
            tool.set_agent(self)
        if hasattr(tool, 'set_context'):
            tool.set_context(self.context)
        self.react_loop.register_tool(tool)

    def register_mcp_tool(self, tool: Tool) -> None:
        """
        Register an MCP tool with the agent.

        MCP tools bypass the allowed_tools whitelist because their names are
        discovered dynamically and cannot be pre-listed in a profile.

        Args:
            tool: MCPAdapterTool instance to register
        """
        self.react_loop.register_mcp_tool(tool)

    def unregister_tool(self, tool_name: str) -> bool:
        """
        Unregister a tool.

        Args:
            tool_name: Name of the tool to unregister

        Returns:
            True if tool was unregistered
        """
        return self.react_loop.unregister_tool(tool_name)

    def process_message(self, message: str) -> str:
        """
        Process a user message and return the response.

        Args:
            message: User's input message

        Returns:
            Agent's response
        """
        result = self.react_loop.run(message)
        return result.response

    def process_message_with_result(self, message: str) -> ReactResult:
        """
        Process a user message and return the full result.

        Args:
            message: User's input message

        Returns:
            Complete ReactResult with steps and metadata
        """
        return self.react_loop.run(message)

    def get_context(self) -> Context:
        """
        Get the agent's execution context.

        Returns:
            The agent's Context instance
        """
        return self.context

    def get_available_tools(self) -> List[str]:
        """
        Get list of available tool names.

        Returns:
            List of registered tool names
        """
        return self.react_loop.get_available_tools()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Get all tool schemas in OpenAI Function format.

        Returns:
            List of tool schema dicts
        """
        return self.react_loop.tool_registry.get_tool_schemas()

    def reset_conversation(self) -> None:
        """Reset the conversation history and state."""
        self.context.reset()

    def export_checkpoint(self) -> Dict[str, Any]:
        """
        Export current state as a checkpoint.

        Returns:
            Checkpoint data dict
        """
        return self.context.export_checkpoint()

    def load_checkpoint(self, checkpoint: Dict[str, Any]) -> None:
        """
        Load state from a checkpoint.

        Args:
            checkpoint: Checkpoint data dict
        """
        self.context.load_checkpoint(checkpoint)

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """
        Get the conversation history.

        Returns:
            List of message dicts
        """
        return self.context.get_messages()

    def get_message_count(self) -> int:
        """
        Get the number of messages in the conversation.

        Returns:
            Number of messages
        """
        return self.context.message_count

    def is_paused(self) -> bool:
        """
        Check if the agent is waiting for user input.

        Returns:
            True if waiting for user answer
        """
        return self.context.is_waiting_user_answer()

    def provide_user_answer(self, answer: str) -> None:
        """
        Provide an answer when the agent is waiting for user input.

        Args:
            answer: User's answer
        """
        self.context.set_user_answer(answer)
        self.context.add_message("user", answer)

    def resume_task(self) -> ReactResult:
        """
        Resume task execution from a paused state.

        Should be called after provide_user_answer() has been used to set
        the user's response to a question.

        Returns:
            ReactResult with the final response

        Raises:
            RuntimeError: If the agent is not paused
        """
        return self.react_loop.resume()

    def stop(self) -> None:
        """
        Request the agent to stop the current ReAct loop.

        Sets a stop flag that will be checked at the next iteration boundary.
        Also drains the pending message queue so no queued messages run after stopping.
        """
        logger.info("🛑 Stop requested by user")
        self.react_loop.request_stop()
        # Drain pending messages from queue
        drained = 0
        while not self._message_queue.empty():
            try:
                self._message_queue.get_nowait()
                self._message_queue.task_done()
                drained += 1
            except queue.Empty:
                break
        if drained:
            logger.info("Drained pending messages from queue", count=drained)

    def get_status(self) -> str:
        """
        Get the current agent status.

        Returns:
            Status string
        """
        return self.context.get_status()

    def get_chat_status(self) -> str:
        """
        Get the current chat status.

        Returns:
            Chat status string
        """
        return self.context.get_chat_status()

    # ==================== Async Message Queue ====================

    def submit(self, message: str) -> bool:
        """
        Submit a message to the agent's queue for async processing.

        Returns immediately. The message will be processed in a background
        thread, and results will be delivered via the response_handler.

        Args:
            message: User's message

        Returns:
            True if message was queued successfully
        """
        self._message_queue.put(message)
        logger.debug("Message queued", queue_size=self._message_queue.qsize())

        # Start worker if not already processing
        with self._processing_lock:
            if not self._processing:
                self._processing = True
                threading.Thread(
                    target=self._run_worker,
                    daemon=True
                ).start()
                logger.debug("Worker thread started")

        return True

    def _run_worker(self) -> None:
        """
        Worker thread that processes messages from the queue.

        Continues processing until the queue is empty, then exits.
        """
        # Set logging context for this worker thread
        from infrastructure.logging import logger_context
        if self._session_id:
            logger_context.set_session(session_id=self._session_id, mode="web")
        if self._instance_id:
            logger_context.set_agent(agent_id=self._instance_id)

        while True:
            try:
                # Get next message (non-blocking to check if we should stop)
                try:
                    message = self._message_queue.get_nowait()
                except queue.Empty:
                    # Queue empty, stop processing
                    break

                logger.info("Processing message from queue", 
                    queue_remaining=self._message_queue.qsize())

                # Check if resuming a paused task
                if self.is_paused():
                    self.provide_user_answer(message)
                    try:
                        result = self.resume_task()
                    except RuntimeError:
                        result = self.process_message_with_result(message)
                else:
                    result = self.process_message_with_result(message)

                # Emit response via handler
                self._emit_response(result)

                self._message_queue.task_done()

            except Exception as e:
                logger.error("Error in worker thread", error=str(e))
                # Continue processing remaining messages

        # Reset processing state
        with self._processing_lock:
            self._processing = False
            logger.debug("Worker thread finished")

    def _emit_response(self, result: ReactResult) -> None:
        """
        Emit the response via the registered handler.

        Args:
            result: The ReactResult to emit
        """
        if self._response_handler:
            try:
                self._response_handler.on_response(result)
            except Exception as e:
                logger.error("Error in response handler", error=str(e))
        else:
            logger.warning("No response handler registered, result not delivered")
