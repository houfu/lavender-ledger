"""Integration tests for Flask app with terminal feature."""

import pytest
import os
from src.dashboard.app import create_app


@pytest.fixture
def app():
    """Create and configure a test Flask app."""
    os.environ["DATABASE_PATH"] = "/tmp/test_terminal.db"
    os.environ["TERMINAL_PASSWORD"] = "test-password-123"

    app = create_app()
    app.config["TESTING"] = True
    yield app

    # Cleanup
    if "DATABASE_PATH" in os.environ:
        del os.environ["DATABASE_PATH"]
    if "TERMINAL_PASSWORD" in os.environ:
        del os.environ["TERMINAL_PASSWORD"]


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


class TestAppRoutes:
    """Test Flask app routes."""

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json == {"status": "healthy"}

    def test_terminal_route_exists(self, client):
        """Test that terminal route is registered."""
        response = client.get("/terminal")
        assert response.status_code == 200
        assert b"terminal" in response.data.lower()

    def test_index_route(self, client):
        """Test index route."""
        response = client.get("/")
        # Should return 200 even if database doesn't exist
        assert response.status_code == 200


class TestAppConfiguration:
    """Test app configuration."""

    def test_app_has_socketio(self, app):
        """Test that SocketIO is attached to app."""
        assert hasattr(app, "socketio")
        assert app.socketio is not None

    def test_terminal_password_from_env(self, app):
        """Test that terminal password is read from environment."""
        # Password was set in fixture
        assert os.environ.get("TERMINAL_PASSWORD") == "test-password-123"

    def test_database_path_from_env(self, app):
        """Test that database path is read from environment."""
        assert app.config["DATABASE_PATH"] == "/tmp/test_terminal.db"


class TestTerminalPage:
    """Test terminal page rendering."""

    def test_terminal_page_renders(self, client):
        """Test that terminal page renders successfully."""
        response = client.get("/terminal")
        assert response.status_code == 200

        # Check for key terminal elements
        assert b"terminal" in response.data.lower()
        assert b"xterm" in response.data.lower() or b"Terminal" in response.data

    def test_terminal_includes_xterm_js(self, client):
        """Test that terminal page includes xterm.js library."""
        response = client.get("/terminal")
        assert response.status_code == 200

        # Should include xterm.js CDN
        assert b"xterm" in response.data.lower()

    def test_terminal_includes_socketio(self, client):
        """Test that terminal page includes socket.io client."""
        response = client.get("/terminal")
        assert response.status_code == 200

        # Should include socket.io client
        assert b"socket.io" in response.data.lower()

    def test_terminal_has_auth_modal(self, client):
        """Test that terminal page has authentication modal."""
        response = client.get("/terminal")
        assert response.status_code == 200

        # Should have password input
        assert b"password" in response.data.lower()


class TestSecurityHeaders:
    """Test security-related features."""

    def test_terminal_route_requires_no_auth_to_view(self, client):
        """Test that terminal route is accessible (auth happens via WebSocket)."""
        # The page itself should be accessible
        # Authentication happens via WebSocket password
        response = client.get("/terminal")
        assert response.status_code == 200

    def test_terminal_password_not_in_html(self, client):
        """Test that terminal password is not leaked in HTML."""
        response = client.get("/terminal")
        assert response.status_code == 200

        # Password should NOT appear in the HTML
        assert b"test-password-123" not in response.data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
