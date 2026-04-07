"""n0va.protocol.http1 のパーサ単体テスト。"""

from __future__ import annotations

import pytest

from n0va.protocol.http1 import Http1ParseError, Http1RequestParser, Http1ResponseParser


def _req(
    method: bytes = b"GET",
    target: bytes = b"/",
    headers: list[tuple[bytes, bytes]] | None = None,
    body: bytes = b"",
) -> bytes:
    h = headers or []
    lines = [b" ".join((method, target, b"HTTP/1.1"))]
    for k, v in h:
        lines.append(k + b": " + v)
    head = b"\r\n".join(lines) + b"\r\n\r\n"
    return head + body


def test_normalize_request_target_absolute_uri() -> None:
    assert Http1RequestParser.normalize_request_target(
        b"http://example.com/foo?x=1"
    ) == b"/foo?x=1"
    assert Http1RequestParser.normalize_request_target(b"*") == b"*"
    assert Http1RequestParser.normalize_request_target(b"/a") == b"/a"


def test_parse_get_no_body() -> None:
    raw = _req()
    r = Http1RequestParser.parse(raw)
    assert r is not None
    assert r.method == b"GET"
    assert r.path_only == "/"
    assert r.body == b""
    assert r.consumed == len(raw)


def test_parse_content_length_body() -> None:
    body = b"hello"
    raw = _req(
        b"POST",
        b"/api",
        [(b"Content-Length", str(len(body)).encode())],
        body,
    )
    r = Http1RequestParser.parse(raw)
    assert r is not None
    assert r.body == body


def test_parse_incomplete_waits() -> None:
    raw = _req(
        b"POST",
        b"/",
        [(b"Content-Length", b"10")],
        b"ab",
    )
    assert Http1RequestParser.parse(raw) is None


def test_parse_chunked() -> None:
    # 5 bytes "hello" then terminator
    chunk_block = (
        b"5\r\nhello\r\n"
        b"0\r\n"
        b"\r\n"
    )
    raw = _req(
        b"POST",
        b"/",
        [(b"Transfer-Encoding", b"chunked")],
        chunk_block,
    )
    r = Http1RequestParser.parse(raw)
    assert r is not None
    assert r.body == b"hello"


def test_parse_bad_request_line() -> None:
    with pytest.raises(Http1ParseError, match="bad request line"):
        Http1RequestParser.parse(b"FOO\r\n\r\n")


def test_parse_conflicting_content_length() -> None:
    raw = _req(
        b"POST",
        b"/",
        [(b"Content-Length", b"3, 3, 4")],
        b"abc",
    )
    with pytest.raises(Http1ParseError, match="conflicting"):
        Http1RequestParser.parse(raw)


def test_to_server_request_dict() -> None:
    raw = _req(b"GET", b"/p?q=1")
    r = Http1RequestParser.parse(raw)
    assert r is not None
    d = Http1RequestParser.to_server_request_dict(r)
    assert d["method"] == b"GET"
    assert d["content"] == b""


def test_response_parse_200_with_cl() -> None:
    body = b"ok"
    msg = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        b"\r\n" + body
    )
    resp = Http1ResponseParser.parse(msg)
    assert resp is not None
    assert resp.status_code == 200
    assert resp.body == b"ok"


def test_response_head_no_body_despite_cl() -> None:
    msg = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Length: 999\r\n"
        b"\r\n"
    )
    resp = Http1ResponseParser.parse(msg, request_method=b"HEAD")
    assert resp is not None
    assert resp.body == b""


def test_response_204_no_body() -> None:
    msg = b"HTTP/1.1 204 No Content\r\n\r\nextra would be next message"
    resp = Http1ResponseParser.parse(msg)
    assert resp is not None
    assert resp.status_code == 204
    assert resp.body == b""
    assert msg[resp.consumed :].startswith(b"extra")
