#!/usr/bin/env python3
"""
TermBot Web Mode Entry Point

Standard entry point for running TermBot in Web mode.
Can be invoked with: python -m termbot.web
"""
import os
import sys
from pathlib import Path

# 必须在导入其他模块前初始化日志系统，确保第三方库日志被禁用
from infrastructure.logging import init_logging
init_logging(level="INFO")


def load_env_file(env_file: str = ".env") -> None:
    """
    Load environment variables from .env file.

    Args:
        env_file: Path to .env file
    """
    env_path = Path(env_file)
    if not env_path.exists():
        print(f"Warning: {env_file} not found. Using default configuration.")
        return

    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Parse KEY=VALUE format
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                # Set environment variable (don't override existing)
                if key not in os.environ:
                    os.environ[key] = value


def create_app():
    """Create and configure Flask application."""
    from flask import Flask, jsonify, render_template, request, send_from_directory
    from flask_socketio import SocketIO

    from infrastructure.llm import get_client
    from agent.profiles import AgentProfileManager
    from interfaces.web import WebHandler

    # Create Flask app
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'termbot-secret-key')

    # Create SocketIO
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode='threading',
        ping_timeout=60,
        ping_interval=25
    )

    # Load environment variables
    load_env_file()

    # Create shared LLM client (auto-select based on config, stateless, safe to share)
    llm_client = get_client()

    # Create Web handler (manages multiple sessions)
    web_handler = WebHandler(socketio, llm_client)

    # Register HTTP routes
    @app.route('/')
    def index():
        """Serve the main page with multi-tab support."""
        try:
            return send_from_directory('static', 'index.html')
        except FileNotFoundError:
            # If static/index.html doesn't exist, return error page
            return '''
<!DOCTYPE html>
<html>
<head>
    <title>TermBot - Frontend Missing</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #333; }
        .error { background: #f8d7da; padding: 15px; border-radius: 5px; margin: 20px 0; border: 1px solid #f5c6cb; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚠️ Frontend File Missing</h1>
        <div class="error">
            <h3>static/index.html not found!</h3>
            <p>Make sure the frontend files are in the <code>static/</code> directory.</p>
        </div>
    </div>
</body>
</html>
            ''', 404

    @app.route('/health')
    def health():
        """Health check endpoint."""
        return {
            'status': 'healthy',
            'sessions': web_handler.get_session_count()
        }

    @app.route('/sessions')
    def sessions():
        """List active sessions."""
        sessions_info = {}
        for sid in list(web_handler.sessions.keys()):
            info = web_handler.get_session_info(sid)
            if info:
                sessions_info[sid] = info
        return {
            'count': len(sessions_info),
            'sessions': sessions_info
        }

    # --- Agent profile REST API ---

    @app.route('/api/agents', methods=['GET'])
    def get_agents():
        """List all agent profiles."""
        return jsonify(AgentProfileManager.get_all())

    @app.route('/api/agents', methods=['POST'])
    def create_agent():
        """Create a new custom agent profile."""
        data = request.get_json(force=True) or {}
        name = data.get('name', '').strip()
        system_prompt = data.get('system_prompt', '').strip()
        if not name:
            return jsonify({'error': 'name is required'}), 400
        if not system_prompt:
            return jsonify({'error': 'system_prompt is required'}), 400
        allowed_skills = data.get('allowed_skills', [])
        allowed_tools = data.get('allowed_tools', [])
        profile = AgentProfileManager.create(name, system_prompt, allowed_skills, allowed_tools)
        return jsonify(profile), 201

    @app.route('/api/agents/<agent_id>', methods=['PUT'])
    def update_agent(agent_id):
        """Update a custom agent profile."""
        if agent_id == 'default':
            return jsonify({'error': 'Cannot edit default agent'}), 400
        data = request.get_json(force=True) or {}
        name = data.get('name', '').strip()
        system_prompt = data.get('system_prompt', '').strip()
        if not name:
            return jsonify({'error': 'name is required'}), 400
        if not system_prompt:
            return jsonify({'error': 'system_prompt is required'}), 400
        allowed_skills = data.get('allowed_skills', [])
        allowed_tools = data.get('allowed_tools', [])
        profile = AgentProfileManager.update(agent_id, name, system_prompt, allowed_skills, allowed_tools)
        if profile:
            return jsonify(profile)
        return jsonify({'error': 'Agent not found'}), 404

    @app.route('/api/agents/<agent_id>', methods=['DELETE'])
    def delete_agent(agent_id):
        """Delete a custom agent profile."""
        if agent_id == 'default':
            return jsonify({'error': 'Cannot delete default agent'}), 400
        deleted = AgentProfileManager.delete(agent_id)
        if deleted:
            return jsonify({'ok': True})
        return jsonify({'error': 'Agent not found'}), 404

    @app.route('/api/skills', methods=['GET'])
    def get_available_skills():
        """Get list of available skills (enabled only)."""
        from agent.skills import SkillManager
        skill_manager = SkillManager()
        skills = skill_manager.list_skill_basics()
        return jsonify({'skills': skills})

    @app.route('/api/tools', methods=['GET'])
    def get_available_tools():
        """Get list of all available tools for agent configuration."""
        return jsonify({'tools': AgentProfileManager.available_tools()})

    # --- Conversation history REST API ---

    @app.route('/api/conversations/<agent_id>', methods=['GET'])
    def list_conversations(agent_id):
        """List conversation sessions for an agent, newest first."""
        import json as _json
        from datetime import datetime as _dt
        from infrastructure.config.settings import settings

        conv_config = settings.get("conversations", {})
        base_dir = Path(conv_config.get("base_dir", "~/.termbot/conversations")).expanduser()
        agent_dir = base_dir / agent_id

        if not agent_dir.exists():
            return jsonify([])

        sessions = []
        for session_dir in sorted(agent_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if not session_dir.is_dir():
                continue
            f = session_dir / "chat.jsonl"
            if not f.exists():
                continue
            first_msg = ""
            total = 0
            try:
                with open(f, encoding="utf-8") as fp:
                    for line in fp:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = _json.loads(line)
                            total += 1
                            if not first_msg and rec.get("role") == "user":
                                first_msg = rec.get("content", "")[:60]
                        except Exception:
                            pass
            except Exception:
                pass

            if total == 0:
                continue

            mtime = f.stat().st_mtime
            sessions.append({
                "session_id": session_dir.name,
                "first_msg": first_msg,
                "count": total,
                "ts": _dt.fromtimestamp(mtime).strftime("%m-%d %H:%M"),
            })

        return jsonify(sessions)

    @app.route('/api/conversations/<agent_id>/<session_id>', methods=['GET'])
    def get_conversation(agent_id, session_id):
        """Get all messages for a specific conversation session."""
        import json as _json
        from infrastructure.config.settings import settings

        conv_config = settings.get("conversations", {})
        base_dir = Path(conv_config.get("base_dir", "~/.termbot/conversations")).expanduser()
        f = base_dir / agent_id / session_id / "chat.jsonl"

        if not f.exists():
            return jsonify({"error": "Not found"}), 404

        messages = []
        try:
            with open(f, encoding="utf-8") as fp:
                for line in fp:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        messages.append(_json.loads(line))
                    except Exception:
                        pass
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify(messages)

    @app.route('/api/conversations/<agent_id>/<session_id>', methods=['DELETE'])
    def delete_conversation(agent_id, session_id):
        """Delete a conversation session directory."""
        import shutil
        from infrastructure.config.settings import settings

        conv_config = settings.get("conversations", {})
        base_dir = Path(conv_config.get("base_dir", "~/.termbot/conversations")).expanduser()
        session_dir = base_dir / agent_id / session_id

        if not session_dir.exists():
            return jsonify({"error": "Not found"}), 404

        try:
            shutil.rmtree(session_dir)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify({"ok": True})

    return app, socketio


def main() -> int:
    """Main entry point for Web mode."""
    # Load environment variables first
    load_env_file()

    # Check API key
    api_key = os.environ.get("LLM_API_KEY", "")
    if not api_key:
        print("⚠️  Warning: LLM_API_KEY not set!")
        print()
        print("Please edit .env file and set your API key:")
        print("  LLM_API_KEY=your-api-key-here")
        print()
        return 1

    # Create app and socketio
    app, socketio = create_app()

    # Get configuration from environment
    host = os.environ.get('TERMBOT_HOST', '0.0.0.0')
    port = int(os.environ.get('TERMBOT_PORT', 5000))
    debug = os.environ.get('TERMBOT_DEBUG', 'false').lower() == 'true'

    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║           TermBot - Web Server                            ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    print(f"Starting server on http://{host}:{port}")
    print(f"Debug mode: {debug}")
    print()
    print("Press Ctrl+C to stop the server")
    print("─" * 60)
    print()

    try:
        socketio.run(
            app,
            host=host,
            port=port,
            debug=debug,
            use_reloader=False,  # Disable reloader to avoid double initialization
            allow_unsafe_werkzeug=True  # Disable Werkzeug warning
        )
    except KeyboardInterrupt:
        print()
        print()
        print("─" * 60)
        print("Server stopped.")
        print()
    except Exception as e:
        print(f"Error starting server: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
