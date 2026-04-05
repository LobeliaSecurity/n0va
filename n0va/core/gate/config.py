from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional, Union

import ssl


class LoadBalanceStrategy(Enum):
    LEAST_CONN = "least_conn"
    ROUND_ROBIN = "round_robin"


@dataclass(frozen=True)
class ListenConfig:
    host: str
    port: int
    backlog: int = 128
    read_limit: int = 256 * 1024


@dataclass(frozen=True)
class UpstreamTls:
    server_hostname: str
    alpn: Optional[tuple[str, ...]] = None


@dataclass(frozen=True)
class Upstream:
    host: str
    port: int
    tls: Optional[UpstreamTls] = None


class Route:
    """
    上流定義と、チャンク単位の観測・改変フック。
    エンドポイント（SNI 名や `EntrancePlain` のルートキー）ごとにサブクラス化して
    `on_entrance_to_destination` / `on_destination_to_entrance` を上書きする。
    """

    def __init__(
        self,
        upstreams: tuple[Upstream, ...],
        strategy: LoadBalanceStrategy = LoadBalanceStrategy.LEAST_CONN,
    ) -> None:
        if not upstreams:
            raise ValueError("route has no upstreams")
        self.upstreams = upstreams
        self.strategy = strategy

    async def on_entrance_to_destination(
        self,
        buf: bytes,
        entrance_connection: Any,
        destination_connection: Any,
    ) -> Optional[bytes]:
        """クライアント → 上流へ送る直前のバイト列。`None` を返すとそのチャンクは転送しない。"""
        return buf

    async def on_destination_to_entrance(
        self,
        buf: bytes,
        destination_connection: Any,
        entrance_connection: Any,
    ) -> Optional[bytes]:
        """上流 → クライアントへ返す直前のバイト列。"""
        return buf


@dataclass(frozen=True)
class EntrancePlain:
    """入口は平文 TCP。`routes` は通常 `default_route` キー 1 件。"""

    default_route: str = "*"


@dataclass(frozen=True)
class EntranceTlsSni:
    """OpenSSL 自動ハンドシェイク + SNI でホストごとに SSLContext を切り替え。"""

    sni_contexts: Mapping[str, ssl.SSLContext]


@dataclass(frozen=True)
class EntranceTlsManual:
    """ClientHello を自前解析（AsyncManualSslStream）して SNI を決定。"""

    sni_contexts: Mapping[str, ssl.SSLContext]


@dataclass(frozen=True)
class GateConfig:
    listen: ListenConfig
    entrance: Union[EntrancePlain, EntranceTlsSni, EntranceTlsManual]
    routes: Mapping[str, Route]


def _attach_sni_labels(entrance: Union[EntranceTlsSni, EntranceTlsManual]) -> None:
    for hostname, ctx in entrance.sni_contexts.items():
        setattr(ctx, "DomainName", hostname)


def validate_gate_config(config: GateConfig) -> None:
    if not config.routes:
        raise ValueError("routes must not be empty")
    for key, route in config.routes.items():
        if not isinstance(route, Route):
            raise TypeError(f"route {key!r} must be a Route instance (subclass)")
    if isinstance(config.entrance, EntrancePlain):
        dr = config.entrance.default_route
        if dr not in config.routes:
            raise ValueError(f"default_route {dr!r} not in routes")
    elif isinstance(config.entrance, (EntranceTlsSni, EntranceTlsManual)):
        for hostname in config.entrance.sni_contexts:
            if hostname not in config.routes:
                raise ValueError(
                    f"SNI host {hostname!r} has no matching route in routes"
                )
        _attach_sni_labels(config.entrance)
