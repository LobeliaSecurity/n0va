"""n0va.Service（HTTP サーバ）の結合テスト。"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import n0va

from tests.integration_backends import await_stop_and_background, wait_n0va_port


def test_service_serves_registered_get_route() -> None:
    async def main() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dummy.txt").write_text("x", encoding="utf-8")
            app = n0va.Service("127.0.0.1", 0, str(root))

            @app.onGet("/api/ping")
            async def ping(ctx):
                from n0va.handler.context import HttpResponse

                return HttpResponse(status=200, body=b"pong", content_type=b"text/plain")

            t = asyncio.create_task(app.__Start__())
            port = await wait_n0va_port(app)
            r, w = await asyncio.open_connection("127.0.0.1", port)
            try:
                w.write(
                    b"GET /api/ping HTTP/1.1\r\n"
                    b"Host: 127.0.0.1\r\n"
                    b"Connection: close\r\n"
                    b"\r\n"
                )
                await w.drain()
                data = await asyncio.wait_for(r.read(256 * 1024), timeout=15.0)
            finally:
                w.close()
                try:
                    await w.wait_closed()
                except (ConnectionError, OSError):
                    pass
            assert b"pong" in data
            assert b"200" in data
            await await_stop_and_background(app.stop(), t)

    asyncio.run(main())


def test_service_serves_static_file_from_memory() -> None:
    async def main() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "static.txt").write_bytes(b"n0va-static-integration")
            app = n0va.Service("127.0.0.1", 0, str(root))
            t = asyncio.create_task(app.__Start__())
            port = await wait_n0va_port(app)
            r, w = await asyncio.open_connection("127.0.0.1", port)
            try:
                w.write(
                    b"GET /static.txt HTTP/1.1\r\n"
                    b"Host: 127.0.0.1\r\n"
                    b"Connection: close\r\n"
                    b"\r\n"
                )
                await w.drain()
                data = await asyncio.wait_for(r.read(256 * 1024), timeout=15.0)
            finally:
                w.close()
                try:
                    await w.wait_closed()
                except (ConnectionError, OSError):
                    pass
            assert b"n0va-static-integration" in data
            await await_stop_and_background(app.stop(), t)

    asyncio.run(main())
