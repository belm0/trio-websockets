#!/usr/bin/env python

# WS client example

import trio
import trio_websockets

async def hello():
    async with trio_websockets.connect(
            'ws://localhost:8765') as websocket:
        name = input("What's your name? ")

        await websocket.send(name)
        await websocket.send(name)
        await websocket.send(name)
        print(f"> {name}")

        greeting = await websocket.recv()
        print(f"< {greeting}")

trio.run(hello)
