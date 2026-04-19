"""
Anthropic Claude API client using direct HTTP requests.

Provides an Anthropic-compatible implementation with the same interface
as OpenAIClient. All format conversions are handled internally.
"""
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union

import requests

from infrastructure.config.settings import settings
from infrastructure.llm.function_calling import ChatResponse, FunctionCall
from infrastructure.logging import get_logger

logger = get_logger("llm.anthropic")


class AnthropicClient:
    """
    Anthropic Claude API client using direct HTTP requests.

    Compatible with OpenAIClient interface - all format conversions
    are handled internally (OpenAI format ↔ Anthropic format).
    """

    # Default Anthropic API endpoint
    DEFAULT_BASE_URL = "https://api.anthropic.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """
        Initialize Anthropic client.

        Args:
            api_key: API key for authentication (defaults to config)
            base_url: Base URL for API (defaults to config or official API)
            model: Model name to use (defaults to config)
        """
        llm_config = settings.llm

        self.api_key = api_key if api_key else llm_config.get("api_key", "")
        self.base_url = base_url if base_url else llm_config.get("base_url", self.DEFAULT_BASE_URL)
        # Remove trailing slash for consistency
        if self.base_url.endswith('/'):
            self.base_url = self.base_url[:-1]

        self.model = model if model else llm_config.get("model", "claude-3-5-sonnet-20241022")

        # API endpoint for messages
        self.messages_url = f"{self.base_url}/v1/messages"

        # Request headers
        self.headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        self._watch_gap = 10
        self._times = 0

    def chat(self, messages: List[Dict[str, str]]) -> str:
        """
        Send chat completion request to LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            LLM response content string
        """
        start_time = time.time()
        self._times += 1

        system, anthropic_messages = self._convert_to_anthropic_messages(messages)

        request_data = {
            "model": self.model,
            "max_tokens": 4096,
            "system": system,
            "messages": anthropic_messages
        }

        response = self._make_request(request_data)

        # Extract text content
        response_content = ""
        for block in response.get("content", []):
            if block.get("type") == "text":
                response_content = block.get("text", "")
                break

        elapsed = time.time() - start_time
        content_preview = (response_content or "")[:400]
        logger.info(f"LLM → Response: {content_preview}... ({elapsed*1000:.0f}ms)")

        if self._times >= self._watch_gap:
            self._times = 0

        return response_content

    def send(self, message: str, is_json: bool = True) -> str:
        """
        Send a single message to LLM.

        Args:
            message: User message content
            is_json: Whether to parse response as JSON

        Returns:
            LLM response (parsed JSON if is_json=True)
        """
        messages = [{"role": "user", "content": message}]
        response = self.chat(messages)

        if is_json:
            response = self._to_json(response)

        return response

    def chat_for_json(self, messages: List[Dict[str, str]]) -> Union[Dict[str, Any], str]:
        """
        Send chat completion request and parse JSON response.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Parsed JSON object or string if parsing fails
        """
        response = self.chat(messages)
        return self._to_json(response)

    def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    ) -> ChatResponse:
        """
        Send chat completion request with function calling support.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: List of tool schemas in OpenAI Function format
            tool_choice: Tool choice setting ('auto', 'none', or specific tool)

        Returns:
            ChatResponse with content and optional function calls
        """
        start_time = time.time()
        self._times += 1

        # Convert messages and tools
        system, anthropic_messages = self._convert_to_anthropic_messages(messages)
        anthropic_tools = self._convert_tools_to_anthropic(tools)

        # Build request data
        request_data: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "system": system,
            "messages": anthropic_messages
        }

        if anthropic_tools:
            request_data["tools"] = anthropic_tools

        # Convert tool_choice if provided
        if tool_choice:
            converted = self._convert_tool_choice(tool_choice)
            if converted is not None:
                request_data["tool_choice"] = converted

        # Make HTTP request
        response = self._make_request(request_data)

        # Convert back to OpenAI-style ChatResponse
        chat_response = self._convert_from_anthropic_response(response)

        elapsed = time.time() - start_time

        # Extract token usage if available
        usage = response.get("usage", {})
        token_info = {}
        if usage:
            token_info = {
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            }

        # Log response
        if chat_response.has_function_call():
            func_name = chat_response.function_call.name if chat_response.function_call else chat_response.tool_calls[0].name if chat_response.tool_calls else "unknown"
            logger.info(f"LLM → Tool: {func_name} ({elapsed*1000:.0f}ms)")
        else:
            content_preview = (chat_response.content or "")[:400]
            logger.info(f"LLM → Response: {content_preview}... ({elapsed*1000:.0f}ms)")

        logger.debug("LLM response details",
            model=self.model,
            duration_ms=round(elapsed * 1000, 2),
            has_function_call=chat_response.has_function_call(),
            function_name=chat_response.function_call.name if chat_response.function_call else None,
            **token_info,
        )

        if self._times >= self._watch_gap:
            self._times = 0

        return chat_response

    def _make_request(self, data: Dict[str, Any], timeout: float = 120.0) -> Dict[str, Any]:
        """
        Make HTTP request to Anthropic API.

        Args:
            data: Request payload
            timeout: Request timeout in seconds

        Returns:
            Parsed JSON response

        Raises:
            requests.HTTPError: If the request fails
        """
        # Debug: 打印请求详情
        import json
        logger.debug(f"📤 发送请求到: {self.messages_url}")
        logger.debug(f"📦 请求体: {json.dumps(data, indent=2, ensure_ascii=False)}")

        try:
            response = requests.post(
                self.messages_url,
                headers=self.headers,
                json=data,
                timeout=timeout
            )
            response.raise_for_status()
            result = response.json()

            # Debug: 打印响应详情
            logger.debug(f"📥 收到响应: {json.dumps(result, indent=2, ensure_ascii=False)}")

            return result

        except requests.exceptions.Timeout:
            logger.error(f"Request timeout after {timeout}s")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise

    # ──────────────────────────────────────
    # Internal conversion methods (private)
    # ──────────────────────────────────────

    def _convert_to_anthropic_messages(self, messages: List[Dict]) -> tuple[str, List[Dict]]:
        """
        Convert OpenAI format messages to Anthropic format.

        Returns:
            (system_prompt, anthropic_messages)
        """
        system = ""
        anthropic_msgs = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")

            if role == "system":
                system = content
            elif role == "tool":
                # OpenAI tool result → Anthropic tool_result content block
                anthropic_msgs.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id"),
                        "content": str(content)
                    }]
                })
            elif role == "assistant" and "tool_calls" in msg:
                # Assistant with tool_calls → assistant with tool_use content blocks
                content_blocks = []

                # Add text content first (if any)
                if content:
                    content_blocks.append({"type": "text", "text": content})

                # Add tool_use blocks
                for tc in msg.get("tool_calls", []):
                    function = tc.get("function", {})
                    arguments = function.get("arguments", {})
                    # arguments is already a dict, no need to json.loads
                    if isinstance(arguments, str):
                        arguments = json.loads(arguments)
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id"),
                        "name": function.get("name"),
                        "input": arguments
                    })

                anthropic_msgs.append({
                    "role": "assistant",
                    "content": content_blocks
                })
            else:
                # Regular user/assistant message
                anthropic_msgs.append({
                    "role": role,
                    "content": content
                })

        return system, anthropic_msgs

    def _convert_from_anthropic_response(self, response: Dict) -> ChatResponse:
        """
        Convert Anthropic response to OpenAI-style ChatResponse.

        Args:
            response: Anthropic API response dict

        Returns:
            ChatResponse with OpenAI-style format
        """
        content_blocks = response.get("content", [])
        text_content = None
        tool_calls = []

        for block in content_blocks:
            if block.get("type") == "text":
                text_content = block.get("text")
            elif block.get("type") == "tool_use":
                tool_calls.append(FunctionCall(
                    id=block.get("id"),
                    name=block.get("name"),
                    arguments=block.get("input", {})
                ))

        # For backward compatibility with react.py (checks response.function_call)
        # Extract first tool_call as function_call
        function_call = tool_calls[0] if tool_calls else None

        return ChatResponse(
            content=text_content,
            function_call=function_call,  # For compatibility
            tool_calls=tool_calls if tool_calls else None,
            raw_response=response
        )

    def _convert_tools_to_anthropic(self, tools: Optional[List[Dict]]) -> Optional[List[Dict]]:
        """
        Convert OpenAI tools schema to Anthropic tools schema.

        OpenAI: {"type": "function", "function": {...}}
        Anthropic: {"name": "...", "description": "...", "input_schema": {...}}
        """
        if not tools:
            return None

        anthropic_tools = []
        for tool in tools:
            func_def = tool.get("function", {})
            anthropic_tools.append({
                "name": func_def.get("name"),
                "description": func_def.get("description"),
                "input_schema": func_def.get("parameters", {})
            })

        return anthropic_tools

    def _convert_tool_choice(self, tool_choice: Union[str, Dict]) -> Any:
        """
        Convert tool_choice parameter from OpenAI to Anthropic format.

        OpenAI: "auto" | "none" | {"type": "function", "function": {"name": "..."}}
        Anthropic: "auto" | "any" | {"type": "tool", "name": "..."}
        """
        if isinstance(tool_choice, str):
            if tool_choice == "auto":
                return "auto"
            elif tool_choice == "none":
                return None  # Don't pass tools parameter
        elif isinstance(tool_choice, dict):
            if tool_choice.get("type") == "function":
                return {
                    "type": "tool",
                    "name": tool_choice.get("function", {}).get("name")
                }

        return "auto"

    def _to_json(self, text: str) -> str:
        """
        Extract and repair JSON from response text.

        Args:
            text: Response text possibly containing JSON

        Returns:
            Repaired JSON string
        """
        from json_repair import repair_json

        # Remove common JSON wrapper tags
        if "<json>" in text:
            text = text.split("<json>")[1]
        if "</json>" in text:
            text = text.split("</json>")[0]
        if "```json" in text:
            text = text.split("```json")[1]
        if "```" in text:
            text = text.split("```")[0]

        # Repair and return JSON
        return repair_json(text, ensure_ascii=False)
