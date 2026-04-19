"""
Function calling support for LLM client.

Provides data structures and utilities for handling
OpenAI-style function calling.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class FunctionCall:
    """
    Represents a function call from the LLM.

    Attributes:
        id: Unique identifier for this tool call
        name: Name of the function to call
        arguments: Arguments to pass to the function
    """
    id: str
    name: str
    arguments: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments
        }


@dataclass
class ChatResponse:
    """
    Response from chat completion with function calling support.

    Attributes:
        content: Text content from the LLM
        function_call: Optional function call requested by the LLM
        tool_calls: Optional list of tool calls requested by the LLM
        raw_response: Raw response from the API
    """
    content: Optional[str]
    function_call: Optional[FunctionCall] = None
    tool_calls: Optional[List[FunctionCall]] = None
    raw_response: Optional[Any] = None

    def has_function_call(self) -> bool:
        """Check if response contains a function call."""
        return self.function_call is not None or (
            self.tool_calls is not None and len(self.tool_calls) > 0
        )

    def get_function_calls(self) -> List[FunctionCall]:
        """Get all function calls from response."""
        calls: List[FunctionCall] = []
        if self.function_call:
            calls.append(self.function_call)
        if self.tool_calls:
            calls.extend(self.tool_calls)
        return calls


def parse_function_call(response_message: Any) -> Optional[FunctionCall]:
    """
    Parse function call from OpenAI response message.

    Args:
        response_message: Response message from OpenAI API

    Returns:
        FunctionCall instance or None if no function call
    """
    import json

    # Check for tool_calls first (newer API)
    if hasattr(response_message, "tool_calls") and response_message.tool_calls:
        tool_call = response_message.tool_calls[0]
        function = tool_call.function
        return FunctionCall(
            id=tool_call.id,
            name=function.name,
            arguments=json.loads(function.arguments)
        )

    # Check for legacy function_call
    if hasattr(response_message, "function_call") and response_message.function_call:
        func = response_message.function_call
        # Generate an ID for legacy format
        import uuid
        return FunctionCall(
            id=f"call_{uuid.uuid4().hex[:8]}",
            name=func.name,
            arguments=json.loads(func.arguments)
        )

    return None
