"""
Gate サンプル: `Route` を継承して `on_entrance_to_destination` / `on_destination_to_entrance`
を実装すると、SNI（エンドポイント）ごとにチャンクを観測できる（透過転送は `return buf`）。

起動:
- 既定: `spawn_and_supervise` で子プロセスがサーバを動かす（シグナル用）。
- 旧サンプルと同様に **単一プロセス** で動かす場合は環境変数 `N0VA_NO_SUPERVISE=1` を設定する。
  その場合、親が `main()` に入ってからだけ `GateService` / `Nova` を構築する（二重初期化しない）。
"""

import asyncio
import os
import pathlib
import ssl
import sys
from typing import Any, Optional

import n0va
from n0va import HttpResponse, RequestContext
from n0va.core.gate import (
    EntranceTlsSni,
    GateConfig,
    GateService,
    ListenConfig,
    Route,
    Upstream,
)

_GATE_VERBOSE = os.environ.get("N0VA_GATE_VERBOSE", "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)


def _analyze_tcp_chunk(buf: bytes, direction: str, sni: str) -> None:
    """
    平文 HTTP のような先頭行だけをログに出す（既定オフ。有効化は N0VA_GATE_VERBOSE=1）。
    リクエストごとに大量 print すると Windows コンソールで体感が著しく遅くなることがある。
    """
    if not _GATE_VERBOSE or not buf:
        return
    prefix = f"[gate {direction} sni={sni}]"
    if buf.startswith(
        (
            b"GET ",
            b"POST ",
            b"HEAD ",
            b"PUT ",
            b"DELETE ",
            b"OPTIONS ",
            b"PATCH ",
            b"CONNECT ",
        )
    ):
        line = buf.split(b"\r\n", 1)[0].decode("utf-8", "replace")
        if len(line) > 180:
            line = line[:180] + "..."
        print(f"{prefix} HTTP request line: {line}", flush=True)
    elif buf.startswith(b"HTTP/"):
        line = buf.split(b"\r\n", 1)[0].decode("utf-8", "replace")
        if len(line) > 180:
            line = line[:180] + "..."
        print(f"{prefix} HTTP status line: {line}", flush=True)
    else:
        print(f"{prefix} {len(buf)} bytes (TLS or non-HTTP)", flush=True)


class SampleAnalyzedRoute(Route):
    """エンドポイント（SNI）ごとに解析ログを分ける `Route` 実装例。"""

    def __init__(self, upstreams: tuple[Upstream, ...], *, sni: str) -> None:
        super().__init__(upstreams)
        self._sni = sni

    async def on_entrance_to_destination(
        self,
        buf: bytes,
        entrance_connection: Any,
        destination_connection: Any,
    ) -> Optional[bytes]:
        _analyze_tcp_chunk(buf, "e2d", self._sni)
        return buf

    async def on_destination_to_entrance(
        self,
        buf: bytes,
        destination_connection: Any,
        entrance_connection: Any,
    ) -> Optional[bytes]:
        _analyze_tcp_chunk(buf, "d2e", self._sni)
        return buf


class Config:
    class Clover:
        Host = "127.0.0.1"
        Port = 7771
        Context = ssl.create_default_context()
        Context.load_cert_chain(
            ".n0va/ca/5/issued/_.lobeliasecurity.com_23122efe.cert.pem",
            ".n0va/ca/5/issued/_.lobeliasecurity.com_23122efe.key.pem",
        )

    class Ivy:
        Host = "127.0.0.1"
        Port = 7772
        Context = ssl.create_default_context()
        Context.load_cert_chain(
            ".n0va/ca/5/issued/_.lobeliasecurity.com_23122efe.cert.pem",
            ".n0va/ca/5/issued/_.lobeliasecurity.com_23122efe.key.pem",
        )

    class Azami:
        Host = "127.0.0.1"
        Port = 7773
        Context = ssl.create_default_context()
        Context.load_cert_chain(
            ".n0va/ca/5/issued/_.lobeliasecurity.com_23122efe.cert.pem",
            ".n0va/ca/5/issued/_.lobeliasecurity.com_23122efe.key.pem",
        )


def create_services() -> tuple[GateService, n0va.Service, n0va.Service, n0va.Service]:
    """ワーカー（または N0VA_NO_SUPERVISE 時の単一プロセス）内でのみ呼ぶ。"""
    gate_config = GateConfig(
        listen=ListenConfig(host="127.0.0.1", port=443),
        entrance=EntranceTlsSni(
            sni_contexts={
                "clover.lobeliasecurity.com": Config.Clover.Context,
                "ivy.lobeliasecurity.com": Config.Ivy.Context,
                "azami.lobeliasecurity.com": Config.Azami.Context,
            }
        ),
        routes={
            "clover.lobeliasecurity.com": SampleAnalyzedRoute(
                (Upstream(host="127.0.0.1", port=7771),),
                sni="clover.lobeliasecurity.com",
            ),
            "ivy.lobeliasecurity.com": SampleAnalyzedRoute(
                (Upstream(host="127.0.0.1", port=7772),),
                sni="ivy.lobeliasecurity.com",
            ),
            "azami.lobeliasecurity.com": SampleAnalyzedRoute(
                (Upstream(host="127.0.0.1", port=7773),),
                sni="azami.lobeliasecurity.com",
            ),
        },
    )
    gate = GateService(gate_config)

    class Nova(n0va.Service):
        def __init__(self, host, port, name: bytes) -> None:
            super().__init__(
                host=host,
                port=port,
                root_path=pathlib.Path(__file__).resolve().parent.as_posix(),
            )
            self.connections = {}
            self.Name = name
            self.onGet("/GetTest.get")(self.GetTest)

        async def GetTest(self, ctx: RequestContext) -> HttpResponse:
            return HttpResponse(
                status=200,
                body=b":".join([b"GET", self.Name, ctx.request.content]),
                content_type=b"text/html",
            )

    clover = Nova(
        host=Config.Clover.Host,
        port=Config.Clover.Port,
        name=b"clover.lobeliasecurity.com",
    )
    ivy = Nova(
        host=Config.Ivy.Host,
        port=Config.Ivy.Port,
        name=b"ivy.lobeliasecurity.com",
    )
    azami = Nova(
        host=Config.Azami.Host,
        port=Config.Azami.Port,
        name=b"azami.lobeliasecurity.com",
    )
    return gate, clover, ivy, azami


async def start(
    gate: GateService,
    clover: n0va.Service,
    ivy: n0va.Service,
    azami: n0va.Service,
) -> None:
    await asyncio.gather(
        clover.__Start__(), ivy.__Start__(), azami.__Start__(), gate.start()
    )


def _no_supervise() -> bool:
    return os.environ.get("N0VA_NO_SUPERVISE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def main() -> None:
    from n0va.core.supervisor import is_worker_process, spawn_and_supervise

    if not is_worker_process() and not _no_supervise():
        raise SystemExit(spawn_and_supervise())
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    gate, clover, ivy, azami = create_services()
    asyncio.run(start(gate, clover, ivy, azami))


if __name__ == "__main__":
    main()
