import asyncio
import ssl

import n0va.handler.http as http
import n0va.core.gate as gate
import n0va.util.cert as cert


class Service(http.server):
    def EnableSSL(self, domain_cert, private_key):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
        ctx.load_cert_chain(domain_cert, private_key)
        self._SSL_Context = ctx

    def Start(self):
        asyncio.run(self.__Start__())
