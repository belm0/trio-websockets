__all__ = [
    'ConnectionClosed',
    'InvalidHandshake',
    'InvalidState',
    'InvalidURI',
    'PayloadTooBig',
    'WebSocketProtocolError',
]


class InvalidHandshake(Exception):
    """
    Exception raised when a handshake request or response is invalid.

    """


class AbortHandshake(InvalidHandshake):
    """
    Exception raised to abort a handshake and return a HTTP response.
    """
    def __init__(self, status, headers, body=b''):
        self.status = status
        self.headers = headers
        self.body = body
        message = "HTTP {}, {} headers, {} bytes".format(
            status, len(headers), len(body))
        super().__init__(message)


class InvalidState(Exception):
    """
    Exception raised when an operation is forbidden in the current state.

    """


CLOSE_CODES = {
    1000: "OK",
    1001: "going away",
    1002: "protocol error",
    1003: "unsupported type",
    # 1004 is reserved
    1005: "no status code [internal]",
    1006: "connection closed abnormally [internal]",
    1007: "invalid data",
    1008: "policy violation",
    1009: "message too big",
    1010: "extension required",
    1011: "unexpected error",
    1015: "TLS failure [internal]",
}


class ConnectionClosed(InvalidState):
    """
    Exception raised when trying to read or write on a closed connection.

    Provides the connection close code and reason in its ``code`` and
    ``reason`` attributes respectively.

    """
    def __init__(self, code, reason):
        self.code = code
        self.reason = reason
        message = "WebSocket connection is closed: "
        if 3000 <= code < 4000:
            explanation = "registered"
        elif 4000 <= code < 5000:
            explanation = "private use"
        else:
            explanation = CLOSE_CODES.get(code, "unknown")
        message += "code = {} ({}), ".format(code, explanation)
        if reason:
            message += "reason = {}".format(reason)
        else:
            message += "no reason"
        super().__init__(message)


class InvalidURI(Exception):
    """
    Exception raised when an URI isn't a valid websocket URI.

    """


class PayloadTooBig(Exception):
    """
    Exception raised when a frame's payload exceeds the maximum size.

    """


class WebSocketProtocolError(Exception):
    """
    Internal exception raised when the remote side breaks the protocol.

    """
