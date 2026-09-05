"""Class for my PDL."""

import asyncio
from collections.abc import Callable, Mapping
from datetime import date, datetime as dt, timedelta, tzinfo as _tzinfo
import logging
from typing import Any, Literal

from aiohttp import ClientSession
from pydantic import BaseModel, ValidationError

from .analytics import EnedisAnalytics
from .api import Enedis
from .const import (
    ATTR_CONSUM,
    ATTR_CUM_PRICE,
    ATTR_CUM_VALUE,
    ATTR_END,
    ATTR_FN,
    ATTR_INTERVALS,
    ATTR_PRICE,
    ATTR_PRICES,
    ATTR_PROD,
    ATTR_START,
    CONF_VALUE,
    DAILY_CONSUM,
    DAILY_PROD,
    DETAIL_CONSUM,
    DETAIL_PROD,
)
from .exceptions import EnedisException, LimitReached
from .types import (
    AccessResponse,
    Contract,
    Cum,
    DataCollect,
    EcowattDay,
    EcowattMapping,
    EnergyCollect,
    Mode,
    Prices,
    Subscription,
    TempoDays,
    TempoMapping,
    UsagePoint,
)
from .tz import as_local, local_now, set_local_timezone

logger = logging.getLogger(__name__)


def _dump(model: BaseModel | None) -> dict[str, Any]:
    """Return a plain mapping for a model, dropping unset/``None`` entries."""
    return model.model_dump(exclude_none=True) if model is not None else {}


