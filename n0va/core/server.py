import asyncio
import signal
import sys

import n0va.core.stream
from n0va.core.supervisor import is_worker_process


class AsyncTcp:
    def __init__(self, host, port):
        self._Host = host
        self._Port = port
        self._SSL_Context = None
        self._asyncio_server: asyncio.Server | None = None
        self._serving_loop: asyncio.AbstractEventLoop | None = None
        self._registered_stop_signals: list[int] = []
        self._stop_signal_fallback: bool = False

    # Need Override
    async def Handler():
        pass

    async def __InitHandler__(self, reader, writer):
        # Connection MUST be argment
        n0va.core.stream.StreamSocketOptions.apply_tcp_nodelay(writer)
        connection = n0va.core.stream.AsyncStream(reader, writer)
        await self.Handler(connection)

    def _install_stop_signal_handlers(self) -> None:
        """Ctrl+C 等で ``serve_forever`` がアイドルで詰まらないよう、ループ統合のシグナル登録を使う。

        ``signal.signal`` だけだとハンドラ内の ``call_soon_threadsafe`` が、次の I/O まで
        処理されない環境（Windows のコンソール＋ Selector 等）がある。
        ``add_signal_handler`` はイベントループと同じ経路でコールバックが走り、待機を抜けられる。

        監督プロセスの子ワーカーでは登録しない。停止は親が ``terminate`` / ``kill`` し、
        子が SIGINT で ``stop()`` すると二重処理や終了不能になることがある。
        """
        if is_worker_process():
            return
        self._registered_stop_signals = []
        self._stop_signal_fallback = False
        loop = self._serving_loop
        if loop is None:
            return

        def _schedule_stop() -> None:
            loop.create_task(self.stop())

        want: list[int] = [signal.SIGINT, signal.SIGTERM]
        if sys.platform == "win32" and hasattr(signal, "SIGBREAK"):
            want.append(signal.SIGBREAK)

        registered: list[int] = []
        for sig in want:
            try:
                loop.add_signal_handler(sig, _schedule_stop)
                registered.append(sig)
            except (NotImplementedError, RuntimeError, OSError):
                for s in registered:
                    try:
                        loop.remove_signal_handler(s)
                    except Exception:
                        pass
                registered.clear()
                break

        if registered:
            self._registered_stop_signals = registered
            self._stop_signal_fallback = False
            return

        self._stop_signal_fallback = True

        def _legacy(sig: int, frame: object | None) -> None:
            self.request_stop()

        signal.signal(signal.SIGINT, _legacy)
        if sys.platform == "win32" and hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, _legacy)
        try:
            signal.signal(signal.SIGTERM, _legacy)
        except (OSError, ValueError):
            pass

    def _remove_stop_signal_handlers(self) -> None:
        loop = self._serving_loop
        if self._stop_signal_fallback:
            try:
                signal.signal(signal.SIGINT, signal.SIG_DFL)
            except (OSError, ValueError):
                pass
            if sys.platform == "win32" and hasattr(signal, "SIGBREAK"):
                try:
                    signal.signal(signal.SIGBREAK, signal.SIG_DFL)
                except (OSError, ValueError):
                    pass
            try:
                signal.signal(signal.SIGTERM, signal.SIG_DFL)
            except (OSError, ValueError):
                pass
            self._stop_signal_fallback = False
            return
        if loop is not None:
            for sig in self._registered_stop_signals:
                try:
                    loop.remove_signal_handler(sig)
                except Exception:
                    pass
        self._registered_stop_signals.clear()

    async def __Start__(self) -> None:
        self._serving_loop = asyncio.get_running_loop()
        self._asyncio_server = await asyncio.start_server(
            self.__InitHandler__,
            self._Host,
            self._Port,
            ssl=self._SSL_Context,
            limit=256 * 1024,
            backlog=128,
        )
        self._install_stop_signal_handlers()
        try:
            async with self._asyncio_server:
                await self._asyncio_server.serve_forever()
        finally:
            self._remove_stop_signal_handlers()
            self._asyncio_server = None
            self._serving_loop = None

    async def stop(self) -> None:
        """リスンを閉じ、接続受け付けを止める。`__Start__` と同一イベントループ上のタスクから `await` する。"""
        srv = self._asyncio_server
        if srv is not None:
            srv.close()
            await srv.wait_closed()

    def request_stop(self) -> None:
        """
        `stop()` をイベントループにスケジュールする。別スレッド・シグナルハンドラからも呼べる。
        同一ループ上では `await stop()` を推奨。
        """
        loop = self._serving_loop
        if loop is None or not loop.is_running():
            return

        def _schedule() -> None:
            # 明示ループに束ねる（Windows 等で create_task の取り違いを避ける）
            loop.create_task(self.stop())

        loop.call_soon_threadsafe(_schedule)
