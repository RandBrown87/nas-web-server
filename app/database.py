import mysql.connector
from config import Config

def get_db():
    conn = mysql.connector.connect(**Config.DB_CONFIG)
    orig_cursor = conn.cursor
    def buffered_cursor(*args, **kwargs):
        if 'buffered' not in kwargs:
            kwargs['buffered'] = True
        return orig_cursor(*args, **kwargs)
    conn.cursor = buffered_cursor
    return conn
