"""n0va.Service を上流にしたゲートの結合テスト（エンドツーエンド）。"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import n0va
from n0va.core.gate import EntrancePlain, GateConfig, ListenConfig, Route, Upstream
from n0va.core.gate.service import GateService

from tests.integration_backends import (
    await_stop_and_background,
    wait_gate_port,
    wait_n0va_port,
)


def test_plain_gate_proxies_to_n0va_static() -> None:
    async def main() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "proxied.txt").write_bytes(b"proxied-through-gate")
            app = n0va.Service("127.0.0.1", 0, str(root))
            st = asyncio.create_task(app.__Start__())
            sport = await wait_n0va_port(app)
            cfg = GateConfig(
                listen=ListenConfig("127.0.0.1", 0, backlog=32),
                entrance=EntrancePlain(default_route="*"),
                routes={"*": Route((Upstream("127.0.0.1", sport),))},
            )
            gate = GateService(cfg)
            gt = asyncio.create_task(gate.start())
            gport = await wait_gate_port(gate)
            r, w = await asyncio.open_connection("127.0.0.1", gport)
            try:
                w.write(
                    b"GET /proxied.txt HTTP/1.1\r\n"
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
            assert b"proxied-through-gate" in data
            await await_stop_and_background(gate.stop(), gt)
            await await_stop_and_background(app.stop(), st)

    asyncio.run(main())
