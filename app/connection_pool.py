import psycopg2.pool
from contextlib import contextmanager

MIN_CONNECTIONS: int = 1
MAX_CONNECTIONS: int = 5

dbpool = None


def init_db(**connection_kwargs):
    """Open the pool explicitly at startup, or against an isolated test database."""
    global dbpool
    if dbpool is not None:
        raise RuntimeError('Database pool is already initialized')
    dbpool = psycopg2.pool.ThreadedConnectionPool(
        MIN_CONNECTIONS, MAX_CONNECTIONS, **connection_kwargs
    )


def close_db():
    global dbpool
    if dbpool is not None:
        dbpool.closeall()
        dbpool = None

@contextmanager
def db_cursor():
    if dbpool is None:
        raise RuntimeError('Database pool is not initialized; call init_db first')
    conn = dbpool.getconn()
    try:
        with conn.cursor() as cur:
            yield cur
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        dbpool.putconn(conn)
