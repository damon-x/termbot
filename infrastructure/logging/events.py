"""
事件类型定义

定义 TermBot 中所有关键事件的常量
"""


class EventType:
    """事件类型常量定义"""
    
    # ============================================
    # Agent 生命周期
    # ============================================
    AGENT_CREATED = "agent_created"
    AGENT_DESTROYED = "agent_destroyed"
    AGENT_PAUSED = "agent_paused"
    AGENT_RESUMED = "agent_resumed"
    
    # ============================================
    # ReAct 循环
    # ============================================
    REACT_LOOP_START = "react_loop_start"
    REACT_LOOP_END = "react_loop_end"
    REACT_STEP = "react_step"
    REACT_THOUGHT = "react_thought"
    REACT_ACTION = "react_action"
    REACT_OBSERVATION = "react_observation"
    
    # ============================================
    # 工具执行
    # ============================================
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    TOOL_CALL_ERROR = "tool_call_error"
    
    # ============================================
    # LLM 交互
    # ============================================
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    LLM_ERROR = "llm_error"
    
    # ============================================
    # PTY 操作
    # ============================================
    PTY_COMMAND = "pty_command"
    PTY_OUTPUT = "pty_output"
    PTY_LOCK_ACQUIRED = "pty_lock_acquired"
    PTY_LOCK_RELEASED = "pty_lock_released"
    PTY_LOCK_PREEMPTED = "pty_lock_preempted"
    
    # ============================================
    # 会话管理
    # ============================================
    SESSION_CREATED = "session_created"
    SESSION_DESTROYED = "session_destroyed"
    SESSION_MESSAGE = "session_message"
    
    # ============================================
    # 内存操作
    # ============================================
    MEMORY_ADD = "memory_add"
    MEMORY_QUERY = "memory_query"
    MEMORY_DELETE = "memory_delete"
    
    # ============================================
    # 技能系统
    # ============================================
    SKILL_LOADED = "skill_loaded"
    SKILL_EXECUTED = "skill_executed"
    SKILL_ERROR = "skill_error"
    
    # ============================================
    # 性能指标
    # ============================================
    PERFORMANCE_METRIC = "performance_metric"


# 关键事件列表（用于审计日志过滤）
CRITICAL_EVENTS = {
    EventType.REACT_STEP,
    EventType.TOOL_CALL_END,
    EventType.TOOL_CALL_ERROR,
    EventType.LLM_RESPONSE,
    EventType.LLM_ERROR,
    EventType.PTY_COMMAND,
    EventType.SESSION_CREATED,
    EventType.SESSION_DESTROYED,
}
