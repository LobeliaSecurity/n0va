# n0va

Python3 simple lightweight async Web(HTTP1.1) server that can handle get/post/websocket and loadbalancing, and no content hosting

## Installation

Install n0va with pip

```bash
pip install git+https://github.com/LobeliaSecurity/n0va.git
```

## Example / 1.0.0

```python
import n0va


class Nova(n0va.Service):
    def __init__(self, host, port) -> None:
        super().__init__(host=host, port=port)
        self.connections = {}
        self.PostFunctions = {
            "/PostTest.post": self.PostTest
        }
        self.GetFunctions = {
            "/GetTest.get": self.GetTest
        }
        self.WebSocketFunctions = {
            "/WebsocketSimpleChat.ws": self.WebsocketSimpleChat
        }
        # self.EnableSSL(
        #     domain_cert="domain.cert.pem",
        #     private_key="private.key.pem"
        # )

    async def PostTest(self, connection, Request, ReplyHeader):
        ReplyHeader["ReplyContent"] = b"POST:" + Request["content"]
        ReplyHeader["Content-Type"] = b"text/html"
        ReplyHeader["Status"] = 200
        await self.Reply(connection, ReplyHeader)

    async def GetTest(self, connection, Request, ReplyHeader):
        ReplyHeader["ReplyContent"] = b"GET:" + Request["content"]
        ReplyHeader["Content-Type"] = b"text/html"
        ReplyHeader["Status"] = 200
        await self.Reply(connection, ReplyHeader)

    async def WebsocketSimpleChat(self, connection, Request, ReplyHeader):
        self.connections[connection] = None
        try:
            while(True):
                opcode, Payload_data = await self.WebSockRecv(connection)
                await self.spread(opcode, Payload_data)

        except:
            self.connections.pop(connection)

    async def spread(self, opcode, Payload_data):
        for c in self.connections:
            await c.Send(
                await self.BuildWebSockFrame(opcode, Payload_data)
            )


nova = Nova(
    host="127.0.0.1",
    port=7777
)

nova.Start()

```

<div align="center">

![](https://repository-images.githubusercontent.com/609695883/30425d66-cee8-461e-a0e6-56aee2f7af1f)

</div>
