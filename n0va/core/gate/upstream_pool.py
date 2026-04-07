"""
HTTP ディスパッチ用の上流 TCP/TLS 接続プール。

論理先（:class:`~n0va.core.gate.config.Upstream`）ごとにアイドル接続を保持し、
リクエスト完了後は閉じずに返却する。期限切れ・過剰アイドル・異常時のみ破棄する。
HTTP/1.1 は接続あたりインフライト 1 リクエスト（取得中は他タスクと共有しない）。
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Tuple

from n0va.core.stream import AsyncStream, StreamSocketOptions

from .config import Upstream


@dataclass
class _IdleEntry:
    stream: AsyncStream
    idle_since: float


class UpstreamConnectionPool:
    """
    :meth:`acquire` で取得したストリームは、成功時も失敗時も必ず :meth:`release` すること。

    ``healthy=False`` のときはソケットを閉じ、プールへ戻さない。
    """

    @staticmethod
    def key_for(upstream: Upstream) -> Tuple[Any, ...]:
        """プール分割用の安定キー（同一内容なら同一プール）。"""
        if upstream.tls is None:
            return (upstream.host, upstream.port, None)
        tls = upstream.tls
        alpn = tuple(tls.alpn) if tls.alpn else None
        return (upstream.host, upstream.port, (tls.server_hostname, alpn))

    @staticmethod
    def transient_error(exc: BaseException) -> bool:
        """上流との送受信で 1 回だけ新規接続に差し替えてよい種類のエラー。"""
        if isinstance(exc, asyncio.CancelledError):
            return False
        if isinstance(exc, (BrokenPipeError, ConnectionResetError, asyncio.IncompleteReadError)):
            return True
        if isinstance(exc, OSError):
            return True
        return False

    def __init__(
        self,
        open_upstream: Callable[[Upstream], Awaitable[tuple]],
        *,
        max_idle_per_key: int = 32,
        idle_timeout: float = 90.0,
    ) -> None:
        self._open_upstream = open_upstream
        self._max_idle = max_idle_per_key
        self._idle_timeout = idle_timeout
        self._idle: Dict[Tuple[Any, ...], List[_IdleEntry]] = defaultdict(list)
        self._locks: Dict[Tuple[Any, ...], asyncio.Lock] = defaultdict(asyncio.Lock)
        self._closed = False

    async def acquire(self, upstream: Upstream) -> AsyncStream:
        if self._closed:
            raise RuntimeError("UpstreamConnectionPool is closed")
        key = self.key_for(upstream)
        lock = self._locks[key]

        stale_to_close: List[AsyncStream] = []
        picked: AsyncStream | None = None

        async with lock:
            now = asyncio.get_running_loop().time()
            bucket = self._idle[key]
            kept: List[_IdleEntry] = []
            for ent in list(bucket):
                if now - ent.idle_since > self._idle_timeout:
                    stale_to_close.append(ent.stream)
                else:
                    kept.append(ent)
            self._idle[key] = kept
            work = self._idle[key]
            while work:
                ent = work.pop()
                if ent.stream.isOnline():
                    picked = ent.stream
                    break
                stale_to_close.append(ent.stream)

        for s in stale_to_close:
            await s.Close()
        if picked is not None:
            return picked

        reader, writer = await self._open_upstream(upstream)
        StreamSocketOptions.apply_tcp_nodelay(writer)
        return AsyncStream(reader, writer)

    async def release(
        self,
        upstream: Upstream,
        stream: AsyncStream,
        *,
        healthy: bool,
    ) -> None:
        if not healthy or self._closed or not stream.isOnline():
            await stream.Close()
            return
        key = self.key_for(upstream)
        lock = self._locks[key]
        async with lock:
            if self._closed:
                await stream.Close()
                return
            bucket = self._idle[key]
            if len(bucket) >= self._max_idle:
                await stream.Close()
                return
            bucket.append(
                _IdleEntry(stream, asyncio.get_running_loop().time())
            )

    async def aclose(self) -> None:
        self._closed = True
        for key in list(self._idle.keys()):
            bucket = self._idle.pop(key, [])
            for ent in bucket:
                await ent.stream.Close()
