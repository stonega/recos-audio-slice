import asyncio
import os
from typing import List
import motor.motor_asyncio

client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGODB_URL"])
db = client.subtitles

async def do_insert(srt_items: List[dict], task_id: str):
    for srt in srt_items:
        srt['task_id'] = task_id
    await db.insert_many(srt_items)


def save_subtitle_result_to_mongodb(srt_items, task_id: str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop = client.get_io_loop()
    loop.run_until_complete(do_insert(srt_items=srt_items, task_id=task_id))
