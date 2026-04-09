import asyncio
import socket
import ssl


class StreamSocketOptions:
    """TCP ストリーム向けソケットオプション。"""

    @staticmethod
    def apply_tcp_nodelay(writer) -> None:
        sock = writer.get_extra_info("socket")
        if sock is None:
            return
        if sock.family not in (socket.AF_INET, socket.AF_INET6):
            return
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass


class TlsClientHelloParser:
    """TLS ClientHello レコードと拡張（SNI / ALPN）の解釈。"""

    @staticmethod
    def extract_extensions(record: bytes) -> bytes:
        """TLS レコード先頭から ClientHello の extensions ブロックを取り出す。"""
        if len(record) < 5:
            raise ValueError("record too short")
        if record[0] != 22:
            raise ValueError("not handshake record")
        rec_len = int.from_bytes(record[3:5], "big")
        if len(record) < 5 + rec_len:
            raise ValueError("incomplete record")
        pos = 5
        if pos + 4 > len(record):
            raise ValueError("handshake header")
        hs_type = record[pos]
        hs_len = int.from_bytes(record[pos + 1 : pos + 4], "big")
        pos += 4
        if hs_type != 1:
            raise ValueError("not client hello")
        if pos + hs_len > len(record):
            raise ValueError("incomplete handshake")
        end_hs = pos + hs_len
        if pos + 34 > end_hs:
            raise ValueError("client hello truncated")
        pos += 2 + 32
        sid_len = record[pos]
        pos += 1
        if pos + sid_len > end_hs:
            raise ValueError("session id")
        pos += sid_len
        if pos + 2 > end_hs:
            return b""
        cs_len = int.from_bytes(record[pos : pos + 2], "big")
        pos += 2
        if pos + cs_len > end_hs:
            raise ValueError("cipher suites")
        pos += cs_len
        if pos + 1 > end_hs:
            return b""
        comp_len = record[pos]
        pos += 1
        if pos + comp_len > end_hs:
            raise ValueError("compression")
        pos += comp_len
        if pos + 2 > end_hs:
            return b""
        ext_len = int.from_bytes(record[pos : pos + 2], "big")
        pos += 2
        if ext_len == 0:
            return b""
        if pos + ext_len > end_hs:
            raise ValueError("extensions")
        return record[pos : pos + ext_len]

    @staticmethod
    def flatten_extensions(ext_block: bytes) -> list:
        """
        [type2, len2, payload, ...] のフラット列（ReadserverName / ReadALPN 互換）。
        """
        out = []
        pos = 0
        n = len(ext_block)
        while pos + 4 <= n:
            etype = ext_block[pos : pos + 2]
            elen_raw = ext_block[pos + 2 : pos + 4]
            elen = int.from_bytes(elen_raw, "big")
            pos += 4
            if pos + elen > n:
                break
            payload = ext_block[pos : pos + elen]
            pos += elen
            out.extend([etype, elen_raw, payload])
        return out

    @staticmethod
    def parse_server_name_hostname(payload: bytes):
        """extension_data (server_name) から最初の host_name を UTF-8 で返す。"""
        if len(payload) < 2:
            return None
        list_len = int.from_bytes(payload[0:2], "big")
        pos = 2
        end = min(len(payload), 2 + list_len)
        while pos + 3 <= end:
            name_type = payload[pos]
            name_len = int.from_bytes(payload[pos + 1 : pos + 3], "big")
            pos += 3
            if pos + name_len > end:
                break
            host = payload[pos : pos + name_len]
            pos += name_len
            if name_type == 0:
                return host.decode("utf-8")
        return None

    @staticmethod
    def parse_alpn_protocol_names(payload: bytes) -> list:
        """ALPN extension_data。先頭2バイトの次から (1バイト長 + 名) を繰り返し。"""
        if len(payload) <= 2:
            return []
        pos = 2
        end = len(payload)
        names = []
        while pos + 1 <= end:
            plen = payload[pos]
            pos += 1
            if pos + plen > end:
                break
            names.append(payload[pos : pos + plen].decode("utf-8"))
            pos += plen
        return names


