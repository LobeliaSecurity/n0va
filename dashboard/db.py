from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


SCHEMA_VERSION = 3


def _utc_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """スキーマバージョンに応じてテーブルを追加・更新する。"""
    row = conn.execute(
        "SELECT value FROM meta WHERE key = 'schema_version'"
    ).fetchone()
    ver = int(row["value"]) if row else 0
    if ver >= SCHEMA_VERSION:
        return
    if ver < 3:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS content_servers (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              host TEXT NOT NULL DEFAULT '127.0.0.1',
              port INTEGER NOT NULL,
              root_path TEXT NOT NULL,
              auto_start INTEGER NOT NULL DEFAULT 0,
              running INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_content_servers_port
              ON content_servers(port);
            """
        )
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )


def _migrate_legacy_ca(conn: sqlite3.Connection) -> None:
    """単一 `ca_state` から複数 `cas` への一回限りの移行。"""
    row = conn.execute(
        "SELECT ca_cert_path, ca_key_path, ca_passphrase FROM ca_state WHERE id = 1"
    ).fetchone()
    if not row or not row["ca_cert_path"]:
        return
    n = conn.execute("SELECT COUNT(*) AS c FROM cas").fetchone()
    if n and n["c"] > 0:
        return
    now = _utc_iso()
    conn.execute(
        """
        INSERT INTO cas (
          name, common_name, organization, state, locality, country,
          ca_cert_path, ca_key_path, ca_passphrase, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "Migrated CA",
            "migrated",
            "",
            "",
            "",
            "",
            row["ca_cert_path"],
            row["ca_key_path"],
            row["ca_passphrase"],
            now,
            now,
        ),
    )
    conn.execute(
        "UPDATE ca_state SET ca_cert_path = NULL, ca_key_path = NULL, ca_passphrase = NULL WHERE id = 1"
    )


@dataclass
class GateRow:
    id: int
    name: str
    config_json: str
    running: int
    created_at: str
    updated_at: str


@dataclass
class CaRow:
    id: int
    name: str
    common_name: str
    organization: str
    state: str
    locality: str
    country: str
    ca_cert_path: str
    ca_key_path: str
    ca_passphrase: Optional[str]
    created_at: str
    updated_at: str
    issued_count: int = 0


@dataclass
class IssuedCertRow:
    id: int
    ca_id: int
    common_name: str
    cert_path: str
    key_path: str
    pfx_path: str
    serial_number: int
    created_at: str


@dataclass
class ContentServerRow:
    id: int
    name: str
    host: str
    port: int
    root_path: str
    auto_start: int
    running: int
    created_at: str
    updated_at: str


@dataclass
class IssuedCertWithCaName:
    """発行済み証明書 + 所属 CA 名（一覧・Gate 参照用）。"""

    id: int
    ca_id: int
    ca_name: str
    common_name: str
    cert_path: str
    key_path: str
    created_at: str


