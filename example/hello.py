#!/usr/bin/env python

import trio
import trio_websockets

async def hello(uri):
    async with trio_websockets.connect(uri) as websocket:
        await websocket.send("Hello world!")

trio.run(hello, 'ws://localhost:8765')
