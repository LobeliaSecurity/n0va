# n0va

Python3 simple lightweight async Web(HTTP1.1) server that can handle get/post/websocket and loadbalancing, and no content hosting  
Designed for rapid experimentation with silly ideas

## Installation

Install n0va with pip

```bash
pip install git+https://github.com/LobeliaSecurity/n0va.git
```

## Example / 1.0.0

```python

import n0va
import pathlib


class Service(n0va.Service):
    def __init__(self, host, port, root_path):
        super().__init__(host=host, port=port, root_path=root_path)
        # self.EnableSSL(
        #     domain_cert="domain.cert.pem",
        #     private_key="private.key.pem"
        # )


service = Service(
    host="127.0.0.1",
    port=80,
    root_path=pathlib.Path("./documents").resolve().as_posix(),
)


@service.onGet("/GetTest.get")
async def GetTest(connection, Request, ReplyHeader):
    ReplyHeader["ReplyContent"] = b"GET:" + Request["content"]
    ReplyHeader["Content-Type"] = b"text/html"
    ReplyHeader["Status"] = 200
    return ReplyHeader


@service.onPost("/PostTest.get")
async def PostTest(connection, Request, ReplyHeader):
    ReplyHeader["ReplyContent"] = b"POST:" + Request["content"]
    ReplyHeader["Content-Type"] = b"text/html"
    ReplyHeader["Status"] = 200
    return ReplyHeader


class WebsocketSimpleChat:
    def __init__(self) -> None:
        self.connections = {}

    async def WebsocketSimpleChat(self, connection, Request, ReplyHeader):
        self.connections[connection] = None
        try:
            while True:
                opcode, Payload_data = await service.WebSockRecv(connection)
                await self.spread(opcode, Payload_data)
        except:
            self.connections.pop(connection)

    async def spread(self, opcode, Payload_data):
        for c in self.connections:
            await c.Send(await service.BuildWebSockFrame(opcode, Payload_data))


websocketSimpleChat = WebsocketSimpleChat()


@service.onWebsocket("/WebsocketSimpleChat.ws")
async def SimpleChat(connection, Request, ReplyHeader):
    await websocketSimpleChat.WebsocketSimpleChat(connection, Request, ReplyHeader)


service.Start()

```

<div align="center">

![](https://repository-images.githubusercontent.com/609695883/30425d66-cee8-461e-a0e6-56aee2f7af1f)

</div>
