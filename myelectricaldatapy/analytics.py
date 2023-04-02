"""Class for analytics."""
from __future__ import annotations

import logging
import re
from datetime import datetime as dt
from datetime import timedelta
from typing import Any, Collection, Tuple

import pandas as pd

_LOGGER = logging.getLogger(__name__)


class EnedisAnalytics:
    """Data analaytics."""

    local_timezone = dt.now().astimezone().tzinfo

    def __init__(self, data: Collection[Collection[str]]) -> None:
        """Initialize Dataframe."""
        self.df = pd.DataFrame(data)

    def get_data_analytics(
        self,
        convertKwh: bool = False,
        convertUTC: bool = False,
        start_date: dt | None = None,
        intervals: list[Tuple[str, str]] | None = None,
        groupby: bool = False,
        summary: bool = False,
        cum_value: dict[str, Any] = {},
        cum_price: dict[str, Any] = {},
        prices: dict[str, Any] | None = None,
        tempo: dict[str, str] | None = None,
    ) -> Any:
        """Convert datas to analyze."""
        step_hour = False
        if not self.df.empty:
            # Convert str to datetime
            self.df.date = pd.to_datetime(self.df.date, format="%Y-%m-%d %H:%M:%S")
            self.df.date = self.df.date.dt.tz_localize(self.local_timezone)

            if convertUTC:
                self.df.date = pd.to_datetime(
                    self.df.date, utc=True, format="%Y-%m-%d %H:%M:%S"
                )

            # Substract 1 minute at hour
            # because Pandas considers hour as the next hour while
            # for Enedis it is the hour before
            if "interval_length" in self.df:
                step_hour = True
                self.df.loc[
                    (
                        self.df.date.dt.minute
                        == dt.strptime("00:00:00", "%H:%M:%S").minute
                    ),
                    "date",
                ] = self.df.date - timedelta(minutes=1)

            if start_date:
                dt_start_date = pd.to_datetime(start_date, format="%Y-%m-%d %H:%M:%S")
                dt_start_date = dt_start_date.tz_localize(self.local_timezone)
                self.df = self.df[(self.df.date > dt_start_date)]

            self.df.index = self.df.date

            # Add mark
            self.df["notes"] = "standard"

        if self.df.empty:
            return self.df.to_dict(orient="records")

        if step_hour:
            self.df.interval_length = self.df.interval_length.transform(
                self._weighted_interval
            )
        else:
            self.df.interval_length = 1

        if convertKwh:
            self.df.value = (
                pd.to_numeric(self.df.value) / 1000 * self.df.interval_length
            )
        else:
            self.df.value = pd.to_numeric(self.df.value) * self.df.interval_length

        if intervals:
            self._get_data_interval(intervals)

        if groupby:
            freq = "H" if step_hour else "D"
            self.df = (
                self.df.groupby(["notes", pd.Grouper(key="date", freq=freq)])["value"]
                .sum()
                .reset_index()
            )

        if tempo:
            self._set_tempo_days(tempo)

        if prices:
            for mode, values in prices.items():
                if isinstance(values, dict):
                    for offset, price in values.items():
                        if tempo and offset in ["blue", "white", "red"]:
                            self.df.loc[
                                (self.df.notes == mode) & (self.df.tempo == offset),
                                "price",
                            ] = (
                                self.df.value * price
                            )
                        elif offset == "price":
                            self.df.loc[(self.df.notes == mode), "price"] = (
                                self.df.value * price
                            )

            if summary:
                for mode, sums in cum_price.items():
                    self.df.loc[(self.df.notes == mode), "sum_price"] = self.df[
                        (self.df.notes == mode)
                    ].price.cumsum() + sums.get("sum_price")

        if summary:
            for mode, sums in cum_value.items():
                self.df.loc[(self.df.notes == mode), "sum_value"] = self.df[
                    (self.df.notes == mode)
                ].value.cumsum() + sums.get("sum_value")

        return self.df.to_dict(orient="records")

    def _weighted_interval(self, interval: str) -> float | int:
        """Compute weighted."""
        if interval and len(rslt := re.findall("PT([0-9]{2})M", interval)) == 1:
            return int(rslt[0]) / 60
        return 1

    def _get_data_interval(self, intervalls: list[Tuple[str, str]]) -> pd.DataFrame:
        """Group date from range time."""
        for intervall in intervalls:
            # Convert str to datetime
            start = pd.to_datetime(intervall[0], format="%H:%M:%S").time()
            end = pd.to_datetime(intervall[1], format="%H:%M:%S").time()
            # Mark
            self.df.loc[
                (self.df.date.dt.time > start) & (self.df.date.dt.time <= end),
                "notes",
            ] = "offpeak"

        return self.df

    def _set_tempo_days(self, tempo: dict[str, str]) -> pd.DataFrame:
        """Add columns with tempo day."""
        for str_date, value in tempo.items():
            dt_date = pd.to_datetime(str_date, format="%Y-%m-%d")
            self.df.loc[(self.df.date.dt.date == dt_date.date()), "tempo"] = value

    def get_last_value(self, data: dict[str, Any], orderby: str, value: str) -> Any:
        """Return last value after order by."""
        df = pd.DataFrame(data)
        if not df.empty and value in df.columns:
            df = df.sort_values(by=orderby)
            return df[value].iloc[-1]  # pylint: disable=unsubscriptable-object