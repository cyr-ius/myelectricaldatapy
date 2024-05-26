"""Class for Enedis Authentication (http://www.myelectricaldata.fr)."""

from __future__ import annotations

import asyncio
import json
import logging
import socket
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

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
        self, session: ClientSession, token: str, timeout: int = TIMEOUT
    ) -> None:
        """Init."""
        self.token = token
        self.timeout = timeout
        self.session = session

    async def async_request(self, path: str, method: str = "get", **kwargs: Any) -> Any:
        """Request session."""
        kwargs.setdefault("headers", {})
        kwargs["headers"].update(
            {"Content-Type": "application/json", "Authorization": self.token}
        )

        try:
            async with asyncio.timeout(self.timeout):
                _LOGGER.debug("Request: %s (%s) - %s", path, method, kwargs.get("json"))
                response = await self.session.request(method, f"{URL}/{path}", **kwargs)
                contents = await response.read()
                response.raise_for_status()
        except (asyncio.CancelledError, asyncio.TimeoutError) as error:
            raise TimeoutExceededError(
                "Timeout occurred while connecting to MyElectricalData."
            ) from error
        except ClientResponseError:
            message = contents.decode("utf8")
            if "application/json" in response.headers.get("Content-Type", ""):
                if response.status == 409:
                    raise LimitReached(json.loads(message))
                raise EnedisException(json.loads(message))
            raise EnedisException({"message": message})
        except (ClientError, socket.gaierror) as error:
            raise HttpRequestError(
                "Error occurred while communicating with MyElectricalData."
            ) from error

        return (
            await response.json()
            if "application/json" in response.headers.get("Content-Type", "")
            else await response.text()
        )
