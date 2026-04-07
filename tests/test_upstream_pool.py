"""n0va.core.gate.upstream_pool の単体・async テスト。"""

from __future__ import annotations

import asyncio

import pytest

from n0va.core.gate.config import Upstream, UpstreamTls
from n0va.core.gate.upstream_pool import UpstreamConnectionPool
from n0va.core.stream import AsyncStream


class _FakeWriter:
    def __init__(self) -> None:
        self._closing = False

    def write(self, data: bytes) -> None:
        pass

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        self._closing = True

    def is_closing(self) -> bool:
        return self._closing

    def get_extra_info(self, name: str):
        return None


class _FakeReader:
    async def read(self, n: int = -1) -> bytes:
        return b""


def test_upstream_pool_key_plain_vs_tls() -> None:
    a = Upstream("h", 80)
    b = Upstream("h", 80, tls=UpstreamTls("h", ("h2",)))
    assert UpstreamConnectionPool.key_for(a) != UpstreamConnectionPool.key_for(b)
    assert UpstreamConnectionPool.key_for(a) == UpstreamConnectionPool.key_for(
        Upstream("h", 80)
    )


def test_transient_upstream_error() -> None:
    assert UpstreamConnectionPool.transient_error(asyncio.CancelledError()) is False
    assert UpstreamConnectionPool.transient_error(BrokenPipeError()) is True
    assert UpstreamConnectionPool.transient_error(ConnectionResetError()) is True
    assert UpstreamConnectionPool.transient_error(
        asyncio.IncompleteReadError(b"", 1)
    ) is True
    assert UpstreamConnectionPool.transient_error(OSError(1, "x")) is True
    assert UpstreamConnectionPool.transient_error(ValueError()) is False


def test_pool_acquire_release_reuses_connection() -> None:
    opens = 0

    async def _run() -> None:
        nonlocal opens

        async def opener(u: Upstream):
            nonlocal opens
            opens += 1
            return _FakeReader(), _FakeWriter()

        pool = UpstreamConnectionPool(opener, max_idle_per_key=4, idle_timeout=3600.0)
        up = Upstream("127.0.0.1", 9)
        try:
            s1 = await pool.acquire(up)
            await pool.release(up, s1, healthy=True)
            s2 = await pool.acquire(up)
            assert opens == 1
            assert s1 is s2
            await pool.release(up, s2, healthy=True)
        finally:
            await pool.aclose()

    asyncio.run(_run())


def test_pool_release_unhealthy_closes() -> None:
    async def _run() -> None:
        async def opener(u: Upstream):
            return _FakeReader(), _FakeWriter()

        pool = UpstreamConnectionPool(opener)
        up = Upstream("127.0.0.1", 8)
        try:
            s = await pool.acquire(up)
            await pool.release(up, s, healthy=False)
            s2 = await pool.acquire(up)
            assert s2 is not s
            await pool.release(up, s2, healthy=True)
        finally:
            await pool.aclose()

    asyncio.run(_run())


def test_pool_acquire_after_close_raises() -> None:
    async def _run() -> None:
        async def opener(u: Upstream):
            return _FakeReader(), _FakeWriter()

        pool = UpstreamConnectionPool(opener)
        await pool.aclose()
        with pytest.raises(RuntimeError, match="closed"):
            await pool.acquire(Upstream("127.0.0.1", 7))

    asyncio.run(_run())
