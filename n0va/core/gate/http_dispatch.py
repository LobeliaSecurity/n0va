"""
HTTP/1.x の先頭リクエストを解析して上流を選ぶゲート（基底 :class:`GateService` を汚染しない）。

:class:`HttpRoutingGateService` は :meth:`~GateService._proxy_with_route` のみを上書きし、
:class:`HttpDispatchRoute` は :class:`Route` を継承してルールを保持する。
"""
from __future__ import annotations

from dataclasses import dataclass

import n0va.core.stream

from n0va.protocol.http1 import Http1ParseError, Http1Request, Http1RequestParser

from .config import LoadBalanceStrategy, Route, Upstream
from .service import GateService


class AsyncStreamPrefix:
    """
    先頭に未送信バイトを差し込むラッパ（1 バッファに複数メッセージがある場合や分割読取との整合用）。
    """

    __slots__ = ("_inner", "_prefix")

    def __init__(self, inner: n0va.core.stream.AsyncStream, prefix: bytes) -> None:
        self._inner = inner
        self._prefix = prefix

    async def Send(self, b: bytes) -> None:
        await self._inner.Send(b)

    async def Recv(self, i: int = 0, timeout: float = 0) -> bytes:
        if self._prefix:
            if i == 0:
                i = self._inner._Recvsize
            take = self._prefix[:i]
            self._prefix = self._prefix[i:]
            if len(take) >= i:
                return take
            rest = await self._inner.Recv(i - len(take), timeout)
            return take + rest
        return await self._inner.Recv(i, timeout)

    async def Close(self) -> None:
        await self._inner.Close()

    def isOnline(self) -> bool:
        return self._inner.isOnline()

    @property
    def _Writer(self):
        return self._inner._Writer

    @property
    def _Reader(self):
        return self._inner._Reader


@dataclass(frozen=True)
class HttpDispatchRule:
    """
    先頭から順に評価し、最初に一致した ``upstream_index`` を使う。

    ``path_exact`` / ``path_prefix`` がどちらも ``None`` のときはパス無条件（メソッドのみ制約）。
    """

    upstream_index: int
    methods: frozenset[str] | None = None
    path_exact: str | None = None
    path_prefix: str | None = None

    def matches(self, method_raw: bytes, path_only: str) -> bool:
        ms = method_raw.decode("ascii", "replace").upper()
        if self.methods is not None and ms not in self.methods:
            return False
        if self.path_exact is None and self.path_prefix is None:
            return True
        if self.path_exact is not None:
            return path_only == self.path_exact
        assert self.path_prefix is not None
        p = self.path_prefix if self.path_prefix.startswith("/") else "/" + self.path_prefix
        return path_only == p or path_only.startswith(p + "/")


class HttpDispatchRoute(Route):
    """
    複数 :class:`Upstream` と HTTP パス（等）ルールを持つ :class:`Route`。

    実際の上流選択は :class:`HttpRoutingGateService` が先頭リクエスト解析で行う。
    """

    def __init__(
        self,
        upstreams: tuple[Upstream, ...],
        rules: tuple[HttpDispatchRule, ...],
        *,
        strategy: LoadBalanceStrategy = LoadBalanceStrategy.LEAST_CONN,
        default_upstream_index: int = 0,
        max_header_bytes: int = 32 * 1024,
        max_body_bytes: int = 3 * 1024 * 1024,
    ) -> None:
        super().__init__(upstreams, strategy=strategy)
        if not (0 <= default_upstream_index < len(upstreams)):
            raise ValueError("default_upstream_index out of range")
        for r in rules:
            if r.upstream_index < 0 or r.upstream_index >= len(upstreams):
                raise ValueError(f"rule upstream_index {r.upstream_index} out of range")
        self.rules = rules
        self.default_upstream_index = default_upstream_index
        self.max_header_bytes = max_header_bytes
        self.max_body_bytes = max_body_bytes

    def pick_upstream_index(self, msg: Http1Request) -> int:
        for rule in self.rules:
            if rule.matches(msg.method, msg.path_only):
                return rule.upstream_index
        return self.default_upstream_index


class HttpRoutingGateService(GateService):
    """
    平文・SNI TLS 入口で、先頭 HTTP/1.x リクエストに基づき上流を選ぶゲート。

    ``EntranceTlsManual`` 経路は未対応（親の分岐のまま）。
    """

    async def _proxy_with_route(
        self,
        entrance_connection: n0va.core.stream.AsyncStream,
        route_key: str,
    ) -> None:
        route = self._config.routes[route_key]
        if isinstance(route, HttpDispatchRoute):
            await self._proxy_http_dispatch(entrance_connection, route_key, route)
        else:
            await super()._proxy_with_route(entrance_connection, route_key)

    async def _proxy_http_dispatch(
        self,
        entrance_connection: n0va.core.stream.AsyncStream,
        route_key: str,
        route: HttpDispatchRoute,
    ) -> None:
        buf = b""
        parsed: Http1Request | None = None
        while True:
            try:
                chunk = await entrance_connection.Recv()
            except Exception:
                await entrance_connection.Close()
                return
            if chunk == b"":
                await entrance_connection.Close()
                return
            buf += chunk
            try:
                parsed = Http1RequestParser.parse(
                    buf,
                    max_header_bytes=route.max_header_bytes,
                    max_body_bytes=route.max_body_bytes,
                )
            except Http1ParseError:
                await entrance_connection.Close()
                return
            if parsed is not None:
                break
            if len(buf) > route.max_header_bytes + route.max_body_bytes:
                await entrance_connection.Close()
                return

        assert parsed is not None
        idx = route.pick_upstream_index(parsed)
        upstream = route.upstreams[idx]
        try:
            reader, writer = await self._open_upstream(upstream)
        except Exception:
            await entrance_connection.Close()
            return
        n0va.core.stream.StreamSocketOptions.apply_tcp_nodelay(writer)
        destination_connection = n0va.core.stream.AsyncStream(reader, writer)
        remainder = buf[parsed.consumed :]
        wrapped = AsyncStreamPrefix(entrance_connection, remainder)
        try:
            await self._opengate(wrapped, destination_connection, route)
        finally:
            self._release_upstream(route_key, idx, route.strategy)
