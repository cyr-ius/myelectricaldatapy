"""Class for Enedis Authentication (http://www.myelectricaldata.fr)."""

from __future__ import annotations

import asyncio
import json
import logging
import socket
from typing import Any

import async_timeout
from aiohttp import ClientError, ClientSession

from .const import TIMEOUT, URL
from .exceptions import (
    EnedisException,
    HttpRequestError,
    LimitReached,
    TimeoutExceededError,
)

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
        url = f"{URL}/{path}"
        if headers := kwargs.get("headers", {}):
            headers = dict(headers)

        headers.update(
            {"Content-Type": "application/json", "Authorization": self.token}
        )

        try:
            async with async_timeout.timeout(TIMEOUT):
                _LOGGER.debug("Request %s (%s)", url, kwargs)
                response = await self.session.request(
                    method, url, **kwargs, headers=headers
                )
        except (asyncio.CancelledError, asyncio.TimeoutError) as error:
            raise TimeoutExceededError(
                "Timeout occurred while connecting to MyElectricalData."
            ) from error
        except (ClientError, socket.gaierror) as error:
            raise HttpRequestError(
                "Error occurred while communicating with MyElectricalData."
            ) from error

        content_type = response.headers.get("Content-Type", "")
        if response.status // 100 in [4, 5]:
            contents = await response.read()
            response.close()

            message = contents.decode("utf8")
            if content_type == "application/json":
                if response.status == 409:
                    raise LimitReached(response.status, json.loads(message))
                raise EnedisException(response.status, json.loads(message))
            raise EnedisException(response.status, {"message": message})

        if "application/json" in content_type:
            rslt = await response.json()
            _LOGGER.debug("Response %s", rslt)
            return rslt

        rslt = await response.text()
        _LOGGER.debug("Response %s", rslt)
        return rslt