class AsyncStream:
    def __init__(self, reader, writer):
        self._Reader = reader
        self._Writer = writer
        self._Recvsize = 1024 * 64
        self._Timeout = 60.0 * 15

    async def Send(self, b):
        self._Writer.write(b)
        await asyncio.wait_for(self._Writer.drain(), timeout=self._Timeout)

    async def Recv(self, i=0, timeout=0):
        if i == 0:
            i = self._Recvsize
        if timeout == 0:
            timeout = self._Timeout
        try:
            return await asyncio.wait_for(self._Reader.read(i), timeout=timeout)
        except TimeoutError:
            # 待ち受けタイムアウトは切断扱い（EOF と同様に b""）。未処理例外で asyncio に出さない。
            return b""

    async def Close(self):
        self._Writer.close()

    def isOnline(self):
        return not self._Writer.is_closing()


class AsyncManualSslStream(AsyncStream):
    def __init__(self, reader, writer):
        super().__init__(reader, writer)
        self.serverSide = True
        self.serverName = None
        self.ALPN = None
        self.SslContext = None

        self.isTryingHandshake = False

        self._tls_in_buff = ssl.MemoryBIO()
        self._tls_out_buff = ssl.MemoryBIO()
        self._tls_Readsize = 4096
        self._client_hello_buf = None

    async def Send(self, b):
        self._tls_obj.write(b)
        self._Writer.write(self._tls_out_buff.read())
        await asyncio.wait_for(self._Writer.drain(), timeout=self._Timeout)

    async def Recv(self, i=0, timeout=0):
        if i == 0:
            i = self._Recvsize
        if timeout == 0:
            timeout = self._Timeout
        try:
            BUF = await asyncio.wait_for(self._Reader.read(i), timeout=timeout)
        except TimeoutError:
            BUF = b""
        self._tls_in_buff.write(BUF)
        parts = []
        while True:
            try:
                chunk = self._tls_obj.read(self._tls_Readsize)
            except ssl.SSLError:
                break
            if not chunk:
                break
            parts.append(chunk)
        return b"".join(parts)

    def ReadserverName(self, ex):
        for i in range(0, len(ex), 3):
            if i + 2 >= len(ex):
                break
            if ex[i] == b"\x00\x00":
                return TlsClientHelloParser.parse_server_name_hostname(ex[i + 2])
        return None

    def ReadALPN(self, ex):
        for i in range(0, len(ex), 3):
            if i + 2 >= len(ex):
                break
            if ex[i] == b"\x00\x10":
                return TlsClientHelloParser.parse_alpn_protocol_names(ex[i + 2])
        return []

    async def ParseClientHello(self):
        R = {}
        self._client_hello_buf = await super().Recv()
        if len(self._client_hello_buf) == 0 or self._client_hello_buf[0] != 22:
            self.isTryingHandshake = False
            return None
        self.isTryingHandshake = True
        try:
            ext_block = TlsClientHelloParser.extract_extensions(self._client_hello_buf)
        except (ValueError, IndexError):
            R["Parsed"] = [[]]
            return R
        flat = TlsClientHelloParser.flatten_extensions(ext_block)
        R["Parsed"] = [flat]
        return R

    async def ReadClientHello(self):
        R = await self.ParseClientHello()
        if self.isTryingHandshake and R is not None:
            self.serverName = self.ReadserverName(R["Parsed"][-1])
            self.ALPN = self.ReadALPN(R["Parsed"][-1])

    async def Handshake(self):
        self._tls_obj = self.SslContext.wrap_bio(
            self._tls_in_buff, self._tls_out_buff, server_side=self.serverSide
        )
        if self.serverSide:
            # Recv Client Hello
            self._tls_in_buff.write(self._client_hello_buf)
        # || TLS Handshake
        try:
            self._tls_obj.do_handshake()
        except ssl.SSLWantReadError:
            if self.serverSide:
                server_hello = self._tls_out_buff.read()
                # serverHello
                await super().Send(server_hello)
                # Client Certificate
                client_cert = await super().Recv()
                self._tls_in_buff.write(client_cert)
                self._tls_obj.do_handshake()
                # Change Cipher
                change_cipher_finished = self._tls_out_buff.read()
                await super().Send(change_cipher_finished)
            else:
                # Client Hello
                await super().Send(self._tls_out_buff.read())
                # server Hello
                self._tls_in_buff.write(await super().Recv())
                try:
                    self._tls_obj.do_handshake()
                except ssl.SSLWantReadError:
                    await super().Send(self._tls_out_buff.read())
                    self._tls_in_buff.write(await super().Recv())
        # -- TLS Handshake
