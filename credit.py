import os
import cuid
import psycopg2
from dotenv import load_dotenv

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

def add_credit_record(task_id: str, user_id: str, name: str | None, type: str):
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    insert = """INSERT INTO "Credit" (id, name, "userId", type) VALUES ( %s, %s, %s, %s);"""
    cursor.execute(insert, (task_id, name, user_id, type))
    conn.commit()
    return cursor.rowcount

def update_credit_record(task_id: str, user_id: str, credit: int, duration: int, type: str):
    print('update credit...', credit)
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    update_query = """UPDATE "User" SET credit = credit + %s WHERE id = %s;"""
    cursor.execute(update_query, (credit, user_id))
    insert = """UPDATE "Credit" SET credit = %s, audio_length = %s, type = %s WHERE ID = %s;"""
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
    cursor.execute(insert, (cuid.cuid(), name, user_id, -credit, duration, type))
    conn.commit()
    return cursor.rowcount
