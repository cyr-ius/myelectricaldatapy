# myelectricaldatapy
Fetch date Enedis Linky from myelectricaldata.fr (enedisgateway.tech)

Check your config, enable or disable heater, change preset mode.

Install
-------
Use the PIP package manager
```bash
$ pip install myelectricaldatapy
```

Or manually download and install the last version from github
```bash
$ git clone https://github.com/cyr-ius/myelectricaldatapy.git
$ python setup.py install
```
Get started
-----------
```python
# Import the myelectricaldatapy package.
from myelectricaldatapy import EnedisGatewayClient

async def main():
    api = EnedisGatewayClient("pdl", "token")
    devices = await api.async_get_devices()
    for device in devices:
        name = device.get("dev_alias")
        data = await api.async_get_device(device["did"])
        mode = data.get("attr").get("mode")
        logger.info("Heater : {} , mode : {}".format(name, mode))
loop = asyncio.get_event_loop()
loop.run_until_complete(main())
```
Have a look at the [example.py](https://github.com/cyr-ius/myelectricaldatapy/blob/master/example.py) for a more complete overview.

Notes on HTTPS
--------------
Not implemented
