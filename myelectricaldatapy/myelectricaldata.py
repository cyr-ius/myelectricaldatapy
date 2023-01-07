"""Class for Enedis Gateway (http://www.myelectricaldata.fr)."""
from __future__ import annotations

import datetime
import logging
import re
from datetime import datetime as dt

from aiohttp import ClientResponse, ClientSession

from .auth import EnedisAuth, TIMEOUT

_LOGGER = logging.getLogger(__name__)


class EnedisGateway:
    """Class for Enedis Gateway API."""

    def __init__(
        self, token: str, session: ClientSession = None, timeout: int = TIMEOUT
    ):
        """Init."""
        self.auth = EnedisAuth(token, session, timeout)

    async def async_close(self) -> None:
        """Close session."""
        await self.auth.async_close()

    async def async_get_contracts(self, pdl: str) -> ClientResponse:
        """Get contracts."""
        path = f"contracts/{pdl}"
        return await self.auth.request(path=path)

    async def async_get_identity(self, pdl: str) -> ClientResponse:
        """Get identity."""
        path = f"identity/{pdl}"
        return await self.auth.request(path=path)

    async def async_get_addresses(self, pdl: str) -> ClientResponse:
        """Get addresses."""
        path = f"addresses/{pdl}"
        return await self.auth.request(path=path)


class EnedisByPDL(EnedisGateway):
    """Get data of pdl."""

    def __init__(
        self, token: str, session: ClientSession = None, timeout: int = TIMEOUT
    ):
        """Initialize."""
        super().__init__(token, session, timeout)
        self.offpeaks = []

    async def async_fetch_datas(
        self, service: str, start: datetime, end: datetime, pdl: str
    ) -> ClientResponse:
        """Get datas."""
        start = start.strftime("%Y-%m-%d")
        end = end.strftime("%Y-%m-%d")
        path = f"{service}/{pdl}/start/{start}/end/{end}"
        return await self.auth.request(path=path)

    async def async_get_max_power(
        self, start: datetime, end: datetime, pdl: str
    ) -> ClientResponse:
        """Get consumption max power."""
        start = start.strftime("%Y-%m-%d")
        end = end.strftime("%Y-%m-%d")
        path = f"daily_consumption_max_power/{pdl}/start/{start}/end/{end}"
        return await self.auth.request(path=path)

    async def async_get_contract(self, pdl: str) -> dict(str, str):
        """Return all."""
        contract = {}
        contracts = await self.async_get_contracts(pdl)
        usage_points = contracts.get("customer", {}).get("usage_points", "")
        for usage_point in usage_points:
            if usage_point.get("usage_point", {}).get("usage_point_id") == pdl:
                contract = usage_point.get("contracts", {})
                if offpeak_hours := contract.get("offpeak_hours"):
                    self.offpeaks = re.findall("(?:(\\w+)-(\\w+))+", offpeak_hours)
        return contract

    async def async_get_address(self, pdl: str) -> dict(str, str):
        """Return all."""
        address = {}
        addresses = await self.async_get_addresses(pdl)
        usage_points = addresses.get("customer", {}).get("usage_points", "")
        for usage_point in usage_points:
            if usage_point.get("usage_point", {}).get("usage_point_id") == pdl:
                address = usage_point.get("usage_point")
        return address

    async def async_has_offpeak(self, pdl: str) -> bool:
        """Has offpeak hours."""
        if not self.offpeaks:
            await self.async_get_contract(pdl)
        return len(self.offpeaks) > 0

    async def async_check_offpeak(self, start: datetime, pdl: str) -> bool:
        """Return offpeak status."""
        if await self.async_has_offpeak(pdl) is True:
            start_time = start.time()
            for range_time in self.offpeaks:
                starting = dt.strptime(range_time[0], "%HH%M").time()
                ending = dt.strptime(range_time[1], "%HH%M").time()
                if start_time > starting and start_time <= ending:
                    return True
        return False
