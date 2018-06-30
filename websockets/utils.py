__all__ = ['encode_data']


def encode_data(data):
    """
    Helper that converts :class:`str` or :class:`bytes` to :class:`bytes`.
    :class:`str` are encoded with UTF-8.
    """
    # Expect str or bytes, return bytes.
    if isinstance(data, str):
        return data.encode('utf-8')
    elif isinstance(data, bytes):
        return data
    else:
        raise TypeError("data must be bytes or str")