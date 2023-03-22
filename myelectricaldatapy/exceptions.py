"""Class exception."""


class EnedisException(Exception):
    """Enedis exception."""


class LimitReached(EnedisException):
    """Limit reached exception."""


class TimeoutExceededError(EnedisException):
    """Limit reached exception."""


class HttpRequestError(EnedisException):
    """Http request error."""
