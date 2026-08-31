"""Class for Enedis Gateway (http://www.myelectricaldata.fr)."""

from collections.abc import Generator
from datetime import date, datetime as dt, timedelta
import logging
import re
from typing import Any

from aiohttp import ClientSession
from pydantic import BaseModel, ValidationError

from .auth import EnedisAuth
from .const import DAILY_CONSUM, DAILY_PROD, DETAIL_CONSUM, DETAIL_PROD
from .exceptions import EnedisException, PayloadError
from .types import (
    AccessResponse,
    Contract,
    CustomerResponse,
    DataCollect,
    EcowattMapping,
    EcowattResponse,
    IdentityResponse,
    Prices,
    Service,
    TempoDays,
    TempoMapping,
    TempoPrice,
    TempoResponse,
    UsagePoint,
)
from .tz import as_local, get_local_timezone, local_now

_LOGGER = logging.getLogger(__name__)


def _validate[ModelT: BaseModel](model: type[ModelT], raw: Any) -> ModelT:
    """Validate ``raw`` against ``model``, wrapping schema errors.

    Keeps every parsing failure inside the :class:`EnedisException` hierarchy so
    consumers of the library only ever have to catch ``EnedisException``.
    """
    try:
        return model.model_validate(raw)
    except ValidationError as error:
        raise PayloadError(
            f"Unexpected {model.__name__} payload from MyElectricalData: {error}"
        ) from error


