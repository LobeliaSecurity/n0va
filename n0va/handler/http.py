from __future__ import annotations

import n0va.core.stream
from n0va.core.server import AsyncTcp
from n0va.protocol.http1 import Http1ParseError, Http1RequestParser

from .context import HttpRequest, HttpResponse, RequestContext
from .router import Router
from .ws import WebSocketSession
from .ws_codec import WebSocketHandshake


class MediaTypes(dict):
    _shared: MediaTypes | None = None

    def __init__(self) -> None:
        super().__init__(
            {
                "txt": b"text/plain",
                "html": b"text/html",
                "css": b"text/css",
                "js": b"application/javascript",
                "jpg": b"image/jpg",
                "jpeg": b"image/jpeg",
                "png": b"image/png",
                "gif": b"image/gif",
                "ico": b"image/ico",
                "webm": b"video/webm",
                "mp4": b"video/mp4",
                "mp3": b"audio/mp3",
                "otf": b"application/x-font-otf",
                "woff": b"application/x-font-woff",
                "woff2": b"application/font-woff2",
                "ttf": b"application/x-font-ttf",
                "svg": b"image/svg+xml",
                "json": b"application/json",
                "md": b"text/markdown",
            }
        )

    @classmethod
    def shared(cls) -> MediaTypes:
        if cls._shared is None:
            cls._shared = cls()
        return cls._shared

    def __getitem__(self, key):
        if key in self:
            return super().__getitem__(key)
        else:
            return b"application/octet-stream"


