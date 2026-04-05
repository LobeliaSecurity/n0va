import hashlib
import base64
import io


class WebSocketFrameCodec:
    """RFC 6455 フレームのエンコード／マスク解除。"""

    @staticmethod
    def unmask_payload(payload: bytes, mask_key: bytes, length: int) -> bytes:
        if length == 0:
            return b""
        out = bytearray(payload[:length])
        for i in range(length):
            out[i] ^= mask_key[i & 3]
        return bytes(out)

    @staticmethod
    def encode_frame(opcode: int, payload: bytes) -> bytes:
        payload_len = len(payload)
        R = io.BytesIO()
        R.write((0x80 + opcode).to_bytes(1, "big"))
        if payload_len <= 125:
            R.write(payload_len.to_bytes(1, "big"))
        elif payload_len <= 65535:
            R.write(b"\x7e" + payload_len.to_bytes(2, "big"))
        elif 65535 < payload_len and payload_len <= 18446744073709551615:
            R.write(b"\x7f" + payload_len.to_bytes(8, "big"))
        R.write(payload)
        R.seek(0)
        return R.read()


class WebSocketHandshake:
    """HTTP Upgrade から WebSocket への切り替え（Sec-WebSocket-Accept）。"""

    @staticmethod
    def sec_websocket_accept(sec_key: bytes) -> bytes:
        m = hashlib.sha1()
        m.update(sec_key)
        m.update(b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11")
        return base64.b64encode(m.digest())
