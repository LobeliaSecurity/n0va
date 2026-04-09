"""
親プロセスが子プロセス上でサーバーを動かし、Ctrl+C / SIGTERM は親が ``terminate`` / ``kill`` する。

同一プロセス内の asyncio が待機中にシグナル処理が遅れる問題を、OS レベルの子終了で避ける。
子は可能なら新しいセッション／プロセスグループにし、コンソールの Ctrl+C が子に重複して届きにくくする。
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time


class Supervisor:
    """単一プロセス監督（親が子を起動し、シグナルで子を止める）。"""

    CHILD_ENV = "N0VA_SUPERVISED_CHILD"
    NO_SUPERVISE_ENV = "N0VA_NO_SUPERVISE"

    @staticmethod
    def is_worker_process() -> bool:
        return os.environ.get(Supervisor.CHILD_ENV) == "1"

    @staticmethod
    def _no_supervise_requested() -> bool:
        v = os.environ.get(Supervisor.NO_SUPERVISE_ENV, "").strip().lower()
        return v in ("1", "true", "yes", "on")

    @staticmethod
    def can_supervise_argv() -> bool:
        a0 = sys.argv[0]
        if a0 in ("", "-c"):
            return False
        try:
            return os.path.isfile(os.path.abspath(a0))
        except OSError:
            return False

    @staticmethod
    def _child_command() -> list[str]:
        """親と同じ起動形にする。``python -m pkg.mod`` で起動したとき子を ``run.py`` 直実行にすると
        パッケージ文脈が失われ相対インポートが壊れるため、利用可能なら :data:`sys.orig_argv` を使う。
        """
        if hasattr(sys, "orig_argv") and len(getattr(sys, "orig_argv", [])) >= 2:
            return [sys.executable] + list(sys.orig_argv[1:]) + sys.argv[1:]
        return [sys.executable, os.path.abspath(sys.argv[0])] + sys.argv[1:]

    @staticmethod
    def should_use_supervisor(supervised: bool | None) -> bool:
        if supervised is False:
            return False
        if Supervisor.is_worker_process():
            return False
        if Supervisor._no_supervise_requested():
            return False
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return False
        if not Supervisor.can_supervise_argv():
            return False
        return True

    @staticmethod
    def spawn_and_supervise() -> int:
        """``sys.executable`` と ``sys.argv`` を引き継いで子を起動し、終了コードを返す。"""
        env = os.environ.copy()
        env[Supervisor.CHILD_ENV] = "1"
        cmd = Supervisor._child_command()
        kwargs: dict[str, object] = {
            "env": env,
            "stdin": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        proc = subprocess.Popen(cmd, **kwargs)

        sig_hits = 0
        # 第 1 シグナルで graceful を送ったあと、これを過ぎても子が生きていれば terminate する。
        graceful_deadline: float | None = None

        def _graceful_child_stop() -> None:
            """子にだけ graceful 停止を試みる（Windows は CTRL+BREAK、Unix は SIGINT）。"""
            if proc.poll() is not None:
                return
            if sys.platform == "win32":
                # CREATE_NEW_PROCESS_GROUP の子はコンソールの Ctrl+C 対象外。
                # CTRL+BREAK を送ると子のシグナルハンドラ／KeyboardInterrupt の余地ができる。
                try:
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                except (OSError, ValueError, AttributeError):
                    proc.terminate()
                return
            try:
                proc.send_signal(signal.SIGINT)
            except (OSError, ValueError):
                proc.terminate()

        def _handle(sig: int, frame: object | None) -> None:
            nonlocal sig_hits, graceful_deadline
            sig_hits += 1
            if sig_hits == 1:
                _graceful_child_stop()
                graceful_deadline = time.monotonic() + 4.0
            else:
                proc.kill()

        old: dict[int, object] = {}
        old[signal.SIGINT] = signal.signal(signal.SIGINT, _handle)
        try:
            old[signal.SIGTERM] = signal.signal(signal.SIGTERM, _handle)
        except (OSError, ValueError):
            pass
        if sys.platform == "win32" and hasattr(signal, "SIGBREAK"):
            try:
                old[signal.SIGBREAK] = signal.signal(signal.SIGBREAK, _handle)
            except (OSError, ValueError):
                pass

        code = 1
        try:
            # Windows 等ではブロッキング wait() 中に Ctrl+C が処理されず親が固まることがある。
            # 短い timeout で待ちを挟み、シグナルハンドラが実行される隙を作る。
            while True:
                try:
                    code = proc.wait(timeout=0.3)
                    break
                except subprocess.TimeoutExpired:
                    if (
                        graceful_deadline is not None
                        and time.monotonic() >= graceful_deadline
                    ):
                        if proc.poll() is None:
                            proc.terminate()
                        graceful_deadline = None
                    continue
        finally:
            for sig, prev in old.items():
                try:
                    signal.signal(sig, prev)
                except (OSError, ValueError):
                    pass
            if proc.poll() is None:
                proc.kill()
                proc.wait()

        return int(code)
