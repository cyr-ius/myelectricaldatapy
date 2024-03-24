#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Example code."""

import asyncio
import logging
from datetime import datetime, timedelta

from myelectricaldatapy import Enedis, EnedisByPDL, EnedisException

logger = logging.getLogger()
logger.setLevel(logging.INFO)
# create console handler and set level to debug
ch = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

# Please , fill good values...
PDL = "0123456789"
TOKEN = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"


async def main() -> None:
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

    myPdl = EnedisByPDL(PDL, TOKEN)
    await myPdl.async_update()
    print(myPdl.stats)


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
