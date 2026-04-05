from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, Optional

import n0va
from n0va.core.gate import GateService, HttpRoutingGateService
from n0va.handler.context import HttpResponse, RequestContext
from n0va.util.cert import Certificate, CertificateAuthority
from n0va.util.password import RandomPassword

from .db import CaRow, DashboardDB, IssuedCertRow, IssuedCertWithCaName
from .gate_builder import default_plain_gate_config, gate_config_from_dict
from .hosts_file import read_hosts, resolved_hosts_path, write_hosts
from .paths import resolve_startup_sqlite_path, storage_root


def _json_response(obj: Any, status: int = 200) -> HttpResponse:
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    return HttpResponse(
        status=status,
        body=body,
        content_type=b"application/json; charset=utf-8",
    )


def _parse_json(ctx: RequestContext) -> Any:
    raw = ctx.request.content
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def _parse_query(content: bytes) -> dict[str, str]:
    if not content:
        return {}
    q = content.decode("utf-8", "replace")
    return {k: v[0] for k, v in urllib.parse.parse_qs(q).items()}


def _query_bool(q: dict[str, str], key: str, default: bool = True) -> bool:
    raw = q.get(key)
    if raw is None or raw == "":
        return default
    s = str(raw).strip().lower()
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off"):
        return False
    return default


def _safe_file_label(s: str, max_len: int = 64) -> str:
    t = "".join(c if (c.isalnum() or c in "-._") else "_" for c in s.strip())
    return t[:max_len] or "cn"


def _ca_public_dict(row: CaRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "common_name": row.common_name,
        "organization": row.organization,
        "state": row.state,
        "locality": row.locality,
        "country": row.country,
        "ca_cert_path": row.ca_cert_path,
        "ca_key_path": row.ca_key_path,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "issued_count": row.issued_count,
    }


def _ca_detail_dict(row: CaRow) -> dict[str, Any]:
    d = _ca_public_dict(row)
    d["ca_passphrase"] = row.ca_passphrase
    return d


def _issued_with_ca_dict(row: IssuedCertWithCaName) -> dict[str, Any]:
    return {
        "id": row.id,
        "ca_id": row.ca_id,
        "ca_name": row.ca_name,
        "common_name": row.common_name,
        "cert_path": row.cert_path,
        "key_path": row.key_path,
        "created_at": row.created_at,
    }


def _issued_dict(row: IssuedCertRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "ca_id": row.ca_id,
        "common_name": row.common_name,
        "cert_path": row.cert_path,
        "key_path": row.key_path,
        "pfx_path": row.pfx_path,
        "serial_number": row.serial_number,
        "created_at": row.created_at,
    }


def _unlink_paths_under_issued_dir(ca_id: int, row: IssuedCertRow, storage: Path) -> None:
    """記録された PEM/PFX を `ca/<ca_id>/issued/` 配下に限り削除する。"""
    issued_root = (storage / "ca" / str(ca_id) / "issued").resolve()
    for rel in (row.cert_path, row.key_path, row.pfx_path):
        p = Path(rel)
        if not p.is_absolute():
            p = (issued_root / p).resolve()
        else:
            p = p.resolve()
        try:
            p.relative_to(issued_root)
        except ValueError:
            continue
        if p.is_file():
            try:
                p.unlink()
            except OSError:
                pass


class GateRuntime:
    def __init__(self) -> None:
        self._services: dict[int, HttpRoutingGateService] = {}
        self._tasks: dict[int, asyncio.Task[None]] = {}

    def is_running(self, gate_id: int) -> bool:
        return gate_id in self._services

    async def start(self, gate_id: int, svc: HttpRoutingGateService) -> None:
        if gate_id in self._services:
            raise RuntimeError("gate already running")

        async def _run() -> None:
            await svc.start()

        task = asyncio.create_task(_run())
        await asyncio.sleep(0.02)
        if task.done():
            exc = task.exception()
            if exc is not None:
                raise exc
        self._services[gate_id] = svc
        self._tasks[gate_id] = task

    async def stop(self, gate_id: int) -> None:
        svc = self._services.pop(gate_id, None)
        task = self._tasks.pop(gate_id, None)
        if svc is not None:
            await svc.stop()
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


