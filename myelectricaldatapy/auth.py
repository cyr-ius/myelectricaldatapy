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
    PayloadError,
    TimeoutExceededError,
)

logger = logging.getLogger(__name__)
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
                logger.debug("Request: %s (%s) - %s", path, method, kwargs.get("json"))
                response = await self.session.request(method, f"{URL}{path}", **kwargs)
                contents = await response.read()
                response.raise_for_status()
        except (TimeoutError, asyncio.CancelledError) as error:
            raise TimeoutExceededError(
                "Timeout occurred while connecting to MyElectricalData."
            ) from error
        except ClientResponseError as error:
            message = contents.decode("utf8", errors="replace")
            headers: Mapping[str, str] = error.headers or {}
            if "application/json" in headers.get("Content-Type", ""):
                try:
                    msg = json.loads(message)
                except json.JSONDecodeError:
                    raise EnedisException({"message": message}) from error
                detail = msg.get("detail", msg) if isinstance(msg, Mapping) else msg
                if error.status == 409:
                    raise LimitReached(detail) from error
                raise EnedisException(detail) from error
            raise EnedisException({"message": message}) from error
        except (ClientError, socket.gaierror) as error:
            raise HttpRequestError(
                "Error occurred while communicating with MyElectricalData."
            ) from error

        if "application/json" not in response.headers.get("Content-Type", ""):
            return await response.text()

        try:
            return await response.json()
        except (ClientError, ValueError) as error:
            raise PayloadError(
                "Malformed JSON response from MyElectricalData."
            ) from error
