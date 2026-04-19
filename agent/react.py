"""
ReAct loop implementation for agent reasoning.

Implements the ReAct (Reasoning + Acting) pattern where the agent
thinks, acts (uses tools), observes results, and repeats until completion.
"""
import json
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from agent.context import Context
from agent.tools.base import Tool, ToolRegistry
from infrastructure.llm.client import OpenAIClient
from infrastructure.llm.function_calling import ChatResponse, FunctionCall
from infrastructure.config.settings import settings
from infrastructure.logging import get_logger, EventType, logger_context

if TYPE_CHECKING:
    from agent.skills.manager import SkillManager

logger = get_logger("agent.react")


@dataclass
class ReactStep:
    """
    Represents a single step in the ReAct loop.

    Attributes:
        thought: What the agent is thinking
        action: Tool name the agent wants to use
        action_input: Arguments for the tool
        observation: Result from executing the tool
        is_final: Whether this is the final step
    """
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None
    is_final: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "thought": self.thought,
            "action": self.action,
            "action_input": self.action_input,
            "observation": self.observation,
            "is_final": self.is_final
        }


@dataclass
class ReactResult:
    """
    Result of running the ReAct loop.

    Attributes:
        response: Final response to the user
        steps: List of steps taken during reasoning
        success: Whether the loop completed successfully
        error: Error message if failed
        status: Execution status ("success", "paused", "failed")
        question: Question to ask user when paused
        options: Optional list of answer options for the question
        request_id: Unique ID for this request round
    """
    response: str
    steps: List[ReactStep] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None
    status: str = "success"
    question: Optional[str] = None
    options: Optional[List[str]] = None
    request_id: Optional[str] = None


