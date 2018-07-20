#!/usr/bin/env python

# WSS (WS over TLS) client example, with a self-signed certificate

import trio
import pathlib
import ssl
import trio_websockets

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ssl_context.load_verify_locations(
    pathlib.Path(__file__).with_name('localhost.pem'))

async def hello():
    async with trio_websockets.connect(
            'wss://localhost:8765', ssl=ssl_context) as websocket:
        name = input("What's your name? ")

        await websocket.send(name)
        print(f"> {name}")

        greeting = await websocket.recv()
        print(f"< {greeting}")

trio.run(hello)
