import os
from typing import List
import motor.motor_asyncio

client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGODB_URL"])
db = client.subtitles

async def do_insert(srt_items: List[dict], task_id: str):
    srts = list(map(lambda s:  (task_id,
                s['id'], s['start_time'], s['end_time'], s['text']), srt_items))
    await db.insert_many(srts)


def save_subtitle_result_to_mongodb(srt_items, task_id: str):
    loop = client.get_io_loop()
    loop.run_until_complete(do_insert(srt_items=srt_items, task_id=task_id))
