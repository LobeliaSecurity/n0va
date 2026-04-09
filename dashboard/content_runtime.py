"""ダッシュボードと同一イベントループ上のローカル静的配信（Gate と同様に asyncio タスクで管理）。"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import n0va

from .db import ContentServerRow

_LOG = logging.getLogger("n0va.dashboard.content")


def _normalize_host(h: str) -> str:
    x = h.strip().lower()
    return "127.0.0.1" if x in ("localhost", "::1") else h.strip()


def bind_conflicts_dashboard(
    host: str, port: int, dash_host: str, dash_port: int
) -> bool:
    """ダッシュボード本体と同じ host:port で待ち受けないよう判定する。"""
    if port != dash_port:
        return False
    return _normalize_host(host) == _normalize_host(dash_host)


class ContentServerRuntime:
    """SQLite 行 ID ごとに :class:`n0va.Service` タスクを 1 つ紐づける（:class:`GateRuntime` と同型）。"""

    def __init__(self, dashboard_host: str, dashboard_port: int) -> None:
        self._dash_host = dashboard_host
        self._dash_port = dashboard_port
        self._services: dict[int, n0va.Service] = {}
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._stop_locks: dict[int, asyncio.Lock] = {}

    def _stop_lock(self, server_id: int) -> asyncio.Lock:
        lk = self._stop_locks.get(server_id)
        if lk is None:
            lk = asyncio.Lock()
            self._stop_locks[server_id] = lk
        return lk

    def set_dashboard_bind(self, host: str, port: int) -> None:
        self._dash_host = host
        self._dash_port = port

    def is_running(self, server_id: int) -> bool:
        return server_id in self._services

    async def start(self, server_id: int, row: ContentServerRow) -> None:
        if server_id in self._services:
            raise RuntimeError("already running")
        if bind_conflicts_dashboard(
            row.host, row.port, self._dash_host, self._dash_port
        ):
            raise OSError(
                "port conflicts with this dashboard; choose another port or host"
            )
        root = Path(row.root_path).expanduser().resolve()
        if not root.is_dir():
            raise OSError(f"document root is not a directory: {root}")
        # ダッシュボード本体がシグナルで止まる。追加リスナーはシグナル登録しない。
        svc = n0va.Service(
            row.host,
            row.port,
            root.as_posix(),
            install_stop_signal_handlers=False,
        )

        async def _run() -> None:
            await svc.__Start__()

        task = asyncio.create_task(_run())
        await asyncio.sleep(0.02)
        if task.done():
            exc = task.exception()
            if exc is not None:
                raise exc
        self._services[server_id] = svc
        self._tasks[server_id] = task

    async def stop(self, server_id: int) -> None:
        async with self._stop_lock(server_id):
            svc = self._services.get(server_id)
            task = self._tasks.get(server_id)
            if svc is None and task is None:
                return
            try:
                if svc is not None:
                    try:
                        await asyncio.wait_for(svc.stop(), timeout=20.0)
                    except asyncio.TimeoutError:
                        pass
                if task is not None and not task.done():
                    task.cancel()
                    try:
                        await asyncio.wait_for(task, timeout=15.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        pass
            finally:
                self._services.pop(server_id, None)
                self._tasks.pop(server_id, None)
                self._stop_locks.pop(server_id, None)

    async def shutdown_all(self) -> None:
        for sid in list(self._services.keys()):
            try:
                await self.stop(sid)
            except Exception as e:
                _LOG.warning("content server %s shutdown: %s", sid, e)
