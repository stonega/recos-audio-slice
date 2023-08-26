import asyncio
import os
from typing import List
import motor.motor_asyncio

client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client.recos

async def do_insert(srt_items: List[dict], task_id: str):
    for srt in srt_items:
        srt['task_id'] = task_id
    await db.subtitles.insert_many(srt_items)
async def do_find(task_id: str):
    cursor = db.subtitles.find({'task_id': {'$eq': task_id}}).sort('subtitle_id')
    document = cursor.to_list(length=100)
    return document


def save_subtitle_result_to_mongodb(srt_items, task_id: str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop = client.get_io_loop()
    loop.run_until_complete(do_insert(srt_items=srt_items, task_id=task_id))

def get_subtitles_from_mongodb(task_id: str):
    cursor = db.subtitles.find({'task_id': {'$eq': task_id}}).sort('subtitle_id')
    document = cursor.to_list(length=1000000)
    return document
