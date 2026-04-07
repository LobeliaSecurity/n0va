"""結合テスト用の最小 HTTP バックエンドとポート待機ヘルパ。"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable
from typing import Any


async def _reply_http_200_close(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, body: bytes) -> None:
    try:
        await reader.read(256 * 1024)
    finally:
        msg = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Length: " + str(len(body)).encode() + b"\r\n"
            b"Connection: close\r\n"
            b"\r\n" + body
        )
        writer.write(msg)
        await writer.drain()
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, OSError):
            pass


def make_http_backend(body: bytes):
    async def _handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await _reply_http_200_close(reader, writer, body)

    return _handler


async def start_http_backend(body: bytes) -> asyncio.Server:
    return await asyncio.start_server(
        make_http_backend(body),
        "127.0.0.1",
        0,
        backlog=128,
    )


def server_port(server: asyncio.Server) -> int:
    sock = server.sockets[0]
    return sock.getsockname()[1]


async def wait_for_attr(
    obj: Any,
    name: str,
    predicate,
    *,
    timeout: float = 5.0,
) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        val = getattr(obj, name, None)
        if predicate(val):
            return val
        await asyncio.sleep(0.01)
    raise TimeoutError(f"timeout waiting for {name!r} on {obj!r}")


async def wait_gate_port(svc: Any, timeout: float = 5.0) -> int:
    await wait_for_attr(svc, "_server", lambda s: s is not None, timeout=timeout)
    return svc._server.sockets[0].getsockname()[1]


async def wait_n0va_port(app: Any, timeout: float = 5.0) -> int:
    await wait_for_attr(
        app, "_asyncio_server", lambda s: s is not None, timeout=timeout
    )
    return app._asyncio_server.sockets[0].getsockname()[1]


async def await_stop_and_background(
    stop_awaitable: Awaitable[Any],
    background: asyncio.Task,
    *,
    wait_timeout: float = 15.0,
) -> None:
    """
    リスン停止（await）のあと、バックグラウンドの `start()` タスクを待つ。

    Windows の Proactor 等で `serve_forever` 終端が CancelledError になることがあるため、
    その場合は握りつぶす。
    """
    await stop_awaitable
    try:
        await asyncio.wait_for(background, timeout=wait_timeout)
    except asyncio.CancelledError:
        pass
    except asyncio.TimeoutError:
        background.cancel()
        try:
            await background
        except asyncio.CancelledError:
            pass
