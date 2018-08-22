"""
The :mod:`websockets.protocol` module handles WebSocket control and data
frames as specified in `sections 4 to 8 of RFC 6455`_.

.. _sections 4 to 8 of RFC 6455: http://tools.ietf.org/html/rfc6455#section-4

"""

import logging

import trio
from wsproto.connection import ConnectionState
from wsproto import events

from .utils import encode_data
from .exceptions import (
    ConnectionClosed, InvalidState, PayloadTooBig, WebSocketProtocolError
)


__all__ = ['WebSocketCommonProtocol']

logger = logging.getLogger(__name__)


class WebSocketCommonProtocol:
    """
    This class implements common parts of the WebSocket protocol.

    It assumes that the WebSocket connection is established. The handshake is
    managed in subclasses such as
    :class:`~websockets.server.WebSocketServerProtocol` and
    :class:`~websockets.client.WebSocketClientProtocol`.

    On Python ≥ 3.6, :class:`WebSocketCommonProtocol` instances support
    asynchronous iteration::

        async for message in websocket:
            await process(message)

    The iterator yields incoming messages. It exits normally when the
    connection is closed with the status code 1000 (OK) or 1001 (going away).
    It raises a :exc:`~websockets.exceptions.ConnectionClosed` exception when
    the connection is closed with any other status code.

    The ``host``, ``port`` and ``secure`` parameters are simply stored as
    attributes for handlers that need them.

    The ``timeout`` parameter defines the maximum wait time in seconds for
    completing the closing handshake and, only on the client side, for
    terminating the TCP connection. :meth:`close()` will complete in at most
    ``4 * timeout`` on the server side and ``5 * timeout`` on the client side.

    The ``max_size`` parameter enforces the maximum size for incoming messages
    in bytes. The default value is 1MB. ``None`` disables the limit. If a
    message larger than the maximum size is received, :meth:`recv()` will
    raise :exc:`~websockets.exceptions.ConnectionClosed` and the connection
    will be closed with status code 1009.

    As soon as the HTTP request and response in the opening handshake are
    processed, the request path is available in the :attr:`path` attribute,
    and the request and response HTTP headers are available:

    * as a :class:`~http.client.HTTPMessage` in the :attr:`request_headers`
      and :attr:`response_headers` attributes
    * as an iterable of (name, value) pairs in the :attr:`raw_request_headers`
      and :attr:`raw_response_headers` attributes

    These attributes must be treated as immutable.

    If a subprotocol was negotiated, it's available in the :attr:`subprotocol`
    attribute.

    Once the connection is closed, the status code is available in the
    :attr:`close_code` attribute and the reason in :attr:`close_reason`.

    """
    # There are only two differences between the client-side and the server-
    # side behavior: masking the payload and closing the underlying TCP
    # connection. Set is_client and side to pick a side.
    is_client = None
    side = 'undefined'

    def __init__(self, *,
                 host=None, port=None, secure=None,
                 timeout=10, max_size=2 ** 20):
        self.host = host
        self.port = port
        self.secure = secure
        self.timeout = timeout
        self.max_size = max_size

        # This class implements the data transfer and closing handshake, which
        # are shared between the client-side and the server-side.
        # Subclasses implement the opening handshake and, on success, execute
        # :meth:`connection_open()` to change the state to OPEN.

        # HTTP protocol parameters.
        self.path = None
        self.request_headers = None
        self.raw_request_headers = None
        self.response_headers = None
        self.raw_response_headers = None

        # WebSocket protocol parameters.
        self.extensions = []
        self.subprotocol = None

        # The close code and reason are set when receiving a close frame or
        # losing the TCP connection.
        self.close_code = None
        self.close_reason = ''

        # Exception that occurred during data transfer, if any.
        self.closed_exc = None
        self._events = None

    @property
    def state(self):
        return self.wsproto._state

    # Public API

    @property
    def local_address(self):
        """
        Local address of the connection.

        This is a ``(host, port)`` tuple or ``None`` if the connection hasn't
        been established yet.

        """
        if self.stream is None:
            return None
        return self.stream.socket.getsockname()

    @property
    def remote_address(self):
        """
        Remote address of the connection.

        This is a ``(host, port)`` tuple or ``None`` if the connection hasn't
        been established yet.

        """
        if self.stream is None:
            return None
        return self.stream.socket.getpeername()

    @property
    def open(self):
        """
        This property is ``True`` when the connection is usable.

        It may be used to detect disconnections but this is discouraged per
        the EAFP_ principle. When ``open`` is ``False``, using the connection
        raises a :exc:`~websockets.exceptions.ConnectionClosed` exception.

        .. _EAFP: https://docs.python.org/3/glossary.html#term-eafp

        """
        return self.state is ConnectionState.OPEN

    @property
    def closed(self):
        """
        This property is ``True`` once the connection is closed.

        Be aware that both :attr:`open` and :attr`closed` are ``False`` during
        the opening and closing sequences.

        """
        return self.wsproto.closed

    async def flush_data(self):
        to_send = self.wsproto.bytes_to_send()
        if to_send:
            try:
                await self.stream.send_all(to_send)
                return

            except (trio.BrokenStreamError, trio.ClosedResourceError) as exc:
                self.closed_exc = exc
                await self.fail_connection(1006)

            raise ConnectionClosed(
                self.close_code, self.close_reason) from self.closed_exc

    async def recv(self):
        """
        This coroutine receives the next message.

        It returns a :class:`str` for a text frame and :class:`bytes` for a
        binary frame.

        When the end of the message stream is reached, :meth:`recv` raises
        :exc:`~websockets.exceptions.ConnectionClosed`. This can happen after
        a normal connection closure, a protocol error or a network failure.
        """
        # Don't await self.ensure_open() here because messages could be
        # available in the queue even if the connection is closed.

        # Don't await self.ensure_open() here because messages could be
        # received before the closing frame even if the connection is closing.

        incomplete_data = None

        while True:

            try:
                msg = await self.read_until_next_event()

                if isinstance(msg, events.ConnectionClosed):
                    # Close our socket
                    await self.close_connection()
                    raise ConnectionClosed(msg.code, msg.reason)

                elif isinstance(msg, events.DataReceived):
                    if incomplete_data:
                        incomplete_data += msg.data
                    else:
                        incomplete_data = msg.data

                    if msg.message_finished:
                        return incomplete_data

                elif isinstance(msg, (events.PingReceived, events.PongReceived)):
                    continue

                else:
                    raise WebSocketProtocolError('Unexpected event: {}'.format(msg))

            except ConnectionClosed as exc:
                self.close_code = exc.code
                self.close_reason = exc.reason
                raise

            except trio.Cancelled as exc:
                self.closed_exc = exc
                raise

            except WebSocketProtocolError as exc:
                self.closed_exc = exc
                await self.fail_connection(1002)

            except (trio.BrokenStreamError, trio.ClosedResourceError) as exc:
                self.closed_exc = exc
                await self.fail_connection(1006)

            except UnicodeDecodeError as exc:
                self.closed_exc = exc
                await self.fail_connection(1007)

            except PayloadTooBig as exc:
                self.closed_exc = exc
                await self.fail_connection(1009)

            if self.closed_exc:
                raise ConnectionClosed(
                    self.close_code, self.close_reason) from self.closed_exc

    async def send(self, data):
        """
        This coroutine sends a message.

        It sends :class:`str` as a text frame and :class:`bytes` as a binary
        frame. It raises a :exc:`TypeError` for other inputs.

        """
        await self.ensure_open()

        if not isinstance(data, (str, bytes)):
            raise TypeError("data must be bytes or str")

        self.wsproto.send_data(data)
        await self.flush_data()

    async def close(self, code=1000, reason=''):
        """
        This coroutine performs the closing handshake.

        It waits for the other end to complete the handshake and for the TCP
        connection to terminate.

        It doesn't do anything once the connection is closed. In other words
        it's idemptotent.

        ``code`` must be an :class:`int` and ``reason`` a :class:`str`.
        """

        self.close_reason = reason
        self.close_code = code

        if self.state == ConnectionState.OPEN:
            with trio.move_on_after(self.timeout) as cancel_scope:
                try:
                    self.wsproto.close()
                    await self.flush_data()
                except trio.ClosedResourceError:
                    pass

            if cancel_scope.cancelled_caught:
                # If the close frame cannot be sent because the send buffers
                # are full, the closing handshake won't complete anyway.
                # Fail the connection to shut down faster.
                self.fail_connection()

            else:
                # Close the connection client-side
                await self.close_connection()

    async def ping(self, data=None):
        """
        This coroutine sends a ping.

        It returns a :class:`~asyncio.Future` which will be completed when the
        corresponding pong is received and which you may ignore if you don't
        want to wait.

        A ping may serve as a keepalive or as a check that the remote endpoint
        received all messages up to this point::

            pong_waiter = await ws.ping()
            await pong_waiter   # only if you want to wait for the pong

        By default, the ping contains four random bytes. The content may be
        overridden with the optional ``data`` argument which must be of type
        :class:`str` (which will be encoded to UTF-8) or :class:`bytes`.

        """
        await self.ensure_open()

        if data is not None:
            data = encode_data(data)
        self.wsproto.ping(data)
        await self.flush_data()

        # The original lib is trying to match the ping/pong payloads,
        # then making this method wait for the matching pong. Port this.
        # We currently do not, but
        # # Protect against duplicates if a payload is explicitly set.
        # if data in self.pings:
        #     raise ValueError("Already waiting for a pong with the same data")
        #
        # # Generate a unique random payload otherwise.
        # while data is None or data in self.pings:
        #     data = struct.pack('!I', random.getrandbits(32))
        #
        # self.pings[data] = asyncio.Future(loop=self.loop)
        #
        # await self.write_frame(OP_PING, data)
        #
        # return asyncio.shield(self.pings[data])

    async def pong(self, data=b''):
        """
        This coroutine sends a pong.

        An unsolicited pong may serve as a unidirectional heartbeat.

        The content may be overridden with the optional ``data`` argument
        which must be of type :class:`str` (which will be encoded to UTF-8) or
        :class:`bytes`.

        """
        await self.ensure_open()
        data = encode_data(data)
        self.wsproto.pong(data)
        await self.flush_data()

    # Private methods - no guarantees.

    async def ensure_open(self):
        """
        Check that the WebSocket connection is open.

        Raise :exc:`~websockets.exceptions.ConnectionClosed` if it isn't.

        """
        # Handle cases from most common to least common for performance.
        if self.state is ConnectionState.OPEN:
            return

        if self.state is ConnectionState.CLOSED:
            raise ConnectionClosed(
                self.close_code, self.close_reason) from self.closed_exc

        if self.state is ConnectionState.CLOSING:
            # This should never happen, as we always flush after calling wsproto.close()
            raise InvalidState()

        # Control may only reach this point in buggy third-party subclasses.
        assert self.state is ConnectionState.CONNECTING
        raise InvalidState("WebSocket connection isn't established yet")

    def next_event(self):
        """
        Return the next event from wsproto, or None if there is no event.
        """

        # If we do not have an events iterator, create one.
        if not self._events:
            self._events = self.wsproto.events()

        try:
            # Get the next event from the iterator.
            return next(self._events)
        except StopIteration:
            # If the current iterator is at the end, create a new one.
            # While we are processing the old one, new events may have
            # arrived.
            self._events = self.wsproto.events()

            try:
                # Return the first event from the new iterator.
                return next(self._events)
            except StopIteration:
                # There is currently no event.
                return None

    async def read_until_next_event(self):
        """
        Read a single message from the connection.

        Re-assemble data frames if the message is fragmented.

        Return ``None`` when the closing handshake is started.
        """
        while True:
            # Check if an event is available, and if so, return it.
            event = self.next_event()
            if event:
                return event

            # If we are out of events, we need to read some data.
            data = await self.stream.receive_some(4096)
            if data == b'':
                data = None   # wsproto only recognizes this as EOF
            self.wsproto.receive_bytes(data)

            # Is this still necessary?
            # to_send = self.wsproto.bytes_to_send()
            # if to_send:
            #     await self.stream.send_all(to_send)

    async def close_connection(self):
        """
        Closes the actual socket.
        """
        try:
            pass
            # wsproto port: should we do this?
            # # Half-close the TCP connection if possible (when there's no TLS).
            # if self.writer.can_write_eof():
            #     logger.debug(
            #         "%s x half-closing TCP connection", self.side)
            #     self.writer.write_eof()
            #
            #     if (await self.wait_for_connection_lost()):
            #         return
            #     logger.debug(
            #         "%s ! timed out waiting for TCP close", self.side)

        finally:
            # The try/finally ensures that the transport never remains open,
            # even if this coroutine is cancelled (for example).

            # Close the TCP connection. Buffers are flushed asynchronously.
            logger.debug(
                "%s x closing TCP connection", self.side)
            await self.stream.aclose()

    async def fail_connection(self, code=1006, reason=''):
        """
        7.1.7. Fail the WebSocket Connection

        This requires:

        1. Stopping all processing of incoming data, which means cancelling
           :attr:`transfer_data_task`. The close code will be 1006 unless a
           close frame was received earlier.

        2. Sending a close frame with an appropriate code if the opening
           handshake succeeded and the other side is likely to process it.

        3. Closing the connection. :meth:`close_connection` takes care of
           this once :attr:`transfer_data_task` exits after being cancelled.

        (The specification describes these steps in the opposite order.)

        """
        logger.debug(
            "%s ! failing WebSocket connection: %d %s",
            self.side, code, reason,
        )

        self.close_code = code
        self.close_reason = reason

        # Send a close frame when the state is OPEN (a close frame was already
        # sent if it's CLOSING), except when failing the connection because of
        # an error reading from or writing to the network.
        # Don't send a close frame if the connection is broken.
        if code != 1006 and self.state is ConnectionState.OPEN:
            self.wsproto.close()
            await self.flush_data()

        await self.close_connection()


try:
    from .py36.protocol import __aiter__
except (SyntaxError, ImportError):                          # pragma: no cover
    pass
else:
    WebSocketCommonProtocol.__aiter__ = __aiter__
