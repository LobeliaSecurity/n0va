import app.server


class WebsocketSimpleChat:
    def __init__(self) -> None:
        self.connections = {}

    async def WebsocketSimpleChat(self, connection, Request, ReplyHeader):
        self.connections[connection] = None
        try:
            while True:
                opcode, Payload_data = await app.server.service.WebSockRecv(connection)
                await self.spread(opcode, Payload_data)
        except:
            self.connections.pop(connection)

    async def spread(self, opcode, Payload_data):
        for c in self.connections:
            await c.Send(
                await app.server.service.BuildWebSockFrame(opcode, Payload_data)
            )


websocketSimpleChat = WebsocketSimpleChat()


@app.server.service.onWebsocket("/WebsocketSimpleChat.ws")
async def SimpleChat(connection, Request, ReplyHeader):
    await websocketSimpleChat.WebsocketSimpleChat(connection, Request, ReplyHeader)
