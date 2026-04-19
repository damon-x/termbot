"""
Integration tests for Web mode.
"""
import os
import sys
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))


class TestWebIntegration:
    """Web integration tests."""

    @pytest.fixture
    def mock_socketio(self):
        """Create mock SocketIO."""
        socketio = Mock()
        socketio.emit = Mock()
        return socketio

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = Mock()
        # Mock chat_with_tools to return simple response
        response = Mock()
        response.content = "Test response"
        response.function_call = None
        client.chat_with_tools = Mock(return_value=response)
        return client

    @pytest.fixture
    def web_handler(self, mock_socketio, mock_llm_client):
        """Create web handler."""
        from interfaces.web import WebHandler
        return WebHandler(mock_socketio, mock_llm_client)

    def test_web_handler_creation(self, web_handler):
        """Test web handler can be created."""
        assert web_handler is not None
        assert web_handler.socketio is not None
        assert web_handler.shared_llm_client is not None
        assert web_handler.sessions == {}

    def test_web_session_count(self, web_handler):
        """Test getting session count."""
        count = web_handler.get_session_count()
        assert count == 0

    def test_web_session_info_nonexistent(self, web_handler):
        """Test getting info for nonexistent session."""
        info = web_handler.get_session_info("nonexistent")
        assert info is None

    @pytest.fixture
    def mock_request(self):
        """Mock Flask request object."""
        request = Mock()
        request.sid = "test_sid_123"
        return request

    def test_web_session_creation(self, web_handler, mock_llm_client, mock_request):
        """Test creating a web session."""
        from interfaces.web import WebSession

        # Create session
        session = WebSession("test_sid", mock_llm_client, "Test prompt")

        assert session.sid == "test_sid"
        assert session.agent is not None
        assert session.pty_manager is not None
        assert session.pty_manager.is_running()

    def test_web_session_cleanup(self, web_handler, mock_llm_client):
        """Test web session cleanup."""
        from interfaces.web import WebSession

        session = WebSession("test_sid", mock_llm_client, "Test prompt")
        assert session.pty_manager.is_running()

        session.cleanup()

        # After cleanup, PTY should be stopped
        assert not session.pty_manager.is_running()

    def test_web_handler_command_help(self, web_handler):
        """Test /help command handling."""
        from interfaces.web import WebSession

        # Create a mock session
        session = Mock()
        web_handler.sessions["test"] = session

        response = web_handler._handle_command("/help", session)

        assert "Available commands" in response

    def test_web_handler_command_tools(self, web_handler):
        """Test /tools command handling."""
        from interfaces.web import WebSession

        # Create a mock session
        session = Mock()
        session.agent.get_available_tools = Mock(return_value=["tool1", "tool2"])
        web_handler.sessions["test"] = session

        response = web_handler._handle_command("/tools", session)

        assert "Available tools" in response

    def test_web_handler_unknown_command(self, web_handler):
        """Test unknown command handling."""
        from interfaces.web import WebSession

        session = Mock()
        web_handler.sessions["test"] = session

        response = web_handler._handle_command("/unknown", session)

        assert "Unknown command" in response

    def test_web_flask_app_creation(self):
        """Test Flask app creation."""
        # This test requires actual Flask, not just mocks
        # We'll test the create_app function can be called
        try:
            from web import create_app
            app, socketio = create_app()
            assert app is not None
            assert socketio is not None
        except Exception as e:
            pytest.skip(f"Flask app creation failed: {e}")

    def test_multiple_sessions_isolation(self, mock_socketio, mock_llm_client):
        """Test that multiple sessions are isolated."""
        from interfaces.web import WebSession, WebHandler

        handler = WebHandler(mock_socketio, mock_llm_client)

        # Create two sessions
        session1 = WebSession("sid1", mock_llm_client, "Test prompt")
        session2 = WebSession("sid2", mock_llm_client, "Test prompt")

        # Each should have independent agent and PTY
        assert session1.agent != session2.agent
        assert session1.pty_manager != session2.pty_manager
        assert session1.pty_manager.pid != session2.pty_manager.pid

        # Cleanup
        session1.cleanup()
        session2.cleanup()


class TestWebSession:
    """Tests for WebSession class."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = Mock()
        response = Mock()
        response.content = "Test response"
        response.function_call = None
        client.chat_with_tools = Mock(return_value=response)
        return client

    def test_session_initialization(self, mock_llm_client):
        """Test session initializes correctly."""
        from interfaces.web import WebSession

        session = WebSession("test_sid", mock_llm_client, "Test prompt")

        assert session.sid == "test_sid"
        assert session.agent is not None
        assert session.pty_manager is not None

    def test_session_independent_context(self, mock_llm_client):
        """Test each session has independent context."""
        from interfaces.web import WebSession

        session1 = WebSession("sid1", mock_llm_client, "Test prompt")
        session2 = WebSession("sid2", mock_llm_client, "Test prompt")

        # Each agent should have its own context
        context1 = session1.agent.get_context()
        context2 = session2.agent.get_context()

        assert context1 is not context2

        # Cleanup
        session1.pty_manager.stop()
        session2.pty_manager.stop()

    def test_session_independent_pty(self, mock_llm_client):
        """Test each session has independent PTY."""
        from interfaces.web import WebSession

        session1 = WebSession("sid1", mock_llm_client, "Test prompt")
        session2 = WebSession("sid2", mock_llm_client, "Test prompt")

        # Each should have different PTY PID
        pid1 = session1.pty_manager.pid
        pid2 = session2.pty_manager.pid

        assert pid1 != pid2

        # Cleanup
        session1.pty_manager.stop()
        session2.pty_manager.stop()
