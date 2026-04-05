"""
OS の hosts ファイルを読み取り、更新時は管理者昇格（Windows: UAC）で反映する。

ベストプラクティス:
- 常時管理者でサーバーを動かさない
- ユーザーが明示的に「保存」したときだけ昇格プロセスを起動し UAC を表示
- 昇格側はコピー 1 操作に限定（本文を一時ファイルに書いてから置換）
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple


MAX_HOSTS_BYTES = 512 * 1024


class HostsInfo(NamedTuple):
    path: str
    content: str
    readable: bool
    read_error: str | None
    """書き込みに管理者が必要か（ヒント用）。"""
    elevation_required_for_write: bool


def default_hosts_path() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        return root / "System32" / "drivers" / "etc" / "hosts"
    return Path("/etc/hosts")


def resolved_hosts_path() -> Path:
    """環境変数 `N0VA_HOSTS_PATH` があればそれを使用（サーバー起動前に設定）。"""
    env = os.environ.get("N0VA_HOSTS_PATH", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return default_hosts_path()


def read_hosts(path: Path | None = None) -> HostsInfo:
    p = path if path is not None else resolved_hosts_path()
    try:
        raw = p.read_bytes()
        if len(raw) > MAX_HOSTS_BYTES:
            return HostsInfo(
                path=p.as_posix(),
                content="",
                readable=False,
                read_error="hosts ファイルが大きすぎます",
                elevation_required_for_write=False,
            )
        text = raw.decode("utf-8", errors="replace")
        need_elev = sys.platform == "win32" or (
            sys.platform != "win32" and hasattr(os, "geteuid") and os.geteuid() != 0
        )
        return HostsInfo(
            path=p.as_posix(),
            content=text,
            readable=True,
            read_error=None,
            elevation_required_for_write=need_elev,
        )
    except OSError as e:
        need_elev = sys.platform == "win32" or (
            sys.platform != "win32" and hasattr(os, "geteuid") and os.geteuid() != 0
        )
        return HostsInfo(
            path=p.as_posix(),
            content="",
            readable=False,
            read_error=str(e),
            elevation_required_for_write=need_elev,
        )


def _write_direct(path: Path, content: str) -> None:
    data = content.encode("utf-8")
    if len(data) > MAX_HOSTS_BYTES:
        raise ValueError("content too large")
    path.write_bytes(data)


def _ps_single_quoted_literal(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def write_hosts_windows_uac(content: str, dest: Path) -> tuple[bool, str | None]:
    """
    一時ファイルへ保存し、昇格 PowerShell が `Copy-Item` のみ実行（UAC は保存操作時のみ）。
    """
    data = content.encode("utf-8")
    if len(data) > MAX_HOSTS_BYTES:
        return False, "content too large"

    tmp: Path | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix="n0va_hosts_", suffix=".txt")
        os.close(fd)
        tmp = Path(tmp_name)
        tmp.write_bytes(data)

        src = str(tmp.resolve())
        dst = str(dest.resolve())

        inner = (
            f"$ErrorActionPreference='Stop'; "
            f"Copy-Item -LiteralPath {_ps_single_quoted_literal(src)} "
            f"-Destination {_ps_single_quoted_literal(dst)} -Force"
        )
        enc = base64.b64encode(inner.encode("utf-16-le")).decode("ascii")

        outer = (
            "$p = Start-Process -FilePath powershell.exe -Verb RunAs -Wait -PassThru "
            f"-ArgumentList '-NoProfile','-EncodedCommand','{enc}'; "
            "if ($null -eq $p) { exit 1 }; "
            "exit $p.ExitCode"
        )
        proc = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                outer,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        if proc.returncode == 0:
            return True, None
        err_parts = [proc.stdout or "", proc.stderr or ""]
        msg = "".join(err_parts).strip() or f"exit code {proc.returncode}"
        return False, msg
    except subprocess.TimeoutExpired:
        return False, "timeout waiting for elevated process"
    except OSError as e:
        return False, str(e)
    finally:
        if tmp is not None and tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def write_hosts_posix(content: str, dest: Path) -> tuple[bool, str | None]:
    """直接書き込み可能ならそのまま。不可なら `sudo -n` の非対話 cp を試す。"""
    try:
        _write_direct(dest, content)
        return True, None
    except PermissionError:
        pass
    except OSError as e:
        return False, str(e)

    fd, tmp_name = tempfile.mkstemp(prefix="n0va_hosts_", suffix=".txt")
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        tmp.write_bytes(content.encode("utf-8"))
        r = subprocess.run(
            ["sudo", "-n", "cp", str(tmp.resolve()), str(dest.resolve())],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode == 0:
            return True, None
        return (
            False,
            "/etc/hosts への書き込みには管理者権限が必要です。"
            "ターミナルで `sudo` 付きでダッシュボードを起動するか、手動で反映してください。"
            f" ({r.stderr or r.stdout or 'sudo -n failed'})",
        )
    except FileNotFoundError:
        return (
            False,
            "sudo が見つかりません。/etc/hosts を手動で編集してください。",
        )
    except subprocess.TimeoutExpired:
        return False, "timeout"
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def write_hosts(content: str, path: Path | None = None) -> tuple[bool, str | None]:
    """プラットフォームに応じて hosts を更新。"""
    dest = path or resolved_hosts_path()
    if sys.platform == "win32":
        return write_hosts_windows_uac(content, dest)
    return write_hosts_posix(content, dest)
