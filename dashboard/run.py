"""
ダッシュボード起動: フロントのビルド出力を `root_path` として配信し、API を同一プロセスで提供する。

既定では :meth:`n0va.Service.Start` が親プロセスを監督し、子が HTTP サーバーを動かす。
Ctrl+C は親が子を終了する（``N0VA_NO_SUPERVISE=1`` で従来の単一プロセス）。

環境変数:
  N0VA_DASHBOARD_DATA  表示上のデータの基準ディレクトリ（既定: カレント）。実体は ``<基準>/.n0va/`` に ``dashboard.sqlite3`` と CA 等を置く。
  N0VA_NO_SUPERVISE     1 で親子プロセス監督を無効化
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

# ``python dashboard/run.py`` や監督プロセスのスクリプト直実行でも import できるようにする
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dashboard.service import create_app

_LOG = logging.getLogger("n0va.dashboard")


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

    _configure_logging()
    app = create_app()
    try:
        app.Start()
    except KeyboardInterrupt:
        _LOG.info("KeyboardInterrupt を受け取りました。終了します。")
        logging.shutdown()
        os._exit(0)


if __name__ == "__main__":
    main()
