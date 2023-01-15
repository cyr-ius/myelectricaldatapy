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
    datas = await async_get_details_consumption(start,end)
    print(datas)
    
    analytics = EnedisAnalytics(datas)
    offpeak_intervals = [(dt.strptime("08H00", "%HH%M"), dt.strptime("12H00", "%HH%M"))]
    
    
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
    
    
loop = asyncio.get_event_loop()
loop.run_until_complete(main())
```

Have a look at the [example.py](https://github.com/cyr-ius/myelectricaldatapy/blob/master/example.py) for a more complete overview.

## Notes on HTTPS

Not implemented
