import app.connection_pool as connection_pool
from psycopg2 import sql
import datetime

async def add_podhod(user: str, volume: float, message: str, date: datetime.datetime) -> bool:
    with connection_pool.db_cursor() as CURSOR:
        CURSOR.execute(sql.SQL("INSERT INTO podhods (sportsmen, volume, original_message, date) VALUES ({user}, {volume}, {message}, {date}) RETURNING id")
                       .format(user=sql.Literal(user),
                               volume=sql.Literal(volume),
                               message=sql.Literal(message),
                               date=sql.Literal(date)))

        if CURSOR.fetchall()[0][0] is not None: return True
        else: return False

async def get_volume(sportsmen = None) -> float:
    query = "SELECT sum(volume) from podhods"
    if sportsmen: query += " where sportsmen={sportsmen}"

    with connection_pool.db_cursor() as CURSOR:
        CURSOR.execute(sql.SQL(query).format(sportsmen=sql.Literal(sportsmen)))
        result = CURSOR.fetchall()[0][0]
        if result:
            return float(result)
        else:
            return 0
