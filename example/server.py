#!/usr/bin/env python

# WS server example

import trio
import trio_websockets

async def hello(websocket, path):
    name = await websocket.recv()
    print(f"< {name}")

    greeting = f"Hello {name}!"

    await websocket.send(greeting)
    print(f"> {greeting}")


async def main():
	await trio_websockets.serve(hello, 'localhost', 8765)


trio.run(main)