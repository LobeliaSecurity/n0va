from .context import HttpRequest, HttpResponse, RequestContext
from .http import MediaTypes, server
from .router import Router
from .ws import WebSocketSession


def __getattr__(name: str):
    if name == "MIME":
        return MediaTypes.shared()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "HttpRequest",
    "HttpResponse",
    "RequestContext",
    "Router",
    "WebSocketSession",
    "server",
    "MIME",
    "MediaTypes",
]
