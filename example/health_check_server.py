#!/usr/bin/env python

# WS echo server with HTTP endpoint at /health/

import http
import trio
import trio_websockets


class ServerProtocol(trio_websockets.WebSocketServerProtocol):

    async def process_request(self, path, request_headers):
        if path == '/health/':
            return http.HTTPStatus.OK, [], b'OK\n'

async def echo(websocket, path):
    async for message in websocket:
        await trio_websockets.send(message)


async def main():
    await trio_websockets.serve(
        echo, 'localhost', 8765, create_protocol=ServerProtocol)


trio.run(main)