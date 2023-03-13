from n0va.core.server import AsyncTcp
import traceback
import hashlib
import base64
import io


class server(AsyncTcp):
    def __init__(self, host, port):
        super().__init__(host=host, port=port)
        self.PostFunctions = {}
        self.GetFunctions = {}
        self.WebSocketFunctions = {}
        # self.MIME = {
        #     "txt": b"text/plain",
        #     "html": b"text/html",
        #     "css": b"text/css",
        #     "js": b"application/javascript",
        #     "jpg": b"image/jpg",
        #     "jpeg": b"image/jpeg",
        #     "png": b"image/png",
        #     "gif": b"image/gif",
        #     "ico": b"image/ico",
        #     "mp4": b"video/mp4",
        #     "mp3": b"audio/mp3",
        #     "otf": b"application/x-font-otf",
        #     "woff": b"application/x-font-woff",
        #     "ttf": b"application/x-font-ttf",
        #     "svg": b"image/svg+xml",
        #     "json": b"application/json"
        # }
        self._Header = b"\r\n".join((
            b"HTTP/1.1 %b",
            b"server: %b",
            b"Accept-Ranges: %b",
            b"Content-Length: %i",
            b"Connection: %b",
            b"Keep-Alive: %b",
            b"Content-Type: %b\r\n"
        ))
        self.serverFunctions = {
            b"GET": self.Get,
            b"POST": self.Post,
            b"WebSocket": self.WebSocket
        }
        self.ContentLengthLimit = 1024 * 1024 * 3

    def NewHeader(self):
        return({
            "Status": 0,
            "server": b"n0va",
            "Accept-Ranges": b"bytes",
            "Content-Length": 0,
            "Connection": b"keep-alive",
            "Keep-Alive": b"timeout=30, max=100",
            "Content-Type": b"",
            "Additional": [],
            "ReplyContent": b""
        })

    async def Reply(self, connection, header):
        _ReplyBuffer = self._Header % (
            header["Status"],
            header["server"],
            header["Accept-Ranges"],
            len(header["ReplyContent"]),
            header["Connection"],
            header["Keep-Alive"],
            header["Content-Type"])

        for a in header["Additional"]:
            _ReplyBuffer += a + b"\r\n"
        await connection.Send(_ReplyBuffer + b"\r\n" + header["ReplyContent"])

    async def WebSockRecv(self, connection):
        buf = await connection.Recv()
        if(len(buf) == 0 or buf[0] == 0x88):
            return(False)
        opcode = (buf[0] & 0x0f)
        is_Masked = (buf[1] >> 7)
        Payload_len = (buf[1] & 0x7f)
        Ptr = 2
        Masking_key = b""
        Payload_data = b""
        if(Payload_len == 126):
            # Extended payload length
            Payload_len = int.from_bytes(buf[2:4], "big")
            Ptr = 4
        elif(Payload_len == 127):
            # Extended payload length
            Payload_len = int.from_bytes(buf[2:10], "big")
            Ptr = 10
        Payload_data = buf[Ptr+4:]
        if(is_Masked):
            # Resulut[ i ] ＝ buf[ i ] xor key [ i mod 4 ]
            Masking_key = buf[Ptr:Ptr+4]
            Result = io.BytesIO()
            for i in range(Payload_len):
                Result.write(
                    (Payload_data[i] ^ Masking_key[i % 4]).to_bytes(1, 'big')
                )
            Result.seek(0)
            Payload_data = Result.read()
        return(opcode, Payload_data)

    async def BuildWebSockFrame(self, opcode, payload):
        payload_len = len(payload)
        R = io.BytesIO()
        R.write((0x80 + opcode).to_bytes(1, "big"))
        if(payload_len <= 125):
            R.write(payload_len.to_bytes(1, 'big'))
        elif(payload_len <= 65535):
            R.write(b"\x7e" + payload_len.to_bytes(2, 'big'))
        elif(65535 < payload_len and payload_len <= 18446744073709551615):
            R.write(b"\x7f" + payload_len.to_bytes(8, 'big'))
        R.write(payload)
        R.seek(0)
        return(R.read())

    async def serverFunctionHandler(self, connection, Request, ReplyHeader):
        await self.serverFunctions[Request["method"]](connection, Request, ReplyHeader)

    async def GetFunctionHandler(self, connection, Request, ReplyHeader):
        await self.GetFunctions[Request["path"].decode("utf-8")](connection, Request, ReplyHeader)

    async def PostFunctionHandler(self, connection, Request, ReplyHeader):
        await self.PostFunctions[Request["path"].decode("utf-8")](connection, Request, ReplyHeader)

    async def WebSocketFunctionHandler(self, connection, Request, ReplyHeader):
        await self.WebSocketFunctions[Request["path"].decode("utf-8")](connection, Request, ReplyHeader)

    async def Get(self, connection, Request, ReplyHeader):
        ReqPath = Request["path"].decode("utf-8")
        if("?" in ReqPath):
            data = Request["path"].split(b"?")
            Request["path"] = data[0]
            Request.update({"content": data[1]})
        await self.GetFunctionHandler(connection, Request, ReplyHeader)

    async def Post(self, connection, Request, ReplyHeader):
        ReqPath = Request["path"].decode("utf-8")
        if(ReqPath in self.PostFunctions):
            await self.PostFunctionHandler(connection, Request, ReplyHeader)
        else:
            await self.ReplyJustCode(404, connection, Request, ReplyHeader)

    async def WebSocket(self, connection, Request, ReplyHeader):
        m = hashlib.sha1()
        m.update(Request["Sec-WebSocket-Key"])
        m.update(b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11")
        await connection.Send(
            b"".join(
                (
                    b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ",
                    base64.b64encode(m.digest()),
                    b"\r\n\r\n"
                )
            )
        )
        await self.WebSocketFunctionHandler(connection, Request, ReplyHeader)

    async def Handler(self, connection):
        try:
            while(not connection._Writer.is_closing()):
                h = self.NewHeader()
                Request = {}
                buf = await connection.Recv()
                if(len(buf) == 0):
                    await connection.Close()
                    return
                while(buf.find(b"\r\n\r\n") == -1):
                    buf += await connection.Recv()
                Request = {}
                body_pointer = buf.find(b"\r\n\r\n")
                headers = buf[:body_pointer].split(b"\r\n")
                request = headers[0].split(b" ")
                Request.update({"method": request[0]})
                Request.update({"path": request[1]})
                try:
                    for param in headers[1:]:
                        p = param.split(b": ")
                        Request.update({p[0].decode("utf-8"): p[1]})
                except:
                    pass
                if("Upgrade" in Request and Request["Upgrade"] == b"websocket"):
                    Request["method"] = b"WebSocket"
                elif("Content-Length" in Request):
                    body = buf[body_pointer+4:]
                    if(self.ContentLengthLimit < int(Request["Content-Length"])):
                        await connection.Close()
                        return
                    while(len(body) < int(Request["Content-Length"])):
                        body += await connection.Recv()
                    Request.update({"content": body})
                await self.serverFunctionHandler(connection, Request, h)
        except:
            # traceback.print_exc()
            await connection.Close()
