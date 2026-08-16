"""Class for analytics."""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime as dt, timedelta
import os
import re
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from .const import ATTR_OFFPEAK, ATTR_STANDARD


def _local_timezone() -> Any:
    """Resolve the local IANA timezone so DST offsets stay correct per-date.

    Falls back to the fixed UTC offset captured at call time when the
    system timezone database cannot be resolved (e.g. non-Linux hosts).
    """
    try:
        tz_path = os.path.realpath("/etc/localtime")
        return ZoneInfo(tz_path.split("zoneinfo/")[-1])
    except Exception:  # noqa: BLE001
        return dt.now().astimezone().tzinfo


class EnedisAnalytics:
    """Data analaytics."""

    local_timezone = _local_timezone()

    def __init__(self, data: Collection[Collection[str]]) -> None:
        """Initialize Dataframe."""
        self.df = pd.DataFrame(data)

    def get_data_analytics(
        self,
        convertKwh: bool = False,
        convertUTC: bool = False,
        start_date: dt | None = None,
        intervals: list[tuple[str, str]] | None = None,
        groupby: bool = False,
        summary: bool = False,
        cum_value: dict[str, Any] | None = None,
        cum_price: dict[str, Any] | None = None,
        prices: dict[str, Any] | None = None,
        tempo: dict[str, str] | None = None,
    ) -> Any:
        """Convert data to analyze."""
        cum_value = cum_value or {}
        cum_price = cum_price or {}
        step_hour = False
        if not self.df.empty:
            # Convert str to datetime
            try:
                self.df.date = pd.to_datetime(self.df.date, format="%Y-%m-%d %H:%M:%S")
            except ValueError:
                self.df.date = pd.to_datetime(self.df.date, format="%Y-%m-%d")
            self.df.date = self.df.date.dt.tz_localize(self.local_timezone)

            if convertUTC:
                self.df.date = pd.to_datetime(
                    self.df.date, utc=True, format="%Y-%m-%d %H:%M:%S"
                )

            # Subtract 1 minute at hour
            # because Pandas considers hour as the next hour while
            # for Enedis it is the hour before
            if "interval_length" in self.df:
                step_hour = True
                self.df.loc[
                    (self.df.date.dt.minute == 0),
                    "date",
                ] = self.df.date - timedelta(minutes=1)

            if start_date:
                dt_start_date = pd.to_datetime(start_date, format="%Y-%m-%d %H:%M:%S")
                dt_start_date = dt_start_date.tz_localize(self.local_timezone)
                self.df = self.df[(self.df.date > dt_start_date)]

            self.df.index = self.df.date

            # Add mark
            self.df["notes"] = ATTR_STANDARD

        if self.df.empty:
            return self.df.to_dict(orient="records")

        self.df.interval_length = (
            self.df.interval_length.transform(self._weighted_interval)
            if step_hour
            else 1
        )

        if convertKwh:
            self.df.value = (
                pd.to_numeric(self.df.value) / 1000 * self.df.interval_length
            )
        else:
            self.df.value = pd.to_numeric(self.df.value) * self.df.interval_length

        if intervals:
            self._get_data_interval(intervals)

        if groupby:
            freq = "h" if step_hour else "D"
            self.df = (
                self.df.groupby(["notes", pd.Grouper(key="date", freq=freq)])["value"]
                .sum()
                .reset_index()
            )

        if tempo:
            self._set_tempo_days(tempo)

        notes = list(self.df.notes.drop_duplicates())
        if prices:
            for mode, values in prices.items():
                if isinstance(values, dict):
                    for offset, price in values.items():
                        if tempo and offset in ["blue", "white", "red"]:
                            self.df.loc[
                                (self.df.notes == mode) & (self.df.tempo == offset),
                                "price",
                            ] = self.df.value * price
                        elif offset == "price":
                            self.df.loc[(self.df.notes == mode), "price"] = (
                                self.df.value * price
                            )
                        else:
                            self.df.loc[(self.df.notes == mode), "price"] = None

            if summary:
                for note in notes:
                    self.df.loc[(self.df.notes == note), "sum_price"] = self.df[
                        (self.df.notes == note)
                    ].price.cumsum() + cum_price.get(note, 0)

        if summary:
            for note in notes:
                self.df.loc[(self.df.notes == note), "sum_value"] = self.df[
                    (self.df.notes == note)
                ].value.cumsum() + cum_value.get(note, 0)

        return self.df.to_dict(orient="records")

    def _weighted_interval(self, interval: str) -> float | int:
        """Compute weighted."""
        if interval and len(rslt := re.findall("PT([0-9]{2})M", interval)) == 1:
            return int(rslt[0]) / 60
        return 1

    def _get_data_interval(self, intervals: list[tuple[str, str]]) -> pd.DataFrame:
        """Group date from range time."""
        for interval in intervals:
            # Convert str to datetime
            start = pd.to_datetime(interval[0], format="%H:%M:%S").time()
            end = pd.to_datetime(interval[1], format="%H:%M:%S").time()
            # Mark
            self.df.loc[
                (self.df.date.dt.time > start) & (self.df.date.dt.time <= end),
                "notes",
            ] = ATTR_OFFPEAK

        return self.df

    def _set_tempo_days(self, tempo: dict[str, str]) -> pd.DataFrame:
        """Add columns with tempo day."""
        for str_date, value in tempo.items():
            dt_date = pd.to_datetime(str_date, format="%Y-%m-%d")
            self.df.loc[(self.df.date.dt.date == dt_date.date()), "tempo"] = value
