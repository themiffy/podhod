import app.connection_pool as connection_pool
from psycopg2 import sql
import logging

async def add_podhod(user: str, volume: str, message: str) -> bool:
    with connection_pool.db_cursor() as CURSOR:
        CURSOR.execute(sql.SQL("INSERT INTO podhods (sportsmen, volume, original_message) VALUES ({user}, {volume}, {message}) RETURNING id")
                       .format(user=sql.Literal(user),
                               volume=sql.Literal(volume),
                               message=sql.Literal(message)))

        if CURSOR.fetchall()[0][0] is not None: return True
        else: return False