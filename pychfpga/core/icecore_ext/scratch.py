""" Handler for the IceBoard's FPGA core UDP communication and hardware management firmware.
"""
# Standard Python packages

import asyncio
import aiohttp
import json
# loop=asyncio.create_event_loop()

async def main():
        connector = aiohttp.TCPConnector(limit=0, limit_per_host=4)
        session = aiohttp.ClientSession(json_serialize=simplejson.dumps,
                                        connector=_connector)
    try:
#         async with aiohttp.ClientSession(json_serialize=json.dumps, connector=_connector) as session:
        session = aiohttp.ClientSession(json_serialize=json.dumps, connector=_connector)
        async with session.post("http://10.10.10.244/tuber", json={"object": "IceBoard"}) as resp:
                json_out = await resp.json(loads=json.loads,content_type=None)
                print(json_out)
        await session.close()
    except Exception as e:
        print('There was an exception:',e)
        raise e
# await main()

asyncio.run(main())