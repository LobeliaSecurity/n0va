"""ゲート（平文 TCP 透過・HTTP ディスパッチ）の結合テスト。"""

from __future__ import annotations

import asyncio

from n0va.core.gate import (
    EntrancePlain,
    GateConfig,
    HttpDispatchRoute,
    HttpDispatchRule,
    HttpRoutingGateService,
    ListenConfig,
    LoadBalanceStrategy,
    Route,
    Upstream,
)
from n0va.core.gate.service import GateService

from tests.integration_backends import (
    await_stop_and_background,
    server_port,
    start_http_backend,
    wait_gate_port,
)


def test_gate_plain_tcp_proxies_http_to_upstream() -> None:
    async def main() -> None:
        backend = await start_http_backend(b"plain-upstream-marker")
        try:
            uport = server_port(backend)
            cfg = GateConfig(
                listen=ListenConfig("127.0.0.1", 0, backlog=32),
                entrance=EntrancePlain(default_route="*"),
                routes={
                    "*": Route((Upstream("127.0.0.1", uport),)),
                },
            )
            gate = GateService(cfg)
            gt = asyncio.create_task(gate.start())
            gport = await wait_gate_port(gate)
            reader, writer = await asyncio.open_connection("127.0.0.1", gport)
            try:
                writer.write(
                    b"GET / HTTP/1.1\r\n"
                    b"Host: 127.0.0.1\r\n"
                    b"Connection: close\r\n"
                    b"\r\n"
                )
                await writer.drain()
                data = await asyncio.wait_for(
                    reader.read(256 * 1024), timeout=15.0
                )
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except (ConnectionError, OSError):
                    pass
            assert b"plain-upstream-marker" in data
            await await_stop_and_background(gate.stop(), gt)
        finally:
            backend.close()
            await backend.wait_closed()

    asyncio.run(main())


def test_http_routing_gate_dispatches_by_path_prefix() -> None:
    async def main() -> None:
        b1 = await start_http_backend(b"backend-one")
        b2 = await start_http_backend(b"backend-two")
        try:
            p1 = server_port(b1)
            p2 = server_port(b2)
            route = HttpDispatchRoute(
                (
                    Upstream("127.0.0.1", p1),
                    Upstream("127.0.0.1", p2),
                ),
                (
                    HttpDispatchRule(
                        0,
                        methods=frozenset(["GET"]),
                        path_prefix="/a",
                    ),
                    HttpDispatchRule(
                        1,
                        methods=frozenset(["GET"]),
                        path_prefix="/b",
                    ),
                ),
                strategy=LoadBalanceStrategy.ROUND_ROBIN,
                default_upstream_index=0,
            )
            cfg = GateConfig(
                listen=ListenConfig("127.0.0.1", 0, backlog=32),
                entrance=EntrancePlain(default_route="*"),
                routes={"*": route},
            )
            gate = HttpRoutingGateService(cfg)
            gt = asyncio.create_task(gate.start())
            gport = await wait_gate_port(gate)

            async def get_path(path: str) -> bytes:
                r, w = await asyncio.open_connection("127.0.0.1", gport)
                try:
                    req = (
                        f"GET {path} HTTP/1.1\r\n"
                        f"Host: 127.0.0.1\r\n"
                        f"Connection: close\r\n"
                        f"\r\n"
                    ).encode("ascii")
                    w.write(req)
                    await w.drain()
                    return await asyncio.wait_for(
                        r.read(256 * 1024), timeout=15.0
                    )
                finally:
                    w.close()
                    try:
                        await w.wait_closed()
                    except (ConnectionError, OSError):
                        pass

            d1 = await get_path("/a/x")
            d2 = await get_path("/b/y")
            assert b"backend-one" in d1
            assert b"backend-two" in d2
            await await_stop_and_background(gate.stop(), gt)
        finally:
            b1.close()
            b2.close()
            await b1.wait_closed()
            await b2.wait_closed()

    asyncio.run(main())


def test_http_dispatch_rule_defaults_to_default_upstream() -> None:
    """ルール不一致時は default_upstream_index が使われる。"""

    async def main() -> None:
        b1 = await start_http_backend(b"only-default")
        b2 = await start_http_backend(b"unused")
        try:
            p1 = server_port(b1)
            p2 = server_port(b2)
            route = HttpDispatchRoute(
                (
                    Upstream("127.0.0.1", p1),
                    Upstream("127.0.0.1", p2),
                ),
                (
                    HttpDispatchRule(
                        1,
                        methods=frozenset(["GET"]),
                        path_prefix="/z",
                    ),
                ),
                strategy=LoadBalanceStrategy.ROUND_ROBIN,
                default_upstream_index=0,
            )
            cfg = GateConfig(
                listen=ListenConfig("127.0.0.1", 0, backlog=32),
                entrance=EntrancePlain(default_route="*"),
                routes={"*": route},
            )
            gate = HttpRoutingGateService(cfg)
            gt = asyncio.create_task(gate.start())
            gport = await wait_gate_port(gate)
            r, w = await asyncio.open_connection("127.0.0.1", gport)
            try:
                w.write(
                    b"GET /no-rule-here HTTP/1.1\r\n"
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
            assert b"only-default" in data
            await await_stop_and_background(gate.stop(), gt)
        finally:
            b1.close()
            b2.close()
            await b1.wait_closed()
            await b2.wait_closed()

    asyncio.run(main())
