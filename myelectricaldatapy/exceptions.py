import logging

_LOGGER = logging.getLogger(__name__)


class EnedisException(Exception):
    """Enedis exception."""


class LimitReached(EnedisException):
    """Limit reached exception."""


class GatewayException(EnedisException):
    """Enedis gateway error."""
