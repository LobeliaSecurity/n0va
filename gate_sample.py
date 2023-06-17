import asyncio
import ssl

import n0va


class Config:
    class Clover:
        Host = "127.0.0.1"
        Port = 7771
        Context = ssl.create_default_context()
        Context.load_cert_chain(
            "*.lobeliasecurity.com/domain.cert.pem",
            "*.lobeliasecurity.com/private.key.pem"
        )

    class Ivy:
        Host = "127.0.0.1"
        Port = 7772
        Context = ssl.create_default_context()
        Context.load_cert_chain(
            "*.lobeliasecurity.com/domain.cert.pem",
            "*.lobeliasecurity.com/private.key.pem"
        )

    class Azami:
        Host = "127.0.0.1"
        Port = 7773
        Context = ssl.create_default_context()
        Context.load_cert_chain(
            "*.lobeliasecurity.com/domain.cert.pem",
            "*.lobeliasecurity.com/private.key.pem"
        )


gate = n0va.gate.Gate(
    {
        "EntranceHost": "127.0.0.1",
        "EntrancePort": 443,
        "GateMapping": {
            "clover.lobeliasecurity.com": {
                "EntranceSslContext": Config.Clover.Context,
                "Destinations": [
                    {
                        "Host": "127.0.0.1",
                        "Port": 7771,
                    },
                ]
            },
            "ivy.lobeliasecurity.com": {
                "EntranceSslContext": Config.Ivy.Context,
                "Destinations": [
                    {
                        "Host": "127.0.0.1",
                        "Port": 7772,
                    },
                ]
            },
            "azami.lobeliasecurity.com": {
                "EntranceSslContext": Config.Azami.Context,
                "Destinations": [
                    {
                        "Host": "127.0.0.1",
                        "Port": 7773,
                    },
                ]
            },
        }
    }
)


class Nova(n0va.Service):
    def __init__(self, host, port, name: bytes) -> None:
        super().__init__(host=host, port=port)
        self.connections = {}
        self.GetFunctions = {
            "/GetTest.get": self.GetTest
        }
        self.Name = name

    async def GetTest(self, connection, Request, ReplyHeader):
        ReplyHeader["ReplyContent"] = b":".join(
            [b"GET", self.Name, Request["content"]]
        )
        ReplyHeader["Content-Type"] = b"text/html"
        ReplyHeader["Status"] = b"200"
        await self.Reply(connection, ReplyHeader)


clover = Nova(
    host=Config.Clover.Host,
    port=Config.Clover.Port,
    name=b"clover.lobeliasecurity.com"
)
ivy = Nova(
    host=Config.Ivy.Host,
    port=Config.Ivy.Port,
    name=b"ivy.lobeliasecurity.com"
)
azami = Nova(
    host=Config.Azami.Host,
    port=Config.Azami.Port,
    name=b"azami.lobeliasecurity.com"
)


async def start():
    await asyncio.gather(
        clover.__Start__(),
        ivy.__Start__(),
        azami.__Start__(),
        gate.__Start__(),
    )

asyncio.run(start())

