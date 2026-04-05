"""データディレクトリ（設定画面のパス）直下の隠しフォルダに SQLite・CA 等をまとめる。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

# 画面上の「データディレクトリ」の直下に置く隠しディレクトリ名
HIDDEN_APP_DIR = ".n0va"


def storage_root(visible_data_dir: Path) -> Path:
    """ユーザーが設定する表示上のルート直下の実体保存先（`.n0va`）。"""
    return (visible_data_dir / HIDDEN_APP_DIR).resolve()


def sqlite_path(visible_data_dir: Path) -> Path:
    """SQLite ファイルの既定パス（`visible/.n0va/dashboard.sqlite3`）。"""
    return storage_root(visible_data_dir) / "dashboard.sqlite3"


def resolve_startup_sqlite_path(env_data_root: Path, explicit_db: Optional[str]) -> Path:
    """
    起動時の DB パス。`explicit_db` があればそれを使う。
    既定は `env_data_root/.n0va/dashboard.sqlite3`。
    旧 `env_data_root/dashboard.sqlite3` があれば隠しフォルダへ移す。
    """
    if explicit_db:
        p = Path(explicit_db).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    hidden = env_data_root / HIDDEN_APP_DIR
    target = hidden / "dashboard.sqlite3"
    legacy = env_data_root / "dashboard.sqlite3"
    hidden.mkdir(parents=True, exist_ok=True)
    if not target.exists() and legacy.is_file():
        shutil.move(legacy, target)
    return target
