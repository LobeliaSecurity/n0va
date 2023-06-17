import asyncio
import ssl

import n0va.handler.http as http
import n0va.core.gate as gate


class Service(http.server):
    def EnableSSL(self, domain_cert, private_key):
        ctx = ssl.create_default_context()
        ctx.load_cert_chain(domain_cert, private_key)
        self._SSL_Context = ctx

    def Start(self):
        asyncio.run(self.__Start__())
