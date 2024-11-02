import sqlite3

def get_connection():
    connection = sqlite3.connect("news.db", check_same_thread=False)
    cursor = connection.cursor()
    return connection, cursor

def init_db():
    connection, cursor = get_connection()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS newslist (
        posttext TEXT NOT NULL,
        channel TEXT NOT NULL,
        userid TEXT NOT NULL,
        imageurl TEXT,
        sended BOOL NOT NULL,
        postid TEXT NOT NULL
    );""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS channels (
        channel TEXT NOT NULL,
        userid TEXT NOT NULL
    );""")
    connection.commit()
    connection.close()