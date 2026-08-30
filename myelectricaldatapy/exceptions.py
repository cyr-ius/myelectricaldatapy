"""Class exception."""


class EnedisException(Exception):
    """Enedis exception."""


class LimitReached(EnedisException):
    """Limit reached exception."""


class TimeoutExceededError(EnedisException):
    """Timeout exceeded exception."""


class HttpRequestError(EnedisException):
    """Http request error."""


class PayloadError(EnedisException):
    """Raised when an API payload cannot be decoded or does not match the schema."""


class AnalyticsError(EnedisException):
    """Raised when analytics computation fails on the provided dataset."""
