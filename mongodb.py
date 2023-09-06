import asyncio
import os
from typing import List
import motor.motor_asyncio

client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client.recos
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

async def do_insert(srt_items: List[dict], task_id: str):
    for srt in srt_items:
        srt['task_id'] = task_id
    await db.subtitle.insert_many(srt_items)

async def do_update(srt_items: List[dict]):
    for srt in srt_items:
        await db.subtitle.replace_one({'id': srt['id'], 'task_id': srt['task_id']}, srt)

async def do_find(task_id: str):
    cursor = db.subtitle.find({'task_id': {'$eq': task_id}}).sort('subtitle_id')
    result = []
    for document in await cursor.to_list(length=10000): # type: ignore
        document.pop('_id')
        result.append(document)
    return result


def save_subtitle_result_to_mongodb(srt_items, task_id: str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop = client.get_io_loop()
    loop.run_until_complete(do_insert(srt_items=srt_items, task_id=task_id))

def update_subtitle_result_to_mongodb(srt_items):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop = client.get_io_loop()
    loop.run_until_complete(do_update(srt_items=srt_items))

def get_subtitles_from_mongodb(task_id: str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop = client.get_io_loop()
    return loop.run_until_complete(do_find(task_id=task_id))


async def do_summary_insert(summary: str, task_id: str):
    document = await db.summary.find_one({'task_id': {'$eq': task_id}})
    if document is None:
        await db.summary.insert_one({'summary': summary, 'task_id': task_id})
    else:
        await db.summary.replace_one({'task_id': task_id}, {'summary': summary, 'task_id': task_id}) 

async def do_summary_update(summary: dict):
    await db.summary.replace_one({'id': summary['id'], 'task_id': ['task_id']}, summary)

def save_subtitle_summary_to_mongodb(summary, task_id: str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop = client.get_io_loop()
    loop.run_until_complete(do_summary_insert(summary, task_id=task_id))

def update_subtitle_summary_to_mongodb(summary):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop = client.get_io_loop()
    loop.run_until_complete(do_summary_update(summary))
