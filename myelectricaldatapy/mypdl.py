"""Class for my PDL."""

from __future__ import annotations

from datetime import date, datetime as dt, timedelta
import logging
from typing import Any, Callable, Tuple

from aiohttp import ClientSession
import voluptuous as vol

from myelectricaldatapy import Enedis, EnedisException, LimitReached

from .analytics import EnedisAnalytics
from .const import (
    ATTR_CUM_PRICE,
    ATTR_CUM_VALUE,
    ATTR_END,
    ATTR_FN,
    ATTR_INTERVALS,
    ATTR_OFFPEAK,
    ATTR_PRICES,
    ATTR_SERVICE,
    ATTR_STANDARD,
    ATTR_START,
    CONSUMPTION,
    DAILY_CONSUM,
    DAILY_PROD,
    DETAIL_CONSUM,
    DETAIL_PROD,
    PRODUCTION,
    TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

MODES_SCH = vol.Schema(
    {
        vol.Optional(CONSUMPTION): {
            vol.Required(ATTR_SERVICE): str,
            vol.Optional(ATTR_START): dt,
            vol.Optional(ATTR_END): dt,
        },
        vol.Optional(PRODUCTION): {
            vol.Required(ATTR_SERVICE): str,
            vol.Optional(ATTR_START): dt,
            vol.Optional(ATTR_END): dt,
        },
    }
)

PRICE_SCH = vol.Schema(
    {
        vol.Required(ATTR_STANDARD): {
            vol.Required("price"): vol.Any(int, float),
        },
        vol.Optional(ATTR_OFFPEAK): {
            vol.Required("price"): vol.Any(int, float),
        },
    }
)

PRICE_TEMPO_SCH = vol.Schema(
    {
        vol.Required(ATTR_STANDARD): {
            vol.Required("blue"): vol.Any(int, float),
            vol.Required("white"): vol.Any(int, float),
            vol.Required("red"): vol.Any(int, float),
        },
        vol.Optional(ATTR_OFFPEAK): {
            vol.Required("blue"): vol.Any(int, float),
            vol.Required("white"): vol.Any(int, float),
            vol.Required("red"): vol.Any(int, float),
        },
    }
)

CUM_SCH = vol.Schema(
    {
        vol.Required(ATTR_STANDARD): vol.Any(int, float),
        vol.Optional(ATTR_OFFPEAK): vol.Any(int, float),
    }
)


class EnedisByPDL:
    """Enedis by PDL class.

    This class allows you to obtain information specific to a connection point.

    The "set_collect" function allows you to specify the collection parameters from Enedis
    The "async_update_collects" function allows you to perform the calculations
    The result is displayed in the property: stats
    y"""

    def __init__(
        self,
        pdl: str,
        token: str,
        session: ClientSession | None = None,
        timeout: int = TIMEOUT,
    ) -> None:
        """Initialize."""
        session = ClientSession() if session is None else session
        self._api: Enedis = Enedis(token, session, timeout)
        self.pdl = pdl
        self._connected: bool = False
        self._ecowatt_subs: bool = False
        self._maxpower_subs: bool = False
        self._off_subs: bool = False
        self._params: dict[str, dict[str, Any]] = {}
        self._tempo_subs: bool = False
        self.access: dict[str, Any] = {}
        self.address: dict[str, Any] = {}
        self.contract: dict[str, Any] = {}
        self.ecowatt: dict[str, Any] = {}
        self.has_collected: bool = False
        self.has_parameters: bool = False
        self.intervals: list[Tuple[str, str]] = []
        self.last_access: dt = dt.now()
        self.last_refresh: date | None = None
        self.max_power: dict[str, Any] = {}
        self.tempo: dict[str, Any] = {}

    @property
    def is_connected(self) -> bool:
        """Connect state."""
        return self.access.get("valid", False) is True

    @property
    def has_intervals(self) -> bool:
        """Intervals exist."""
        return len(self.intervals) > 0

    @property
    def ecowatt_day(self) -> Any:
        """ecowatt."""
        str_date = dt.now().strftime("%Y-%m-%d")
        return self.ecowatt.get(str_date, {})

    @property
    def tempo_day(self) -> str | None:
        """Tempo day."""
        str_date = dt.now().strftime("%Y-%-m-%-d")
        return self.tempo.get(str_date)

    @property
    def prod_prices(self) -> dict[str, Any] | None:
        """Production resel price."""
        return self._params[PRODUCTION].get(ATTR_PRICES)

    @property
    def consum_prices(self) -> dict[str, Any] | None:
        """Offpeak hours prices."""
        return self._params[CONSUMPTION].get(ATTR_PRICES)

    @property
    def stats(self) -> dict[str, Any]:
        """Statistics."""
        stats = {}
        for mode, params in self._params.items():
            data = params.get("data", {})
            analytics = EnedisAnalytics(data)
            resultat = analytics.get_data_analytics(
                convertKwh=True,
                convertUTC=False,
                intervals=params.get(ATTR_INTERVALS, []),
                groupby=True,
                summary=True,
                prices=params.get(ATTR_PRICES, {}),
                cum_value=params.get(ATTR_CUM_VALUE, {}),
                cum_price=params.get(ATTR_CUM_PRICE, {}),
                start_date=params.get(ATTR_START),
                tempo=self.tempo,
            )
            stats.update({mode: resultat})
        return stats

    async def async_update(self, force_refresh: bool = False) -> None:
        """Update data."""
        start = dt.now() - timedelta(days=1095)
        end = dt.now() + timedelta(days=1)
        if force_refresh or self.last_access.date() != dt.now().date():
            self.contract = {}
            self.address = {}
            self.ecowatt = {}
            self.max_power = {}
            self.has_collected = False
        try:
            self.access = await self._api.async_valid_access(self.pdl)
            if self.access.get("quota_reached", False):
                detail = self.access.get("information", "Quota reached")
                raise LimitReached(409, {"detail": detail})

            if self.is_connected is False:
                raise EnedisException(200, {"detail": "Api access not valid"})

            if not self.contract and self.has_collected is False:
                try:
                    self.contract = await self._api.async_get_contract(self.pdl)
                except EnedisException as error:
                    _LOGGER.warning(error)

            if not self.address and self.has_collected is False:
                try:
                    self.address = await self._api.async_get_address(self.pdl)
                except EnedisException as error:
                    _LOGGER.warning(error)

            if not self.ecowatt and self._ecowatt_subs:
                self.ecowatt = await self._api.async_get_ecowatt(start, end)

            if not self.max_power and self._maxpower_subs:
                self.max_power = await self._api.async_get_max_power(
                    self.pdl, start, end
                )

            if self.has_parameters and self.has_collected is False:
                await self.async_update_collects()
                self.last_refresh = dt.now()
        except EnedisException as error:
            raise error from error
        finally:
            self.last_access = dt.now()

    def tempo_subscription(self, activate: bool = False) -> None:
        """Enable or Disable Tempo Subscription."""
        self._off_subs = False
        self._tempo_subs = activate is True

    def offpeak_subscription(self, activate: bool = False) -> None:
        """Enable or Disable Offpeak Hours Subscription."""
        self._tempo_subs = False
        self._off_subs = activate is True

    def ecowatt_subscription(self, activate: bool = False) -> None:
        """Enable or Disable Ecowatt Subscription."""
        self._ecowatt_subs = activate is True

    def maxpower_subscription(self, activate: bool = False) -> None:
        """Enable or Disable Max power Subscription."""
        self._maxpower_subs = activate is True

    def _set_intervals(self, mode: str, intervals: list[Tuple[str, str]]) -> None:
        """Set intervals."""
        if isinstance(intervals, list):
            self.intervals = intervals
            self._params[mode].update({ATTR_INTERVALS: intervals})

    def _set_prices(self, mode: str, prices: dict[str, Any]) -> None:
        """Set intervals.

        prices = {
            "standard":{"price":[float]},
            "offpeak":{"price":[float]}
        }
        or
        prices = {
            "standard":{"blue":[float],"white":[float],"red":[float]},
            "offpeak":{"blue":[float],"white":[float],"red":[float]}
        }
        """
        try:
            validate = PRICE_SCH(prices)
        except vol.Error:
            try:
                validate = PRICE_TEMPO_SCH(prices)
            except vol.Error as error:
                _LOGGER.error("Format is incorrect (%s)", error)
            else:
                self.tempo_subscription(True)
                self._params[mode].update({ATTR_PRICES: validate})
        else:
            self.offpeak_subscription(True)
            self._params[mode].update({ATTR_PRICES: validate})

    def _set_cumsum(self, mode: str, form: str, cum_sum: dict[str, Any]) -> None:
        """Set cumulative summary.

        mode: "production" or "consumption"
        format: "value" or "price"
        cum_sum = {"standard":[float], "offpeak":[float]}
        """
        try:
            validate = CUM_SCH(cum_sum)
        except vol.Error as error:
            _LOGGER.error("Format is incorrect (%s)", error)
        else:
            self._params[mode].update({f"cum_{form}".lower(): validate})

    def set_collects(
        self,
        service: str,
        start: dt | None = None,
        end: dt | None = None,
        intervals: list[Tuple[str, str]] | None = None,
        prices: dict[str, Any] | None = None,
        cum_value: dict[str, Any] | None = None,
        cum_price: dict[str, Any] | None = None,
    ) -> None:
        """Set parameters for data collect.

        service: "daily_production" or "daily_consumption" or "detail_production" or "detail_consumption"
        start: date of begin to collect data
        end: date of end to collect data
        intervals: offpeak hours range - ex: [("01:00","05:00"),("12:00","14:00")]
        prices: price for standard interval and offpeak interval
            ex: {
                    "standard": [float], "offpeak": [float]
                }
            ex: {
                    "standard":{"blue":[float],"white":[float],"red":[float]},
                    "offpeak":{"blue":[float],"white":[float],"red":[float]}
                }
        cum_sum: price of start
            ex: {"standard":[float], "offpeak":[float]}
        cum_price:
            ex: {"standard":[float], "offpeak":[float]}
        """
        funcs: dict[str, Callable[..., Any]] = {
            DAILY_PROD: self._api.async_get_daily_production,
            DETAIL_PROD: self._api.async_get_details_production,
            DAILY_CONSUM: self._api.async_get_daily_consumption,
            DETAIL_CONSUM: self._api.async_get_details_consumption,
        }
        days = 1095 if service in [DAILY_PROD, DAILY_CONSUM] else 7
        mode = CONSUMPTION if service in [DAILY_CONSUM, DETAIL_CONSUM] else PRODUCTION
        func = funcs[service]
        dt_start = start if start else dt.now() - timedelta(days=days)
        dt_end = end if end else dt.now() + timedelta(days=1)
        self._params[mode] = {ATTR_FN: func, ATTR_START: dt_start, ATTR_END: dt_end}
        if intervals:
            self._set_intervals(mode, intervals)
        if prices:
            self._set_prices(mode, prices)
        if cum_value:
            self._set_cumsum(mode, "value", cum_value)
        if cum_price:
            self._set_cumsum(mode, "price", cum_price)
        self.has_parameters = True

    async def async_update_collects(self) -> None:
        """Update data to collect.

        It is necessary to value the initial data via the method: set_collects.
        The execution of this method updates the property: stats.
        """
        checked = True
        self.has_collected = False
        for mode, attr in self._params.items():
            dataset = {}
            start = attr[ATTR_START]
            end = attr[ATTR_END]
            fn = attr[ATTR_FN]
            try:
                dataset = await fn(self.pdl, start, end)
            except EnedisException as error:
                checked = False
                _LOGGER.error(error)
            else:
                if dataset is None:
                    raise EnedisException("Data collection is empty")
                data = dataset.get("meter_reading", {}).get("interval_reading", [])
                if len(data) == 0:
                    raise EnedisException("Data collection is empty")
                checked = checked and len(data) > 0
                self._params[mode].update({"data": data})

            if mode == CONSUMPTION and self._tempo_subs:
                self.tempo = await self._api.async_get_tempo(start, end)

        self.has_collected = checked

    async def __aexit__(self, *_exc_info: object) -> None:
        """Async exit."""
        await self.async_close()

    async def async_close(self) -> None:
        """Close the session."""
        if self._api.auth.session:
            await self._api.auth.session.close()
