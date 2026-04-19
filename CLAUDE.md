# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/claude-code) when working with code in this repository.

## Project Overview

TermBot is an intelligent terminal assistant that uses AI to understand natural language and execute terminal commands through PTY (pseudo-terminal). It supports both CLI and Web modes with complete decoupling between the Agent core and interface layers.

## Virtual Environment

**Important**: Use the virtual environment at `.venv` in the project root.

```bash
# Activate virtual environment
source .venv/bin/activate

# Or use Python directly from the virtual environment
.venv/bin/python3 <command>
```

## Common Commands

```bash
# Run Python script
.venv/bin/python3 script.py

# Install dependencies
.venv/bin/pip install <package>

# Code linting
.venv/bin/python3 -m pylint agent/ infrastructure/ interfaces/
.venv/bin/python3 -m mypy agent/ infrastructure/ interfaces/ --ignore-missing-imports

# Run tests
.venv/bin/python3 -m pytest tests/

# Run single test file
.venv/bin/python3 -m pytest tests/unit/test_agent.py

# Run tests with coverage
.venv/bin/python3 -m pytest --cov=agent --cov=infrastructure tests/
```

## Architecture: Session Isolation Principle

**Critical Design: 1 Web Session = 1 Agent Instance = 1 PTY Instance**

Each user session has completely isolated:
- Agent instance (independent Context and conversation history)
- PTY Manager (separate terminal process)
- Session state and memory

### Shared vs Independent Components

| Component | Multi-Session Strategy | Reason |
|-----------|------------------------|--------|
| LLM Client | ✅ Shared | Stateless, just API calls |
| Agent Instance | ❌ Independent | Has state (Context, conversation history) |
| PTY Manager | ❌ Independent | Each session needs separate terminal |
| Memory/Notes | ❌ Independent | User data isolation |

**Why independent Agents?**
- Shared Agent would cause conversation history mixing between users
- Note queries would return wrong user's data
- Task execution conflicts when multiple users command simultaneously
- Context state pollution

## Environment Setup

Required environment variables (set in `.env` file):
```bash
OPENAI_API_KEY=your-api-key-here  # Required for LLM functionality
SECRET_KEY=your-secret-key          # For Flask sessions (optional, auto-generated)
TERMBOT_HOST=0.0.0.0              # Web server host (default: 0.0.0.0)
TERMBOT_PORT=5000                   # Web server port (default: 5000)
TERMBOT_DEBUG=false                 # Debug mode (default: false)
```

## Entry Points

The project has multiple ways to start:

### CLI Mode

```bash
# Method 1: Quick start script
./start.sh

# Method 2: Direct Python
.venv/bin/python3 cli.py

# Method 3: Module invocation
.venv/bin/python3 -m termbot.cli
```

The `start.sh` → `start.py` → `cli.py` chain delegates to the standard entry point.

Creates a single Agent instance with PTY Manager for interactive terminal use.

### Web Mode

```bash
.venv/bin/python3 web.py

# With custom host/port
TERMBOT_HOST=127.0.0.1 TERMBOT_PORT=8080 .venv/bin/python3 web.py
```

Flask + SocketIO server that creates independent Agent+PTY instances per WebSocket connection.

### Web Mode SocketIO Events

Key events handled in `interfaces/web.py`:
- `connect` → Creates new WebSession with independent Agent+PTY
- `disconnect` → Cleans up session resources
- `chat_in` → Chat messages to agent (supports `/` commands)
- `chat_out` → Agent responses sent to client
- `terminal_input` → Direct terminal input from frontend
- `terminal_output` → PTY output streamed to client
- `terminal_resize` → Terminal resize events
- `cmd_res` → Terminal content from frontend (legacy compatibility)

## Module Structure