class Enedis:
    """Enedis API."""

    def __init__(
        self, token: str, session: ClientSession | None = None, timeout: int = 30
    ) -> None:
        """Initialize."""

        session = session or ClientSession()
        self.auth = EnedisAuth(session, token, timeout)
        self.async_request = self.auth.async_request
        self.offpeaks: list[tuple[str, str]] = []
        self.last_access: date | None = None

    async def async_fetch_datas(
        self, service: Service, pdl: str, start: dt | None = None, end: dt | None = None
    ) -> Any:
        """Retrieve date from service."""

        self.last_access = local_now()
        path_range = ""
        if start and end:
            start_date = start.strftime("%Y-%m-%d")
            end_date = end.strftime("%Y-%m-%d")
            path_range = f"/start/{start_date}/end/{end_date}"
        path = f"/{service}/{pdl}{path_range}"
        return await self.async_request(path=path)

    async def async_valid_access(self, pdl: str) -> AccessResponse:
        """Return valid access."""
        return _validate(
            AccessResponse, await self.async_fetch_datas("valid_access", pdl)
        )

    async def async_has_access(self, pdl: str) -> bool:
        """Check valid access."""
        access = await self.async_valid_access(pdl)
        return access.valid is True

    async def async_get_contract(self, pdl: str) -> Contract | None:
        """Return contract information."""
        contract: Contract | None = None
        contracts = await self.async_get_contracts(pdl)
        for usage_point in contracts.customer.usage_points:
            if usage_point.usage_point.usage_point_id == pdl:
                contract = usage_point.contracts
                if contract and contract.offpeak_hours:
                    self.offpeaks = re.findall(
                        "(?:(\\w+)-(\\w+))+", contract.offpeak_hours
                    )
        return contract

    async def async_get_contracts(self, pdl: str) -> CustomerResponse:
        """Return all contracts information."""
        return _validate(
            CustomerResponse, await self.async_fetch_datas("contracts", pdl)
        )

    async def async_get_address(self, pdl: str) -> UsagePoint | None:
        """Return address information."""
        address: UsagePoint | None = None
        addresses = await self.async_get_addresses(pdl)
        for usage_point in addresses.customer.usage_points:
            if usage_point.usage_point.usage_point_id == pdl:
                address = usage_point.usage_point
        return address

    async def async_get_addresses(self, pdl: str) -> CustomerResponse:
        """Return all addresses information."""
        return _validate(
            CustomerResponse, await self.async_fetch_datas("addresses", pdl)
        )

    async def async_get_tempo(
        self, start: dt | None = None, end: dt | None = None
    ) -> TempoMapping:
        """Return Tempo Day."""
        str_start = (
            start.strftime("%Y-%m-%d") if start else local_now().strftime("%Y-%m-%d")
        )
        str_end = (
            end.strftime("%Y-%m-%d")
            if end
            else (local_now() + timedelta(days=1)).strftime("%Y-%m-%d")
        )
        raw = await self.auth.async_request(path=f"/rte/tempo/{str_start}/{str_end}")
        try:
            return TempoResponse.validate_python(raw)
        except ValidationError as error:
            _LOGGER.debug("Unexpected tempo payload: %s (%s)", raw, error)
            return {}

    async def async_get_tempo_days(self) -> TempoDays | None:
        """Summary Tempo days before the end of year."""
        raw = await self.auth.async_request(path="/edf/tempo/days")
        try:
            return TempoDays.model_validate(raw)
        except ValidationError as error:
            _LOGGER.debug("Unexpected tempo days payload: %s (%s)", raw, error)
            return None

    async def async_get_tempo_prices(self) -> Prices | None:
        """Return Tempo prices as a :class:`Prices` model, one value per colour."""
        raw = await self.auth.async_request(path="/edf/tempo/price")
        try:
            return Prices(
                standard=TempoPrice(
                    blue=raw.get("blue_hp", 0),
                    white=raw.get("white_hp", 0),
                    red=raw.get("red_hp", 0),
                ),
                offpeak=TempoPrice(
                    blue=raw.get("blue_hc", 0),
                    white=raw.get("white_hc", 0),
                    red=raw.get("red_hc", 0),
                ),
            )
        except (AttributeError, ValidationError) as error:
            _LOGGER.debug("Unexpected tempo prices payload: %s (%s)", raw, error)
            return None

    async def async_get_ecowatt(
        self, start: dt | None = None, end: dt | None = None
    ) -> EcowattMapping:
        """Return Ecowatt information."""
        str_start = (
            start.strftime("%Y-%m-%d") if start else local_now().strftime("%Y-%m-%d")
        )
        str_end = (
            end.strftime("%Y-%m-%d")
            if end
            else (local_now() + timedelta(days=1)).strftime("%Y-%m-%d")
        )
        raw = await self.async_request(path=f"/rte/ecowatt/{str_start}/{str_end}")
        try:
            return EcowattResponse.validate_python(raw)
        except ValidationError as error:
            _LOGGER.debug("Unexpected ecowatt payload: %s (%s)", raw, error)
            return {}

    async def async_has_offpeak(self, pdl: str) -> bool:
        """Has offpeak hours."""
        if not self.offpeaks:
            await self.async_get_contract(pdl)
        return len(self.offpeaks) > 0

    async def async_check_offpeak(self, pdl: str, start: dt) -> bool:
        """Return offpeak status."""
        if await self.async_has_offpeak(pdl) is True:
            # Off-peak windows are defined in local wall-clock time, so a
            # start given in another timezone must be converted first.
            local_timezone = get_local_timezone()
            start_time = as_local(start).astimezone(local_timezone).time()
            for range_time in self.offpeaks:
                starting = (
                    dt.strptime(range_time[0], "%HH%M")
                    .replace(tzinfo=local_timezone)
                    .time()
                )
                ending = (
                    dt.strptime(range_time[1], "%HH%M")
                    .replace(tzinfo=local_timezone)
                    .time()
                )
                if starting < start_time <= ending:
                    return True
        return False

    async def async_get_identity(self, pdl: str) -> IdentityResponse:
        """Get identity."""
        return _validate(
            IdentityResponse, await self.async_fetch_datas("identity", pdl)
        )

    async def async_get_daily_consumption(
        self, pdl: str, start: dt, end: dt
    ) -> DataCollect:
        """Get daily consumption."""
        return _validate(
            DataCollect, await self.async_fetch_datas(DAILY_CONSUM, pdl, start, end)
        )

    async def async_get_daily_production(
        self, pdl: str, start: dt, end: dt
    ) -> DataCollect:
        """Get daily production."""
        return _validate(
            DataCollect, await self.async_fetch_datas(DAILY_PROD, pdl, start, end)
        )

    async def async_get_details_consumption(
        self, pdl: str, start: dt, end: dt
    ) -> DataCollect | None:
        """Get consumption details. (max: 7 days)."""
        return await self._async_get_details(DETAIL_CONSUM, pdl, start, end)

    async def async_get_details_production(
        self, pdl: str, start: dt, end: dt
    ) -> DataCollect | None:
        """Get production details. (max: 7 days)."""
        return await self._async_get_details(DETAIL_PROD, pdl, start, end)

    async def async_get_max_power(self, pdl: str, start: dt, end: dt) -> DataCollect:
        """Get consumption max power."""
        return _validate(
            DataCollect,
            await self.async_fetch_datas(
                "daily_consumption_max_power", pdl, start, end
            ),
        )

    async def _async_get_details(
        self, service: Service, pdl: str, start: dt, end: dt
    ) -> DataCollect | None:
        """Fetch details (max: 7 days)."""

        data: DataCollect | None = None
        raise_error = False

        for interval in list(self.date_range(start, end, 7)):
            start, end = interval
            response: DataCollect | None = None
            try:
                if raise_error is False:
                    response = _validate(
                        DataCollect,
                        await self.async_fetch_datas(service, pdl, start, end),
                    )
            except EnedisException as error:
                raise_error = True
                _LOGGER.error(error)

            if response is None:
                continue

            new_data = response.meter_reading.interval_reading
            if not new_data:
                continue
            elif data is None:
                data = response
            else:
                data.meter_reading.interval_reading.extend(new_data)

        return data

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

    async def async_close(self) -> None:
        """Close the session."""
        if self.auth.session:
            await self.auth.session.close()