class ReactLoop:
    """
    ReAct loop implementation.

    The agent repeatedly thinks, decides on actions, executes tools,
    observes results, and continues until the task is complete.
    """

    # System prompt for the agent
    DEFAULT_SYSTEM_PROMPT = """You are an intelligent assistant with a PTY (pseudo-terminal). You can execute any shell command through the PTY to help users.

Your capabilities:
- Execute shell commands through the PTY (ls, cd, grep, docker, etc.)
- Open websites or applications by running appropriate commands
- Use tools for specific tasks (notes, weather, email, etc.)

When users ask you to "open" something, "launch" something, or perform any system operation, use the exec_terminal_cmd tool to execute the appropriate command through your PTY.

When you need to use a tool, respond with a function call. When you have enough information to answer the user's question, respond directly.

Available tools will be provided in the tools parameter. Use them when necessary."""

    def __init__(
        self,
        llm_client: OpenAIClient,
        context: Context,
        max_iterations: int = 20,
        system_prompt: Optional[str] = None,
        skill_manager: Optional['SkillManager'] = None,
        allowed_skills: Optional[List[str]] = None,
        allowed_tools: Optional[List[str]] = None
    ) -> None:
        """
        Initialize the ReAct loop.

        Args:
            llm_client: LLM client for generating responses
            context: Execution context for message history
            max_iterations: Maximum number of iterations to prevent infinite loops
            system_prompt: Optional custom system prompt
            skill_manager: Optional SkillManager for injecting available skills
            allowed_skills: Optional list of allowed skill names (empty = all)
            allowed_tools: Optional list of allowed tool names (empty = all)
        """
        self.llm_client = llm_client
        self.context = context
        self.max_iterations = max_iterations
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        self.skill_manager = skill_manager
        self.allowed_skills = allowed_skills
        self.allowed_tools = allowed_tools
        self.tool_registry = ToolRegistry()
        self._stop_event = threading.Event()
        self.instance_id: Optional[str] = None
        self.agent_id: Optional[str] = None
        self.session_id: Optional[str] = None

        # Memory injection configuration
        agent_config = settings.get("agent", {})
        self.memory_injection_enabled = agent_config.get("enable_memory_injection", False)
        self.memory_injection_config = agent_config.get("memory_injection", {
            "max_results": 3,
            "similarity_threshold": 0.3,
            "max_length": 2000
        })

    def register_tool(self, tool: Tool) -> None:
        """
        Register a tool for use in the ReAct loop.

        Tools are filtered based on allowed_tools configuration:
        - None or empty list: all tools allowed
        - Non-empty list: only tools in the list are allowed

        Args:
            tool: Tool instance to register
        """
        # Check if tool is allowed
        if self.allowed_tools is not None and len(self.allowed_tools) > 0:
            if tool.schema.name not in self.allowed_tools:
                return  # Skip this tool

        self.tool_registry.register(tool)

    def unregister_tool(self, tool_name: str) -> bool:
        """
        Unregister a tool.

        Args:
            tool_name: Name of the tool to unregister

        Returns:
            True if tool was unregistered
        """
        return self.tool_registry.unregister(tool_name)

    def run(self, user_input: str) -> ReactResult:
        """
        Run the ReAct loop with user input.

        Args:
            user_input: User's message or request

        Returns:
            ReactResult with the final response and reasoning steps
        """
        import random
        request_id = str(random.randint(1_000_000_000, 9_999_999_999))
        self.context.set_request_id(request_id)

        with logger_context.scope(request_id=request_id):
            return self._run_inner(user_input, request_id)

    def _run_inner(self, user_input: str, request_id: str) -> ReactResult:
        """Inner ReAct loop execution within an established logging scope."""
        # 简洁的用户输入日志
        preview = user_input[:400] + "..." if len(user_input) > 400 else user_input
        logger.info(f"👤 User: {preview}")

        # Retrieve relevant memory before adding user message
        memory_context = self._retrieve_and_inject_memory(user_input)

        # Add user message to context
        self.context.add_message("user", user_input)
        self.context.set_user_input(user_input)
        self.context.set_status("running")

        steps: List[ReactStep] = []
        self._stop_event.clear()

        for iteration in range(self.max_iterations):
            # Check if stop was requested
            if self._stop_event.is_set():
                logger.info("🛑 ReAct loop stopped by user request", iteration=iteration, steps=len(steps))
                self.context.set_status("stopped")
                return ReactResult(
                    response="已停止当前任务。",
                    steps=steps,
                    success=True,
                    status="stopped",
                    request_id=request_id
                )

            # Get tool schemas
            tools = self.tool_registry.get_tool_schemas()

            # Build messages for LLM (with optional memory context)
            messages = self._build_messages(memory_context)

            # Get response from LLM
            try:
                response = self.llm_client.chat_with_tools(
                    messages=messages,
                    tools=tools if tools else None
                )
            except Exception as e:
                return ReactResult(
                    response=f"Error communicating with LLM: {e}",
                    steps=steps,
                    success=False,
                    error=str(e),
                    status="failed",
                    request_id=request_id
                )

            # Check if LLM wants to use a tool
            if response.function_call:
                # First, add the assistant message with tool_calls info
                # This is required by OpenAI API format
                tool_call_id = response.function_call.id
                self.context.add_message(
                    "assistant",
                    "",  # Empty string when using tools (not None)
                    metadata={
                        "tool_calls": [
                            {
                                "id": tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": response.function_call.name,
                                    "arguments": json.dumps(response.function_call.arguments)
                                }
                            }
                        ]
                    }
                )
                logger.debug("Assistant message with tool_call", 
                    tool_call_id=tool_call_id, 
                    tool=response.function_call.name)

                # Execute the tool
                step = self._execute_function_call(response.function_call)
                steps.append(step)
                
                # DEBUG 级别：详细信息
                logger.debug(f"Tool result: {step.action}", 
                    observation_length=len(step.observation) if step.observation else 0,
                    is_final=step.is_final)

                # Check if ask_user triggered a pause
                if step.observation == "__ASK_USER_PENDING__":
                    question_data = self.context.get_state("pending_question", {})
                    self.context.add_message(
                        "tool",
                        "Waiting for user input...",
                        metadata={"tool_call_id": response.function_call.id}
                    )
                    self.context.set_status("paused")

                    # Build response with full question for frontend display
                    question_text = question_data.get("question", "")
                    options = question_data.get("options")
                    if options:
                        options_text = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options))
                        full_response = f"{question_text}\n\n选项：\n{options_text}"
                    else:
                        full_response = question_text

                    return ReactResult(
                        response=full_response,
                        steps=steps,
                        status="paused",
                        question=question_data.get("question"),
                        options=question_data.get("options"),
                        request_id=request_id
                    )

                # Add the tool result to context with tool_call_id
                # Always add tool message to maintain message sequence integrity
                observation = step.observation if step.observation is not None else ""
                self.context.add_message(
                    "tool",
                    observation,
                    metadata={"tool_call_id": response.function_call.id}
                )
                logger.debug("Added tool message", tool_call_id=response.function_call.id)

                # Check if this should be the final step (tool marked as final)
                if step.is_final:
                    break
            else:
                # LLM provided a direct response
                final_response = response.content or "I apologize, but I couldn't generate a response."
                steps.append(ReactStep(thought=final_response, is_final=True))
                self.context.add_message("assistant", final_response)
                self.context.set_status("success")
                return ReactResult(response=final_response, steps=steps, success=True, status="success",
                                   request_id=request_id)

        # Reached max iterations or completed
        final_response = self._generate_final_response(steps)
        self.context.add_message("assistant", final_response)
        self.context.set_status("success")

        # 简洁的响应日志
        preview = final_response[:400] + "..." if len(final_response) > 400 else final_response
        logger.info(f"🤖 Agent: {preview}")

        return ReactResult(response=final_response, steps=steps, success=True, status="success",
                           request_id=request_id)

    def _retrieve_and_inject_memory(self, user_input: str) -> Optional[str]:
        """
        Retrieve relevant memories and format for injection.

        Args:
            user_input: User's input message

        Returns:
            Formatted memory context string, or None if no relevant memories found
        """
        if not self.memory_injection_enabled:
            return None

        try:
            from agent.memory.long_term_memory import get_long_term_memory

            ltm = get_long_term_memory()
            results = ltm.get(
                queries=[user_input],
                limit=self.memory_injection_config.get("max_results", 3),
                use_rerank=False
            )

            if not results or not results[0].memories:
                logger.debug("No memories found for query", query=user_input[:400])
                return None

            memories = results[0].memories
            threshold = self.memory_injection_config.get("similarity_threshold", 0.3)

            # Calculate average score
            avg_score = sum(m.get("score", 0) for m in memories) / len(memories)

            if avg_score < threshold:
                logger.debug("Memories below threshold", avg_score=round(avg_score, 2), threshold=threshold)
                return None

            # Format memories for injection
            max_length = self.memory_injection_config.get("max_length", 2000)
            memory_lines = [f"[Relevant Memory - retrieved based on your query]"]

            for mem in memories:
                content = mem.get("content", "")
                tags = mem.get("tags", [])
                score = mem.get("score", 0)
                mem_id = mem.get("id", "?")

                # Truncate if too long
                if len(content) > max_length:
                    content = content[:max_length] + "..."

                tags_str = ", ".join(tags) if tags else "none"
                memory_lines.append(
                    f"- [ID={mem_id}, relevance={score:.2f}] {content}\n  (tags: {tags_str})"
                )

            memory_context = "\n".join(memory_lines)
            # 删除冗余日志：memory injection 是内部操作
            return memory_context

        except Exception as e:
            # If memory retrieval fails, log but continue
            logger.warning("Memory retrieval failed", event_data={"error": str(e), "error_type": type(e).__name__})
            return None

    def _build_messages(self, memory_context: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Build messages for LLM including system prompt.

        Args:
            memory_context: Optional retrieved memory context to inject

        Returns:
            List of message dicts for LLM
        """
        # Build system prompt with optional memory context
        system_content = self.system_prompt
        if memory_context:
            system_content += f"\n\n{memory_context}\n"

        # Inject available skills (real-time load on each react loop)
        skills_context = self._build_skills_context()
        if skills_context:
            system_content += f"\n\n{skills_context}\n"

        # Inject runtime context variables
        runtime_context = self._build_runtime_context()
        if runtime_context:
            system_content += f"\n\n{runtime_context}\n"

        messages = [{"role": "system", "content": system_content}]
        messages.extend(self.context.get_messages())

        # Debug: Validate message sequence
        self._validate_message_sequence(messages)

        return messages

    def _build_skills_context(self) -> Optional[str]:
        """
        Build skills context string from enabled skills.

        Real-time load: calls skill_manager.list_skill_basics() on each invocation
        to ensure skill enable/disable changes are immediately reflected.

        Skills are filtered by:
        1. Skill's enabled flag (already filtered by list_skill_basics)
        2. Agent's allowed_skills configuration (if set)

        Returns:
            Formatted skills context string, or None if no skills available
        """
        if not self.skill_manager:
            return None

        skills = self.skill_manager.list_skill_basics()
        if not skills:
            return None

        # Filter by agent's allowed_skills configuration
        if self.allowed_skills is not None and len(self.allowed_skills) > 0:
            skills = [s for s in skills if s['name'] in self.allowed_skills]

        if not skills:
            return None

        lines = ["## Available Skills\n"]
        lines.append(
            "You can use these skills by calling the `use_skill` tool.\n"
            "Skills have two execution modes:\n"
            "- **agent mode**: A dedicated sub-agent will execute the task. "
            "Call `use_skill` once with the full task description and wait for the result.\n"
            "- **inject mode**: The skill returns its instructions to YOU. "
            "After calling `use_skill`, read the returned instructions carefully and "
            "execute the task yourself using tools like `exec_terminal_cmd`. "
            "Do NOT call `use_skill` again for the same skill after receiving its instructions.\n"
        )

        for skill in skills:
            mode = skill.get("execution_mode", "agent")
            mode_tag = "[inject]" if mode == "inject" else "[agent]"
            lines.append(f"- **/{skill['name']}** {mode_tag}: {skill['description']}")

        return "\n".join(lines)

    def _build_runtime_context(self) -> Optional[str]:
        """
        Build runtime context block with injected variables.

        Returns:
            Formatted runtime context string, or None if no variables available
        """
        lines = []
        if self.agent_id:
            lines.append(f"AGENT_ID: {self.agent_id}")
        if self.session_id:
            lines.append(f"SESSION_ID: {self.session_id}")

        if not lines:
            return None

        return "## Runtime Context\n" + "\n".join(lines)

    def _execute_function_call(self, function_call: FunctionCall) -> ReactStep:
        """
        Execute a function call from the LLM.

        Args:
            function_call: Function call to execute

        Returns:
            ReactStep with the execution result
        """
        step = ReactStep(
            thought=f"Using tool: {function_call.name}",
            action=function_call.name,
            action_input=function_call.arguments
        )

        try:
            # Execute the tool via ToolRegistry to get logging
            result = self.tool_registry.execute_tool(function_call.name, **function_call.arguments)
            step.observation = str(result)

        except ValueError as e:
            step.observation = f"Argument validation error: {e}"
        except Exception as e:
            step.observation = f"Error executing tool: {e}"
            step.is_final = True

        return step

    def _generate_final_response(self, steps: List[ReactStep]) -> str:
        """
        Generate a final response based on the steps taken.

        When max iterations is reached, ask LLM to summarize the work done.

        Args:
            steps: List of reasoning steps

        Returns:
            Final response string
        """
        if not steps:
            return "No actions were taken."

        # Build summary of actions taken
        actions_summary = []
        for i, step in enumerate(steps, 1):
            action_desc = f"{i}. {step.action}"
            if step.observation:
                # Truncate long observations
                obs_preview = step.observation[:500] + "..." if len(step.observation) > 500 else step.observation
                action_desc += f"\n   Result: {obs_preview}"
            actions_summary.append(action_desc)

        summary_text = "\n".join(actions_summary)

        # Ask LLM to summarize
        summarize_prompt = f"""Based on the actions taken, provide a concise summary of what was accomplished.

Actions taken:
{summary_text}

Please summarize the results in a clear, helpful way for the user."""

        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": summarize_prompt}
            ]
            response = self.llm_client.chat(messages=messages)
            return response or "Task processing completed."
        except Exception as e:
            # Fallback if LLM call fails
            logger.warning("Failed to generate summary", error=str(e))
            last_step = steps[-1]
            if last_step.observation:
                return f"Task completed. Last action: {last_step.action}\nResult: {last_step.observation[:500]}"
            return "Task processing completed."

    def _validate_message_sequence(self, messages: List[Dict[str, Any]]) -> None:
        """
        Validate that the message sequence is correct for OpenAI API.

        Args:
            messages: List of message dicts

        Raises:
            ValueError: If message sequence is invalid
        """
        pending_tool_calls = []

        for i, msg in enumerate(messages):
            role = msg.get("role")

            if role == "assistant":
                # Check if this assistant message has tool_calls
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    # Track tool_call_ids that need responses
                    for tc in tool_calls:
                        tc_id = tc.get("id")
                        if tc_id:
                            pending_tool_calls.append((i, tc_id))
                            logger.debug("Assistant message with tool_call", 
                                message_index=i, tool_call_id=tc_id)

            elif role == "tool":
                # Check if this tool message has a tool_call_id
                tool_call_id = msg.get("tool_call_id")
                if not tool_call_id:
                    logger.warning("Tool message missing tool_call_id", message_index=i)
                    continue

                # Check if this tool_call_id was pending
                found = False
                for idx, pending_id in pending_tool_calls:
                    if pending_id == tool_call_id:
                        pending_tool_calls.remove((idx, pending_id))
                        found = True
                        logger.debug("Tool response matched", 
                            message_index=i, tool_call_id=tool_call_id)
                        break

                if not found:
                    logger.warning("Tool message with unknown tool_call_id", 
                        message_index=i, tool_call_id=tool_call_id)

        # Report any pending tool_calls that weren't responded to
        if pending_tool_calls:
            logger.error("Tool calls without responses", 
                count=len(pending_tool_calls),
                pending=[{"index": idx, "tool_call_id": tc_id} for idx, tc_id in pending_tool_calls])

    def resume(self) -> ReactResult:
        """
        Resume execution from a paused state.

        Should be called after:
        1. User provides an answer via Context.set_user_answer()
        2. The answer is added to message history

        Returns:
            ReactResult with the final response

        Raises:
            RuntimeError: If the agent is not paused
        """
        if not self.context.is_waiting_user_answer():
            raise RuntimeError("Cannot resume: agent is not paused")

        # Clear the waiting flag now that we're actually resuming
        self.context.set_waiting_user_answer(False)

        # The user's answer has already been added to message history
        # by provide_user_answer(). Continue the ReAct loop.
        self.context.set_status("running")

        steps: List[ReactStep] = []

        for iteration in range(self.max_iterations):
            # Check if stop was requested
            if self._stop_event.is_set():
                logger.info("🛑 ReAct loop stopped by user request (resume)", iteration=iteration, steps=len(steps))
                self.context.set_status("stopped")
                return ReactResult(
                    response="已停止当前任务。",
                    steps=steps,
                    success=True,
                    status="stopped"
                )

            # Get tool schemas
            tools = self.tool_registry.get_tool_schemas()

            # Build messages for LLM (no new memory retrieval on resume)
            messages = self._build_messages()

            # Get response from LLM
            try:
                response = self.llm_client.chat_with_tools(
                    messages=messages,
                    tools=tools if tools else None
                )
            except Exception as e:
                return ReactResult(
                    response=f"Error communicating with LLM: {e}",
                    steps=steps,
                    success=False,
                    error=str(e),
                    status="failed"
                )

            # Check if LLM wants to use a tool
            if response.function_call:
                # First, add the assistant message with tool_calls info
                self.context.add_message(
                    "assistant",
                    "",  # Empty string when using tools (not None)
                    metadata={
                        "tool_calls": [
                            {
                                "id": response.function_call.id,
                                "type": "function",
                                "function": {
                                    "name": response.function_call.name,
                                    "arguments": json.dumps(response.function_call.arguments)
                                }
                            }
                        ]
                    }
                )

                # Execute the tool
                step = self._execute_function_call(response.function_call)
                steps.append(step)

                # Check if ask_user triggered a pause again
                if step.observation == "__ASK_USER_PENDING__":
                    question_data = self.context.get_state("pending_question", {})
                    self.context.add_message(
                        "tool",
                        "Waiting for user input...",
                        metadata={"tool_call_id": response.function_call.id}
                    )
                    self.context.set_status("paused")

                    # Build response with full question for frontend display
                    question_text = question_data.get("question", "")
                    options = question_data.get("options")
                    if options:
                        options_text = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options))
                        full_response = f"{question_text}\n\n选项：\n{options_text}"
                    else:
                        full_response = question_text

                    return ReactResult(
                        response=full_response,
                        steps=steps,
                        status="paused",
                        question=question_data.get("question"),
                        options=question_data.get("options")
                    )

                # Add the tool result to context with tool_call_id
                # Always add tool message to maintain message sequence integrity
                observation = step.observation if step.observation is not None else ""
                self.context.add_message(
                    "tool",
                    observation,
                    metadata={"tool_call_id": response.function_call.id}
                )
                logger.debug("Added tool message in resume", tool_call_id=response.function_call.id)

                # Check if this should be the final step
                if step.is_final or self._is_complete(step.observation):
                    break
            else:
                # LLM provided a direct response
                final_response = response.content or "I apologize, but I couldn't generate a response."
                steps.append(ReactStep(thought=final_response, is_final=True))
                self.context.add_message("assistant", final_response)
                self.context.set_status("success")
                return ReactResult(response=final_response, steps=steps, success=True, status="success")

        # Reached max iterations or completed
        final_response = self._generate_final_response(steps)
        self.context.add_message("assistant", final_response)
        self.context.set_status("success")
        return ReactResult(response=final_response, steps=steps, success=True, status="success")

    def request_stop(self) -> None:
        """Request the ReAct loop to stop at the next iteration boundary."""
        self._stop_event.set()

    def reset(self) -> None:
        """Reset the ReAct loop state."""
        self.context.reset()

    def get_available_tools(self) -> List[str]:
        """
        Get list of available tool names.

        Returns:
            List of tool names
        """
        return self.tool_registry.list_tools()
