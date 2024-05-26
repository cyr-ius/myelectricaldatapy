#!/usr/bin/env python3
"""Example code."""

import asyncio
from datetime import datetime, timedelta
import logging

import yaml

from myelectricaldatapy import Enedis, EnedisByPDL, EnedisException

logger = logging.getLogger()
logger.setLevel(logging.INFO)
# create console handler and set level to debug
ch = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

# Fill out the secrets in secrets.yaml, you can find an example
# _secrets.yaml file, which has to be renamed after filling out the secrets.
with open("./secrets.yaml", encoding="UTF-8") as file:
    secrets = yaml.safe_load(file)

TOKEN = secrets["TOKEN"]
PDL = secrets["PDL"]


async def async_main() -> None:
    """Main function."""

    api = Enedis(token=TOKEN)

    try:
        start = datetime.now() - timedelta(days=7)
        end = datetime.now()
        data = await api.async_fetch_datas("consumption_load_curve", PDL, start, end)
        logger.info(data)
        data = await api.async_get_contract(PDL)
        logger.info(data)
        data = await api.async_get_addresses(PDL)
        logger.info(data)
    except EnedisException as error:
        logger.error(error)

    await api.async_close()

    myPdl = EnedisByPDL(PDL, TOKEN)
    try:
        await myPdl.async_update()
        logger.info(myPdl.stats)
    except EnedisException as error:
        logger.error(error)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_main())
