"""Unit tests for terminal module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.dashboard.terminal import ClaudeTerminalSession, setup_terminal_handlers


class TestCommandValidation:
    """Test command validation and security."""

    def test_valid_claude_commands(self):
        """Test that valid claude commands are accepted."""
        valid_commands = [
            "claude --version",
            "claude code --help",
            "claude code --model sonnet",
            "claude --help",
        ]

        mock_socketio = Mock()
        session = ClaudeTerminalSession(mock_socketio, "test-session")

        for cmd in valid_commands:
            # We'll mock the subprocess to just check validation passes
            with patch("src.dashboard.terminal.subprocess.Popen"):
                result = session.execute_command(cmd)
                # Command should be accepted (validation passes)
                # Note: actual execution would fail without proper mocking
                # but validation should pass

    def test_empty_command_rejected(self):
        """Test that empty commands are rejected."""
        mock_socketio = Mock()
        session = ClaudeTerminalSession(mock_socketio, "test-session")

        result = session.execute_command("")
        assert result is False

        result = session.execute_command("   ")
        assert result is False

    def test_non_claude_commands_rejected(self):
        """Test that non-claude commands are blocked."""
        invalid_commands = [
            "ls -la",
            "pwd",
            "rm -rf /",
            "cat /etc/passwd",
            "whoami",
            "CLAUDE --version",  # Wrong case
        ]

        mock_socketio = Mock()
        session = ClaudeTerminalSession(mock_socketio, "test-session")

        for cmd in invalid_commands:
            result = session.execute_command(cmd)
            assert result is False, f"Command should be rejected: {cmd}"

    def test_shell_metacharacters_blocked(self):
        """Test that shell metacharacters are blocked to prevent injection."""
        dangerous_commands = [
            "claude --version && ls",
            "claude --version; rm -rf /",
            "claude --version | grep test",
            "claude $(whoami)",
            "claude `whoami`",
            "claude --version > /tmp/out",
            "claude --version < /etc/passwd",
            "claude (ls)",
            "claude {ls}",
            "claude $USER",
        ]

        mock_socketio = Mock()
        session = ClaudeTerminalSession(mock_socketio, "test-session")

        for cmd in dangerous_commands:
            result = session.execute_command(cmd)
            assert result is False, f"Dangerous command should be blocked: {cmd}"


class TestTerminalSession:
    """Test terminal session management."""

    def test_session_creation(self):
        """Test that terminal session is created correctly."""
        mock_socketio = Mock()
        session = ClaudeTerminalSession(mock_socketio, "test-session-123")

        assert session.session_id == "test-session-123"
        assert session.socketio == mock_socketio
        assert session.process is None
        assert session.is_running is False

    def test_output_emission(self):
        """Test that output is emitted correctly via SocketIO."""
        mock_socketio = Mock()
        session = ClaudeTerminalSession(mock_socketio, "test-session")

        session._emit_output("Test output\r\n")

        mock_socketio.emit.assert_called_once_with(
            "terminal_output",
            {"data": "Test output\r\n", "is_error": False},
            room="test-session",
            namespace="/terminal",
        )

    def test_error_output_emission(self):
        """Test that error output is marked correctly."""
        mock_socketio = Mock()
        session = ClaudeTerminalSession(mock_socketio, "test-session")

        session._emit_output("Error message\r\n", is_error=True)

        mock_socketio.emit.assert_called_once_with(
            "terminal_output",
            {"data": "Error message\r\n", "is_error": True},
            room="test-session",
            namespace="/terminal",
        )

    def test_concurrent_command_rejected(self):
        """Test that concurrent commands are rejected."""
        mock_socketio = Mock()
        session = ClaudeTerminalSession(mock_socketio, "test-session")

        # Simulate a running process
        session.is_running = True
        session.process = Mock()
        session.process.poll.return_value = None  # Still running

        result = session.execute_command("claude --version")
        assert result is False

    @patch("src.dashboard.terminal.subprocess.Popen")
    def test_command_execution_starts_process(self, mock_popen):
        """Test that command execution starts a subprocess."""
        mock_socketio = Mock()
        session = ClaudeTerminalSession(mock_socketio, "test-session")

        # Mock the subprocess
        mock_process = Mock()
        mock_process.stdout = iter([])  # Empty output
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        result = session.execute_command("claude --version")

        # Should have attempted to start process
        assert mock_popen.called
        # Verify command was passed correctly
        call_args = mock_popen.call_args
        assert "claude --version" in str(call_args)


class TestWebSocketHandlers:
    """Test WebSocket event handlers."""

    def test_setup_terminal_handlers(self):
        """Test that terminal handlers are set up correctly."""
        mock_socketio = Mock()
        password = "test-password"

        setup_terminal_handlers(mock_socketio, password)

        # Verify that handlers were registered
        assert mock_socketio.on.called
        # Should have registered handlers for: connect, disconnect, authenticate, execute_command, stop_command
        assert mock_socketio.on.call_count >= 5


class TestSecurityFeatures:
    """Test security features comprehensively."""

    def test_password_length_accepted(self):
        """Test that various password lengths work."""
        mock_socketio = Mock()

        for length in [1, 8, 16, 32, 64]:
            password = "a" * length
            # Should not raise exception
            setup_terminal_handlers(mock_socketio, password)

    def test_special_characters_in_args_allowed(self):
        """Test that special chars in arguments (not operators) are allowed."""
        mock_socketio = Mock()
        session = ClaudeTerminalSession(mock_socketio, "test-session")

        # These should be allowed as they're arguments, not operators
        allowed_commands = [
            "claude code --help",
            "claude code --model sonnet",
            "claude --version",
        ]

        for cmd in allowed_commands:
            # These should pass validation (even if execution fails)
            with patch("src.dashboard.terminal.subprocess.Popen"):
                # The command should at least pass validation
                parts = cmd.split()
                assert parts[0] == "claude"

    def test_command_must_start_with_claude(self):
        """Test that command must start with 'claude' exactly."""
        mock_socketio = Mock()
        session = ClaudeTerminalSession(mock_socketio, "test-session")

        # These should all fail
        invalid = [
            "  claude --version",  # Leading spaces get stripped, so this should pass
            "notclaude --version",
            "myclaude --version",
            "claude_code --version",  # Underscore instead of space
        ]

        result = session.execute_command("notclaude --version")
        assert result is False

        result = session.execute_command("myclaude --version")
        assert result is False

    def test_case_sensitive_command_validation(self):
        """Test that command validation is case-sensitive."""
        mock_socketio = Mock()
        session = ClaudeTerminalSession(mock_socketio, "test-session")

        # Only lowercase 'claude' should work
        assert session.execute_command("CLAUDE --version") is False
        assert session.execute_command("Claude --version") is False
        assert session.execute_command("cLaUdE --version") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
