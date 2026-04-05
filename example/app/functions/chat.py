import app.server
import n0va


class WebsocketSimpleChat:
    def __init__(self) -> None:
        self.sessions: dict = {}

    async def WebsocketSimpleChat(
        self, session: n0va.WebSocketSession, ctx: n0va.RequestContext
    ):
        self.sessions[session] = None
        try:
            while True:
                r = await session.recv_frame()
                if r is False:
                    break
                opcode, payload_data = r
                await self.spread(opcode, payload_data)
        except Exception:
            pass
        finally:
            self.sessions.pop(session, None)

    async def spread(self, opcode, payload_data):
        for s in list(self.sessions):
            await s.send_frame(opcode, payload_data)


websocketSimpleChat = WebsocketSimpleChat()


@app.server.service.onWebsocket("/WebsocketSimpleChat.ws")
async def SimpleChat(session: n0va.WebSocketSession, ctx: n0va.RequestContext):
    await websocketSimpleChat.WebsocketSimpleChat(session, ctx)
