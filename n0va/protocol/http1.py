"""
HTTP/1.x リクエストメッセージの解析（RFC 7230 / 9110 / 9112 系）。

- 外部依存なし（標準ライブラリのみ）。
- 接続再利用・パイプライン化のため、バッファ先頭から 1 メッセージ分の消費バイト数を返す。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional
from urllib.parse import urlparse


class Http1ParseError(ValueError):
    """構文エラー・制限超過など、再試行しても完了しない場合。"""


@dataclass(frozen=True)
class Http1Request:
    """単一の HTTP/1.x リクエストメッセージ。"""

    method: bytes
    raw_target: bytes
    http_version: bytes
    headers: Mapping[str, bytes]
    body: bytes
    consumed: int
    """バッファ先頭からこのリクエスト全体で消費したバイト数。"""
    path: str
    """ルーティング用。`?` 以降を含めたパス相当（既存 :class:`HttpRequest.path` と整合）。"""
    path_only: str
    """クエリを除いたパス部分。"""


class Http1RequestParser:
    """
    HTTP/1.x リクエストのバイト列解析と、既存ハンドラ向けの辞書変換。
    """

    @staticmethod
    def normalize_request_target(target: bytes) -> bytes:
        """
        RFC 9112 の request-target をオリジン形式に近いバイト列へ寄せる。

        絶対形式 ``http(s)://host/path?query`` は ``/path?query`` に変換する。
        ``*`` はそのまま。
        """
        if not target or target == b"*":
            return target
        if not target.startswith((b"http://", b"https://")):
            return target
        try:
            u = urlparse(target.decode("ascii", errors="replace"))
            path = u.path or "/"
            if u.query:
                path = f"{path}?{u.query}"
            return path.encode("utf-8")
        except Exception:
            return target

    @staticmethod
    def _split_path_and_query(norm: bytes) -> tuple[str, str]:
        if b"?" in norm:
            p, q = norm.split(b"?", 1)
            return p.decode("utf-8", "replace"), (p + b"?" + q).decode("utf-8", "replace")
        s = norm.decode("utf-8", "replace")
        return s, s

    @staticmethod
    def _parse_field_line_list(field_lines: list[bytes]) -> dict[str, bytes]:
        """field-line のリスト（各要素は CRLF 不含）を解釈。obs-fold に対応。キーは小文字。"""
        headers: dict[str, bytes] = {}
        last_key: str | None = None
        for line in field_lines:
            if not line:
                continue
            if line[0] in (32, 9) and last_key is not None:
                headers[last_key] = headers[last_key] + b" " + line.lstrip()
                continue
            colon = line.find(b":")
            if colon <= 0:
                raise Http1ParseError("bad header line")
            name = line[:colon].decode("ascii", "replace").strip()
            if not name:
                raise Http1ParseError("empty header name")
            key = name.lower()
            val = line[colon + 1 :].lstrip(b" \t")
            val_end = len(val)
            while val_end > 0 and val[val_end - 1] in (32, 9):
                val_end -= 1
            val = val[:val_end]
            if key in headers:
                headers[key] = headers[key] + b", " + val
            else:
                headers[key] = val
            last_key = key
        return headers

    @staticmethod
    def _request_line_and_headers_from_head(head: bytes) -> tuple[bytes, dict[str, bytes]]:
        """
        ``\\r\\n\\r\\n`` 直前までのブロック（最後の field-line の終端 ``\\r\\n`` を含む）を渡す。
        先頭行をリクエスト行、以降を field-line として解釈する。
        """
        lines = head.split(b"\r\n")
        if not lines:
            raise Http1ParseError("bad message")
        request_line = lines[0]
        field_lines = lines[1:]
        while field_lines and field_lines[-1] == b"":
            field_lines.pop()
        return request_line, Http1RequestParser._parse_field_line_list(field_lines)

    @staticmethod
    def _header_section_end(data: bytes, max_scan: int) -> int:
        return data.find(b"\r\n\r\n", 0, max_scan)

    @staticmethod
    def _transfer_encoding_chunked(headers: dict[str, bytes]) -> bool:
        te = headers.get("transfer-encoding")
        if not te:
            return False
        parts = [p.strip().lower() for p in te.split(b",")]
        return any(p == b"chunked" for p in parts)

    @staticmethod
    def _content_length(headers: dict[str, bytes]) -> Optional[int]:
        cl = headers.get("content-length")
        if not cl:
            return None
        parts = [p.strip() for p in cl.split(b",")]
        values: list[int] = []
        for p in parts:
            if not p or not p.isdigit():
                raise Http1ParseError("invalid Content-Length")
            values.append(int(p))
        if len(set(values)) > 1:
            raise Http1ParseError("conflicting Content-Length")
        return values[0]

    @staticmethod
    def _parse_chunked_body(
        data: bytes, start: int, max_body: int
    ) -> tuple[bytes, int] | None:
        out = bytearray()
        pos = start
        while True:
            line_end = data.find(b"\r\n", pos)
            if line_end == -1:
                return None
            line = data[pos:line_end]
            semi = line.find(b";")
            size_hex = line[:semi] if semi != -1 else line
            size_hex = size_hex.strip()
            if not size_hex:
                raise Http1ParseError("chunk size empty")
            try:
                chunk_size = int(size_hex, 16)
            except ValueError as e:
                raise Http1ParseError("chunk size") from e
            pos = line_end + 2
            if chunk_size == 0:
                while True:
                    line_end = data.find(b"\r\n", pos)
                    if line_end == -1:
                        return None
                    line = data[pos:line_end]
                    pos = line_end + 2
                    if line == b"":
                        return bytes(out), pos
            if pos + chunk_size > len(data):
                return None
            piece = data[pos : pos + chunk_size]
            if len(out) + len(piece) > max_body:
                raise Http1ParseError("body too large")
            out.extend(piece)
            pos += chunk_size
            if pos + 2 > len(data):
                return None
            if data[pos : pos + 2] != b"\r\n":
                raise Http1ParseError("chunk CRLF")
            pos += 2

    @staticmethod
    def parse(
        data: bytes,
        *,
        max_header_bytes: int = 32 * 1024,
        max_body_bytes: int = 3 * 1024 * 1024,
    ) -> Http1Request | None:
        """
        ``data`` 先頭から 1 リクエスト分を解釈する。

        - ヘッダが終わる前に `max_header_bytes` を超えたら :exc:`Http1ParseError`。
        - ボディが足りないときは ``None``（さらにバイトが必要）。
        - 完了時は :class:`Http1Request`（``consumed`` はメッセージ全体）。
        """
        if not data:
            return None
        hend = Http1RequestParser._header_section_end(
            data, min(len(data), max_header_bytes + 4)
        )
        if hend == -1:
            if len(data) >= max_header_bytes:
                raise Http1ParseError("headers too large")
            return None
        if hend + 2 > max_header_bytes:
            raise Http1ParseError("headers too large")
        header_end_exclusive = hend + 4
        head = data[: hend + 2]
        request_line, headers = Http1RequestParser._request_line_and_headers_from_head(head)
        parts = request_line.split(b" ")
        if len(parts) < 3:
            raise Http1ParseError("bad request line")
        method = parts[0]
        raw_target = parts[1]
        http_version = parts[2]
        if not http_version.startswith(b"HTTP/"):
            raise Http1ParseError("bad HTTP-Version")
        ver_rest = http_version[5:]
        if (
            len(ver_rest) != 3
            or ver_rest[0] not in b"01"
            or ver_rest[1] != 46
            or ver_rest[2] not in b"01"
        ):
            raise Http1ParseError("unsupported HTTP version")

        norm = Http1RequestParser.normalize_request_target(raw_target)
        path_only, path_full = Http1RequestParser._split_path_and_query(norm)

        body_start = header_end_exclusive
        body: bytes
        consumed: int

        if Http1RequestParser._transfer_encoding_chunked(headers):
            got = Http1RequestParser._parse_chunked_body(data, body_start, max_body_bytes)
            if got is None:
                return None
            body, consumed = got
        else:
            cl = Http1RequestParser._content_length(headers)
            if cl is not None:
                if cl > max_body_bytes:
                    raise Http1ParseError("body too large")
                if len(data) < body_start + cl:
                    return None
                body = data[body_start : body_start + cl]
                consumed = body_start + cl
            else:
                sm = method.upper()
                if sm in (b"GET", b"HEAD", b"CONNECT", b"TRACE"):
                    body = b""
                    consumed = body_start
                else:
                    body = b""
                    consumed = body_start

        return Http1Request(
            method=method,
            raw_target=raw_target,
            http_version=http_version,
            headers=headers,
            body=body,
            consumed=consumed,
            path=path_full,
            path_only=path_only,
        )

    @staticmethod
    def to_server_request_dict(req: Http1Request) -> dict:
        """
        既存 :class:`n0va.handler.http.server` が期待する ``Request`` dict 形へ変換。
        """
        d: dict = {
            "method": req.method,
            "path": Http1RequestParser.normalize_request_target(req.raw_target),
            "content": req.body,
        }
        for k, v in req.headers.items():
            d[k] = v
        return d