class EnedisByPDL:
    """Enedis by PDL class.

    This class allows you to obtain information specific to a connection point.

    The "set_collect" function allows you to specify the collection parameters from Enedis
    The "_async_fetch_data" function allows you to perform the calculations
    The result is displayed in the property: stats
    y"""

    def __init__(
        self,
        pdl: str,
        token: str,
        subscription: Subscription = Subscription.STANDARD,
        session: ClientSession | None = None,
        timeout: int = 30,
        timezone: _tzinfo | None = None,
    ) -> None:
        """Initialize.

        timezone: the timezone to interpret naive datetimes in (e.g. Home
            Assistant's hass.config.time_zone / dt_util.get_default_time_zone()).
            Defaults to the host machine's timezone, which has no reason to
            match the consuming application's configured timezone.
        """
        session = ClientSession() if session is None else session
        self._api: Enedis = Enedis(token, session, timeout)
        self.pdl = pdl
        self._timezone = timezone
        self._connected: bool = False
        self._ecowatt_subs: bool = False
        self._maxpower_subs: bool = False
        self._convert_kwh: bool = True
        self._params: dict[Mode, dict[str, Any]] = {}
        self.subscription: Subscription = subscription
        self.access: AccessResponse | None = None
        self.address: UsagePoint | None = None
        self.contract: Contract | None = None
        self.ecowatt: EcowattMapping | None = None
        self.has_collected: bool = False
        self.has_parameters: bool = False
        self.offpeak_intervals: list[tuple[str, str]] = []
        self.last_access: dt = local_now()
        self._update_lock = asyncio.Lock()
        self.last_refresh: date | None = None
        self.max_power: DataCollect | None = None
        self.tempo_historics: TempoMapping | None = None
        self.tempo_days: TempoDays | None = None
        self.tempo_prices: Prices | None = None

        if timezone is not None:
            set_local_timezone(timezone)

    @property
    def is_connected(self) -> bool:
        """Connect state."""
        return self.access is not None and self.access.valid is True

    @property
    def has_intervals(self) -> bool:
        """Intervals exist."""
        return len(self.offpeak_intervals) > 0

    @property
    def has_tempo_subscription(self) -> bool:
        """Tempo subscription status."""
        return self.subscription == Subscription.TEMPO

    @property
    def has_offpeak_hours_subscription(self) -> bool:
        """Offpeak hours subscription status."""
        return self.subscription == Subscription.HPHC

    @property
    def has_standard_subscription(self) -> bool:
        """Standard subscription status."""
        return self.subscription == Subscription.STANDARD

    @property
    def has_ecowatt_subscription(self) -> bool:
        """Ecowatt subscription status."""
        return self._ecowatt_subs

    @property
    def has_maxpower_subscription(self) -> bool:
        """Max power subscription status."""
        return self._maxpower_subs

    @property
    def ecowatt_day(self) -> EcowattDay | None:
        """ecowatt."""
        str_date = local_now().strftime("%Y-%m-%d")
        return self.ecowatt.get(str_date) if self.ecowatt is not None else None

    @property
    def tempo(self) -> str | None:
        """Tempo day."""
        str_date = local_now().strftime("%Y-%m-%d")
        return (
            self.tempo_historics.get(str_date)
            if self.tempo_historics is not None
            else None
        )

    @property
    def tempo_next(self) -> str | None:
        """Tempo next days."""
        str_date = (local_now() + timedelta(days=1)).strftime("%Y-%m-%d")
        return (
            self.tempo_historics.get(str_date)
            if self.tempo_historics is not None
            else None
        )

    @property
    def prod_prices(self) -> Prices | None:
        """Production resel price."""
        return self._params.get(ATTR_PROD, {}).get(ATTR_PRICES)

    @property
    def consum_prices(self) -> Prices | None:
        """Consumption prices."""
        return self._params.get(ATTR_CONSUM, {}).get(ATTR_PRICES)

    @property
    def stats(self) -> dict[str, Any]:
        """Statistics."""
        stats: dict[str, Any] = {}
        for mode, params in self._params.items():
            data = params.get("data", [])
            analytics = EnedisAnalytics(data, timezone=self._timezone)
            resultat = analytics.get_data_analytics(
                convertKwh=self._convert_kwh,
                intervals=params.get(ATTR_INTERVALS, []),
                groupby=True,
                summary=True,
                prices=_dump(params.get(ATTR_PRICES)),
                cum_value=_dump(params.get(ATTR_CUM_VALUE)),
                cum_price=_dump(params.get(ATTR_CUM_PRICE)),
                start_date=params.get(ATTR_START),
                tempo=self.tempo_historics,
            )
            stats.update({mode: resultat})
        return stats

    def _cache_is_stale(self) -> bool:
        """Return True when the cached data belongs to a past calendar day.

        The Enedis daily call quota resets at local midnight, so a day change
        is the right trigger to drop the cache and refetch.
        """
        return self.last_access.date() != local_now().date()

    def _reset_daily_cache(self) -> None:
        """Drop every per-day cached attribute so the next update refetches it."""
        self.access = None
        self.contract = None
        self.address = None
        self.ecowatt = None
        self.max_power = None
        self.has_collected = False
        self.tempo_historics = None
        self.tempo_days = None
        self.tempo_prices = None

    async def async_update(self, force_refresh: bool = False) -> None:
        """Update data."""
        async with self._update_lock:
            await self._async_update(force_refresh)

    async def _async_update(self, force_refresh: bool = False) -> None:
        """Update data (serialized by async_update's lock)."""

        start = local_now() - timedelta(days=1095)
        end = local_now() + timedelta(days=1)

        if force_refresh or self._cache_is_stale():
            self._reset_daily_cache()

        try:
            self.access = await self._api.async_valid_access(self.pdl)
            if self.access is not None and self.access.quota_reached:
                detail = self.access.information or "Quota reached"
                raise LimitReached(409, {"detail": detail})

            if self.is_connected is False:
                raise EnedisException(200, {"detail": "Api access not valid"})

            if self.contract is None and self.has_collected is False:
                try:
                    self.contract = await self._api.async_get_contract(self.pdl)
                    self.offpeak_intervals = self._api.offpeaks
                except EnedisException as error:
                    logger.warning(error)

            if self.address is None and self.has_collected is False:
                try:
                    self.address = await self._api.async_get_address(self.pdl)
                except EnedisException as error:
                    logger.warning(error)

            if self.ecowatt is None and self.has_ecowatt_subscription:
                self.ecowatt = await self._api.async_get_ecowatt(start, end)

            if self.max_power is None and self.has_maxpower_subscription:
                self.max_power = await self._api.async_get_max_power(
                    self.pdl, start, end
                )

            if self.tempo_historics is None and self.has_tempo_subscription:
                start = local_now() - timedelta(days=1095)
                end = local_now() + timedelta(days=1)
                self.tempo_historics = await self._api.async_get_tempo(start, end)

            if self.tempo_prices is None and self.has_tempo_subscription:
                self.tempo_prices = await self._api.async_get_tempo_prices()

            if self.tempo_days is None and self.has_tempo_subscription:
                self.tempo_days = await self._api.async_get_tempo_days()

            if self.has_parameters and self.has_collected is False:
                await self._async_fetch_data()
                self.last_refresh = local_now()

        except EnedisException as error:
            raise error from error
        finally:
            self.last_access = local_now()

    def set_ecowatt_subscription(self, activate: bool = False) -> None:
        """Enable or Disable Ecowatt Subscription."""
        self._ecowatt_subs = activate is True

    def set_maxpower_subscription(self, activate: bool = False) -> None:
        """Enable or Disable Max power Subscription."""
        self._maxpower_subs = activate is True

    def _set_intervals(self, mode: Mode, intervals: list[tuple[str, str]]) -> None:
        """Set intervals."""
        if isinstance(intervals, list):
            self.offpeak_intervals = intervals
            self._params[mode].update({ATTR_INTERVALS: intervals})

    def _set_prices(self, mode: Mode, prices: Prices | Mapping[str, Any]) -> None:
        """Set prices."""
        try:
            model = (
                prices if isinstance(prices, Prices) else Prices.model_validate(prices)
            )
        except ValidationError as error:
            logger.error("Format is incorrect (%s)", error)
            return

        self._params[mode].update({ATTR_PRICES: model})

    def _set_cumsum(
        self,
        mode: Mode,
        form: Literal["value", "price"],
        cum_sum: Cum | Mapping[str, Any],
    ) -> None:
        """Set cumulative summary."""
        try:
            model = cum_sum if isinstance(cum_sum, Cum) else Cum.model_validate(cum_sum)
        except ValidationError as error:
            logger.error("Format is incorrect (%s)", error)
            return

        self._params[mode].update({f"cum_{form}".lower(): model})

    def set_data_fetch(
        self,
        service: EnergyCollect,
        start: dt | None = None,
        end: dt | None = None,
        intervals: list[tuple[str, str]] | None = None,
        prices: Prices | Mapping[str, Any] | None = None,
        cum_value: Cum | Mapping[str, Any] | None = None,
        cum_price: Cum | Mapping[str, Any] | None = None,
        convert_kwh: bool = True,
    ) -> None:
        """Set parameters for data fetching.

        service: type of data collected
        start: date of begin to collect data
        end: date of end to collect data
        intervals: offpeak hours range - ex: [("01:00","05:00"),("12:00","14:00")]
        prices: price for standard interval and offpeak interval
        cum_sum: Cumulative kwh value of start
        cum_price: Cumulative price of start
        convert_kwh: whether to convert kWh to Wh
        """
        funcs: dict[str, Callable[..., Any]] = {
            DAILY_PROD: self._api.async_get_daily_production,
            DETAIL_PROD: self._api.async_get_details_production,
            DAILY_CONSUM: self._api.async_get_daily_consumption,
            DETAIL_CONSUM: self._api.async_get_details_consumption,
        }
        days = 1095 if service in [DAILY_PROD, DAILY_CONSUM] else 7
        mode: Mode = (
            ATTR_CONSUM if service in [DAILY_CONSUM, DETAIL_CONSUM] else ATTR_PROD
        )
        func = funcs[service]
        dt_start = as_local(start) if start else local_now() - timedelta(days=days)
        dt_end = as_local(end) if end else local_now() + timedelta(days=1)
        self._params[mode] = {ATTR_FN: func, ATTR_START: dt_start, ATTR_END: dt_end}

        if intervals:
            self._set_intervals(mode, intervals)
        if prices:
            self._set_prices(mode, prices)
        if cum_value:
            self._set_cumsum(mode, CONF_VALUE, cum_value)
        if cum_price:
            self._set_cumsum(mode, ATTR_PRICE, cum_price)

        self._convert_kwh = convert_kwh
        self.has_parameters = True

    async def _async_fetch_data(self) -> None:
        """Fetch data.

        It is necessary to value the initial data via the method: set_data_fetch.
        The execution of this method updates the property: stats.
        """

        for mode, attr in self._params.items():
            start = attr[ATTR_START]
            end = attr[ATTR_END]
            fn = attr[ATTR_FN]

            dataset: DataCollect | None = await fn(self.pdl, start, end)

            if dataset is None:
                raise EnedisException("Data collection is empty")

            readings = dataset.meter_reading.interval_reading
            if len(readings) == 0:
                raise EnedisException("Data collection is empty")

            self._params[mode].update(
                {
                    "data": [
                        reading.model_dump(exclude_none=True) for reading in readings
                    ]
                }
            )

        self.has_collected = True

    async def async_close(self) -> None:
        """Close the session."""
        if self._api.auth.session:
            await self._api.auth.session.close()
