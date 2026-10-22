"""Real PostgreSQL + real routing; Telegram and LLM stop at their API boundaries.

Run via python -m scripts.check --integration, which manages a temporary local cluster.
Each test creates its own randomly named schema; there are no TRUNCATE/DROP DATABASE calls.
"""

import datetime
import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import psycopg2
from psycopg2 import sql

from app import connection_pool
from app.database_func import add_podhod, edit_podhod, get_podhod_history, get_volume
from app.llm import StatsLLM, UNAVAILABLE_COMMENT
from app.llm_client import LLMError
from app.llm_config import LLMSettings
from tests.support import make_callback, make_dispatcher, make_update


TEST_DSN = os.environ.get('PODHOD_TEST_DATABASE_URL')
SCHEMA_SQL = Path(__file__).resolve().parents[2] / 'db' / 'schema.sql'


@unittest.skipUnless(TEST_DSN, 'Set PODHOD_TEST_DATABASE_URL to a separate test PostgreSQL')
class DatabaseScenarios(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.schema = 'podhod_test_' + uuid.uuid4().hex
        # The test role is expected to have CREATE privileges only in its test database.
        self.admin = psycopg2.connect(TEST_DSN)
        self.admin.autocommit = True
        self.addCleanup(self.admin.close)
        if not self.admin.info.dbname.endswith('_test'):
            self.fail('Integration database name must end with _test; production databases are forbidden')
        with self.admin.cursor() as cursor:
            cursor.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.addCleanup(self.drop_schema)
        connection_pool.init_db(dsn=TEST_DSN, options=f'-c search_path={self.schema}')
        self.addCleanup(connection_pool.close_db)
        with connection_pool.db_cursor() as cursor:
            cursor.execute(SCHEMA_SQL.read_text(encoding='utf-8'))
        self.dispatcher, self.bot, self.telegram = make_dispatcher()
        self.client = MagicMock(complete=AsyncMock(return_value='Это плавность'))
        self.llm = StatsLLM(LLMSettings(), self.client)
        self.now = datetime.datetime.now(datetime.timezone.utc)
        self.requester = 1000

    def drop_schema(self):
        # Only the UUID schema created above is removed, never public or another database.
        with self.admin.cursor() as cursor:
            cursor.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))

    async def asyncTearDown(self):
        await self.bot.session.close()

    async def dispatch(self, text=None, **kwargs):
        update = make_update(text, date=int(self.now.timestamp()), **kwargs)
        await self.dispatcher.feed_update(self.bot, update, llm=self.llm)

    async def click(self, data, **kwargs):
        # These scenarios compare reports by independent requesters; cooldown has dedicated tests.
        self.requester += 1
        kwargs.setdefault('user_id', self.requester)
        await self.dispatcher.feed_update(self.bot, make_callback(data, **kwargs), llm=self.llm)

    def rows(self, query):
        with connection_pool.db_cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()

    async def seed(self, sportsmen, volume, days_ago=0, message_id=1, chat_id=-100123):
        return await add_podhod(sportsmen, volume, f'#подход #{sportsmen.lower()} {volume}л',
                                self.now - datetime.timedelta(days=days_ago), chat_id, message_id)

    async def test_register_and_edit_updates_record_and_correct_bot_message(self):
        await self.dispatch('#подход #миша 0,5л + 1л эсса', message_id=10)
        self.assertEqual(self.rows('SELECT sportsmen, volume, tg_chat_id, tg_message_id FROM podhods'),
                         [('Миша', 1.5, -100123, 10)])
        self.assertEqual(self.rows('SELECT podhod_id, bot_chat_id, bot_message_id FROM bot_answers'),
                         [(1, -100123, 1001)])
        self.assertIn('объём: 1.5л', self.telegram.calls[-1][1]['text'])
        await self.dispatch('#подход #миша 2л', message_id=10, edited=True)
        self.assertEqual(self.rows('SELECT volume FROM podhods'), [(2.0,)])
        method, request = self.telegram.calls[-1]
        self.assertEqual(method, 'editMessageText')
        self.assertEqual(request['message_id'], '1001')
        self.assertEqual(request['chat_id'], '-100123')
        self.assertIn('объём: 2.0л', request['text'])
        self.assertEqual(self.rows('SELECT count(*) FROM bot_answers'), [(1,)])

    async def test_photo_caption_registers_approach(self):
        await self.dispatch(caption='#подход #миша 0,5л', photo=[{
            'file_id': 'test', 'file_unique_id': 'test', 'width': 100, 'height': 100,
        }])
        self.assertEqual(self.rows('SELECT sportsmen, volume FROM podhods'), [('Миша', 0.5)])
        self.assertEqual(self.telegram.calls[-1][0], 'sendMessage')

    async def test_statistics_filter_person_and_period(self):
        await self.seed('Миша', 1.5, message_id=1)
        await self.seed('Миша', 2, days_ago=8, message_id=2)
        await self.seed('Петя', 3, message_id=3)
        await self.dispatch('/stats', message_id=4)
        rows = json.loads(self.telegram.calls[-1][1]['reply_markup'])['inline_keyboard']
        self.assertEqual([[b['text'] for b in row] for row in rows],
                         [['Общая статистика'], ['Миша', 'Петя']])
        await self.click(rows[0][0]['callback_data'])
        report = self.telegram.calls[-1][1]['text']
        self.assertIn('Всего всеми выпито 6.5л', report)
        self.assertIn('7 дней вы выпили 4.5л', report)
        await self.click(rows[1][0]['callback_data'])
        report = self.telegram.calls[-1][1]['text']
        self.assertIn('Спортсмен Миша выпил 3.5л', report)
        self.assertIn('7 дней он выпил 1.5л', report)
        messages = self.client.complete.call_args.args[0]
        self.assertNotIn('#петя', messages[1]['content'])
        self.assertNotIn('#миша 2л', messages[1]['content'])

    async def test_empty_database_and_unknown_sportsman(self):
        await self.dispatch('/stats')
        await self.click('stats:all')
        self.assertIn('Всего всеми выпито 0л', self.telegram.calls[-1][1]['text'])
        await self.dispatch('/stats неизвестный', message_id=2)
        self.assertIn('выпил 0л', self.telegram.calls[-1][1]['text'])
        self.assertEqual(await get_podhod_history('Неизвестный', 7), '')

    async def test_edit_without_registered_answer_is_ignored(self):
        await self.dispatch('#подход #миша 1л', edited=True)
        self.assertEqual(self.telegram.calls, [])
        self.assertEqual(self.rows('SELECT count(*) FROM podhods'), [(0,)])
        self.assertFalse(await edit_podhod('Миша', 1, 'text', self.now, -100123, 99))

    async def test_invalid_edit_keeps_original_record(self):
        await self.dispatch('#подход #миша 1л')
        await self.dispatch('#подход 2л', edited=True)
        self.assertEqual(self.rows('SELECT sportsmen, volume FROM podhods'), [('Миша', 1.0)])
        self.assertIn('Подход не изменён', self.telegram.calls[-1][1]['text'])

    async def test_sql_error_rolls_back_and_connection_remains_usable(self):
        with self.assertRaises(psycopg2.errors.NotNullViolation):
            with connection_pool.db_cursor() as cursor:
                cursor.execute("INSERT INTO podhods (sportsmen, volume) VALUES ('Rollback', 1)")
                cursor.execute('INSERT INTO bot_answers (podhod_id) VALUES (1)')
        self.assertEqual(self.rows('SELECT count(*) FROM podhods'), [(0,)])
        await self.seed('Миша', 1)
        self.assertEqual(await get_volume(), 1)

    async def test_same_message_ids_in_different_chats_edit_correct_record(self):
        await self.dispatch('#подход #миша 1л', chat_id=-1001)
        await self.dispatch('#подход #петя 2л', chat_id=-1002)
        await self.dispatch('#подход #миша 3л', chat_id=-1001, edited=True)
        self.assertEqual(self.rows('SELECT tg_chat_id, volume FROM podhods ORDER BY tg_chat_id'),
                         [(-1002, 2.0), (-1001, 3.0)])
        self.assertEqual(self.telegram.calls[-1][1]['chat_id'], '-1001')

    async def test_llm_failure_still_sends_database_statistics(self):
        await self.seed('Миша', 1.5)
        self.client.complete.side_effect = LLMError('HTTP 500')
        with self.assertLogs('app.llm', level='WARNING'):
            await self.click('stats:all')
        report = self.telegram.calls[-1][1]['text']
        self.assertIn('Всего всеми выпито 1.5л', report)
        self.assertIn(UNAVAILABLE_COMMENT, report)

    async def test_menu_refresh_and_old_buttons_keep_correct_names(self):
        await self.seed('Петя', 2)
        await self.dispatch('/stats')
        rows = json.loads(self.telegram.calls[-1][1]['reply_markup'])['inline_keyboard']
        petya_button = rows[1][0]['callback_data']
        # Adding an alphabetically earlier name must not change an old button's meaning.
        await self.seed('Миша', 1, message_id=2)
        await self.seed('Петя', 3, message_id=3)
        with connection_pool.db_cursor() as cursor:
            cursor.execute("INSERT INTO podhods (sportsmen) VALUES (NULL), (''), ('   ')")
        await self.dispatch('/stats', message_id=4)
        rows = json.loads(self.telegram.calls[-1][1]['reply_markup'])['inline_keyboard']
        self.assertEqual([[b['text'] for b in row] for row in rows],
                         [['Общая статистика'], ['Миша', 'Петя']])
        await self.click(petya_button, user_id=1234)
        self.assertIn('Спортсмен Петя выпил 5.0л', self.telegram.calls[-1][1]['text'])
        self.assertEqual(self.telegram.calls[-1][0], 'editMessageText')
        self.assertEqual(self.telegram.calls[-1][1]['chat_id'], '-100123')
        # Editing the name on the original approach must not redirect its old button.
        with connection_pool.db_cursor() as cursor:
            cursor.execute("UPDATE podhods SET sportsmen = 'Саша' WHERE id = 1")
        await self.click(petya_button)
        self.assertIn('Спортсмен Петя выпил 3.0л', self.telegram.calls[-1][1]['text'])

    async def test_old_button_for_renamed_sportsman_shows_alert(self):
        await self.seed('Петя', 2)
        await self.dispatch('/stats')
        rows = json.loads(self.telegram.calls[-1][1]['reply_markup'])['inline_keyboard']
        with connection_pool.db_cursor() as cursor:
            cursor.execute("UPDATE podhods SET sportsmen = 'Миша'")
        await self.click(rows[1][0]['callback_data'])
        self.assertEqual(self.telegram.calls[-1][0], 'answerCallbackQuery')
        self.assertIn('Спортсмен не найден', self.telegram.calls[-1][1]['text'])

    async def test_distinct_names_have_no_period_limit(self):
        await self.seed('Ветеран', 1, days_ago=400)
        await self.dispatch('/stats')
        rows = json.loads(self.telegram.calls[-1][1]['reply_markup'])['inline_keyboard']
        self.assertEqual(rows[1][0]['text'], 'Ветеран')

    async def test_shared_menu_reports_are_attributed_and_rate_limited(self):
        await self.seed('Миша', 1.5)
        await self.dispatch('/stats', message_id=22)
        menu = self.telegram.calls[-1][1]
        self.assertEqual(json.loads(menu['reply_parameters'])['message_id'], 22)
        rows = json.loads(menu['reply_markup'])['inline_keyboard']
        await self.click('stats:all', user_id=700)
        result = self.telegram.calls[-1][1]
        self.assertEqual(json.loads(result['entities'])[0]['user']['id'], 700)
        self.assertIn('выпито 1.5л', result['text'])
        count = len(self.telegram.calls)
        await self.click(rows[1][0]['callback_data'], user_id=700)
        self.assertEqual(len(self.telegram.calls), count + 1)
        self.assertEqual(self.telegram.calls[-1][0], 'answerCallbackQuery')
        self.assertIn('Повтори через', self.telegram.calls[-1][1]['text'])
        self.assertEqual(self.client.complete.await_count, 1)
        await self.click(rows[1][0]['callback_data'], user_id=701)
        self.assertIn('Спортсмен Миша выпил 1.5л', self.telegram.calls[-1][1]['text'])
        self.assertEqual(self.client.complete.await_count, 2)
