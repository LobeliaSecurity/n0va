from .config import (
    EntrancePlain,
    EntranceTlsManual,
    EntranceTlsSni,
    GateConfig,
    ListenConfig,
    LoadBalanceStrategy,
    Route,
    Upstream,
    UpstreamTls,
)
from .http_dispatch import (
    AsyncStreamPrefix,
    HttpDispatchRoute,
    HttpDispatchRule,
    HttpRoutingGateService,
)
from .service import GateService
from .upstream_pool import UpstreamConnectionPool

# 後方互換・短い名前（パッケージ公開 API）
upstream_pool_key = UpstreamConnectionPool.key_for
transient_upstream_error = UpstreamConnectionPool.transient_error

__all__ = [
    "AsyncStreamPrefix",
    "EntrancePlain",
    "EntranceTlsManual",
    "EntranceTlsSni",
    "GateConfig",
    "GateService",
    "HttpDispatchRoute",
    "HttpDispatchRule",
    "HttpRoutingGateService",
    "ListenConfig",
    "LoadBalanceStrategy",
    "Route",
    "Upstream",
    "UpstreamConnectionPool",
    "UpstreamTls",
    "transient_upstream_error",
    "upstream_pool_key",
]
