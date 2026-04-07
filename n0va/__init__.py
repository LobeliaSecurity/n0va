import asyncio
import ssl
import pathlib
import time
from collections.abc import Sequence

import n0va.handler.http as http
import n0va.core.gate as gate
from n0va.handler.context import HttpRequest, HttpResponse, RequestContext
from n0va.handler.router import Router
from n0va.handler.ws import WebSocketSession


class OnMemoryFile(pathlib.Path):
    """起動時に登録したパスをメモリに載せ、mtime 変化時のみ再読込（開発用の簡易配信）。"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.__data__ = None
        self.__previous_st_mtime__ = None
        if len(self.suffixes):
            self.mime = http.MediaTypes.shared()[self.suffixes[-1][1:]]

    @property
    def data(self):
        """
        ディスク上の `st_mtime` と前回読み込み時を比較し、変化時のみ再読込する。
        反映は HTTP リクエストごと（保存の瞬間にプッシュはしない）。
        起動後に追加されたファイルは `Service` のディスク再スキャンで `OnMemoryFiles` に載る。
        """
        st_mtime = self.stat().st_mtime
        if self.__data__ is not None and self.__previous_st_mtime__ == st_mtime:
            return self.__data__
        with self.open("rb") as f:
            self.__data__ = f.read()
        self.__previous_st_mtime__ = st_mtime
        return self.__data__


class Service(http.server):
    def __init__(
        self,
        host,
        port,
        root_path,
        *,
        dev_static_cache_control: bytes | None = b"no-store",
        dev_static_rescan_interval: float = 2.0,
    ):
        """
        `root_path` 以下のファイルは開発向けにメモリ登録され GET で配信される。
        本番の大規模静的配信・CDN は n0va 外の専用基盤を前提とする。
        `dev_static_cache_control`: その配信に付与する `Cache-Control`（`None` で省略）。
        `dev_static_rescan_interval`: 未登録パス時のディスク再 glob の最短間隔（秒）。`0` で毎回。
        """
        super().__init__(
            host=host, port=port, dev_static_cache_control=dev_static_cache_control
        )
        self.RootPath = root_path
        self.OnMemoryFiles = {}
        self._dev_static_rescan_at = 0.0
        self._dev_static_rescan_interval = dev_static_rescan_interval
        self.SetFilesOnMemory(root_path)

    def route(self, path: str, *, methods: Sequence[str]):
        """
        同一ハンドラを複数 HTTP メソッドに登録する。
        WebSocket は `onWebsocket` を使う。
        """

        def decorator(func):
            async def adapter(ctx: RequestContext):
                return await func(ctx)

            for m in methods:
                mu = m.upper()
                if mu == "WEBSOCKET":
                    raise ValueError(
                        "register WebSocket routes with onWebsocket(), not route()"
                    )
                self.router.register(mu, path, adapter)
            return func

        return decorator

    def onGet(self, path: str):
        return self.route(path, methods=("GET",))

    def onPost(self, path: str):
        return self.route(path, methods=("POST",))

    def onWebsocket(self, path: str):
        def decorator(func):
            async def adapter(session: WebSocketSession, ctx: RequestContext):
                return await func(session, ctx)

            self.router.register("WEBSOCKET", path, adapter)
            return func

        return decorator

    def SetFilesOnMemory(self, path):
        """`path` 配下のファイルを `OnMemoryFiles` に登録（開発用）。"""
        path_object = pathlib.Path(path).resolve()
        self.root_dir = path_object.as_posix()
        self.static_files_root = path_object
        for file_path in path_object.glob("**/*"):
            if file_path.is_file():
                self.OnMemoryFiles[
                    "/" + file_path.relative_to(path_object).as_posix()
                ] = OnMemoryFile(file_path)

    def _sync_dev_static_files(self, req_path: str) -> None:
        """
        リクエストパスが未登録のとき `root_path` を再 glob し、ディスク上のファイル集合と
        `OnMemoryFiles` を突き合わせる（新規追加・削除の双方）。
        """
        root = self.static_files_root
        if req_path in self.OnMemoryFiles:
            return
        base = req_path.split("?", 1)[0]
        leaf = base.rsplit("/", 1)[-1] if base else ""
        # 拡張子のないパスはアプリルートの可能性が高く、静的ファイル再スキャンはしない（404 を速くする）
        if leaf and "." not in leaf and base not in ("/", "/index.html"):
            return
        now = time.monotonic()
        if (
            self._dev_static_rescan_interval > 0
            and self._dev_static_rescan_at != 0.0
            and now - self._dev_static_rescan_at < self._dev_static_rescan_interval
        ):
            return
        self._dev_static_rescan_at = now
        present: set[str] = set()
        for file_path in root.glob("**/*"):
            if file_path.is_file():
                key = "/" + file_path.relative_to(root).as_posix()
                present.add(key)
                if key not in self.OnMemoryFiles:
                    self.OnMemoryFiles[key] = OnMemoryFile(file_path)
        for key in list(self.OnMemoryFiles.keys()):
            if key not in present:
                del self.OnMemoryFiles[key]

    def EnableSSL(self, domain_cert, private_key):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
        ctx.load_cert_chain(domain_cert, private_key)
        self._SSL_Context = ctx

    def Start(self, *, supervised: bool | None = None) -> None:
        """`asyncio.run` で `__Start__`（リスン）を実行。

        既定では :mod:`n0va.core.supervisor` により親プロセスが子を起動し、Ctrl+C は親が子を終了する。
        無効化は環境変数 ``N0VA_NO_SUPERVISE=1`` か ``supervised=False``。
        ``python -c`` のように再実行できない場合は自動的に同一プロセスのみで動く。
        """
        from n0va.core.supervisor import Supervisor

        if supervised is None:
            supervised = True
        if Supervisor.should_use_supervisor(supervised):
            raise SystemExit(Supervisor.spawn_and_supervise())
        asyncio.run(self.__Start__())
