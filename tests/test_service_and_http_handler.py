"""n0va.Service と handler.http.server の周辺テスト。"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

import n0va
from n0va.handler.context import HttpRequest
from n0va.handler.http import server


def test_service_route_rejects_websocket_method() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "dummy.txt").write_text("x", encoding="utf-8")
        app = n0va.Service("127.0.0.1", 0, str(root))

        with pytest.raises(ValueError, match="onWebsocket"):

            @app.route("/ws", methods=("WEBSOCKET",))
            async def _h(ctx):
                return None


def test_server_to_http_request_query_in_path() -> None:
    d = {
        "method": b"GET",
        "path": b"/items?q=1",
        "content": b"",
        "X-Test": b"1",
    }
    req = server._to_http_request(d)
    assert isinstance(req, HttpRequest)
    assert req.path == "/items"
    assert req.content == b"q=1"
    assert req.method_str == "GET"
    assert req.headers["x-test"] == b"1"


def test_server_to_http_request_post_body() -> None:
    d = {
        "method": b"POST",
        "path": b"/api",
        "content": b'{"a":1}',
    }
    req = server._to_http_request(d)
    assert req.path == "/api"
    assert req.content == b'{"a":1}'
