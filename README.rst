trio-websockets
===============

|rtd| |pypi-v| |pypi-pyversions| |pypi-l| |pypi-wheel|

.. |rtd| image:: https://readthedocs.org/projects/trio-websockets/badge/?version=latest
   :target: https://trio-websockets.readthedocs.io/

.. |pypi-v| image:: https://img.shields.io/pypi/v/trio-websockets.svg
    :target: https://pypi.python.org/pypi/trio-websockets

.. |pypi-pyversions| image:: https://img.shields.io/pypi/pyversions/trio-websockets.svg
    :target: https://pypi.python.org/pypi/trio-websockets

.. |pypi-l| image:: https://img.shields.io/pypi/l/websockets.svg
    :target: https://pypi.python.org/pypi/trio-websockets

.. |pypi-wheel| image:: https://img.shields.io/pypi/wheel/trio-websockets.svg
    :target: https://pypi.python.org/pypi/trio-websockets


What is ``trio-websockets``?
----------------------------

``trio-websockets`` is a library for building WebSocket servers_ and clients_ in
Python, based on ``trio``, an asynchronous I/O framework.

.. _servers: https://github.com/miracle2k/trio-websockets/blob/master/example/server.py
.. _clients: https://github.com/miracle2k/trio-websockets/blob/master/example/client.py


**Currently a work in progress**. The status is:

- The client-side works.
- The server-side does not.


History of the library
----------------------

The code is originally forked from aaugustin's websockets_ library for asyncio,
with the following changes:

- Rip out all asyncio things, replace with trio.
- Rip out the websocket protocol code, replace with wsproto.

.. _websockets: https://github.com/aaugustin/websockets

What remains of the original websockets library itself?

- Most of the remaining code seems to be additional error checking around connection
  state. Rather than a "trio.BrokenStreamError", you will receive a ConnectionClosed
  exception when trying to write on a closed connection.

- The same/very similar interface to websockets, which might be slightly more
  user-friendly than a raw wsproto connection (say, exposing attributes like .subprotocol,
  which wsproto passes along during the ConnectionEstablished event).


TODO
----

- Port the server-side.
- Make the examples run.
- Make the tests run.
- Support for curio.
- Cleanup documentation and readme.
- Experiment with a different architecture, using reader/writer tasks.


How to use it
-------------

Here's a client that says "Hello world!":

.. code:: python

    #!/usr/bin/env python

    import trio
    import trio_websockets

    async def hello(uri):
        async with trio_websockets.connect(uri) as websocket:
            await websocket.send("Hello world!")

    trio.run(hello, 'ws://localhost:8765')

And here's an echo server (for Python ≥ 3.6):

.. code:: python

    #!/usr/bin/env python

    import trio
    import trio_websockets

    async def echo(websocket, path):
        async for message in websocket:
            await websocket.send(message)

    trio.run(trio_websockets.serve, echo, 'localhost', 8765)

Does that look good? `Start here`_.

.. _Start here: https://trio-websockets.readthedocs.io/en/stable/intro.html


What else?
----------

Bug reports, patches and suggestions welcome! Just open an issue_ or send a
`pull request`_.

.. _issue: https://github.com/miracle2k/trio-websockets/issues/new
.. _pull request: https://github.com/miracle2k/trio-websockets/compare/

``trio-websockets`` is released under the `BSD license`_.

.. _BSD license: https://trio-websockets.readthedocs.io/en/stable/license.html
