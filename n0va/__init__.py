import asyncio
import ssl
import glob
import pathlib

import n0va.handler.http as http
import n0va.core.gate as gate


class OnMemoryFile(pathlib.Path):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.__data__ = None
        self.__previous_st_mtime__ = None
        if len(self.suffixes):
            self.mime = http.MIME[self.suffixes[-1][1:]]

    @property
    def data(self):
        if self.__data__:
            if self.__previous_st_mtime__ != self.stat().st_mtime:
                self.__previous_st_mtime__ = self.stat().st_mtime
                with self.open("rb") as f:
                    self.__data__ = f.read()
        else:
            with self.open("rb") as f:
                self.__data__ = f.read()
        return self.__data__


class Service(http.server):
    def __init__(self, host, port, root_path):
        super().__init__(host=host, port=port)
        self.RootPath = root_path
        self.OnMemoryFiles = {}
        self.SetFilesOnMemory(root_path)

    def onGet(self, path: str):
        def _setFunction(func):
            self.GetFunctions[path] = func

        return _setFunction

    def onPost(self, path: str):
        def _setFunction(func):
            self.PostFunctions[path] = func

        return _setFunction

    def onWebsocket(self, path: str):
        def _setFunction(func):
            self.WebSocketFunctions[path] = func

        return _setFunction

    def SetFilesOnMemory(self, path):
        path_object = pathlib.Path(path)
        self.root_dir = path_object.resolve().as_posix()
        for file_path in path_object.glob("**/*"):
            if file_path.is_file():
                self.OnMemoryFiles[
                    "/" + file_path.relative_to(path_object).as_posix()
                ] = OnMemoryFile(file_path)

    def EnableSSL(self, domain_cert, private_key):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
        ctx.load_cert_chain(domain_cert, private_key)
        self._SSL_Context = ctx

    def Start(self):
        asyncio.run(self.__Start__())
