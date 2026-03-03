from asynchat import simple_producer

import app.connection_pool as connection_pool
from psycopg2 import sql
import datetime

async def add_podhod(user: str, volume: float, message: str, date: datetime.datetime, tg_chat_id: int, tg_message_id: int) -> int:
    with connection_pool.db_cursor() as CURSOR:
        CURSOR.execute(sql.SQL("""INSERT INTO podhods (sportsmen, volume, original_message, date, tg_chat_id, tg_message_id) 
                                    VALUES ({user}, {volume}, {message}, {date}, {tg_chat_id}, {tg_message_id}) RETURNING id""")
                       .format(user=sql.Literal(user),
                               volume=sql.Literal(volume),
                               message=sql.Literal(message),
                               date=sql.Literal(date),
                               tg_chat_id=sql.Literal(tg_chat_id),
                               tg_message_id=sql.Literal(tg_message_id)))


        return CURSOR.fetchall()[0][0]

async def get_volume(sportsmen = None, depth: int = 365) -> float:
    query = "SELECT sum(volume) from podhods where date > NOW() - interval '1 day' * {depth}"
    if sportsmen: query += " and sportsmen={sportsmen}"

    with connection_pool.db_cursor() as CURSOR:
        CURSOR.execute(sql.SQL(query).format(sportsmen=sql.Literal(sportsmen), depth=sql.Literal(depth)))
        result = CURSOR.fetchall()[0][0]
        if result:
            return float(result)
        else:
            return 0

async def edit_podhod(user: str, volume: float, message: str, date: datetime.datetime, tg_chat_id: int, tg_message_id: int) -> bool:

    with connection_pool.db_cursor() as CURSOR:
        CURSOR.execute(sql.SQL("""UPDATE podhods SET (sportsmen, volume, original_message) 
                                    = ({user}, {volume}, {message}) 
                                    WHERE tg_chat_id={tg_chat_id} and tg_message_id={tg_message_id} RETURNING id""")
                       .format(user=sql.Literal(user),
                               volume=sql.Literal(volume),
                               message=sql.Literal(message),
                               tg_chat_id=sql.Literal(tg_chat_id),
                               tg_message_id=sql.Literal(tg_message_id)))


        return CURSOR.fetchall()[0][0] is not None

async def add_answer(podhod_id: int, bot_message_id: int, bot_chat_id: int) -> int:
    with connection_pool.db_cursor() as CURSOR:
        CURSOR.execute(sql.SQL("""INSERT INTO bot_answers (podhod_id, bot_message_id, bot_chat_id) 
                                    VALUES ({podhod_id}, {bot_message_id}, {bot_chat_id}) RETURNING id""")
                       .format(podhod_id=sql.Literal(podhod_id),
                               bot_message_id=sql.Literal(bot_message_id),
                               bot_chat_id=sql.Literal(bot_chat_id)))


        return CURSOR.fetchall()[0][0]

async def get_answer(tg_message_id: int, tg_chat_id: int) -> int:
    with connection_pool.db_cursor() as CURSOR:
        CURSOR.execute(sql.SQL("""SELECT bot_message_id, bot_chat_id from bot_answers 
                                WHERE podhod_id = 
                                    (SELECT id FROM podhods WHERE tg_message_id={tg_message_id} and tg_chat_id={tg_chat_id})""")
                       .format(tg_message_id=sql.Literal(tg_message_id),
                               tg_chat_id=sql.Literal(tg_chat_id)))
        # (1648, 219449850) = (bot_message_id, bot_chat_id)
        return CURSOR.fetchall()[0]

async def get_podhod_history(sportsmen: str, depth: int = 14) -> str:

    """If no arguments select everyone with depth of 7 days"""

    query = """SELECT original_message from podhods WHERE True"""
    if sportsmen: query += """ and sportsmen = {sportsmen}"""
    query += """ and date > NOW() - interval '1 day' * {depth} ORDER BY id DESC"""

    with connection_pool.db_cursor() as CURSOR:
        CURSOR.execute(sql.SQL(query)
                       .format(sportsmen=sql.Literal(sportsmen),
                                depth = sql.Literal(depth)))
        # [('#подход #миша 2л эссулечкии лаймулечки любимой',), ('#подход #миша 1л',)]

        temp_result = CURSOR.fetchall()
        print(temp_result)
        podhod_stats = ''
        for tup in temp_result:
            podhod_stats += f'{tup[0].replace("#подход", "")}\n'

        return podhod_stats