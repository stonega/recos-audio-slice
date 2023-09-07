from typing import List
import os
import uuid
import cuid
import psycopg2
from dotenv import load_dotenv

from utils import SrtItem

load_dotenv()


def get_user_credit(user_id: str):
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    select_query = """SELECT * FROM "User" where id = %s;"""
    cursor.execute(select_query, (user_id,))
    user = cursor.fetchone()
    if user is None:
        insert = """INSERT INTO "User" (id, credit) VALUES ( %s, %s);"""
        cursor.execute(insert, (user_id, 0))
        conn.commit()
        return 0
    return user[-1]

def get_user_lang(user_id: str):
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    select_query = """SELECT * FROM "User" where id = %s;"""
    cursor.execute(select_query, (user_id,))
    user = cursor.fetchone()
    if user is None:
        insert = """INSERT INTO "User" (id, credit) VALUES ( %s, %s);"""
        cursor.execute(insert, (user_id, 0))
        conn.commit()
        return 0
    return user[-2]


def add_credit_record(task_id: str, user_id: str, name: str | None, type: str, audio_url: str, audio_image: str = ""):
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    insert = """INSERT INTO "Credit" (id, name, "userId", type, "audio_url", "audio_image") VALUES ( %s, %s, %s, %s, %s, %s);"""
    cursor.execute(insert, (task_id, name, user_id, type, audio_url, audio_image))
    conn.commit()
    return cursor.rowcount


def update_credit_record(task_id: str, user_id: str, credit: int, duration: int, type: str):
    print('update credit...', credit)
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    update_query = """UPDATE "User" SET credit = credit + %s WHERE id = %s;"""
    cursor.execute(update_query, (credit, user_id))
    insert = """UPDATE "Credit" SET credit = %s, audio_length = %s, type = %s, status = 'completed' WHERE ID = %s;"""
    cursor.execute(insert, (-credit, duration, type, task_id))
    conn.commit()
    return cursor.rowcount


def update_user_credit(user_id: str, credit: int, duration: int, name: str | None, type: str):
    print('update credit...', credit)
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    update_query = """UPDATE "User" SET credit = credit + %s WHERE id = %s;"""
    cursor.execute(update_query, (credit, user_id))
    insert = """INSERT INTO "Credit" (id, name, "userId", credit, audio_length, type) VALUES (%s, %s, %s, %s, %s, %s);"""
    cursor.execute(insert, (cuid.cuid(), name,
                   user_id, -credit, duration, type))
    conn.commit()
    return cursor.rowcount


def save_subtitle_result(srt_items: List[SrtItem], task_id: str):
    print('save result...')
    srts = list(map(lambda s: (str(uuid.uuid4()), task_id,
                s['id'], s['start_time'], s['end_time'], s['text']), srt_items))
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    insert = """INSERT INTO "Subtitle" (id, task_id, subtitle_id, start_timestamp, end_timestamp, text ) VALUES (%s, %s, %s, %s, %s, %s);"""
    cursor.executemany(insert, srts)
    conn.commit()
    return cursor.rowcount


def get_subtitle_result(task_id: str):
    print('get subtitle result...')
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    select_query = """SELECT * FROM "Subtitle" where task_id = %s ORDER BY subtitle_id;"""
    cursor.execute(select_query, (task_id,))
    subtitles = cursor.fetchall()
    return subtitles
