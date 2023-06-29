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

    async def __start__(self):
        entrance_ssl_context = ssl.create_default_context(
            purpose=ssl.Purpose.CLIENT_AUTH
        )
        entrance_ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
        entrance_ssl_context.sni_callback = self.__gateSniCallback__
        server = await asyncio.start_server(self.__proxyInitHandler__, self.EntranceHost, self.EntrancePort, ssl=entrance_ssl_context)
        async with server:
            await server.serve_forever()

    def Start(self):
        asyncio.run(self.__start__())


class EFI:
    class Bravegate():
        def __init__(self, gate_setting_tree):
            """
            Parameters
            this is non ssl mode
            ----------
            {
                "EntranceHost": ip address or domain name,
                "EntrancePort": port num,
                "gateMapping": {
                    "Host": ip address or domain name ,
                    "Port": port num,
                }
            }
            """
            self.gateSettingTree = gate_setting_tree
            self.EntranceHost = self.gateSettingTree["EntranceHost"]
            self.EntrancePort = self.gateSettingTree["EntrancePort"]
            self.gateMapping = self.gateSettingTree["gateMapping"]
            print(self.gateSettingTree)

        async def onEntranceToDestination(self, B, entrance_connection, destination_connection):
            return B

        async def onDestinationToEntrance(self, B, destination_connection, entrance_connection):
            return B

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
            destination_connection = await self.__openDestination__()
            await self.__opengate__(
                entrance_connection,
                destination_connection
            )

        async def __openDestination__(self):
            reader, writer = await asyncio.open_connection(
                self.gateMapping["Host"],
                self.gateMapping["Port"])
            return n0va.core.stream.AsyncStream(reader, writer)

        async def __proxyInitHandler__(self, reader, writer):
            # Connection MUST be argment
            connection = n0va.core.stream.AsyncStream(reader, writer)
            await self.__proxyHandler__(connection)

        async def __start__(self):
            server = await asyncio.start_server(self.__proxyInitHandler__, self.EntranceHost, self.EntrancePort)
            async with server:
                await server.serve_forever()

        def Start(self):
            asyncio.run(self.__start__())

    class Stablegate():
        def __init__(self, gate_setting_tree):
            """
            Parameters
            ----------
            {
                "EntranceHost": ip address or domain name,
                "EntrancePort": port num,
                "gateMapping": {
                    mapping hostname, this is used for SNI callback. key of "EntranceSslContext": {
                        "EntranceSslContext": ssl.SSLContext of mapping hostname this cant be None object(must TLS),
                        "Destinations": [ this parameter is array because gate has load balancing
                            {
                                "Host": ip address or domain name ,
                                "Port": port num,
                                "SSL": {
                                    "serverName": for checking host name,
                                    "Context": ssl.SSLContext using for conect to Destination or if non TLS, just set None object,
                                }
                            }
                        ]
                    }
                }
            }
            """
            self.gateSettingTree = gate_setting_tree
            self.EntranceHost = self.gateSettingTree["EntranceHost"]
            self.EntrancePort = self.gateSettingTree["EntrancePort"]
            self.gateMapping = self.gateSettingTree["gateMapping"]
            self.DestinationsWeight = {}
            for gate_map in self.gateMapping:
                """
                    self.DestinationsWeight = {
                        gateMapping, mapping hostname: [0, ... Destinations[n]]
                    }
                """
                self.DestinationsWeight[gate_map] = [
                    0 for x in self.gateMapping[gate_map]['Destinations']
                ]
                setattr(
                    self.gateMapping[gate_map]["EntranceSslContext"],
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
                ssl_sock.context = self.gateMapping[domain]["EntranceSslContext"]

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
            destination = self.gateMapping[destination_name]["Destinations"][minimum_index]
            destination_context = ssl.create_default_context()
            reader, writer = await asyncio.open_connection(
                destination["Host"],
                destination["Port"],
                ssl=destination_context,
                server_hostname=destination["SSL"]["serverName"])
            self.DestinationsWeight[destination_name][minimum_index] += 1
            return n0va.core.stream.AsyncStream(reader, writer), minimum_index

        async def __proxyInitHandler__(self, reader, writer):
            # Connection MUST be argment
            connection = n0va.core.stream.AsyncStream(reader, writer)
            await self.__proxyHandler__(connection)

        async def __start__(self):
            entrance_ssl_context = ssl.create_default_context(
                purpose=ssl.Purpose.CLIENT_AUTH
            )
            entrance_ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
            entrance_ssl_context.sni_callback = self.__gateSniCallback__
            server = await asyncio.start_server(self.__proxyInitHandler__, self.EntranceHost, self.EntrancePort, ssl=entrance_ssl_context)
            async with server:
                await server.serve_forever()

        def Start(self):
            asyncio.run(self.__start__())

    class Gate():
        def __init__(self, gate_setting_tree):
            """
            Parameters
            ----------
            {
                "EntranceHost": ip address or domain name,
                "EntrancePort": port num,
                "gateMapping": {
                    mapping hostname, this is used for SNI callback. key of "EntranceSslContext": {
                        "EntranceSslContext": ssl.SSLContext of mapping hostname this cant be None object(must TLS),
                        "Destinations": [ this parameter is array because gate has load balancing
                            {
                                "Host": ip address or domain name ,
                                "Port": port num,
                                "SSL": {
                                    "serverName": for checking host name,
                                    "Context": ssl.SSLContext using for conect to Destination or if non TLS, just set None object,
                                }
                            }
                        ]
                    }
                }
            }
            """
            self.gateSettingTree = gate_setting_tree
            self.EntranceHost = self.gateSettingTree["EntranceHost"]
            self.EntrancePort = self.gateSettingTree["EntrancePort"]
            self.gateMapping = self.gateSettingTree["gateMapping"]
            self.EntranceSslContextTree = {}
            self.DestinationsWeight = {}
            for gate_map in self.gateMapping:
                """
                    self.DestinationsWeight = {
                        gateMapping, mapping hostname: [0, ... Destinations[n]]
                    }
                """
                self.DestinationsWeight[gate_map] = [
                    0 for x in self.gateMapping[gate_map]['Destinations']
                ]
                setattr(
                    self.gateMapping[gate_map]["EntranceSslContext"],
                    "DomainName",
                    gate_map
                )
                self.EntranceSslContextTree[gate_map] = self.gateMapping[gate_map]["EntranceSslContext"]

        async def onEntranceToDestination(self, B, entrance_connection, destination_connection):
            return B

        async def onDestinationToEntrance(self, B, destination_connection, entrance_connection):
            return B

        def __gateSniCallback__(self, ssl_sock, domain, ssl_ctx, as_callback=True):
            try:
                ssl_sock.context = self.gateMapping[domain]["EntranceSslContext"]

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

        async def __gateInitHandler__(self, reader, writer):
            # Connection MUST be argment
            entrance_connection = n0va.core.stream.AsyncManualSslStream(
                reader, writer)
            await entrance_connection.ReadClientHello()
            server_name = entrance_connection.serverName
            if(server_name is None):
                server_name = [
                    x for x in self.EntranceSslContextTree][0]

            minimum_index = self.DestinationsWeight[server_name].index(
                min(self.DestinationsWeight[server_name]))
            destination = self.gateMapping[server_name]["Destinations"][minimum_index]

            destination_connection = None
            if(entrance_connection.isTryingHandshake):
                if(destination["SSL"] is not None):
                    # open ssl connection
                    destination_context = ssl.create_default_context()
                    if(len(entrance_connection.ALPN) > 0):
                        destination_context.set_alpn_protocols(
                            entrance_connection.ALPN
                        )
                    reader, writer = await asyncio.open_connection(
                        destination["Host"],
                        destination["Port"],
                        ssl=destination_context,
                        server_hostname=destination["SSL"]["serverName"])
                    destination_connection = n0va.core.stream.AsyncStream(
                        reader, writer)
                    # create entrance ssl context
                    selected_alpn = destination_connection._Writer.get_extra_info(
                        "ssl_object"
                    ).selected_alpn_protocol()
                    entrance_ssl_context = self.EntranceSslContextTree[server_name]
                    if(selected_alpn is not None):
                        entrance_ssl_context.set_alpn_protocols(
                            [selected_alpn])
                    entrance_connection.SslContext = entrance_ssl_context
                    # handshake entrance
                    await entrance_connection.Handshake()
                else:
                    entrance_ssl_context = self.EntranceSslContextTree[server_name]
                    entrance_connection.SslContext = entrance_ssl_context
                    # handshake entrance
                    await entrance_connection.Handshake()
                    reader, writer = await asyncio.open_connection(
                        destination["Host"],
                        destination["Port"])
                    destination_connection = n0va.core.stream.AsyncStream(
                        reader, writer)
            else:
                if(destination["SSL"] is not None):
                    destination_context = ssl.create_default_context()
                    reader, writer = await asyncio.open_connection(
                        destination["Host"],
                        destination["Port"],
                        ssl=destination_context,
                        server_hostname=destination["SSL"]["serverName"])
                    destination_connection = n0va.core.stream.AsyncStream(
                        reader, writer)
                else:
                    reader, writer = await asyncio.open_connection(
                        destination["Host"],
                        destination["Port"])
                    destination_connection = n0va.core.stream.AsyncStream(
                        reader, writer)

                await destination_connection.Send(
                    await self.onEntranceToDestination(
                        entrance_connection._client_hello_buf, entrance_connection, destination_connection)
                )
                entrance_connection = n0va.core.stream.AsyncStream(
                    entrance_connection._Reader, entrance_connection._Writer
                )

            self.DestinationsWeight[server_name][minimum_index] += 1
            await self.__opengate__(
                entrance_connection,
                destination_connection
            )
            self.DestinationsWeight[server_name][minimum_index] -= 1

        async def __start__(self):
            server = await asyncio.start_server(self.__gateInitHandler__, self.EntranceHost, self.EntrancePort)
            async with server:
                await server.serve_forever()

        def Start(self):
            asyncio.run(self.__start__())