```
termbot/
├── agent/              # Core Agent Logic (interface-agnostic)
│   ├── core.py         # Agent class - main orchestrator
│   ├── react.py        # ReAct loop (Reasoning + Acting pattern)
│   ├── context.py      # Execution context - messages, state, tasks
│   ├── tools/          # Tool system
│   │   ├── base.py     # Tool base classes and registry
│   │   ├── terminal.py # Terminal tool (uses PTY Manager)
│   │   └── impl.py     # Built-in tool implementations
│   ├── components/     # Legacy components (LLM, Chat, Route, Cmd)
│   ├── memory/         # Memory management (notes, experience, quick commands)
│   └── prompts/        # Prompt templates
├── infrastructure/     # Infrastructure Layer
│   ├── llm/           # LLM client (OpenAI-compatible)
│   ├── terminal/       # PTY Manager with session-based locking
│   ├── config/        # Configuration management
│   ├── memory/        # Vector database, text search (Whoosh + jieba)
│   └── mcp/          # MCP (Model Context Protocol) support
├── interfaces/        # Interface Layer
│   ├── base.py        # Base handler class
│   ├── cli.py         # CLI interface handler
│   └── web.py         # Web interface handler (SocketIO)
├── config/            # Configuration files
│   ├── default.json
│   ├── development.json
│   └── mcp_servers.json
├── cli.py            # CLI entry point
├── web.py            # Web entry point
└── start.sh          # Quick start script
```

## ReAct Loop Pattern

The Agent uses the **ReAct (Reasoning + Acting)** pattern implemented in `agent/react.py`:

1. **Think**: LLM analyzes the user request and available tools
2. **Act**: LLM chooses a tool to execute (via Function Calling)
3. **Observe**: Tool result is added to conversation history
4. **Repeat**: Process continues until task is complete or max iterations reached

Each iteration produces a `ReactStep` with:
- `thought`: What the agent is thinking
- `action`: Tool name being used
- `action_input`: Arguments for the tool
- `observation`: Result from executing the tool

## Key Classes and Their Roles

### Agent Core
- **`Agent`** (`agent/core.py`): Main orchestrator, manages ReactLoop and tools
- **`ReactLoop`** (`agent/react.py`): Implements ReAct pattern - thinks, acts, observes, repeats
- **`Context`** (`agent/context.py`): Manages conversation state, message history, task tracking

### Tool System
- **`Tool`** (`agent/tools/base.py`): Abstract base for all tools
- **`SimpleTool`**: Convenience class for quick tool creation with just a name, description, and function
- **`ToolRegistry`**: Manages available tools, generates schemas for LLM
- **`TerminalTool`** (`agent/tools/terminal.py`): Uses PTY Manager to execute real commands

### Built-in Tools (`agent/tools/impl.py`)
- `exec_terminal_cmd`: Execute shell commands in the PTY
- `add_note`: Record notes for future reference
- `get_all_note`: Retrieve all stored notes
- `send_msg_to_user`: Send messages to the user
- `create_quick_cmd`: Create quick command templates
- `get_all_quick_cmd`: Retrieve all quick commands
- `search_weather`: Query weather information
- `send_email`: Send emails
- `send_file_user`: Send files to the user

### PTY Management
- **`PTYManager`** (`infrastructure/terminal/pty_manager.py`): Manages pseudo-terminal process
- **`PTYInputLock`**: Session-based locking with priority preemption (Agent can preempt Web)

Lock priority levels:
- `AGENT` (HIGH=10): Agent commands have high priority, can preempt web sessions
- `WEB` (NORMAL=5): Web user input has normal priority

### Interface Handlers
- **`CLIHandler`** (`interfaces/cli.py`): Interactive command-line session
- **`WebHandler`** (`interfaces/web.py`): Multi-session WebSocket handler
- **`WebSession`**: Per-session Agent+PTY instance with independent state

## Configuration

- `config/default.json` - Default configuration
- `config/development.json` - Development environment overrides
- `config/mcp_servers.json` - MCP server configurations

Environment variable substitution is supported: `"${OPENAI_API_KEY}"`

## Code Standards

- Follow PEP 8 conventions
- Use type annotations
- Import order: standard library → third-party → local modules
- Pylint score requirement: ≥ 8.0

## Refactoring Phases

**All phases completed** ✅

- [x] Phase 1: Basic refactoring (code standards, module splitting)
- [x] Phase 2: Agent core decoupling
- [x] Phase 3: LLM optimization & terminal management
- [x] Phase 4: CLI mode & Web integration

See `docs/REFACTOR_PLAN.md` for details.

## Development Workflow

### Git Commit Policy

**CRITICAL**: Do NOT execute `git commit` automatically unless user explicitly requests it.
