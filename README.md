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

## Attributs
 - tempo_day : RED/WHITE/BLUE
 - ecowatt : Information Dictionary 
 - power_datas: Datas 

## Methods
- async_get_max_power
- async_get_details_production
- async_get_details_consumption
- async_get_daily_production
- async_get_daily_consumption
- async_get_identity
- async_check_offpeak
- async_has_offpeak
- async_get_ecowatt
- async_get_tempoday
- async_get_address
- async_get_contract
- async_valid_access
- async_fetch_datas

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
    datas = await api.async_get_details_consumption(start,end)
    print(datas)
    
    analytics = EnedisAnalytics(datas)
    offpeak_intervals = [(dt.strptime("08H00", "%HH%M"), dt.strptime("12H00", "%HH%M"))]
        
    # it is possible to load detailed production and consumption data within the object (in the power_datas attribute)
    await api.async_load()
    print(api.power_datas)
    # and refresh datas load.
    await api.async_refresh()
    
    # Analytics data convert
    resultat = analytics.get_data_analytcis(
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
