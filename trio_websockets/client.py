"""
The :mod:`websockets.client` module defines a simple WebSocket client API.

"""

import trio
from wsproto.connection import ConnectionType, WSConnection
from wsproto.events import ConnectionEstablished
from wsproto.extensions import PerMessageDeflate
from .exceptions import WebSocketProtocolError
from .protocol import WebSocketCommonProtocol
from .uri import parse_uri


__all__ = ['connect', 'WebSocketClientProtocol']


class WebSocketClientProtocol(WebSocketCommonProtocol):
    """
    Complete WebSocket client implementation.

    This class inherits most of its methods from
    :class:`~websockets.protocol.WebSocketCommonProtocol`.
    """

    is_client = True
    side = 'client'

    def __init__(self, stream, *,
                 origin=None, extensions=None, subprotocols=None,
                 extra_headers=None, **kwds):
        self.stream = stream
        self.origin = origin
        self.available_extensions = extensions
        self.available_subprotocols = subprotocols
        self.extra_headers = extra_headers
        super().__init__(**kwds)
    
    async def handshake(self, wsuri, origin=None, available_extensions=None,
                  available_subprotocols=None, extra_headers=None):
        """
        Perform the client side of the opening handshake.

        If provided, ``origin`` sets the Origin HTTP header.

        If provided, ``available_extensions`` is a list of supported
        extensions in the order in which they should be used.

        If provided, ``available_subprotocols`` is a list of supported
        subprotocols in order of decreasing preference.

        If provided, ``extra_headers`` sets additional HTTP request headers.
        It must be a mapping or an iterable of (name, value) pairs.

        Raise :exc:`~websockets.exceptions.InvalidHandshake` if the handshake
        fails.
        """
        if wsuri.port == (443 if wsuri.secure else 80):     # pragma: no cover
            host = wsuri.host
        else:
            host = '{}:{}'.format(wsuri.host, wsuri.port)

        self.wsproto = WSConnection(
            ConnectionType.CLIENT,
            host=host,
            resource=wsuri.resource_name,
            extensions=available_extensions,
            subprotocols=available_subprotocols
        )

        # Not supported by wsproto?
        # if wsuri.user_info:
        #     set_header(*basic_auth_header(*wsuri.user_info))

        # Not supported by wsproto?
        # if origin is not None:
        #     set_header('Origin', origin)

        # Not supported by wsproto?
        # if extra_headers is not None:
        #     if isinstance(extra_headers, collections.abc.Mapping):
        #         extra_headers = extra_headers.items()
        #     for name, value in extra_headers:
        #         set_header(name, value)

        # Supported by wsproto?
        # if not is_header_set('User-Agent'):
        #     set_header('User-Agent', USER_AGENT)

        to_send = self.wsproto.bytes_to_send()
        if to_send:
            await self.stream.send_all(to_send)

        event = await self.read_until_next_event()
        if not isinstance(event, ConnectionEstablished):
            raise WebSocketProtocolError('Unexpected event: {}'.format(event))

        # wsproto should tell us these
        self.extensions = event.extensions
        self.subprotocol = event.subprotocol


class Connect:
    """
    Connect to the WebSocket server at the given ``uri``.

    :func:`connect` returns an awaitable. Awaiting it yields an instance of
    :class:`WebSocketClientProtocol` which can then be used to send and
    receive messages.

    On Python ≥ 3.5.1, :func:`connect` can be used as a asynchronous context
    manager. In that case, the connection is closed when exiting the context.

    The ``create_protocol`` parameter allows customizing the asyncio protocol
    that manages the connection. It should be a callable or class accepting
    the same arguments as :class:`WebSocketClientProtocol` and returning a
    :class:`WebSocketClientProtocol` instance. It defaults to
    :class:`WebSocketClientProtocol`.

    :func:`connect` also accepts the following optional arguments:

    * ``origin`` sets the Origin HTTP header
    * ``extensions`` is a list of supported extensions in order of
      decreasing preference
    * ``subprotocols`` is a list of supported subprotocols in order of
      decreasing preference
    * ``extra_headers`` sets additional HTTP request headers – it can be a
      mapping or an iterable of (name, value) pairs
    * ``compression`` is a shortcut to configure compression extensions;
      by default it enables the "permessage-deflate" extension; set it to
      ``None`` to disable compression

    :func:`connect` raises :exc:`~websockets.uri.InvalidURI` if ``uri`` is
    invalid and :exc:`~websockets.handshake.InvalidHandshake` if the opening
    handshake fails.

    """

    def __init__(self, uri, *,
                 create_protocol=None,
                 timeout=10, max_size=2 ** 20,
                 origin=None, extensions=None, subprotocols=None,
                 extra_headers=None, compression='deflate',
                 ssl_context=None):
        
        if create_protocol is None:
            create_protocol = WebSocketClientProtocol

        wsuri = parse_uri(uri)

        if compression == 'deflate':
            if extensions is None:
                extensions = []
            if not any(
                extension_factory.name == PerMessageDeflate.name
                for extension_factory in extensions
            ):
                extensions.append(PerMessageDeflate())
        elif compression is not None:
            raise ValueError("Unsupported compression: {}".format(compression))

        self.factory = lambda stream: create_protocol(stream,
            host=wsuri.host, port=wsuri.port, secure=wsuri.secure,
            timeout=timeout, max_size=max_size,
            origin=origin, extensions=extensions, subprotocols=subprotocols,
            extra_headers=extra_headers,
        )

        # TODO: Bring back socket support, removed during port
        # if sock is None:
        #     host, port = wsuri.host, wsuri.port
        # else:
        #     # If sock is given, host and port mustn't be specified.
        #     host, port = None, None

        self._wsuri = wsuri
        self._origin = origin
        self._ssl_context = ssl_context
    
    async def __aenter__(self):
        wsuri = self._wsuri

        try:
            if wsuri.secure:
                stream = await trio.open_ssl_over_tcp_stream(
                    wsuri.host, wsuri.port, https_compatible=True,
                    ssl_context=self._ssl_context)
            else:
                stream = await trio.open_tcp_stream(wsuri.host, wsuri.port)
        except OSError as exc:
            # Because augustin/websockets raises a ConnectionError.
            raise ConnectionError() from exc
        
        protocol = self.factory(stream)

        try:
            await protocol.handshake(
                self._wsuri, origin=self._origin,
                available_extensions=protocol.available_extensions,
                available_subprotocols=protocol.available_subprotocols,
                extra_headers=protocol.extra_headers,
            )
        except Exception:
            await protocol.fail_connection()
            raise

        self.ws_client = protocol
        return protocol
    
    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.ws_client.close()


connect = Connect
