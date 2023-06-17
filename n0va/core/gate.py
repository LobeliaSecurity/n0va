import asyncio
import ssl
import n0va.core.stream


class Gate():
    def __init__(self, gate_setting_tree):
        """
        Parameters
        ----------
        {
            "EntranceHost": ip address or domain name,
            "EntrancePort": port num,
            "GateMapping": {
                mapping hostname, this is used for SNI callback. key of "EntranceSslContext": {
                    "EntranceSslContext": ssl.SSLContext of mapping hostname this cant be None object(must TLS),
                    "Destinations": [ this parameter is array because gate has load balancing
                        {
                            "Host": ip address or domain name ,
                            "Port": port num,
                        }
                    ]
                }
            }
        }
        """
        self.gateSettingTree = gate_setting_tree
        self.EntranceHost = self.gateSettingTree["EntranceHost"]
        self.EntrancePort = self.gateSettingTree["EntrancePort"]
        self.GateMapping = self.gateSettingTree["GateMapping"]
        self.DestinationsWeight = {}
        for gate_map in self.GateMapping:
            """
                self.DestinationsWeight = {
                    GateMapping, mapping hostname: [0, ... Destinations[n]]
                }
            """
            self.DestinationsWeight[gate_map] = [
                0 for x in self.GateMapping[gate_map]['Destinations']
            ]
            setattr(
                self.GateMapping[gate_map]["EntranceSslContext"],
                "DomainName",
                gate_map
            )
        print(self.gateSettingTree)
        print(self.DestinationsWeight)

    async def onEntranceToDestination(self, B, entrance_connection, destination_connection):
        return B

    async def onDestinationToEntrance(self, B, destination_connection, entrance_connection):
        return B

    def __gateSniCallback__(self, ssl_sock, domain, ssl_ctx, as_callback=True):
        try:
            ssl_sock.context = self.GateMapping[domain]["EntranceSslContext"]
        except:
            raise ssl.ALERT_DESCRIPTION_HANDSHAKE_FAILURE
        return None

    async def __getDestinationName__(self, entrance_connection):
        return entrance_connection._Writer.get_extra_info("ssl_object").context.DomainName

    async def __opengate__(self, entrance_connection, destination_connection):
        await asyncio.gather(
            self.__entranceHandler__(
                entrance_connection, destination_connection),
            self.__transportHandler__(
                destination_connection, entrance_connection)
        )

    async def __entranceHandler__(self, entrance_connection, destination_connection):
        try:
            while(entrance_connection.isOnline()):
                buf = await entrance_connection.Recv()
                event_handling_result_buf = await self.onEntranceToDestination(buf, entrance_connection, destination_connection)
                if(buf == b""):
                    await entrance_connection.Close()
                    await destination_connection.Close()
                    break
                if(event_handling_result_buf is not None):
                    await destination_connection.Send(event_handling_result_buf)
        except:
            await entrance_connection.Close()
            await destination_connection.Close()

    async def __transportHandler__(self, destination_connection, entrance_connection):
        try:
            while(destination_connection.isOnline()):
                buf = await destination_connection.Recv()
                event_handling_result_buf = await self.onDestinationToEntrance(buf, destination_connection, entrance_connection)
                if(buf == b""):
                    await entrance_connection.Close()
                    await destination_connection.Close()
                    break
                if(event_handling_result_buf is not None):
                    await entrance_connection.Send(event_handling_result_buf)
        except:
            await entrance_connection.Close()
            await destination_connection.Close()

    async def __proxyHandler__(self, entrance_connection):
        destination_name = await self.__getDestinationName__(entrance_connection)
        destination_connection, destination_index = await self.__openDestination__(
            destination_name
        )
        await self.__opengate__(
            entrance_connection,
            destination_connection
        )
        self.DestinationsWeight[destination_name][destination_index] -= 1

    async def __openDestination__(self, destination_name):
        minimum_index = self.DestinationsWeight[destination_name].index(
            min(self.DestinationsWeight[destination_name]))
        destination = self.GateMapping[destination_name]["Destinations"][minimum_index]
        # destination_context = ssl.create_default_context()
        reader, writer = await asyncio.open_connection(
            destination["Host"],
            destination["Port"],
            # ssl=destination_context,
            # server_hostname=destination["SSL"]["serverName"]
        )
        self.DestinationsWeight[destination_name][minimum_index] += 1
        return n0va.core.stream.AsyncStream(reader, writer), minimum_index

    async def __proxyInitHandler__(self, reader, writer):
        # Connection MUST be argment
        connection = n0va.core.stream.AsyncStream(reader, writer)
        await self.__proxyHandler__(connection)

    async def __Start__(self):
        entrance_ssl_context = ssl.create_default_context(
            purpose=ssl.Purpose.CLIENT_AUTH
        )
        entrance_ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
        entrance_ssl_context.sni_callback = self.__gateSniCallback__
        server = await asyncio.start_server(self.__proxyInitHandler__, self.EntranceHost, self.EntrancePort, ssl=entrance_ssl_context)
        async with server:
            await server.serve_forever()

    def Start(self):
        asyncio.run(self.__Start__())
