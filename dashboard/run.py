"""
ダッシュボード起動: フロントのビルド出力を `root_path` として配信し、API を同一プロセスで提供する。

既定では :meth:`n0va.Service.Start` が親プロセスを監督し、子が HTTP サーバーを動かす。
Ctrl+C は親が子を終了する（``N0VA_NO_SUPERVISE=1`` で従来の単一プロセス）。

環境変数:
  N0VA_DASHBOARD_DATA  表示上のデータの基準ディレクトリ（既定: カレント）。実体は ``<基準>/.n0va/`` に ``dashboard.sqlite3`` と CA 等を置く。
  N0VA_NO_SUPERVISE     1 で親子プロセス監督を無効化

コマンドライン:
  ``-p`` / ``--port``  待ち受けポート（既定: 8765）
  ``--host``            バインドアドレス（既定: 127.0.0.1）
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# ``python dashboard/run.py`` や監督プロセスのスクリプト直実行でも import できるようにする
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dashboard.service import create_app

_LOG = logging.getLogger("n0va.dashboard")


def _parse_tcp_port(s: str) -> int:
    try:
        n = int(s, 10)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"invalid port: {s!r}") from e
    if not (1 <= n <= 65535):
        raise argparse.ArgumentTypeError(f"port must be 1..65535, got {n}")
    return n


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="n0va ダッシュボード HTTP サーバー")
    p.add_argument(
        "-p",
        "--port",
        type=_parse_tcp_port,
        default=8765,
        metavar="PORT",
        help="待ち受け TCP ポート（既定: %(default)s）",
    )
    p.add_argument(
        "--host",
        default="127.0.0.1",
        metavar="ADDR",
        help="バインドするアドレス（既定: %(default)s）",
    )
    return p.parse_args(argv)


def _configure_logging() -> None:
    root = logging.getLogger()
    if not root.handlers:
        root.setLevel(logging.INFO)
        h = logging.StreamHandler(sys.stdout)
        h.setLevel(logging.INFO)
        h.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root.addHandler(h)
    else:
        root.setLevel(logging.INFO)


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    args = _parse_args()
    _configure_logging()
    app = create_app(host=args.host, port=args.port)
    try:
        app.Start()
    except KeyboardInterrupt:
        _LOG.info(
            "KeyboardInterrupt を受け取りました。静的配信を含めて終了処理に入ります。"
        )
        for _h in logging.root.handlers:
            try:
                _h.flush()
            except OSError:
                pass
        print(
            "KeyboardInterrupt: shutting down (including static content servers)…",
            file=sys.stderr,
            flush=True,
        )
    finally:
        try:
            app.shutdown_content_servers_sync()
        except Exception:
            pass
        logging.shutdown()


if __name__ == "__main__":
    main()
