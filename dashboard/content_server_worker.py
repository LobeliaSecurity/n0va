"""
単体起動用 CLI: n0va :class:`n0va.Service` によるローカル静的ファイル配信。

ダッシュボード組み込み時は同一プロセス内タスクで動かす（``dashboard.content_runtime``）。
このスクリプトは手動デバッグ・切り分け用。
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="n0va ローカル静的配信（単体 CLI）")
    p.add_argument("--host", default="127.0.0.1", help="バインドアドレス")
    p.add_argument("--port", type=int, required=True, metavar="PORT", help="待ち受けポート")
    p.add_argument(
        "--root",
        required=True,
        metavar="DIR",
        help="ドキュメントルート（ディレクトリの絶対パス）",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"content_server_worker: not a directory: {root}", file=sys.stderr)
        raise SystemExit(2)

    os.environ["N0VA_NO_SUPERVISE"] = "1"
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    import n0va

    svc = n0va.Service(args.host, args.port, root.as_posix())
    svc.Start(supervised=False)


if __name__ == "__main__":
    main()
