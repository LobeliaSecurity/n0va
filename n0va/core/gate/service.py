from __future__ import annotations

import asyncio
import ssl
import n0va.core.stream

from .config import (
    EntrancePlain,
    EntranceTlsManual,
    EntranceTlsSni,
    GateConfig,
    LoadBalanceStrategy,
    Route,
    Upstream,
)


class GateService:
    """
    単一の TCP/TLS プロキシエンジン。`GateConfig` で入口モードと上流を宣言的に指定する。
    チャンクごとの処理は各 `Route` サブクラスのメソッドで定義する。
    """

    def __init__(self, config: GateConfig) -> None:
        config.validate()
        self._config = config
        self._generation = 0
        self._lock = asyncio.Lock()
        self._server: asyncio.Server | None = None
        self._serving_loop: asyncio.AbstractEventLoop | None = None
        self._accept_writers: set[asyncio.StreamWriter] = set()
        self._lb: dict[str, list[int]] = {}
        self._rr: dict[str, int] = {}
        self._rebuild_lb()

    @property
    def config(self) -> GateConfig:
        return self._config

    @property
    def config_generation(self) -> int:
        return self._generation

    def _rebuild_lb(self) -> None:
        self._lb = {k: [0] * len(v.upstreams) for k, v in self._config.routes.items()}
        self._rr = {k: 0 for k in self._config.routes}

    async def apply_routing(self, config: GateConfig) -> None:
        """ルーティングと入口定義を置き換える（新規接続から有効）。"""
        async with self._lock:
            config.validate()
            self._config = config
            self._generation += 1
            self._rebuild_lb()

    async def start(self) -> None:
        """リスンして `serve_forever` する（ブロックする）。"""
        self._serving_loop = asyncio.get_running_loop()
        lc = self._config.listen
        ent = self._config.entrance
        if isinstance(ent, EntrancePlain):
            self._server = await asyncio.start_server(
                self._on_plain_client,
                lc.host,
                lc.port,
                limit=lc.read_limit,
                backlog=lc.backlog,
            )
        elif isinstance(ent, EntranceTlsSni):
            ssl_ctx = self._make_sni_server_ssl_context()
            self._server = await asyncio.start_server(
                self._on_tls_sni_client,
                lc.host,
                lc.port,
                ssl=ssl_ctx,
                limit=lc.read_limit,
                backlog=lc.backlog,
            )
        elif isinstance(ent, EntranceTlsManual):
            self._server = await asyncio.start_server(
                self._on_tls_manual_client,
                lc.host,
                lc.port,
                limit=lc.read_limit,
                backlog=lc.backlog,
            )
        else:
            raise TypeError(type(ent))
        try:
            async with self._server:
                await self._server.serve_forever()
        finally:
            self._server = None
            self._serving_loop = None

    def _abort_accept_writers(self) -> None:
        """accept 済みクライアントを即切断。serve_forever キャンセル経路の wait_closed が進まないのを防ぐ。"""
        for w in list(self._accept_writers):
            try:
                t = w.transport
                if t is not None and not t.is_closing():
                    t.abort()
            except Exception:
                pass
        self._accept_writers.clear()

    async def stop(self) -> None:
        """`start` と同一イベントループ上のタスクから `await` してリスンを止める。"""
        self._abort_accept_writers()
        srv = self._server
        if srv is not None:
            srv.close()
            try:
                await asyncio.wait_for(srv.wait_closed(), timeout=12.0)
            except asyncio.TimeoutError:
                pass

    def request_stop(self) -> None:
        """
        `stop()` をイベントループにスケジュールする。別スレッド・シグナルハンドラからも呼べる。
        同一ループ上では `await stop()` を推奨。
        """
        loop = self._serving_loop
        if loop is None or not loop.is_running():
            return

        def _schedule() -> None:
            asyncio.get_running_loop().create_task(self.stop())

        loop.call_soon_threadsafe(_schedule)

    def _make_sni_server_ssl_context(self) -> ssl.SSLContext:
        ctx = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
        ctx.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
        ctx.sni_callback = self._sni_callback
        return ctx

    def _sni_callback(self, ssl_sock, server_name, ssl_ctx):
        """
        OpenSSL の SNI コールバック。失敗時は :exc:`ssl.SSLError` を投げる必要がある。
        ``ssl.ALERT_DESCRIPTION_*`` は整数であり例外ではない（``raise`` すると TypeError）。
        """
        cfg = self._config
        if not isinstance(cfg.entrance, EntranceTlsSni):
            raise ssl.SSLError("TLS entrance is not EntranceTlsSni")
        try:
            ssl_sock.context = cfg.entrance.sni_contexts[server_name]
        except KeyError as e:
            raise ssl.SSLError(f"unknown SNI hostname: {server_name!r}") from e
        return None

    def _pick_upstream(self, route_key: str) -> tuple[Upstream, int]:
        route = self._config.routes[route_key]
        n = len(route.upstreams)
        if route.strategy == LoadBalanceStrategy.LEAST_CONN:
            weights = self._lb[route_key]
            idx = min(range(n), key=lambda i: weights[i])
            weights[idx] += 1
            return route.upstreams[idx], idx
        idx = self._rr[route_key] % n
        self._rr[route_key] += 1
        return route.upstreams[idx], idx

    def _release_upstream(
        self, route_key: str, idx: int, strategy: LoadBalanceStrategy
    ) -> None:
        if strategy == LoadBalanceStrategy.LEAST_CONN:
            self._lb[route_key][idx] -= 1

    async def _open_upstream(self, upstream: Upstream):
        if upstream.tls is None:
            return await asyncio.open_connection(upstream.host, upstream.port)
        ctx = ssl.create_default_context()
        if upstream.tls.alpn:
            ctx.set_alpn_protocols(list(upstream.tls.alpn))
        return await asyncio.open_connection(
            upstream.host,
            upstream.port,
            ssl=ctx,
            server_hostname=upstream.tls.server_hostname,
        )

    async def _on_plain_client(self, reader, writer):
        n0va.core.stream.StreamSocketOptions.apply_tcp_nodelay(writer)
        self._accept_writers.add(writer)
        try:
            connection = n0va.core.stream.AsyncStream(reader, writer)
            route_key = self._config.entrance.default_route
            await self._proxy_with_route(connection, route_key)
        finally:
            self._accept_writers.discard(writer)

    async def _on_tls_sni_client(self, reader, writer):
        n0va.core.stream.StreamSocketOptions.apply_tcp_nodelay(writer)
        self._accept_writers.add(writer)
        try:
            connection = n0va.core.stream.AsyncStream(reader, writer)
            route_key = connection._Writer.get_extra_info("ssl_object").context.DomainName
            await self._proxy_with_route(connection, route_key)
        finally:
            self._accept_writers.discard(writer)

    async def _proxy_with_route(
        self,
        entrance_connection: n0va.core.stream.AsyncStream,
        route_key: str,
    ) -> None:
        route = self._config.routes[route_key]
        upstream, idx = self._pick_upstream(route_key)
        try:
            reader, writer = await self._open_upstream(upstream)
            n0va.core.stream.StreamSocketOptions.apply_tcp_nodelay(writer)
            destination_connection = n0va.core.stream.AsyncStream(reader, writer)
            await self._opengate(entrance_connection, destination_connection, route)
        finally:
            self._release_upstream(route_key, idx, route.strategy)

    async def _opengate(
        self,
        entrance_connection: n0va.core.stream.AsyncStream,
        destination_connection: n0va.core.stream.AsyncStream,
        route: Route,
    ) -> None:
        await asyncio.gather(
            self._entrance_handler(entrance_connection, destination_connection, route),
            self._transport_handler(destination_connection, entrance_connection, route),
        )

    async def _entrance_handler(
        self,
        entrance_connection: n0va.core.stream.AsyncStream,
        destination_connection: n0va.core.stream.AsyncStream,
        route: Route,
    ) -> None:
        try:
            while entrance_connection.isOnline():
                buf = await entrance_connection.Recv()
                out = await route.on_entrance_to_destination(
                    buf, entrance_connection, destination_connection
                )
                if buf == b"":
                    await entrance_connection.Close()
                    await destination_connection.Close()
                    break
                if out is not None:
                    await destination_connection.Send(out)
        except Exception:
            await entrance_connection.Close()
            await destination_connection.Close()

    async def _transport_handler(
        self,
        destination_connection: n0va.core.stream.AsyncStream,
        entrance_connection: n0va.core.stream.AsyncStream,
        route: Route,
    ) -> None:
        try:
            while destination_connection.isOnline():
                buf = await destination_connection.Recv()
                out = await route.on_destination_to_entrance(
                    buf, destination_connection, entrance_connection
                )
                if buf == b"":
                    await entrance_connection.Close()
                    await destination_connection.Close()
                    break
                if out is not None:
                    await entrance_connection.Send(out)
        except Exception:
            await entrance_connection.Close()
            await destination_connection.Close()

    async def _on_tls_manual_client(self, reader, writer):
        n0va.core.stream.StreamSocketOptions.apply_tcp_nodelay(writer)
        self._accept_writers.add(writer)
        try:
            entrance_connection = n0va.core.stream.AsyncManualSslStream(reader, writer)
            await entrance_connection.ReadClientHello()
            server_name = entrance_connection.serverName
            cfg = self._config
            if not isinstance(cfg.entrance, EntranceTlsManual):
                writer.close()
                return
            ctx_map = cfg.entrance.sni_contexts
            if server_name is None:
                server_name = next(iter(ctx_map.keys()))
            route = cfg.routes[server_name]
            upstream, minimum_index = self._pick_upstream(server_name)
            destination_connection = None
            try:
                if entrance_connection.isTryingHandshake:
                    if upstream.tls is not None:
                        dest_ctx = ssl.create_default_context()
                        if len(entrance_connection.ALPN) > 0:
                            dest_ctx.set_alpn_protocols(entrance_connection.ALPN)
                        dr, dw = await asyncio.open_connection(
                            upstream.host,
                            upstream.port,
                            ssl=dest_ctx,
                            server_hostname=upstream.tls.server_hostname,
                        )
                        n0va.core.stream.StreamSocketOptions.apply_tcp_nodelay(dw)
                        destination_connection = n0va.core.stream.AsyncStream(dr, dw)
                        selected_alpn = destination_connection._Writer.get_extra_info(
                            "ssl_object"
                        ).selected_alpn_protocol()
                        entrance_ssl_context = ctx_map[server_name]
                        if selected_alpn is not None:
                            entrance_ssl_context.set_alpn_protocols([selected_alpn])
                        entrance_connection.SslContext = entrance_ssl_context
                        await entrance_connection.Handshake()
                    else:
                        entrance_ssl_context = ctx_map[server_name]
                        entrance_connection.SslContext = entrance_ssl_context
                        await entrance_connection.Handshake()
                        dr, dw = await asyncio.open_connection(
                            upstream.host, upstream.port
                        )
                        n0va.core.stream.StreamSocketOptions.apply_tcp_nodelay(dw)
                        destination_connection = n0va.core.stream.AsyncStream(dr, dw)
                else:
                    if upstream.tls is not None:
                        dest_ctx = ssl.create_default_context()
                        dr, dw = await asyncio.open_connection(
                            upstream.host,
                            upstream.port,
                            ssl=dest_ctx,
                            server_hostname=upstream.tls.server_hostname,
                        )
                        n0va.core.stream.StreamSocketOptions.apply_tcp_nodelay(dw)
                        destination_connection = n0va.core.stream.AsyncStream(dr, dw)
                    else:
                        dr, dw = await asyncio.open_connection(
                            upstream.host, upstream.port
                        )
                        n0va.core.stream.StreamSocketOptions.apply_tcp_nodelay(dw)
                        destination_connection = n0va.core.stream.AsyncStream(dr, dw)
                    raw = await route.on_entrance_to_destination(
                        entrance_connection._client_hello_buf,
                        entrance_connection,
                        destination_connection,
                    )
                    if raw is not None:
                        await destination_connection.Send(raw)
                    entrance_connection = n0va.core.stream.AsyncStream(
                        entrance_connection._Reader, entrance_connection._Writer
                    )

                await self._opengate(entrance_connection, destination_connection, route)
            finally:
                self._release_upstream(server_name, minimum_index, route.strategy)
        finally:
            self._accept_writers.discard(writer)
