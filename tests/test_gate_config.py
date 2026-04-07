"""n0va.core.gate.config の検証ロジックテスト。"""

from __future__ import annotations

import ssl

import pytest

from n0va.core.gate.config import (
    EntrancePlain,
    EntranceTlsSni,
    GateConfig,
    ListenConfig,
    Route,
    Upstream,
)


def test_route_requires_upstreams() -> None:
    with pytest.raises(ValueError, match="no upstreams"):
        Route(())


def test_validate_plain_default_route_missing() -> None:
    u = Upstream("127.0.0.1", 8080)
    r = Route((u,))
    cfg = GateConfig(
        listen=ListenConfig("0.0.0.0", 443),
        entrance=EntrancePlain(default_route="missing"),
        routes={"*": r},
    )
    with pytest.raises(ValueError, match="default_route"):
        cfg.validate()


def test_validate_plain_ok() -> None:
    u = Upstream("127.0.0.1", 8080)
    r = Route((u,))
    cfg = GateConfig(
        listen=ListenConfig("0.0.0.0", 443),
        entrance=EntrancePlain(default_route="*"),
        routes={"*": r},
    )
    cfg.validate()


def test_validate_tls_sni_hostname_must_exist_in_routes() -> None:
    u = Upstream("127.0.0.1", 8080)
    r = Route((u,))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    cfg = GateConfig(
        listen=ListenConfig("0.0.0.0", 443),
        entrance=EntranceTlsSni(sni_contexts={"a.example": ctx}),
        routes={"other.example": r},
    )
    with pytest.raises(ValueError, match="SNI host"):
        cfg.validate()


def test_validate_tls_sni_ok_sets_domain_name() -> None:
    u = Upstream("127.0.0.1", 8080)
    r = Route((u,))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    cfg = GateConfig(
        listen=ListenConfig("0.0.0.0", 443),
        entrance=EntranceTlsSni(sni_contexts={"app.example": ctx}),
        routes={"app.example": r},
    )
    cfg.validate()
    assert getattr(ctx, "DomainName", None) == "app.example"


def test_validate_routes_must_not_be_empty() -> None:
    with pytest.raises(ValueError, match="routes must not be empty"):
        GateConfig(
            listen=ListenConfig("0.0.0.0", 443),
            entrance=EntrancePlain(),
            routes={},
        ).validate()
