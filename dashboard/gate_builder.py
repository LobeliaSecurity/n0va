from __future__ import annotations

from typing import Any, Mapping

from n0va.core.gate import (
    EntrancePlain,
    EntranceTlsSni,
    GateConfig,
    HttpDispatchRoute,
    HttpDispatchRule,
    ListenConfig,
    LoadBalanceStrategy,
    Route,
    Upstream,
    UpstreamTls,
)
from n0va.util.cert import load_server_ssl_context


def _strategy(s: str) -> LoadBalanceStrategy:
    key = (s or "least_conn").strip().lower()
    if key == "round_robin":
        return LoadBalanceStrategy.ROUND_ROBIN
    return LoadBalanceStrategy.LEAST_CONN


def _upstream(u: Mapping[str, Any]) -> Upstream:
    tls = u.get("tls")
    utls = None
    if isinstance(tls, dict):
        utls = UpstreamTls(
            server_hostname=str(tls["server_hostname"]),
            alpn=tuple(tls["alpn"]) if tls.get("alpn") else None,
        )
    return Upstream(
        host=str(u["host"]),
        port=int(u["port"]),
        tls=utls,
    )


def _http_dispatch_rule(r: Mapping[str, Any]) -> HttpDispatchRule:
    idx = int(r["upstream_index"])
    methods_raw = r.get("methods")
    if methods_raw is None:
        mset: frozenset[str] | None = None
    elif isinstance(methods_raw, (list, tuple)):
        mset = frozenset(str(x).upper() for x in methods_raw if str(x).strip())
        if not mset:
            mset = None
    else:
        raise ValueError("http_dispatch.rules[].methods must be a list or null")
    pe = r.get("path_exact")
    pp = r.get("path_prefix")
    if pe is not None and pp is not None:
        raise ValueError("http_dispatch rule cannot set both path_exact and path_prefix")
    path_exact = str(pe) if pe is not None else None
    path_prefix = str(pp) if pp is not None else None
    return HttpDispatchRule(
        upstream_index=idx,
        methods=mset,
        path_exact=path_exact,
        path_prefix=path_prefix,
    )


def _route_from_raw(rv: Mapping[str, Any]) -> Route:
    ups = tuple(_upstream(x) for x in rv["upstreams"])
    strat = _strategy(str(rv.get("strategy", "least_conn")))
    hd = rv.get("http_dispatch")
    if hd is None:
        return Route(ups, strategy=strat)
    if not isinstance(hd, dict):
        raise ValueError("http_dispatch must be an object when present")
    n = len(ups)
    default_idx = int(hd.get("default_upstream_index", 0))
    if not (0 <= default_idx < n):
        raise ValueError("http_dispatch.default_upstream_index out of range")
    rules_raw = hd.get("rules")
    if not isinstance(rules_raw, list):
        raise ValueError("http_dispatch.rules must be a list")
    rules: list[HttpDispatchRule] = []
    for i, raw in enumerate(rules_raw):
        if not isinstance(raw, dict):
            raise ValueError(f"http_dispatch.rules[{i}] must be an object")
        rule = _http_dispatch_rule(raw)
        if not (0 <= rule.upstream_index < n):
            raise ValueError(
                f"http_dispatch.rules[{i}].upstream_index out of range for upstreams"
            )
        rules.append(rule)
    max_header = int(hd.get("max_header_bytes", 32 * 1024))
    max_body = int(hd.get("max_body_bytes", 3 * 1024 * 1024))
    if max_header < 1024 or max_body < 0:
        raise ValueError("http_dispatch max_header_bytes / max_body_bytes invalid")
    return HttpDispatchRoute(
        ups,
        tuple(rules),
        strategy=strat,
        default_upstream_index=default_idx,
        max_header_bytes=max_header,
        max_body_bytes=max_body,
    )


def gate_config_from_dict(d: Mapping[str, Any]) -> GateConfig:
    """ダッシュボード用 JSON から `GateConfig` を構築する。"""
    lc = d["listen"]
    listen = ListenConfig(
        host=str(lc["host"]),
        port=int(lc["port"]),
        backlog=int(lc.get("backlog", 128)),
        read_limit=int(lc.get("read_limit", 256 * 1024)),
    )
    ent = d["entrance"]
    et = str(ent["type"]).lower()
    if et == "plain":
        entrance = EntrancePlain(default_route=str(ent["default_route"]))
    elif et == "tls_sni":
        sni_contexts: dict[str, Any] = {}
        for item in ent["snis"]:
            hostname = str(item["hostname"])
            sni_contexts[hostname] = load_server_ssl_context(
                str(item["cert_file"]),
                str(item["key_file"]),
            )
        entrance = EntranceTlsSni(sni_contexts=sni_contexts)
    else:
        raise ValueError(f"unsupported entrance type: {et!r}")

    routes: dict[str, Route] = {}
    raw_routes = d["routes"]
    for key, rv in raw_routes.items():
        if not isinstance(rv, dict):
            raise ValueError(f"route {key!r} must be an object")
        routes[str(key)] = _route_from_raw(rv)

    return GateConfig(listen=listen, entrance=entrance, routes=routes)


def default_plain_gate_config(
    *,
    listen_host: str = "127.0.0.1",
    listen_port: int = 8443,
    upstream_host: str = "127.0.0.1",
    upstream_port: int = 8080,
) -> dict[str, Any]:
    """新規ゲート用の既定 JSON（平文 TCP・単一ルート）。

    REST で config を省略して作成するときのみ使用。ダッシュボード UI は TLS（SNI）のみ
    （平文の設定・保存は行わない）。平文で保存済みの設定は編集時に TLS フォームへ移行される。
    """
    return {
        "listen": {
            "host": listen_host,
            "port": listen_port,
            "backlog": 128,
            "read_limit": 256 * 1024,
        },
        "entrance": {"type": "plain", "default_route": "*"},
        "routes": {
            "*": {
                "upstreams": [{"host": upstream_host, "port": upstream_port}],
                "strategy": "least_conn",
            }
        },
    }
