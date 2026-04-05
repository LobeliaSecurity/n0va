from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, Union

import n0va.core.stream

from .ws_codec import WebSocketFrameCodec


class WebSocketSession:
    """
    WebSocket 接続 1 本に対応。フレーム送受信と `state` をまとめる。
    """

    def __init__(
        self,
        connection: n0va.core.stream.AsyncStream,
        state: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._connection = connection
        self.state = state if state is not None else {}

    @property
    def connection(self) -> n0va.core.stream.AsyncStream:
        return self._connection

    async def recv_frame(self) -> Union[Tuple[int, bytes], bool]:
        buf = await self._connection.Recv()
        if len(buf) == 0 or buf[0] == 0x88:
            return False
        opcode = buf[0] & 0x0F
        is_masked = buf[1] >> 7
        payload_len = buf[1] & 0x7F
        ptr = 2
        if payload_len == 126:
            payload_len = int.from_bytes(buf[2:4], "big")
            ptr = 4
        elif payload_len == 127:
            payload_len = int.from_bytes(buf[2:10], "big")
            ptr = 10
        payload_data = buf[ptr + 4 :]
        if is_masked:
            masking_key = buf[ptr : ptr + 4]
            payload_data = WebSocketFrameCodec.unmask_payload(
                payload_data, masking_key, payload_len
            )
        return (opcode, payload_data)

    async def send_frame(self, opcode: int, payload: bytes) -> None:
        data = WebSocketFrameCodec.encode_frame(opcode, payload)
        await self._connection.Send(data)