class server(AsyncTcp):
    def __init__(
        self,
        host,
        port,
        *,
        dev_static_cache_control: bytes | None = b"no-store",
    ):
        """
        `dev_static_cache_control`: 組み込み静的ファイル配信（`OnMemoryFiles`）に付ける
        `Cache-Control`。ローカル開発ではブラウザキャッシュを避ける `no-store` が既定。
        本番向けの静的配信は別途（リバースプロキシ・オブジェクトストレージ等）を想定し、
        `None` で無効化もできる。
        """
        super().__init__(host=host, port=port)
        self.DefaultFile = "/index.html"
        self.router = Router()
        self.OnMemoryFiles = {}
        self.dev_static_cache_control = dev_static_cache_control
        self.MIME = MediaTypes.shared()
        self._Header = b"\r\n".join(
            (
                b"HTTP/1.1 %i",
                b"server: %b",
                b"Content-Length: %i",
                b"Connection: %b",
                b"Keep-Alive: %b",
                b"Content-Type: %b\r\n",
            )
        )
        self.ContentLengthLimit = 1024 * 1024 * 3
        self.MaxHeaderBytes = 32 * 1024

    @staticmethod
    def _normalize_request_target(target: bytes) -> bytes:
        """:meth:`n0va.protocol.http1.Http1RequestParser.normalize_request_target` への互換エイリアス。"""
        return Http1RequestParser.normalize_request_target(target)

    @staticmethod
    def _to_http_request(d: dict) -> HttpRequest:
        method = d["method"]
        raw_path = d["path"]
        skip = {"method", "path", "content"}
        headers: dict[str, bytes] = {}
        for k, v in d.items():
            if k in skip:
                continue
            if isinstance(k, str):
                headers[k.lower()] = v if isinstance(v, bytes) else str(v).encode()
        if b"?" in raw_path:
            path_part, qs = raw_path.split(b"?", 1)
            path_str = path_part.decode("utf-8")
            content = qs
        else:
            path_str = raw_path.decode("utf-8")
            content = d.get("content", b"")
        method_str = method.decode("ascii", "replace").upper()
        return HttpRequest(
            method=method,
            method_str=method_str,
            path=path_str,
            raw_path=raw_path,
            headers=headers,
            content=content,
        )

    async def send_http_response(
        self, connection: n0va.core.stream.AsyncStream, response: HttpResponse
    ) -> None:
        rc = response.body
        parts = [
            self._Header
            % (
                response.status,
                response.server,
                len(rc),
                response.connection,
                response.keep_alive,
                response.content_type,
            )
        ]
        if response.cache_control is not None:
            parts.append(b"Cache-Control: ")
            parts.append(response.cache_control)
            parts.append(b"\r\n")
        for line in response.additional_header_lines:
            parts.append(line)
            parts.append(b"\r\n")
        parts.append(b"\r\n")
        parts.append(rc)
        await connection.Send(b"".join(parts))

    async def serverFunctionHandler(self, connection, Request):
        m = Request["method"]
        if m == b"GET":
            await self.Get(connection, Request)
        elif m == b"WebSocket":
            await self.WebSocket(connection, Request)
        else:
            await self.dispatch_http_handler(connection, Request)

    async def GetFunctionHandler(
        self, connection, Request, ctx: RequestContext
    ) -> None:
        await self._invoke_registered_http(connection, ctx)

    async def _invoke_registered_http(self, connection, ctx: RequestContext) -> bool:
        handler = self.router.get(ctx.request.method_str, ctx.request.path)
        if handler is None:
            return False
        resp = await handler(ctx)
        if resp is not None:
            await self.send_http_response(connection, resp)
        return True

    async def dispatch_http_handler(self, connection, Request) -> None:
        ctx = RequestContext(self._to_http_request(Request), connection, self)
        if not await self._invoke_registered_http(connection, ctx):
            await self._reply_code(connection, 404)

    def _sync_dev_static_files(self, req_path: str) -> None:
        """サブクラスが `OnMemoryFiles` をディスクと同期する（開発用のフック）。"""
        pass

    def _take_static_if_present(self, url_path: str):
        """
        `url_path` が `OnMemoryFiles` にあり実ファイルが残っていれば `OnMemoryFile` を返す。
        ディスク上に無ければインデックスから削除して `None`。
        """
        if url_path not in self.OnMemoryFiles:
            return None
        of = self.OnMemoryFiles[url_path]
        if not of.exists():
            del self.OnMemoryFiles[url_path]
            return None
        return of

    @staticmethod
    def _path_route_str(raw_target: bytes) -> str:
        """request-target からクエリを除いたパス（ルータキー用）。"""
        path_part = raw_target.split(b"?", 1)[0]
        return path_part.decode("utf-8", "replace") or "/"

    async def Get(self, connection, Request):
        raw = Request["path"]
        # ルータに登録されたパスを、/ → index.html 寄せより優先する
        route_key = self._path_route_str(raw)
        if self.router.get("GET", route_key) is not None:
            if b"?" in raw:
                path_bytes, qs = raw.split(b"?", 1)
                Request["path"] = path_bytes
                Request.update({"content": qs})
            else:
                Request.update({"content": b""})
            ctx = RequestContext(self._to_http_request(Request), connection, self)
            await self.GetFunctionHandler(connection, Request, ctx)
            return

        if Request["path"] == b"/":
            Request["path"] = self.DefaultFile.encode("utf-8")
        elif len(Request["path"]) >= 2 and Request["path"][:2] == b"/?":
            Request["path"] = self.DefaultFile.encode("utf-8") + Request["path"][1:]
        ReqPath = Request["path"].decode("utf-8")
        path_route = ReqPath.split("?", 1)[0] if "?" in ReqPath else ReqPath

        if self.router.get("GET", path_route) is not None:
            if "?" in ReqPath:
                data = Request["path"].split(b"?", 1)
                Request["path"] = data[0]
                Request.update({"content": data[1] if len(data) > 1 else b""})
            else:
                Request.update({"content": b""})
            ctx = RequestContext(self._to_http_request(Request), connection, self)
            await self.GetFunctionHandler(connection, Request, ctx)
            return

        self._sync_dev_static_files(path_route)

        of = self._take_static_if_present(path_route)
        if of is not None:
            if "?" in ReqPath:
                data = Request["path"].split(b"?", 1)
                Request["path"] = data[0]
                Request.update({"content": data[1] if len(data) > 1 else b""})
            else:
                Request.update({"content": b""})
            await self.send_http_response(
                connection,
                HttpResponse(
                    status=200,
                    body=of.data,
                    content_type=of.mime,
                    cache_control=self.dev_static_cache_control,
                ),
            )
            return

        await self._reply_code(connection, 404)

    async def _reply_code(self, connection, code: int) -> None:
        await self.send_http_response(
            connection,
            HttpResponse(
                status=code,
                body=b"%i" % code,
                content_type=b"text/html",
            ),
        )

    async def WebSocket(self, connection, Request):
        accept = WebSocketHandshake.sec_websocket_accept(Request["Sec-WebSocket-Key"])
        await connection.Send(
            b"".join(
                (
                    b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ",
                    accept,
                    b"\r\n\r\n",
                )
            )
        )
        ctx = RequestContext(self._to_http_request(Request), connection, self)
        handler = self.router.get("WEBSOCKET", ctx.request.path)
        session = WebSocketSession(connection, ctx.state)
        if handler is not None:
            await handler(session, ctx)

    async def Handler(self, connection):
        try:
            pending = b""
            while not connection._Writer.is_closing():
                buf = pending
                pending = b""
                while True:
                    try:
                        req = Http1RequestParser.parse(
                            buf,
                            max_header_bytes=self.MaxHeaderBytes,
                            max_body_bytes=self.ContentLengthLimit,
                        )
                    except Http1ParseError:
                        await connection.Close()
                        return
                    if req is not None:
                        break
                    chunk = await connection.Recv()
                    if len(chunk) == 0:
                        await connection.Close()
                        return
                    buf += chunk
                    if len(buf) > self.MaxHeaderBytes + self.ContentLengthLimit:
                        await connection.Close()
                        return
                Request = Http1RequestParser.to_server_request_dict(req)
                if "Upgrade" in Request and Request.get("Upgrade") == b"websocket":
                    Request["method"] = b"WebSocket"
                pending = buf[req.consumed :]
                await self.serverFunctionHandler(connection, Request)
        except Exception as e:
            await connection.Close()
            raise e
