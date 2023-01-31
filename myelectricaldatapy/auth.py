"""Class for Enedis Authentification (http://www.myelectricaldata.fr)."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError, ClientSession

from .exceptions import EnedisException, GatewayException, LimitReached

URL = "https://myelectricaldata.fr"
TIMEOUT = 30

_LOGGER = logging.getLogger(__name__)


class EnedisAuth:
    """Class for Enedis Auth API."""

    def __init__(
        self, token: str, session: ClientSession | None = None, timeout: int = TIMEOUT
    ) -> None:
        """Init."""
        self.token = token
        self.timeout = timeout
        self.session = session if session else ClientSession()

    async def async_close(self) -> None:
        """Close session."""
        await self.session.close()

    async def request(self, path: str, method: str = "GET", **kwargs: Any) -> Any:
        """Request session."""
        response = {}
        if headers := kwargs.get("headers", {}):
            headers = dict(headers)

        headers["Content-Type"] = "application/json"
        headers["Authorization"] = self.token

        try:
            _LOGGER.debug("Request %s/%s (%s)", URL, path, kwargs)
            resp = await self.session.request(
                method, f"{URL}/{path}", **kwargs, headers=headers, timeout=self.timeout
            )
            response = await resp.json()
            _LOGGER.debug("Response %s (%s)", response, resp.status)
            if resp.status == 409:
                raise LimitReached(response.get("detail"))
            if resp.status != 200:
                raise GatewayException(response.get("detail"))
        except ClientError as error:
            raise EnedisException from error
        else:
            return response
