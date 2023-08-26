import os
from typing import List
import motor.motor_asyncio

client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGODB_URL"])
db = client.subtitles

async def save_subtitle_result_to_mongodb(srt_items, task_id: str):
    print('save result...')
    srts = list(map(lambda s:  (task_id,
                s['id'], s['start_time'], s['end_time'], s['text']), srt_items))
    await db.insert_many(srts)
