import asyncio
import ssl

import n0va.handler.http


class Service(n0va.handler.http.server):
    def EnableSSL(self, domain_cert, private_key):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS)
        ctx.load_cert_chain(domain_cert, private_key)
        ctx.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
        self._SSL_Context = ctx

    def Start(self):
        asyncio.run(self.__Start__())
