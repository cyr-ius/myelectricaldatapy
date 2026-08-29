"""Class for Enedis Authentication (http://www.myelectricaldata.fr)."""

import asyncio
from collections.abc import Mapping
import json
import logging
import socket
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

from .exceptions import (
    EnedisException,
    HttpRequestError,
    LimitReached,
    TimeoutExceededError,
)

_LOGGER = logging.getLogger(__name__)
URL = "https://myelectricaldata.fr"


class EnedisAuth:
    """Class for Enedis Auth API."""

    def __init__(self, session: ClientSession, token: str, timeout: int = 30) -> None:
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
        contents = b""

        try:
            async with asyncio.timeout(self.timeout):
                _LOGGER.debug("Request: %s (%s) - %s", path, method, kwargs.get("json"))
                response = await self.session.request(method, f"{URL}/{path}", **kwargs)
                contents = await response.read()
                response.raise_for_status()
        except (TimeoutError, asyncio.CancelledError) as error:
            raise TimeoutExceededError(
                "Timeout occurred while connecting to MyElectricalData."
            ) from error
        except ClientResponseError as error:
            message = contents.decode("utf8")
            headers: Mapping[str, str] = error.headers or {}
            if "application/json" in headers.get("Content-Type", ""):
                msg = json.loads(message)
                if error.status == 409:
                    raise LimitReached(msg.get("detail", msg))
                raise EnedisException(msg.get("detail", msg))
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