class DashboardDB:
    """SQLite 永続化（標準ライブラリ `sqlite3`）。"""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path.as_posix())
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS meta (
                      key TEXT PRIMARY KEY,
                      value TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS gates (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT NOT NULL,
                      config_json TEXT NOT NULL,
                      running INTEGER NOT NULL DEFAULT 0,
                      created_at TEXT NOT NULL,
                      updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS ca_state (
                      id INTEGER PRIMARY KEY CHECK (id = 1),
                      data_dir TEXT NOT NULL DEFAULT '.',
                      ca_cert_path TEXT,
                      ca_key_path TEXT,
                      ca_passphrase TEXT
                    );
                    """
                )
                conn.execute(
                    "INSERT OR IGNORE INTO ca_state (id, data_dir) VALUES (1, '.')"
                )
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS cas (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT NOT NULL,
                      common_name TEXT NOT NULL,
                      organization TEXT NOT NULL DEFAULT '',
                      state TEXT NOT NULL DEFAULT '',
                      locality TEXT NOT NULL DEFAULT '',
                      country TEXT NOT NULL DEFAULT '',
                      ca_cert_path TEXT NOT NULL,
                      ca_key_path TEXT NOT NULL,
                      ca_passphrase TEXT,
                      created_at TEXT NOT NULL,
                      updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS issued_certs (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      ca_id INTEGER NOT NULL,
                      common_name TEXT NOT NULL,
                      cert_path TEXT NOT NULL,
                      key_path TEXT NOT NULL,
                      pfx_path TEXT NOT NULL,
                      serial_number INTEGER NOT NULL DEFAULT 0,
                      created_at TEXT NOT NULL,
                      FOREIGN KEY (ca_id) REFERENCES cas(id) ON DELETE CASCADE
                    );
                    CREATE INDEX IF NOT EXISTS idx_issued_certs_ca_id ON issued_certs(ca_id);
                    """
                )
                _migrate_legacy_ca(conn)
                _migrate_schema(conn)
                conn.commit()
            finally:
                conn.close()

    def list_gates(self) -> list[GateRow]:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "SELECT id, name, config_json, running, created_at, updated_at FROM gates ORDER BY id"
                )
                return [
                    GateRow(
                        id=r["id"],
                        name=r["name"],
                        config_json=r["config_json"],
                        running=r["running"],
                        created_at=r["created_at"],
                        updated_at=r["updated_at"],
                    )
                    for r in cur.fetchall()
                ]
            finally:
                conn.close()

    def get_gate(self, gate_id: int) -> Optional[GateRow]:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "SELECT id, name, config_json, running, created_at, updated_at FROM gates WHERE id = ?",
                    (gate_id,),
                )
                r = cur.fetchone()
                if r is None:
                    return None
                return GateRow(
                    id=r["id"],
                    name=r["name"],
                    config_json=r["config_json"],
                    running=r["running"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
            finally:
                conn.close()

    def insert_gate(self, name: str, config: dict[str, Any]) -> int:
        now = _utc_iso()
        cfg = json.dumps(config, ensure_ascii=False)
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "INSERT INTO gates (name, config_json, running, created_at, updated_at) VALUES (?,?,0,?,?)",
                    (name, cfg, now, now),
                )
                conn.commit()
                return int(cur.lastrowid)
            finally:
                conn.close()

    def update_gate(self, gate_id: int, name: str, config: dict[str, Any]) -> bool:
        now = _utc_iso()
        cfg = json.dumps(config, ensure_ascii=False)
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "UPDATE gates SET name = ?, config_json = ?, updated_at = ? WHERE id = ?",
                    (name, cfg, now, gate_id),
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    def delete_gate(self, gate_id: int) -> bool:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute("DELETE FROM gates WHERE id = ?", (gate_id,))
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    def set_running(self, gate_id: int, running: bool) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE gates SET running = ?, updated_at = ? WHERE id = ?",
                    (1 if running else 0, _utc_iso(), gate_id),
                )
                conn.commit()
            finally:
                conn.close()

    def get_ca_state(self) -> dict[str, Any]:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "SELECT data_dir, ca_cert_path, ca_key_path, ca_passphrase FROM ca_state WHERE id = 1"
                )
                r = cur.fetchone()
                if r is None:
                    return {
                        "data_dir": ".",
                        "ca_cert_path": None,
                        "ca_key_path": None,
                        "ca_passphrase": None,
                    }
                return {
                    "data_dir": r["data_dir"],
                    "ca_cert_path": r["ca_cert_path"],
                    "ca_key_path": r["ca_key_path"],
                    "ca_passphrase": r["ca_passphrase"],
                }
            finally:
                conn.close()

    def set_ca_state(
        self,
        *,
        data_dir: Optional[str] = None,
        ca_cert_path: Optional[str] = None,
        ca_key_path: Optional[str] = None,
        ca_passphrase: Optional[str] = None,
    ) -> None:
        with self._lock:
            conn = self._connect()
            try:
                if data_dir is not None:
                    conn.execute(
                        "UPDATE ca_state SET data_dir = ? WHERE id = 1", (data_dir,)
                    )
                if ca_cert_path is not None:
                    conn.execute(
                        "UPDATE ca_state SET ca_cert_path = ? WHERE id = 1",
                        (ca_cert_path,),
                    )
                if ca_key_path is not None:
                    conn.execute(
                        "UPDATE ca_state SET ca_key_path = ? WHERE id = 1",
                        (ca_key_path,),
                    )
                if ca_passphrase is not None:
                    conn.execute(
                        "UPDATE ca_state SET ca_passphrase = ? WHERE id = 1",
                        (ca_passphrase,),
                    )
                conn.commit()
            finally:
                conn.close()

    def remap_stored_paths(self, old_prefix: str, new_prefix: str) -> None:
        """絶対パス列を old_prefix 配下から new_prefix 配下へ付け替える（データディレクトリ移動時）。"""
        old_root = Path(old_prefix).resolve()
        new_root = Path(new_prefix).resolve()

        def fix(p: Optional[str]) -> Optional[str]:
            if not p:
                return p
            try:
                rel = Path(p).resolve().relative_to(old_root)
                return str((new_root / rel).resolve())
            except ValueError:
                return p

        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT ca_cert_path, ca_key_path FROM ca_state WHERE id = 1"
                ).fetchone()
                if row is not None:
                    conn.execute(
                        "UPDATE ca_state SET ca_cert_path = ?, ca_key_path = ? WHERE id = 1",
                        (fix(row["ca_cert_path"]), fix(row["ca_key_path"])),
                    )
                for r in conn.execute("SELECT id, ca_cert_path, ca_key_path FROM cas"):
                    conn.execute(
                        "UPDATE cas SET ca_cert_path = ?, ca_key_path = ? WHERE id = ?",
                        (
                            fix(r["ca_cert_path"]) or "",
                            fix(r["ca_key_path"]) or "",
                            r["id"],
                        ),
                    )
                for r in conn.execute(
                    "SELECT id, cert_path, key_path, pfx_path FROM issued_certs"
                ):
                    conn.execute(
                        "UPDATE issued_certs SET cert_path = ?, key_path = ?, pfx_path = ? WHERE id = ?",
                        (
                            fix(r["cert_path"]) or "",
                            fix(r["key_path"]) or "",
                            fix(r["pfx_path"]) or "",
                            r["id"],
                        ),
                    )
                conn.commit()
            finally:
                conn.close()

    def list_cas(self) -> list[CaRow]:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    SELECT c.id, c.name, c.common_name, c.organization, c.state, c.locality, c.country,
                           c.ca_cert_path, c.ca_key_path, c.ca_passphrase, c.created_at, c.updated_at,
                           (SELECT COUNT(*) FROM issued_certs i WHERE i.ca_id = c.id) AS issued_count
                    FROM cas c
                    ORDER BY c.id
                    """
                )
                return [
                    CaRow(
                        id=r["id"],
                        name=r["name"],
                        common_name=r["common_name"],
                        organization=r["organization"],
                        state=r["state"],
                        locality=r["locality"],
                        country=r["country"],
                        ca_cert_path=r["ca_cert_path"],
                        ca_key_path=r["ca_key_path"],
                        ca_passphrase=r["ca_passphrase"],
                        created_at=r["created_at"],
                        updated_at=r["updated_at"],
                        issued_count=int(r["issued_count"]),
                    )
                    for r in cur.fetchall()
                ]
            finally:
                conn.close()

    def get_ca(self, ca_id: int) -> Optional[CaRow]:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    SELECT c.id, c.name, c.common_name, c.organization, c.state, c.locality, c.country,
                           c.ca_cert_path, c.ca_key_path, c.ca_passphrase, c.created_at, c.updated_at,
                           (SELECT COUNT(*) FROM issued_certs i WHERE i.ca_id = c.id) AS issued_count
                    FROM cas c WHERE c.id = ?
                    """,
                    (ca_id,),
                )
                r = cur.fetchone()
                if r is None:
                    return None
                return CaRow(
                    id=r["id"],
                    name=r["name"],
                    common_name=r["common_name"],
                    organization=r["organization"],
                    state=r["state"],
                    locality=r["locality"],
                    country=r["country"],
                    ca_cert_path=r["ca_cert_path"],
                    ca_key_path=r["ca_key_path"],
                    ca_passphrase=r["ca_passphrase"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    issued_count=int(r["issued_count"]),
                )
            finally:
                conn.close()

    def insert_ca_row(
        self,
        *,
        name: str,
        common_name: str,
        organization: str,
        state: str,
        locality: str,
        country: str,
        ca_passphrase: Optional[str],
    ) -> int:
        """パスは空で挿入し、ファイル作成後に `update_ca_paths` する。"""
        now = _utc_iso()
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    INSERT INTO cas (
                      name, common_name, organization, state, locality, country,
                      ca_cert_path, ca_key_path, ca_passphrase, created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        name,
                        common_name,
                        organization,
                        state,
                        locality,
                        country,
                        "",
                        "",
                        ca_passphrase,
                        now,
                        now,
                    ),
                )
                conn.commit()
                return int(cur.lastrowid)
            finally:
                conn.close()

    def update_ca_paths(
        self,
        ca_id: int,
        *,
        ca_cert_path: str,
        ca_key_path: str,
        ca_passphrase: Optional[str] = None,
    ) -> bool:
        now = _utc_iso()
        with self._lock:
            conn = self._connect()
            try:
                if ca_passphrase is not None:
                    cur = conn.execute(
                        """
                        UPDATE cas SET ca_cert_path = ?, ca_key_path = ?, ca_passphrase = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (ca_cert_path, ca_key_path, ca_passphrase, now, ca_id),
                    )
                else:
                    cur = conn.execute(
                        """
                        UPDATE cas SET ca_cert_path = ?, ca_key_path = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (ca_cert_path, ca_key_path, now, ca_id),
                    )
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    def delete_ca(self, ca_id: int) -> bool:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute("DELETE FROM cas WHERE id = ?", (ca_id,))
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    def list_all_issued_with_ca(self) -> list[IssuedCertWithCaName]:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    SELECT i.id, i.ca_id, c.name AS ca_name, i.common_name,
                           i.cert_path, i.key_path, i.created_at
                    FROM issued_certs i
                    JOIN cas c ON c.id = i.ca_id
                    ORDER BY i.id DESC
                    """
                )
                return [
                    IssuedCertWithCaName(
                        id=r["id"],
                        ca_id=r["ca_id"],
                        ca_name=r["ca_name"],
                        common_name=r["common_name"],
                        cert_path=r["cert_path"],
                        key_path=r["key_path"],
                        created_at=r["created_at"],
                    )
                    for r in cur.fetchall()
                ]
            finally:
                conn.close()

    def list_issued_for_ca(self, ca_id: int) -> list[IssuedCertRow]:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    SELECT id, ca_id, common_name, cert_path, key_path, pfx_path, serial_number, created_at
                    FROM issued_certs WHERE ca_id = ? ORDER BY id DESC
                    """,
                    (ca_id,),
                )
                return [
                    IssuedCertRow(
                        id=r["id"],
                        ca_id=r["ca_id"],
                        common_name=r["common_name"],
                        cert_path=r["cert_path"],
                        key_path=r["key_path"],
                        pfx_path=r["pfx_path"],
                        serial_number=r["serial_number"],
                        created_at=r["created_at"],
                    )
                    for r in cur.fetchall()
                ]
            finally:
                conn.close()

    def insert_issued_cert(
        self,
        *,
        ca_id: int,
        common_name: str,
        cert_path: str,
        key_path: str,
        pfx_path: str,
        serial_number: int,
    ) -> int:
        now = _utc_iso()
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    INSERT INTO issued_certs (
                      ca_id, common_name, cert_path, key_path, pfx_path, serial_number, created_at
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        ca_id,
                        common_name,
                        cert_path,
                        key_path,
                        pfx_path,
                        serial_number,
                        now,
                    ),
                )
                conn.commit()
                return int(cur.lastrowid)
            finally:
                conn.close()

    def pop_issued_cert(self, ca_id: int, issued_id: int) -> Optional[IssuedCertRow]:
        """該当 CA に属する発行済み行を 1 件削除し、削除前の行を返す。無ければ None。"""
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    SELECT id, ca_id, common_name, cert_path, key_path, pfx_path, serial_number, created_at
                    FROM issued_certs WHERE id = ? AND ca_id = ?
                    """,
                    (issued_id, ca_id),
                )
                r = cur.fetchone()
                if r is None:
                    return None
                row = IssuedCertRow(
                    id=r["id"],
                    ca_id=r["ca_id"],
                    common_name=r["common_name"],
                    cert_path=r["cert_path"],
                    key_path=r["key_path"],
                    pfx_path=r["pfx_path"],
                    serial_number=r["serial_number"],
                    created_at=r["created_at"],
                )
                conn.execute(
                    "DELETE FROM issued_certs WHERE id = ? AND ca_id = ?",
                    (issued_id, ca_id),
                )
                conn.commit()
                return row
            finally:
                conn.close()

    def list_content_servers(self) -> list[ContentServerRow]:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    SELECT id, name, host, port, root_path, auto_start, running, created_at, updated_at
                    FROM content_servers ORDER BY id
                    """
                )
                return [
                    ContentServerRow(
                        id=r["id"],
                        name=r["name"],
                        host=r["host"],
                        port=int(r["port"]),
                        root_path=r["root_path"],
                        auto_start=int(r["auto_start"]),
                        running=int(r["running"]),
                        created_at=r["created_at"],
                        updated_at=r["updated_at"],
                    )
                    for r in cur.fetchall()
                ]
            finally:
                conn.close()

    def get_content_server(self, server_id: int) -> Optional[ContentServerRow]:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    SELECT id, name, host, port, root_path, auto_start, running, created_at, updated_at
                    FROM content_servers WHERE id = ?
                    """,
                    (server_id,),
                )
                r = cur.fetchone()
                if r is None:
                    return None
                return ContentServerRow(
                    id=r["id"],
                    name=r["name"],
                    host=r["host"],
                    port=int(r["port"]),
                    root_path=r["root_path"],
                    auto_start=int(r["auto_start"]),
                    running=int(r["running"]),
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
            finally:
                conn.close()

    def insert_content_server(
        self,
        *,
        name: str,
        host: str,
        port: int,
        root_path: str,
        auto_start: bool,
    ) -> int:
        now = _utc_iso()
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    INSERT INTO content_servers (
                      name, host, port, root_path, auto_start, running, created_at, updated_at
                    ) VALUES (?,?,?,?,?,0,?,?)
                    """,
                    (
                        name,
                        host,
                        port,
                        root_path,
                        1 if auto_start else 0,
                        now,
                        now,
                    ),
                )
                conn.commit()
                return int(cur.lastrowid)
            finally:
                conn.close()

    def update_content_server(
        self,
        server_id: int,
        *,
        name: str,
        host: str,
        port: int,
        root_path: str,
        auto_start: bool,
    ) -> bool:
        now = _utc_iso()
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    UPDATE content_servers SET
                      name = ?, host = ?, port = ?, root_path = ?, auto_start = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        name,
                        host,
                        port,
                        root_path,
                        1 if auto_start else 0,
                        now,
                        server_id,
                    ),
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    def delete_content_server(self, server_id: int) -> bool:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "DELETE FROM content_servers WHERE id = ?", (server_id,)
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    def set_content_server_running(self, server_id: int, running: bool) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    UPDATE content_servers SET running = ?, updated_at = ? WHERE id = ?
                    """,
                    (1 if running else 0, _utc_iso(), server_id),
                )
                conn.commit()
            finally:
                conn.close()
