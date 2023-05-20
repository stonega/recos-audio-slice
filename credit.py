import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_user_credit(user_id: str):
    print('connecting...')
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    select_query = """SELECT * FROM "User" where id = %s;"""
    cursor.execute(select_query, (user_id,))
    user = cursor.fetchone()
    return user[-1]

def update_user_credit(user_id: str, credit: int, name: str | None):
    print('update credit...', credit)
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    update_query = """UPDATE "User" SET credit = credit + %s WHERE id = %s;"""
    cursor.execute(update_query, (credit, user_id))
    insert = """INSERT INTO "Credit" (name, user_id, credit) VALUES (%s, %s, %s);"""
    cursor.execute(insert, (name, user_id, -credit))
    conn.commit()
    return cursor.rowcount
