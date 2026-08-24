# myelectricaldatapy

Fetch date Enedis Linky from myelectricaldata.fr (enedisgateway.tech)

## Install

Use the PIP package manager

```bash
$ pip install myelectricaldatapy
```

Or manually download and install the last version from github

```bash
$ git clone https://github.com/cyr-ius/myelectricaldatapy.git
$ python setup.py install
```

## Attributes

- tempo_day : RED/WHITE/BLUE
- ecowatt : Information Dictionary
- power_Data: Data

## Methods

- async_get_max_power (start: datetime, end: datetime) Return: max power
- async_get_details_production (start: datetime, end: datetime) Return: details production (max 7days)
- async_get_details_consumption (start: datetime, end: datetime) Return: details consumption (max 7days)
- async_get_daily_production (day: datetime, end: datetime) Return: production (max 1095 days)
- async_get_daily_consumption (start: datetime, end: datetime) Return: consumption (max 1095 days)
- async_get_identity Return: Data identity
- async_check_offpeak (start: datetime) : check if datetime in range offpeak
- async_has_offpeak Return boolean if offpeak detected
- async_get_ecowatt Return: ecowatt information
- async_get_tempoday Return: Tempo day (RED/WHITE/BLUE)
- async_get_address Return address
- async_get_contract Return contact
- async_valid_access Return information access from mylelectricaldata
- async_load (start: datetime, end: datetime) Return None - Load Data in power_Data attribute
- async_refresh Return None - Refresh power_Data , tempo_day and ecowatt attributes.

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
api = EnedisByPDL(token=TOKEN, pdl=PDL, timezone=ZoneInfo("Europe/Paris"))
```

Alternatively, set it once globally for every instance:

```python
from myelectricaldatapy import set_local_timezone

set_local_timezone(ZoneInfo("Europe/Paris"))
```

## Get started

```python
# Import the myelectricaldatapy package.
from myelectricaldatapy import EnedisByPDL,EnedisAnalytics

TOKEN="012345"
PDL="012345012345"

async def main():
    api = EnedisByPDL(token=TOKEN, pdl=PDL)

    print(await api.async_get_contract())
    print(await api.async_get_address())

    start = datetime.now() - timedelta(days=7)
    end = datetime.now()
    Data = await api.async_get_details_consumption(start,end)
    print(Data)

    analytics = EnedisAnalytics(Data)
    offpeak_intervals = [(dt.strptime("08H00", "%HH%M"), dt.strptime("12H00", "%HH%M"))]

    # it is possible to load detailed production and consumption data within the object (in the power_Data attribute)
    await api.async_load()
    print(api.power_Data)
    # and refresh Data load.
    await api.async_refresh()

    # Analytics data convert
    resultat = analytics.get_data_analytics(
        convertKwh=True,
        convertUTC=True,
        intervals=offpeak_intervals,
        groupby="date",
        summary=True,
    )

    offpeak = analytics.set_price(resultat[0], 0.1641, True)
    normal = analytics.set_price(resultat[1], 0.18, True)

    print(offpeak)
    print(normal)



    await api.async_close()

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
```

Have a look at the [example.py](https://github.com/cyr-ius/myelectricaldatapy/blob/master/example.py) for a more complete overview.
