"""Class for Enedis Gateway (http://www.myelectricaldata.fr)."""

from __future__ import annotations

from datetime import date, datetime as dt, timedelta
import logging
import re
from types import TracebackType
from typing import Any, Generator, cast

from .auth import EnedisAuth
from .const import DAILY_CONSUM, DAILY_PROD, DETAIL_CONSUM, DETAIL_PROD, TIMEOUT

_LOGGER = logging.getLogger(__name__)


class Enedis:
    """Get data of pdl."""

    def __init__(
        self, token: str, session: Any | None = None, timeout: int = TIMEOUT
    ) -> None:
        """Initialize."""
        self.auth = EnedisAuth(token, session, timeout)
        self.offpeaks: list[str] = []
        self.dt_offpeak: list[dt] = []
        self.last_access: date | None = None

    async def async_fetch_datas(
        self, service: str, pdl: str, start: dt | None = None, end: dt | None = None
    ) -> Any:
        """Retrieve date from service.

        service:    contracts, identity, contact, addresses,
                    daily_consumption_max_power,
                    daily_consumption, daily_production,
                    consumption_load_curve, production_load_curve
        """
        self.last_access = dt.now()
        path_range = ""
        if start and end:
            start_date = start.strftime("%Y-%m-%d")
            end_date = end.strftime("%Y-%m-%d")
            path_range = f"/start/{start_date}/end/{end_date}"
        path = f"{service}/{pdl}{path_range}"
        return await self.auth.request(path=path)

    async def async_valid_access(self, pdl: str) -> Any:
        """Return valid access."""
        return await self.async_fetch_datas("valid_access", pdl)

    async def async_has_access(self, pdl: str) -> bool:
        """Check valid access."""
        access = await self.async_valid_access(pdl)
        return access.get("valid", False) is True

    async def async_get_contract(self, pdl: str) -> Any:
        """Return contract information."""
        contract = {}
        contracts = await self.async_fetch_datas("contracts", pdl)
        usage_points = contracts.get("customer", {}).get("usage_points", "")
        for usage_point in usage_points:
            if usage_point.get("usage_point", {}).get("usage_point_id") == pdl:
                contract = usage_point.get("contracts", {})
                if offpeak_hours := contract.get("offpeak_hours"):
                    self.offpeaks = re.findall("(?:(\\w+)-(\\w+))+", offpeak_hours)
                    self.dt_offpeak = [
                        (  # type: ignore
                            dt.strptime(offpeak[0], "%HH%M"),
                            dt.strptime(offpeak[1], "%HH%M"),
                        )
                        for offpeak in self.offpeaks
                    ]
        return contract

    async def async_get_contracts(self, pdl: str) -> Any:
        """Return all contracts information."""
        return await self.async_fetch_datas("contracts", pdl)

    async def async_get_address(self, pdl: str) -> Any:
        """Return address information."""
        address = {}
        addresses = await self.async_fetch_datas("addresses", pdl)
        usage_points = addresses.get("customer", {}).get("usage_points", "")
        for usage_point in usage_points:
            if usage_point.get("usage_point", {}).get("usage_point_id") == pdl:
                address = usage_point.get("usage_point")
        return address

    async def async_get_addresses(self, pdl: str) -> Any:
        """Return all addresses information."""
        return await self.async_fetch_datas("addresses", pdl)

    async def async_get_tempo(
        self, start: dt | None = None, end: dt | None = None
    ) -> Any:
        """Return Tempo Day."""
        str_start = (
            start.strftime("%Y-%m-%d") if start else dt.now().strftime("%Y-%m-%d")
        )
        str_end = (
            end.strftime("%Y-%m-%d")
            if end
            else (dt.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        )
        return await self.auth.request(path=f"rte/tempo/{str_start}/{str_end}")

    async def async_get_ecowatt(
        self, start: dt | None = None, end: dt | None = None
    ) -> Any:
        """Return Ecowatt information."""
        str_start = (
            start.strftime("%Y-%m-%d") if start else dt.now().strftime("%Y-%m-%d")
        )
        str_end = (
            end.strftime("%Y-%m-%d")
            if end
            else (dt.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        )
        return await self.auth.request(path=f"rte/ecowatt/{str_start}/{str_end}")

    async def async_has_offpeak(self, pdl: str) -> bool:
        """Has offpeak hours."""
        if not self.offpeaks:
            await self.async_get_contract(pdl)
        return len(self.offpeaks) > 0

    async def async_check_offpeak(self, pdl: str, start: dt) -> bool:
        """Return offpeak status."""
        if await self.async_has_offpeak(pdl) is True:
            start_time = start.time()
            for range_time in self.offpeaks:
                starting = dt.strptime(range_time[0], "%HH%M").time()
                ending = dt.strptime(range_time[1], "%HH%M").time()
                if ending <= start_time > starting:
                    return True
        return False

    async def async_get_identity(self, pdl: str) -> Any:
        """Get identity."""
        return await self.async_fetch_datas("identity", pdl)

    async def async_get_daily_consumption(self, pdl: str, start: dt, end: dt) -> Any:
        """Get daily consumption."""
        return await self.async_fetch_datas(DAILY_CONSUM, pdl, start, end)

    async def async_get_daily_production(self, pdl: str, start: dt, end: dt) -> Any:
        """Get daily production."""
        return await self.async_fetch_datas(DAILY_PROD, pdl, start, end)

    async def async_get_details_consumption(self, pdl: str, start: dt, end: dt) -> Any:
        """Get consumption details. (max: 7 days)."""
        data = None
        for interval in list(self.date_range(start, end, 7)):
            start, end = interval
            try:
                rsp = await self.async_fetch_datas(DETAIL_CONSUM, pdl, start, end)
            finally:
                if (
                    rsp is None
                    or rsp.get("meter_reading", {}).get("interval_reading") is None
                ):
                    continue
                elif data is None:
                    data = cast(dict[str, Any], rsp)
                else:
                    data["meter_reading"]["interval_reading"].extend(
                        rsp.get("meter_reading", {}).get("interval_reading")
                    )

        return data

    async def async_get_details_production(self, pdl: str, start: dt, end: dt) -> Any:
        """Get production details. (max: 7 days)."""
        data = None
        for interval in list(self.date_range(start, end, 7)):
            start, end = interval
            try:
                rsp = await self.async_fetch_datas(DETAIL_PROD, pdl, start, end)
            finally:
                if (
                    rsp is None
                    or rsp.get("meter_reading", {}).get("interval_reading") is None
                ):
                    continue
                elif data is None:
                    data = cast(dict[str, Any], rsp)
                else:
                    data["meter_reading"]["interval_reading"].extend(
                        rsp.get("meter_reading", {}).get("interval_reading")
                    )

        return data

    async def async_get_max_power(self, pdl: str, start: dt, end: dt) -> Any:
        """Get consumption max power."""
        return await self.async_fetch_datas(
            "daily_consumption_max_power", pdl, start, end
        )

    async def __aenter__(self) -> Enedis:
        """Asynchronous enter."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Asynchronous exit."""
        await self.close()

    async def close(self) -> None:
        """Close the session."""
        await self.auth.async_close()

    @staticmethod
    def date_range(start: dt, end: dt, intv: int) -> Generator[tuple[dt, dt], dt, None]:
        """Return range by interval date."""
        diff = (
            (end - start).days // intv
            if (end - start).days % intv == 0
            else ((end - start).days // intv) + 1
        )
        for i in range(1, diff):
            s_end = start + timedelta(days=intv)
            yield (start, s_end)
            start = s_end
        yield (start, end)
