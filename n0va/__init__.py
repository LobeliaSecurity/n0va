import asyncio
import ssl
import glob

import n0va.handler.http as http
import n0va.core.gate as gate
import n0va.util.cert as cert


class Service(http.server):
    def __init__(self, host, port, root_path):
        super().__init__(host=host, port=port)
        self.RootPath = root_path
        self.OnMemoryFiles = {}
        self.SetFilesOnMemory(root_path)

    def SetFilesOnMemory(self, path):
        path = (path + "/**").replace("//", "/")
        l = glob.glob(path, recursive=True)
        self.root_dir = l[0]
        print("Root Directory:", self.root_dir)
        tmp = [a.replace(self.root_dir, "/") for a in l]
        for p in tmp:
            if "." in p:
                p = p.replace("\\", "/")
                extension = p.split(".")[-1]
                if extension in self.MIME:
                    f = open(self.root_dir + p[1:], "rb")
                    data = f.read()
                    f.close()
                    self.OnMemoryFiles[p] = {"MIME": self.MIME[extension], "DATA": data}
                    print("Stored File:", p)

    def Reflesh(self, path):
        try:
            if path.decode("utf-8") in self.OnMemoryFiles:
                p = path.decode("utf-8").replace("\\", "/")
                extension = p.split(".")[-1]
                if extension in self.MIME:
                    f = open(self.root_dir + p[1:], "rb")
                    data = f.read()
                    f.close()
                    self.OnMemoryFiles[p] = {"MIME": self.MIME[extension], "DATA": data}
            else:
                p = path.decode("utf-8").replace("\\", "/")
                extension = p.split(".")[-1]
                if extension in self.MIME:
                    f = open(self.root_dir + p[1:], "rb")
                    data = f.read()
                    f.close()
                self.OnMemoryFiles[p] = {"MIME": self.MIME[extension], "DATA": data}
        except:
            pass

    async def Get(self, connection, Request, ReplyHeader):
        try:
            self.Reflesh(Request["path"])
            await super().Get(connection, Request, ReplyHeader)
        except:
            import traceback
            traceback.print_exc()

    def EnableSSL(self, domain_cert, private_key):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
        ctx.load_cert_chain(domain_cert, private_key)
        self._SSL_Context = ctx

    def Start(self):
        asyncio.run(self.__Start__())
