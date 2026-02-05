import psycopg2
import psycopg2.pool
import json
from contextlib import contextmanager

MIN_CONNECTIONS: int = 1
MAX_CONNECTIONS: int = 5

with open("env.json", "r") as file:
    env = json.load(file)

dbpool = psycopg2.pool.ThreadedConnectionPool(MIN_CONNECTIONS, MAX_CONNECTIONS, host=env['DB_HOST'],
                                              dbname=env['DB_NAME'],
                                              user=env['DB_USER'],
                                              password=env['DB_PASS'])

@contextmanager
def db_cursor():
    conn = dbpool.getconn()
    try:
        with conn.cursor() as cur:
            yield cur
            conn.commit()
    except:
        """
        Better handle errors here
        """
        conn.rollback()
        raise
    finally:
        dbpool.putconn(conn)