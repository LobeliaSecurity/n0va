"""
HTTP/1.x リクエストごとにパス等で上流を選ぶゲート（基底 :class:`GateService` を汚染しない）。

keep-alive では同一 TCP に複数リクエストが載るため、先頭 1 本だけ選んで生転送すると
2 本目以降も誤った上流へ流れる。リクエスト単位で論理上流を選び、
:class:`UpstreamConnectionPool` で TCP を再利用しつつ 1 レスポンス境界まで転送する。

:class:`HttpRoutingGateService` は :meth:`~GateService._proxy_with_route` のみを上書きし、
:class:`HttpDispatchRoute` は :class:`Route` を継承してルールを保持する。
"""

from __future__ import annotations

from dataclasses import dataclass

import n0va.core.stream

from n0va.protocol.http1 import (
    Http1ParseError,
    Http1Request,
    Http1RequestParser,
    Http1ResponseParser,
)

from .config import GateConfig, LoadBalanceStrategy, Route, Upstream
from .service import GateService
from .upstream_pool import UpstreamConnectionPool


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
            # プレフィックスが要求長より短い（先頭 HTTP 再送など）。残りは内側ではなく短い読みで返す。
            if not self._prefix:
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
        p = (
            self.path_prefix
            if self.path_prefix.startswith("/")
            else "/" + self.path_prefix
        )
        # "/api/" と "/api" を同じプレフィックスに。p + "/" が "//" になって一致しなくなるのを防ぐ。
        while len(p) > 1 and p.endswith("/"):
            p = p[:-1]
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

    def __init__(
        self,
        config: GateConfig,
        *,
        upstream_pool_max_idle: int = 32,
        upstream_pool_idle_timeout: float = 90.0,
    ) -> None:
        super().__init__(config)
        self._upstream_pool_max_idle = upstream_pool_max_idle
        self._upstream_pool_idle_timeout = upstream_pool_idle_timeout
        self._upstream_pool = UpstreamConnectionPool(
            self._open_upstream,
            max_idle_per_key=upstream_pool_max_idle,
            idle_timeout=upstream_pool_idle_timeout,
        )

    async def start(self) -> None:
        try:
            await super().start()
        finally:
            await self._upstream_pool.aclose()

    async def apply_routing(self, config: GateConfig) -> None:
        await self._upstream_pool.aclose()
        self._upstream_pool = UpstreamConnectionPool(
            self._open_upstream,
            max_idle_per_key=self._upstream_pool_max_idle,
            idle_timeout=self._upstream_pool_idle_timeout,
        )
        await super().apply_routing(config)

    def _sni_callback(self, ssl_sock, server_name, ssl_ctx):
        """
        ブラウザは TLS で ``h2`` / ``http/1.1`` の ALPN を送る。入口 SSLContext に ALPN
        制約が無いと ``h2`` が選ばれ、ゲートは HTTP/1 テキストとして解釈できず
        応答を返さずに閉じる（Chrome: ERR_EMPTY_RESPONSE）。
        SNI で選んだ文脈に ``http/1.1`` のみを宣伝する。
        """
        super()._sni_callback(ssl_sock, server_name, ssl_ctx)
        ssl_sock.context.set_alpn_protocols(["http/1.1"])
        return None

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
        """
        クライアント側 keep-alive では 1 TCP に複数リクエストが載るため、リクエストごとに
        解析して上流を選ぶ。上流側はプール済み接続を再利用し、往復完了後に返却する。
        送受信が途切れた場合は接続を捨て、別接続で最大 1 回だけ再試行する。
        """
        max_req = route.max_header_bytes + route.max_body_bytes
        max_resp = route.max_header_bytes + route.max_body_bytes
        pending = b""
        if not entrance_connection.isOnline():
            return
        while entrance_connection.isOnline():
            buf = pending
            pending = b""
            parsed: Http1Request | None = None
            while True:
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
                try:
                    chunk = await entrance_connection.Recv()
                except Exception:
                    await entrance_connection.Close()
                    return
                if chunk == b"":
                    await entrance_connection.Close()
                    return
                buf += chunk
                if len(buf) > max_req:
                    await entrance_connection.Close()
                    return

            assert parsed is not None
            req_bytes = buf[: parsed.consumed]
            pending = buf[parsed.consumed :]
            if not req_bytes:
                await entrance_connection.Close()
                return

            idx = route.pick_upstream_index(parsed)
            upstream = route.upstreams[idx]
            if route.strategy == LoadBalanceStrategy.LEAST_CONN:
                self._lb[route_key][idx] += 1
            try:
                relay_ok = False
                for attempt in range(2):
                    try:
                        dest = await self._upstream_pool.acquire(upstream)
                    except Exception:
                        await entrance_connection.Close()
                        return

                    try:
                        await dest.Send(req_bytes)
                    except Exception as e:
                        await self._upstream_pool.release(upstream, dest, healthy=False)
                        if attempt == 0 and UpstreamConnectionPool.transient_error(e):
                            continue
                        await entrance_connection.Close()
                        return

                    resp_buf = b""
                    while True:
                        try:
                            parsed_resp = Http1ResponseParser.parse(
                                resp_buf,
                                request_method=parsed.method,
                                max_header_bytes=route.max_header_bytes,
                                max_body_bytes=route.max_body_bytes,
                            )
                        except Http1ParseError:
                            await self._upstream_pool.release(
                                upstream, dest, healthy=False
                            )
                            await entrance_connection.Close()
                            return
                        if parsed_resp is not None:
                            out = resp_buf[: parsed_resp.consumed]
                            try:
                                await entrance_connection.Send(out)
                            except Exception:
                                await self._upstream_pool.release(
                                    upstream, dest, healthy=False
                                )
                                await entrance_connection.Close()
                                return
                            await self._upstream_pool.release(
                                upstream, dest, healthy=True
                            )
                            relay_ok = True
                            break

                        try:
                            chunk = await dest.Recv()
                        except Exception as e:
                            await self._upstream_pool.release(
                                upstream, dest, healthy=False
                            )
                            if attempt == 0 and UpstreamConnectionPool.transient_error(e):
                                break
                            await entrance_connection.Close()
                            return
                        if chunk == b"":
                            await self._upstream_pool.release(
                                upstream, dest, healthy=False
                            )
                            if attempt == 0:
                                break
                            await entrance_connection.Close()
                            return
                        resp_buf += chunk
                        if len(resp_buf) > max_resp:
                            await self._upstream_pool.release(
                                upstream, dest, healthy=False
                            )
                            await entrance_connection.Close()
                            return

                    if relay_ok:
                        break

                if not relay_ok:
                    await entrance_connection.Close()
                    return
            finally:
                self._release_upstream(route_key, idx, route.strategy)
