"""Terminal backend for executing Claude Code commands via WebSocket."""

import os
import subprocess
import threading
from queue import Queue, Empty
from typing import Optional

from flask_socketio import SocketIO, emit, disconnect


class ClaudeTerminalSession:
    """Manages a Claude Code terminal session with real-time output streaming."""

    def __init__(self, socketio: SocketIO, session_id: str):
        """Initialize terminal session.

        Args:
            socketio: Flask-SocketIO instance for emitting events
            session_id: Unique session identifier
        """
        self.socketio = socketio
        self.session_id = session_id
        self.process: Optional[subprocess.Popen] = None
        self.output_queue: Queue = Queue()
        self.is_running = False

    def execute_command(self, command: str) -> bool:
        """Execute a Claude Code command.

        Args:
            command: Command string to execute (must start with 'claude')

        Returns:
            True if command was started successfully, False otherwise
        """
        # Security: Only allow claude commands
        command = command.strip()
        if not command:
            self._emit_output("\r\n❌ Empty command\r\n", is_error=True)
            return False

        # Check for shell metacharacters that could enable command injection
        dangerous_chars = [";", "&", "|", "$", "`", "(", ")", "{", "}", "<", ">"]
        if any(char in command for char in dangerous_chars):
            self._emit_output(
                "\r\n❌ Command contains forbidden characters\r\n", is_error=True
            )
            self._emit_output("Shell operators (;, &, |, etc.) are not allowed\r\n")
            return False

        # Parse command - must be 'claude' or start with 'claude '
        parts = command.split()
        if not parts or parts[0] != "claude":
            self._emit_output(
                "\r\n❌ Only 'claude' commands are allowed\r\n", is_error=True
            )
            self._emit_output("Example: claude code --help\r\n")
            return False

        # Check if a command is already running
        if self.is_running and self.process and self.process.poll() is None:
            self._emit_output(
                "\r\n⚠️  Command already running. Please wait...\r\n", is_error=True
            )
            return False

        try:
            # Echo the command
            self._emit_output(f"$ {command}\r\n")

            # Start the process
            self.process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                bufsize=0,
                universal_newlines=True,
                cwd=os.path.expanduser("~"),  # Run from home directory
            )

            self.is_running = True

            # Start output reader thread
            output_thread = threading.Thread(
                target=self._read_output, daemon=True, name=f"output-{self.session_id}"
            )
            output_thread.start()

            return True

        except Exception as e:
            self._emit_output(f"\r\n❌ Error executing command: {e}\r\n", is_error=True)
            self.is_running = False
            return False

    def _read_output(self):
        """Read process output and emit to client (runs in separate thread)."""
        try:
            if not self.process or not self.process.stdout:
                return

            # Read output line by line
            for line in self.process.stdout:
                self._emit_output(line)

            # Wait for process to complete
            return_code = self.process.wait()

            # Emit completion status
            if return_code == 0:
                self._emit_output(f"\r\n✅ Command completed successfully\r\n")
            else:
                self._emit_output(
                    f"\r\n❌ Command exited with code {return_code}\r\n", is_error=True
                )

        except Exception as e:
            self._emit_output(f"\r\n❌ Error reading output: {e}\r\n", is_error=True)
        finally:
            self.is_running = False
            self._emit_output("\r\n$ ")  # Show prompt

    def _emit_output(self, text: str, is_error: bool = False):
        """Emit output to the WebSocket client.

        Args:
            text: Text to emit
            is_error: Whether this is error output (for styling)
        """
        self.socketio.emit(
            "terminal_output",
            {"data": text, "is_error": is_error},
            room=self.session_id,
            namespace="/terminal",
        )

    def stop(self):
        """Stop the current running process."""
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            finally:
                self.is_running = False


def setup_terminal_handlers(socketio: SocketIO, terminal_password: str):
    """Setup WebSocket event handlers for terminal.

    Args:
        socketio: Flask-SocketIO instance
        terminal_password: Password required to activate terminal
    """
    # Store active sessions
    sessions = {}

    @socketio.on("connect", namespace="/terminal")
    def handle_connect():
        """Handle client connection."""
        from flask import request

        session_id = request.sid
        print(f"Terminal client connected: {session_id}")
        emit("connected", {"session_id": session_id})

    @socketio.on("disconnect", namespace="/terminal")
    def handle_disconnect():
        """Handle client disconnection."""
        from flask import request

        session_id = request.sid
        if session_id in sessions:
            sessions[session_id].stop()
            del sessions[session_id]
        print(f"Terminal client disconnected: {session_id}")

    @socketio.on("authenticate", namespace="/terminal")
    def handle_authenticate(data):
        """Handle authentication request.

        Args:
            data: Dict with 'password' key
        """
        from flask import request

        session_id = request.sid
        password = data.get("password", "")

        if password == terminal_password:
            # Create new session
            sessions[session_id] = ClaudeTerminalSession(socketio, session_id)
            emit("auth_success", {"message": "Authentication successful"})
            emit("terminal_output", {"data": "🌸 Lavender Ledger Terminal\r\n"})
            emit(
                "terminal_output",
                {"data": "Restricted to Claude Code commands only\r\n"},
            )
            emit("terminal_output", {"data": "Type 'claude code --help' to start\r\n"})
            emit("terminal_output", {"data": "\r\n$ "})
        else:
            emit("auth_failed", {"message": "Invalid password"})

    @socketio.on("execute_command", namespace="/terminal")
    def handle_execute_command(data):
        """Handle command execution request.

        Args:
            data: Dict with 'command' key
        """
        from flask import request

        session_id = request.sid

        # Check if authenticated
        if session_id not in sessions:
            emit("terminal_output", {"data": "\r\n❌ Not authenticated\r\n"})
            return

        command = data.get("command", "").strip()
        if command:
            sessions[session_id].execute_command(command)

    @socketio.on("stop_command", namespace="/terminal")
    def handle_stop_command():
        """Handle request to stop current command."""
        from flask import request

        session_id = request.sid
        if session_id in sessions:
            sessions[session_id].stop()
            emit("terminal_output", {"data": "\r\n⚠️  Command stopped\r\n$ "})
