"""Tests for DevToolkitClient decoupled HTTP/SSE daemon client."""

import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from devtoolkit.client.api import DevToolkitAPIError, DevToolkitClient


def test_client_initialization():
    """Verify default properties and base URL calculation."""
    client = DevToolkitClient(host="127.0.0.1", port=4321, timeout=5.0)
    assert client.host == "127.0.0.1"
    assert client.port == 4321
    assert client.timeout == 5.0
    assert client.base_url == "http://127.0.0.1:4321"


def test_client_is_alive_true():
    """Verify is_alive returns True when health probe responds ok."""
    client = DevToolkitClient()
    with patch.object(client, "get_health", return_value={"status": "ok", "app": "devtoolkit"}):
        assert client.is_alive() is True


def test_client_is_alive_false():
    """Verify is_alive returns False when connection fails."""
    client = DevToolkitClient()
    with patch.object(client, "get_health", side_effect=DevToolkitAPIError("Connection refused")):
        assert client.is_alive() is False


def test_client_get_request_success():
    """Test successful GET request parsing."""
    client = DevToolkitClient()
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"status": "ok", "tools": []}'
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = client._get("/api/tools")
        assert res == {"status": "ok", "tools": []}


def test_client_http_error_handling():
    """Test HTTPError wrapping into DevToolkitAPIError."""
    client = DevToolkitClient()
    http_err = urllib.error.HTTPError(
        url="http://127.0.0.1:4321/api/unknown",
        code=404,
        msg="Not Found",
        hdrs={},
        fp=MagicMock(read=lambda: b'{"detail": "Endpoint not found"}'),
    )

    with patch("urllib.request.urlopen", side_effect=http_err):
        with pytest.raises(DevToolkitAPIError) as exc_info:
            client._get("/api/unknown")
        assert exc_info.value.status_code == 404
        assert "404" in str(exc_info.value)


def test_client_url_error_handling():
    """Test URLError (connection refused) wrapping into DevToolkitAPIError."""
    client = DevToolkitClient()
    url_err = urllib.error.URLError(reason="Connection refused")

    with patch("urllib.request.urlopen", side_effect=url_err):
        with pytest.raises(DevToolkitAPIError) as exc_info:
            client._get("/api/health")
        assert "Failed to connect" in str(exc_info.value)


def test_client_run_async_callback():
    """Verify run_async runs task in background thread and fires callback."""
    client = DevToolkitClient()
    callback_res = []

    def sample_task(x, y):
        return x + y

    t = client.run_async(sample_task, 10, 20, callback=lambda r: callback_res.append(r))
    t.join(timeout=2.0)
    assert callback_res == [30]


def test_client_run_async_errback():
    """Verify run_async fires errback when exception is raised."""
    client = DevToolkitClient()
    errors = []

    def failing_task():
        raise ValueError("Task error")

    t = client.run_async(failing_task, errback=lambda e: errors.append(e))
    t.join(timeout=2.0)
    assert len(errors) == 1
    assert isinstance(errors[0], ValueError)


def test_client_api_methods_mapped():
    """Test that all high-level domain methods invoke appropriate HTTP verbs and paths."""
    client = DevToolkitClient()

    with patch.object(client, "_request", return_value={"status": "ok"}) as mock_req:
        client.get_system()
        mock_req.assert_called_with("GET", "/api/system", timeout=None)

        client.get_config()
        mock_req.assert_called_with("GET", "/api/config", timeout=None)

        client.set_close_action("minimize")
        mock_req.assert_called_with("POST", "/api/config/close-action", payload={"action": "minimize"}, timeout=None)

        client.add_search_path("D:/Projects")
        mock_req.assert_called_with("POST", "/api/config/search-paths", payload={"path": "D:/Projects"}, timeout=None)

        client.remove_search_path(index=0)
        mock_req.assert_called_with("DELETE", "/api/config/search-paths", payload={"index": 0}, timeout=None)

        client.send_notification("Title", "Msg", 1)
        mock_req.assert_called_with(
            "POST", "/api/daemon/notify", payload={"title": "Title", "message": "Msg", "icon_type": 1}, timeout=None
        )

        client.get_ports()
        mock_req.assert_called_with("GET", "/api/ports", timeout=None)

        client.kill_port(8080, force=True)
        mock_req.assert_called_with("POST", "/api/ports/kill", payload={"port": 8080, "force": True}, timeout=None)

        client.run_project_audit("D:/App")
        mock_req.assert_called_with("POST", "/api/project/audit", payload={"path": "D:/App"}, timeout=30.0)

        client.search_query("test.py", category="code")
        mock_req.assert_called_with(
            "POST",
            "/api/search/query",
            payload={
                "query": "test.py",
                "category": "code",
                "scope": "all",
                "match_path": False,
                "is_regex": False,
                "case_sensitive": False,
                "whole_word": False,
                "limit": 500,
                "offset": 0,
            },
            timeout=None,
        )

        client.trigger_reindex()
        mock_req.assert_called_with("POST", "/api/search/reindex", payload={}, timeout=None)