class DashboardApp(n0va.Service):
    """
    ダッシュボード HTTP サーバー。`root_path` はフロントのビルド出力（例: `dashboard/frontend/dist`）。
    """

    def __init__(
        self,
        host: str,
        port: int,
        root_path: str,
        db_path: Optional[str] = None,
    ) -> None:
        super().__init__(host=host, port=port, root_path=root_path)
        env_root = Path(os.environ.get("N0VA_DASHBOARD_DATA", ".")).expanduser().resolve()
        self._db_path = (
            Path(db_path).expanduser().resolve()
            if db_path
            else resolve_startup_sqlite_path(env_root, None)
        )
        self._db = DashboardDB(self._db_path)
        self._migrate_legacy_ca_tree()
        self._gates = GateRuntime()
        for row in self._db.list_gates():
            if row.running:
                self._db.set_running(row.id, False)
        self._register_routes()

    async def __Start__(self) -> None:
        log = logging.getLogger("n0va.dashboard")
        log.info(
            "Listening on http://%s:%s (static: %s)",
            self._Host,
            self._Port,
            self.RootPath,
        )
        log.info("Database: %s", self._db_path.as_posix())
        log.info("Ctrl+C で停止します（親プロセスが子サーバーを終了します）。")
        try:
            await super().__Start__()
        finally:
            log.info("サーバーを停止しました。")

    def _data_dir_path(self) -> Path:
        st = self._db.get_ca_state()
        return Path(st["data_dir"] or ".").expanduser().resolve()

    def _storage_root(self) -> Path:
        """SQLite・CA など実体を置く隠しフォルダ（`<表示上のデータディレクトリ>/.n0va`）。"""
        p = storage_root(self._data_dir_path())
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _migrate_legacy_ca_tree(self) -> None:
        """旧レイアウト `<data_dir>/ca` を `<data_dir>/.n0va/ca` へ移す。"""
        visible = self._data_dir_path()
        sr = storage_root(visible)
        sr.mkdir(parents=True, exist_ok=True)
        old_ca = (visible / "ca").resolve()
        new_ca = (sr / "ca").resolve()
        if old_ca.is_dir() and not new_ca.exists():
            shutil.move(old_ca, new_ca)
            self._db.remap_stored_paths(str(old_ca), str(new_ca))

    def _register_routes(self) -> None:
        r = self.router
        r.register("GET", "/api/v1/health", self._api_health)
        r.register("GET", "/api/v1/gates", self._api_list_gates)
        r.register("POST", "/api/v1/gates", self._api_create_gate)
        r.register_regex("GET", r"/api/v1/gates/(\d+)", self._api_get_gate)
        r.register_regex("PUT", r"/api/v1/gates/(\d+)", self._api_update_gate)
        r.register_regex("DELETE", r"/api/v1/gates/(\d+)", self._api_delete_gate)
        r.register_regex("POST", r"/api/v1/gates/(\d+)/start", self._api_start_gate)
        r.register_regex("POST", r"/api/v1/gates/(\d+)/stop", self._api_stop_gate)

        r.register("GET", "/api/v1/cas", self._api_cas_list)
        r.register("POST", "/api/v1/cas", self._api_cas_create)
        r.register_regex("GET", r"/api/v1/cas/(\d+)", self._api_ca_get_one)
        r.register_regex("DELETE", r"/api/v1/cas/(\d+)", self._api_ca_delete)
        r.register_regex(
            "GET", r"/api/v1/cas/(\d+)/certificates", self._api_ca_certificates
        )
        r.register_regex(
            "DELETE",
            r"/api/v1/cas/(\d+)/certificates/(\d+)",
            self._api_delete_issued_cert,
        )
        r.register_regex("POST", r"/api/v1/cas/(\d+)/issue", self._api_ca_issue_for)
        r.register("GET", "/api/v1/issued-certificates", self._api_list_all_issued)
        r.register("POST", "/api/v1/settings/data-dir", self._api_set_data_dir)

        r.register("GET", "/api/v1/password/generate", self._api_password_generate)

        r.register("GET", "/api/v1/hosts", self._api_hosts_get)
        r.register("PUT", "/api/v1/hosts", self._api_hosts_put)

    async def serverFunctionHandler(self, connection, Request):  # noqa: N802
        log = logging.getLogger("n0va.dashboard.access")
        meth = Request.get("method", b"?")
        path = Request.get("path", b"")
        try:
            ms = meth.decode("ascii", "replace")
            ps = path.decode("utf-8", "replace")
            if len(ps) > 256:
                ps = ps[:256] + "…"
        except Exception:
            ms, ps = "?", "?"
        log.info("%s %s", ms, ps)
        await super().serverFunctionHandler(connection, Request)

    async def _api_health(self, ctx: RequestContext) -> HttpResponse:
        return _json_response({"ok": True, "db": self._db_path.as_posix()})

    async def _api_list_gates(self, ctx: RequestContext) -> HttpResponse:
        rows = self._db.list_gates()
        out = []
        for row in rows:
            cfg = json.loads(row.config_json)
            out.append(
                {
                    "id": row.id,
                    "name": row.name,
                    "config": cfg,
                    "running": bool(row.running) and self._gates.is_running(row.id),
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
            )
        return _json_response({"gates": out})

    async def _api_create_gate(self, ctx: RequestContext) -> HttpResponse:
        try:
            body = _parse_json(ctx) or {}
        except json.JSONDecodeError as e:
            return _json_response({"error": f"invalid json: {e}"}, status=400)
        name = str(body.get("name") or "gate")
        if "config" in body and isinstance(body["config"], dict):
            cfg = body["config"]
        else:
            cfg = default_plain_gate_config()
        try:
            gate_config_from_dict(cfg)
        except Exception as e:
            return _json_response({"error": str(e)}, status=400)
        gid = self._db.insert_gate(name, cfg)
        row = self._db.get_gate(gid)
        assert row is not None
        return _json_response(
            {
                "id": gid,
                "name": row.name,
                "config": json.loads(row.config_json),
                "running": False,
            },
            status=201,
        )

    async def _api_get_gate(self, ctx: RequestContext) -> HttpResponse:
        m = re.fullmatch(r"/api/v1/gates/(\d+)", ctx.request.path)
        if not m:
            return _json_response({"error": "not found"}, status=404)
        gid = int(m.group(1))
        row = self._db.get_gate(gid)
        if row is None:
            return _json_response({"error": "not found"}, status=404)
        cfg = json.loads(row.config_json)
        return _json_response(
            {
                "id": row.id,
                "name": row.name,
                "config": cfg,
                "running": bool(row.running) and self._gates.is_running(gid),
            }
        )

    async def _api_update_gate(self, ctx: RequestContext) -> HttpResponse:
        m = re.fullmatch(r"/api/v1/gates/(\d+)", ctx.request.path)
        if not m:
            return _json_response({"error": "not found"}, status=404)
        gid = int(m.group(1))
        if self._gates.is_running(gid):
            return _json_response(
                {"error": "stop the gate before editing"}, status=409
            )
        try:
            body = _parse_json(ctx) or {}
        except json.JSONDecodeError as e:
            return _json_response({"error": f"invalid json: {e}"}, status=400)
        row = self._db.get_gate(gid)
        if row is None:
            return _json_response({"error": "not found"}, status=404)
        name = str(body.get("name", row.name))
        cfg = body.get("config")
        if not isinstance(cfg, dict):
            return _json_response({"error": "config must be an object"}, status=400)
        try:
            gate_config_from_dict(cfg)
        except Exception as e:
            return _json_response({"error": str(e)}, status=400)
        self._db.update_gate(gid, name, cfg)
        new_row = self._db.get_gate(gid)
        assert new_row is not None
        return _json_response(
            {
                "id": new_row.id,
                "name": new_row.name,
                "config": json.loads(new_row.config_json),
                "running": False,
            }
        )

    async def _api_delete_gate(self, ctx: RequestContext) -> HttpResponse:
        m = re.fullmatch(r"/api/v1/gates/(\d+)", ctx.request.path)
        if not m:
            return _json_response({"error": "not found"}, status=404)
        gid = int(m.group(1))
        if self._gates.is_running(gid):
            await self._gates.stop(gid)
            self._db.set_running(gid, False)
        ok = self._db.delete_gate(gid)
        if not ok:
            return _json_response({"error": "not found"}, status=404)
        return _json_response({"ok": True})

    async def _api_start_gate(self, ctx: RequestContext) -> HttpResponse:
        m = re.fullmatch(r"/api/v1/gates/(\d+)/start", ctx.request.path)
        if not m:
            return _json_response({"error": "not found"}, status=404)
        gid = int(m.group(1))
        row = self._db.get_gate(gid)
        if row is None:
            return _json_response({"error": "not found"}, status=404)
        if self._gates.is_running(gid):
            return _json_response({"error": "already running"}, status=409)
        cfg_dict = json.loads(row.config_json)
        try:
            gcfg = gate_config_from_dict(cfg_dict)
            svc = HttpRoutingGateService(gcfg)
            await self._gates.start(gid, svc)
        except OSError as e:
            return _json_response({"error": str(e)}, status=500)
        except Exception as e:
            return _json_response({"error": str(e)}, status=400)
        self._db.set_running(gid, True)
        return _json_response({"ok": True, "id": gid, "running": True})

    async def _api_stop_gate(self, ctx: RequestContext) -> HttpResponse:
        m = re.fullmatch(r"/api/v1/gates/(\d+)/stop", ctx.request.path)
        if not m:
            return _json_response({"error": "not found"}, status=404)
        gid = int(m.group(1))
        if not self._gates.is_running(gid):
            self._db.set_running(gid, False)
            return _json_response({"ok": True, "id": gid, "running": False})
        await self._gates.stop(gid)
        self._db.set_running(gid, False)
        return _json_response({"ok": True, "id": gid, "running": False})

    async def _api_cas_list(self, ctx: RequestContext) -> HttpResponse:
        st = self._db.get_ca_state()
        rows = self._db.list_cas()
        return _json_response(
            {
                "data_dir": st["data_dir"],
                "cas": [_ca_public_dict(r) for r in rows],
            }
        )

    async def _api_cas_create(self, ctx: RequestContext) -> HttpResponse:
        try:
            body = _parse_json(ctx) or {}
        except json.JSONDecodeError as e:
            return _json_response({"error": f"invalid json: {e}"}, status=400)
        name = str(body.get("name") or "").strip()
        if not name:
            return _json_response({"error": "name is required"}, status=400)
        common_name = str(body.get("common_name") or "n0va-local-ca")
        ca_id = self._db.insert_ca_row(
            name=name,
            common_name=common_name,
            organization=str(body.get("organization") or ""),
            state=str(body.get("state") or ""),
            locality=str(body.get("locality") or ""),
            country=str(body.get("country") or ""),
            ca_passphrase=None,
        )
        base = self._storage_root()
        ca_dir = base / "ca" / str(ca_id)
        try:
            ca_dir.mkdir(parents=True, exist_ok=True)
            ca = CertificateAuthority()
            ca.CA_CommonName = common_name
            ca.CA_Organization = str(body.get("organization") or "")
            ca.CA_State = str(body.get("state") or "")
            ca.CA_Locality = str(body.get("locality") or "")
            ca.CA_Country = str(body.get("country") or "")
            # 開発用: CA 秘密鍵はパスフレーズなし（平文 PEM）。対話プロンプトを避ける。
            ca.CA_PrivatePassKey = ""
            ca.CA_SerialNumber = int(body.get("serial", 1))
            ca.CA_NotBefore = int(body.get("not_before", 0))
            ca.CA_NotAfter = int(body.get("not_after_sec", 30 * 365 * 24 * 60 * 60))
            ca.CA_CertPath_pem = (ca_dir / "ca.cert.pem").as_posix()
            ca.CA_PrivateKeyPath_pem = (ca_dir / "ca.private.pem").as_posix()
            ca.CA_PrivateKeyPath_der = (ca_dir / "ca.cert.der").as_posix()
            ca.ca_make()
            self._db.update_ca_paths(
                ca_id,
                ca_cert_path=ca.CA_CertPath_pem,
                ca_key_path=ca.CA_PrivateKeyPath_pem,
                ca_passphrase=None,
            )
        except Exception as e:
            shutil.rmtree(ca_dir, ignore_errors=True)
            self._db.delete_ca(ca_id)
            return _json_response({"error": str(e)}, status=500)
        row = self._db.get_ca(ca_id)
        assert row is not None
        return _json_response(_ca_detail_dict(row), status=201)

    async def _api_ca_get_one(self, ctx: RequestContext) -> HttpResponse:
        m = re.fullmatch(r"/api/v1/cas/(\d+)", ctx.request.path)
        if not m:
            return _json_response({"error": "not found"}, status=404)
        ca_id = int(m.group(1))
        row = self._db.get_ca(ca_id)
        if row is None or not row.ca_cert_path:
            return _json_response({"error": "not found"}, status=404)
        st = self._db.get_ca_state()
        d = _ca_detail_dict(row)
        d["data_dir"] = st["data_dir"]
        return _json_response(d)

    async def _api_ca_delete(self, ctx: RequestContext) -> HttpResponse:
        m = re.fullmatch(r"/api/v1/cas/(\d+)", ctx.request.path)
        if not m:
            return _json_response({"error": "not found"}, status=404)
        ca_id = int(m.group(1))
        row = self._db.get_ca(ca_id)
        if row is None:
            return _json_response({"error": "not found"}, status=404)
        ca_dir = self._storage_root() / "ca" / str(ca_id)
        if ca_dir.is_dir():
            shutil.rmtree(ca_dir, ignore_errors=True)
        self._db.delete_ca(ca_id)
        return _json_response({"ok": True, "id": ca_id})

    async def _api_ca_certificates(self, ctx: RequestContext) -> HttpResponse:
        m = re.fullmatch(r"/api/v1/cas/(\d+)/certificates", ctx.request.path)
        if not m:
            return _json_response({"error": "not found"}, status=404)
        ca_id = int(m.group(1))
        if self._db.get_ca(ca_id) is None:
            return _json_response({"error": "not found"}, status=404)
        rows = self._db.list_issued_for_ca(ca_id)
        return _json_response(
            {"ca_id": ca_id, "certificates": [_issued_dict(r) for r in rows]}
        )

    async def _api_delete_issued_cert(self, ctx: RequestContext) -> HttpResponse:
        m = re.fullmatch(r"/api/v1/cas/(\d+)/certificates/(\d+)", ctx.request.path)
        if not m:
            return _json_response({"error": "not found"}, status=404)
        ca_id = int(m.group(1))
        issued_id = int(m.group(2))
        if self._db.get_ca(ca_id) is None:
            return _json_response({"error": "not found"}, status=404)
        row = self._db.pop_issued_cert(ca_id, issued_id)
        if row is None:
            return _json_response({"error": "not found"}, status=404)
        _unlink_paths_under_issued_dir(ca_id, row, self._storage_root())
        return _json_response({"ok": True, "id": issued_id})

    async def _api_list_all_issued(self, ctx: RequestContext) -> HttpResponse:
        rows = self._db.list_all_issued_with_ca()
        return _json_response(
            {"certificates": [_issued_with_ca_dict(r) for r in rows]}
        )

    async def _api_ca_issue_for(self, ctx: RequestContext) -> HttpResponse:
        m = re.fullmatch(r"/api/v1/cas/(\d+)/issue", ctx.request.path)
        if not m:
            return _json_response({"error": "not found"}, status=404)
        ca_id = int(m.group(1))
        row = self._db.get_ca(ca_id)
        if row is None or not row.ca_cert_path:
            return _json_response({"error": "not found"}, status=404)
        try:
            body = _parse_json(ctx) or {}
        except json.JSONDecodeError as e:
            return _json_response({"error": f"invalid json: {e}"}, status=400)
        cn = str(body.get("common_name") or "localhost")
        issued_list = self._db.list_issued_for_ca(ca_id)
        next_serial = max((r.serial_number for r in issued_list), default=1) + 1
        serial = int(body.get("serial", next_serial))
        uid = uuid.uuid4().hex[:8]
        safe = _safe_file_label(cn)
        issued_dir = self._storage_root() / "ca" / str(ca_id) / "issued"
        issued_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{safe}_{uid}"
        cert = Certificate()
        cert.CA_CertPath_pem = row.ca_cert_path
        cert.CA_PrivateKeyPath_pem = row.ca_key_path
        cert.CA_PrivatePassKey = str(row.ca_passphrase or "")
        cert.commonName = cn
        cert.organization = str(body.get("organization") or "")
        cert.state = str(body.get("state") or "")
        cert.locality = str(body.get("locality") or "")
        cert.country = str(body.get("country") or "")
        cert.serialNumber = serial
        cert.notBefore = int(body.get("not_before", 0))
        cert.notAfter = int(body.get("not_after_sec", 365 * 24 * 60 * 60))
        cert.certPath = (issued_dir / f"{stem}.cert.pem").as_posix()
        cert.privateKeyPath = (issued_dir / f"{stem}.key.pem").as_posix()
        cert.pfxPath = (issued_dir / f"{stem}.pfx").as_posix()
        try:
            cert.c_make()
        except Exception as e:
            return _json_response({"error": str(e)}, status=500)
        iid = self._db.insert_issued_cert(
            ca_id=ca_id,
            common_name=cn,
            cert_path=cert.certPath,
            key_path=cert.privateKeyPath,
            pfx_path=cert.pfxPath,
            serial_number=serial,
        )
        return _json_response(
            {
                "ok": True,
                "id": iid,
                "cert": cert.certPath,
                "key": cert.privateKeyPath,
                "pfx": cert.pfxPath,
                "serial_number": serial,
            },
            status=201,
        )

    async def _api_set_data_dir(self, ctx: RequestContext) -> HttpResponse:
        try:
            body = _parse_json(ctx) or {}
        except json.JSONDecodeError as e:
            return _json_response({"error": f"invalid json: {e}"}, status=400)
        p = str(body.get("data_dir") or "").strip()
        if not p:
            return _json_response({"error": "data_dir required"}, status=400)
        new_visible = Path(p).expanduser().resolve()
        new_visible.mkdir(parents=True, exist_ok=True)
        old_visible = self._data_dir_path()
        if old_visible.resolve() == new_visible.resolve():
            return _json_response({"ok": True, "data_dir": new_visible.as_posix()})

        old_h = storage_root(old_visible)
        new_h = storage_root(new_visible)

        if old_h.exists():
            if new_h.exists():
                return _json_response(
                    {
                        "error": "Target data directory already contains .n0va; remove or merge it manually."
                    },
                    status=400,
                )
            shutil.move(old_h, new_h)
            self._db_path = new_h / "dashboard.sqlite3"
            self._db = DashboardDB(self._db_path)
            self._db.remap_stored_paths(
                str(old_h.resolve()),
                str(new_h.resolve()),
            )
        elif self._db_path.is_file():
            dest = new_h / "dashboard.sqlite3"
            new_h.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                return _json_response(
                    {"error": "Target already contains dashboard.sqlite3."},
                    status=400,
                )
            shutil.move(self._db_path, dest)
            self._db_path = dest
            self._db = DashboardDB(dest)

        self._db.set_ca_state(data_dir=new_visible.as_posix())
        return _json_response({"ok": True, "data_dir": new_visible.as_posix()})

    async def _api_password_generate(self, ctx: RequestContext) -> HttpResponse:
        q = _parse_query(ctx.request.content)
        style = (q.get("style") or "safari").lower()
        try:
            if style == "safari":
                pwd = RandomPassword.safari_style()
            elif style == "firefox":
                pwd = RandomPassword.firefox_style()
            elif style == "preset":
                preset = (q.get("preset") or "medium").lower()
                pwd = RandomPassword.from_preset(preset)
            elif style == "custom":
                length_raw = q.get("length")
                n = int(length_raw or 24)
                n = max(4, min(512, n))
                upper = _query_bool(q, "uppercase", True)
                lower = _query_bool(q, "lowercase", True)
                digits = _query_bool(q, "digits", True)
                symbols = _query_bool(q, "symbols", True)
                pwd = RandomPassword.generate(
                    n, upper=upper, lower=lower, digits=digits, symbols=symbols
                )
            else:
                return _json_response({"error": "unknown style"}, status=400)
        except ValueError as e:
            return _json_response({"error": str(e)}, status=400)
        return _json_response({"password": pwd, "style": style})

    async def _api_hosts_get(self, ctx: RequestContext) -> HttpResponse:
        path = resolved_hosts_path()
        info = await asyncio.to_thread(read_hosts, path)
        return _json_response(
            {
                "path": info.path,
                "content": info.content,
                "readable": info.readable,
                "read_error": info.read_error,
                "elevation_required_for_write": info.elevation_required_for_write,
            }
        )

    async def _api_hosts_put(self, ctx: RequestContext) -> HttpResponse:
        try:
            body = _parse_json(ctx) or {}
        except json.JSONDecodeError as e:
            return _json_response({"error": f"invalid json: {e}"}, status=400)
        content = body.get("content")
        if not isinstance(content, str):
            return _json_response({"error": "content must be a string"}, status=400)
        path = resolved_hosts_path()
        ok, err = await asyncio.to_thread(write_hosts, content, path)
        if ok:
            return _json_response({"ok": True, "path": path.as_posix()})
        return _json_response(
            {"ok": False, "error": err or "write failed"},
            status=500,
        )


def create_app(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    static_root: Optional[str] = None,
    db_path: Optional[str] = None,
) -> DashboardApp:
    root = static_root
    if root is None:
        root = (Path(__file__).resolve().parent / "frontend" / "dist").as_posix()
    return DashboardApp(host=host, port=port, root_path=root, db_path=db_path)
