import asyncio


class AsyncStream():
    def __init__(self, reader, writer):
        self._Reader = reader
        self._Writer = writer
        self._Recvsize = 1024 * 4
        self._Timeout = 60.0 * 15
    ### Send ###

    async def Send(self, b):
        self._Writer.write(b)
        await asyncio.wait_for(self._Writer.drain(), timeout=self._Timeout)

    async def Recv(self, i=0, timeout=0):
        R = b""
        if(i == 0):
            i = self._Recvsize
        if(timeout == 0):
            timeout = self._Timeout
        R = await asyncio.wait_for(self._Reader.read(i), timeout=timeout)
        return(R)

    async def Close(self):
        self._Writer.close()

    def isOnline(self):
        return(not self._Writer.is_closing())
