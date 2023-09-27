import os
import cuid
import psycopg2
from dotenv import load_dotenv
from utils import logger

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
    return user[-2]

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
    return user[-1]

def get_credit_record(id: str):
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    select_query = """SELECT * FROM "Credit" where id = %s;"""
    cursor.execute(select_query, (id,))
    record = cursor.fetchone()
    if record is None:
        return None
    return { "type": record[5], "audio_url": record[7], "prompt": record[8], "task_id": record[-1]}

def add_credit_record(task_id: str, user_id: str, name: str | None, type: str, audio_url: str, audio_image: str = ""):
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    insert = """INSERT INTO "Credit" (id, name, "userId", type, "audio_url", "audio_image", "task_id") VALUES ( %s, %s, %s, %s, %s, %s, %s);"""
    cursor.execute(insert, (task_id, name, user_id, type, audio_url, audio_image, task_id))
    conn.commit()
    return cursor.rowcount


def update_credit_record(task_id: str, user_id: str, credit: int, duration: int, type: str):
    logger.info(f'update credit... {credit}')
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    update_query = """UPDATE "User" SET credit = credit + %s WHERE id = %s;"""
    cursor.execute(update_query, (credit, user_id))
    insert = """UPDATE "Credit" SET credit = %s, audio_length = %s, type = %s, status = 'completed' WHERE task_id = %s;"""
    cursor.execute(insert, (-credit, duration, type, task_id))
    conn.commit()
    return cursor.rowcount

def update_credit_record_status(task_id: str, status: str):
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    insert = """UPDATE "Credit" SET status = %s WHERE task_id = %s;"""
    cursor.execute(insert, (status, task_id))
    conn.commit()
    return cursor.rowcount

def update_credit_record_task_id(id: str, new_task_id: str):
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    insert = """UPDATE "Credit" SET task_id = %s, status = 'pending' WHERE id = %s;"""
    cursor.execute(insert, (new_task_id, id))
    conn.commit()
    return cursor.rowcount

def update_user_credit(user_id: str, credit: int, duration: int, name: str | None, type: str):
    logger.info('update credit...', credit)
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    update_query = """UPDATE "User" SET credit = credit + %s WHERE id = %s;"""
    cursor.execute(update_query, (credit, user_id))
    insert = """INSERT INTO "Credit" (id, name, "userId", credit, audio_length, type) VALUES (%s, %s, %s, %s, %s, %s);"""
    cursor.execute(insert, (cuid.cuid(), name,
                   user_id, -credit, duration, type))
    conn.commit()
    return cursor.rowcount
