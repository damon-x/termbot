"""
LLM client module for interacting with language model APIs.

This module provides a unified interface for communicating with
OpenAI-compatible APIs for chat completions and embeddings.
"""
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union

from json_repair import repair_json
from openai import OpenAI

from infrastructure.config.settings import settings
from infrastructure.llm.function_calling import ChatResponse, FunctionCall, parse_function_call
from infrastructure.logging import get_logger, EventType

logging.getLogger("httpx").setLevel(logging.CRITICAL)
logger = get_logger("llm.client")

class OpenAIClient:
    """
    OpenAI-compatible API client for chat completions.

    Supports communication with OpenAI and compatible services
    like Alibaba Dashscope (Qwen), DeepSeek, etc.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """
        Initialize OpenAI client.

        Args:
            api_key: API key for authentication (defaults to config)
            base_url: Base URL for API (defaults to config)
            model: Model name to use (defaults to config)
        """
        llm_config = settings.llm

        self.api_key = api_key if api_key else llm_config.get("api_key", "")
        self.base_url = base_url if base_url else llm_config.get("base_url", "")
        self.model = model if model else llm_config.get("model", "qwen3-max-preview")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
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
        # DEBUG 级别：请求详情（不显示）
        # logger.log_event(EventType.LLM_REQUEST, {
        #     "model": self.model,
        #     "num_messages": len(messages),
        # })

        start_time = time.time()
        self._times += 1

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )

        response_content = completion.choices[0].message.content

        elapsed = time.time() - start_time

        # INFO 级别：简洁输出
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
        # DEBUG 级别：请求详情（不显示）
        # logger.debug(f"LLM Request: {len(messages)} messages, {len(tools) if tools else 0} tools")

        start_time = time.time()
        self._times += 1

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }

        if tools:
            kwargs["tools"] = tools

        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        completion = self.client.chat.completions.create(**kwargs)

        response_message = completion.choices[0].message
        function_call = parse_function_call(response_message)

        elapsed = time.time() - start_time

        # Extract token usage if available
        usage = getattr(completion, 'usage', None)
        token_info = {}
        if usage:
            token_info = {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            }

        # INFO 级别：简洁摘要
        if function_call:
            logger.info(f"LLM → Tool: {function_call.name} ({elapsed*1000:.0f}ms)")
        else:
            content_preview = (response_message.content or "")[:400]
            logger.info(f"LLM → Response: {content_preview}... ({elapsed*1000:.0f}ms)")

        # DEBUG 级别：详细信息
        logger.debug("LLM response details",
            model=self.model,
            duration_ms=round(elapsed * 1000, 2),
            has_function_call=function_call is not None,
            function_name=function_call.name if function_call else None,
            **token_info,
        )

        if self._times >= self._watch_gap:
            self._times = 0

        return ChatResponse(
            content=response_message.content,
            function_call=function_call,
            raw_response=completion
        )

    def _to_json(self, text: str) -> str:
        """
        Extract and repair JSON from response text.

        Args:
            text: Response text possibly containing JSON

        Returns:
            Repaired JSON string
        """
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


class EmbeddingClient:
    """
    Embedding client for vectorizing text.

    Supports text embedding via OpenAI-compatible APIs.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """
        Initialize embedding client.

        Args:
            api_key: API key for authentication (defaults to config)
            base_url: Base URL for API (defaults to config)
            model: Embedding model name (defaults to config)
        """
        llm_config = settings.llm

        self.api_key = api_key if api_key else llm_config.get("api_key", "")
        self.base_url = base_url if base_url else llm_config.get("base_url", "")
        self.model = model if model else llm_config.get("embed_model", "text-embedding-v4")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for input texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        # DEBUG 级别：请求详情（不显示）
        # logger.log_event(EventType.LLM_REQUEST, {
        #     "model": self.model,
        #     "num_texts": len(texts),
        #     "type": "embedding",
        # })

        completion = self.client.embeddings.create(model=self.model, input=texts)

        response_json = completion.model_dump_json()
        response_obj = json.loads(response_json)

        return [item["embedding"] for item in response_obj["data"]]

