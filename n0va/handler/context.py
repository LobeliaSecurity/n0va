from __future__ import annotations

import n0va.core.stream
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional


@dataclass(frozen=True)
class HttpRequest:
    """HTTP リクエスト（1 リクエスト分の不変スナップショット）。"""

    method: bytes
    method_str: str
    """大文字のメソッド名（例: GET, POST, PUT）。ルータ照合・分岐に使う。"""
    path: str
    raw_path: bytes
    headers: Mapping[str, bytes]
    content: bytes
    """POST ボディ、または GET のクエリ部分（`?` 以降の生バイト）。"""


@dataclass
class HttpResponse:
    """HTTP 応答（ハンドラの戻り値）。"""

    status: int = 200
    body: bytes = b""
    content_type: bytes = b"text/html"
    server: bytes = b"n0va"
    connection: bytes = b"keep-alive"
    keep_alive: bytes = b"timeout=30, max=100"
    cache_control: Optional[bytes] = None
    """`Cache-Control` の値（生バイト）。`None` のときはヘッダを出さない。"""
    additional_header_lines: List[bytes] = field(default_factory=list)


class RequestContext:
    """
    1 接続・1 リクエスト処理の共有コンテキスト。
    `state` にアプリ独自オブジェクトを参照で載せられる。
    """

    def __init__(
        self,
        request: HttpRequest,
        connection: n0va.core.stream.AsyncStream,
        server: Any,
        state: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.request = request
        self._connection = connection
        self._server = server
        self.state: Dict[str, Any] = state if state is not None else {}

    @property
    def connection(self) -> n0va.core.stream.AsyncStream:
        return self._connection

    @property
    def server(self) -> Any:
        return self._server
