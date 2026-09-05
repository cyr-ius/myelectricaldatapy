# myelectricaldatapy

Fetch Enedis Linky data from myelectricaldata.fr (enedisgateway.tech)

## Install

Use the PIP package manager

```bash
$ pip install myelectricaldatapy
```

Or manually download and install the last version from github

```bash
$ git clone https://github.com/cyr-ius/myelectricaldatapy.git
$ pip install .
```

## Public API

```python
from myelectricaldatapy import Enedis, EnedisByPDL, EnedisException
```

- `Enedis` : thin async client, one method per myelectricaldata.fr endpoint.
- `EnedisByPDL` : higher level helper that aggregates every piece of
  information for a single delivery point (PDL) and computes analytics.
- `EnedisException` : base exception. Every library error
  (`HttpRequestError`, `LimitReached`, `PayloadError`,
  `TimeoutExceededError`, `AnalyticsError`) derives from it.

All payloads are validated and returned as [pydantic](https://docs.pydantic.dev)
models (`Contract`, `UsagePoint`, `DataCollect`, `TempoDays`, `Prices`, ...).

## `Enedis`

```python
Enedis(token: str, session: ClientSession | None = None, timeout: int = 30)
```

| Method                                                       | Description                         |
| ------------------------------------------------------------ | ----------------------------------- |
| `async_fetch_datas(service, pdl, start=None, end=None)`      | Raw call to any service             |
| `async_valid_access(pdl)` / `async_has_access(pdl)`          | Access / quota status               |
| `async_get_contract(pdl)` / `async_get_contracts(pdl)`       | Contract(s)                         |
| `async_get_address(pdl)` / `async_get_addresses(pdl)`        | Address(es)                         |
| `async_get_identity(pdl)`                                    | Identity                            |
| `async_get_daily_consumption(pdl, start, end)`               | Daily consumption (max 1095 days)   |
| `async_get_daily_production(pdl, start, end)`                | Daily production (max 1095 days)    |
| `async_get_details_consumption(pdl, start, end)`             | Load curve consumption (max 7 days) |
| `async_get_details_production(pdl, start, end)`              | Load curve production (max 7 days)  |
| `async_get_max_power(pdl, start, end)`                       | Max power                           |
| `async_get_ecowatt(start=None, end=None)`                    | Ecowatt forecast                    |
| `async_get_tempo(start=None, end=None)`                      | Tempo day colors on a range         |
| `async_get_tempo_days()`                                     | Tempo calendar                      |
| `async_get_tempo_prices()`                                   | Tempo prices                        |
| `async_has_offpeak(pdl)` / `async_check_offpeak(pdl, start)` | Off-peak helpers                    |
| `async_close()`                                              | Close the aiohttp session           |

## `EnedisByPDL`

```python
EnedisByPDL(
    pdl: str,
    token: str,
    subscription: str = "standard",   # "standard" | "hphc" | "tempo"
    session: ClientSession | None = None,
    timeout: int = 30,
    timezone: tzinfo | None = None,
)
```

Workflow:

1. Optionally declare what you want to collect with
   `set_data_fetch(...)`, `set_ecowatt_subscription(True)` and
   `set_maxpower_subscription(True)`.
2. Call `await async_update()` (or `async_update(force_refresh=True)`).
3. Read the aggregated results.

| Member                                                                                                                                                                            | Description                                                                                           |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `set_data_fetch(service, start=None, end=None, intervals=None, prices=None, cum_value=None, cum_price=None)`                                                                      | Register a collect (`service` is one of `DAILY_CONSUM`, `DAILY_PROD`, `DETAIL_CONSUM`, `DETAIL_PROD`) |
| `set_ecowatt_subscription(activate=False)`                                                                                                                                        | Enable Ecowatt retrieval                                                                              |
| `set_maxpower_subscription(activate=False)`                                                                                                                                       | Enable max power retrieval                                                                            |
| `async_update(force_refresh=False)`                                                                                                                                               | Refresh access, contract, address, tempo, ecowatt, collects                                           |
| `_async_fetch_data()`                                                                                                                                                             | Refresh only the registered collects                                                                  |
| `stats`                                                                                                                                                                           | `dict` keyed by mode (`"consumption"` / `"production"`) with the computed analytics                   |
| `access`, `contract`, `address`, `ecowatt`, `max_power`, `tempo`, `tempo_days`, `tempo_prices`                                                                                    | Last fetched models                                                                                   |
| `is_connected`, `has_intervals`, `has_tempo_subscription`, `has_offpeak_hours_subscription`, `has_standard_subscription`, `has_ecowatt_subscription`, `has_maxpower_subscription` | Boolean state                                                                                         |
| `ecowatt_day`, `tempo_day`, `consum_prices`, `prod_prices`                                                                                                                        | Convenience accessors for today                                                                       |
| `async_close()`                                                                                                                                                                   | Close the aiohttp session                                                                             |

## Timezone

Enedis/RTE APIs return naive timestamps that represent local wall-clock time. This
library needs to know which timezone that is in order to compute things like
off-peak hours or hourly statistics correctly.

By default it falls back to the timezone of the host machine running the code
(`/etc/localtime`), but that has no reason to match the timezone your
application is actually configured for (e.g. Home Assistant's
`hass.config.time_zone`). Pass it explicitly to avoid a fixed-offset shift in
the reported times:

```python
api = EnedisByPDL(pdl=PDL, token=TOKEN, timezone=ZoneInfo("Europe/Paris"))
```

Alternatively, set it once globally for every instance:

```python
from myelectricaldatapy import set_local_timezone

set_local_timezone(ZoneInfo("Europe/Paris"))
```

## Get started

```python
import asyncio
from datetime import timedelta

from myelectricaldatapy import DETAIL_CONSUM, EnedisByPDL, EnedisException
from myelectricaldatapy.tz import local_now

TOKEN = "012345"
PDL = "012345012345"


async def main() -> None:
    api = EnedisByPDL(pdl=PDL, token=TOKEN)

    try:
        # Off-peak intervals and per-interval prices are optional.
        api.set_data_fetch(
            DETAIL_CONSUM,
            start=local_now() - timedelta(days=7),
            end=local_now(),
            intervals=[("08:00", "12:00")],
            prices={"standard": {"price": 0.18}, "offpeak": {"price": 0.1641}},
        )
        await api.async_update()

        print(api.contract)
        print(api.address)
        print(api.stats["consumption"])
    except EnedisException as error:
        print(error)
    finally:
        await api.async_close()


asyncio.run(main())
```

Have a look at [example.py](https://github.com/cyr-ius/myelectricaldatapy/blob/master/example.py)
for a more complete overview.
