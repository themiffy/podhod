"""Real aiogram dispatch and Telegram requests; only DB/LLM are replaced."""

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import Update

from app.llm import StatsLLM, UNAVAILABLE_COMMENT
from app.llm_client import LLMError
from app.llm_config import LLMSettings
from tests.support import make_callback, make_dispatcher, make_update

MISHA_CALLBACK = 'stats:person:a2011a92f0f1efc6b0af6a0fb4e623fc'


class StatsCommandTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.volume = AsyncMock(side_effect=[12.5, 2.5])
        self.history = AsyncMock(return_value='#миша 2,5л')
        self.sportsmen = AsyncMock(return_value=['Миша', 'Петя'])
        self.patches = [
            patch('app.stats.get_volume', self.volume),
            patch('app.stats.get_podhod_history', self.history),
            patch('routers.commands.get_sportsmen', self.sportsmen),
        ]
        for replacement in self.patches:
            replacement.start()
            self.addCleanup(replacement.stop)
        self.dispatcher, self.bot, self.telegram = make_dispatcher()
        self.client = MagicMock(complete=AsyncMock(return_value='Это плавность'))

    async def asyncTearDown(self):
        await self.bot.session.close()

    async def dispatch(self, text=None, enabled=True, callback=None):
        await self.dispatcher.feed_update(
            self.bot, make_callback(callback) if callback is not None else make_update(text),
            llm=StatsLLM(LLMSettings(enabled=enabled), self.client),
        )
        self.assertEqual([method for method, _ in self.telegram.calls],
                         ['answerCallbackQuery', 'sendMessage'] if callback is not None else ['sendMessage'])
        method, request = self.telegram.calls[-1]
        self.assertEqual(method, 'sendMessage')
        self.assertEqual(request['chat_id'], '-100123')
        self.assertIsNone(request['parse_mode'])
        return request['text']

    async def test_general_report_with_comment(self):
        report = await self.dispatch(callback='stats:all')
        self.assertIn('Всего всеми выпито 12.5л', report)
        self.assertIn('7 дней вы выпили 2.5л', report)
        self.assertIn('Это плавность', report)
        self.history.assert_awaited_once_with(sportsmen=None, depth=7)

    async def test_personal_report_with_comment(self):
        report = await self.dispatch('/stats МИША')
        self.assertIn('Спортсмен Миша выпил 12.5л', report)
        self.assertIn('Это плавность', report)
        self.history.assert_awaited_once_with(sportsmen='Миша', depth=7)
        self.assertIn('Миша', self.client.complete.call_args.args[0][1]['content'])

    async def test_api_error_preserves_numeric_report(self):
        self.client.complete.side_effect = LLMError('HTTP 500')
        with self.assertLogs('app.llm', level='WARNING'):
            report = await self.dispatch(callback='stats:all')
        self.assertIn('Всего всеми выпито 12.5л', report)
        self.assertIn(UNAVAILABLE_COMMENT, report)

    async def test_disabled_llm_skips_history_and_api(self):
        report = await self.dispatch(callback='stats:all', enabled=False)
        self.assertIn('Всего всеми выпито 12.5л', report)
        self.history.assert_not_awaited()
        self.client.complete.assert_not_awaited()
        self.assertNotIn(UNAVAILABLE_COMMENT, report)

    async def test_stats_opens_menu_without_querying_reports_or_llm(self):
        await self.dispatch('/stats')
        keyboard = json.loads(self.telegram.calls[-1][1]['reply_markup'])['inline_keyboard']
        self.assertEqual([[b['text'] for b in row] for row in keyboard],
                         [['Общая статистика'], ['Миша', 'Петя']])
        self.assertEqual(keyboard[1][0]['callback_data'], MISHA_CALLBACK)
        self.volume.assert_not_awaited()
        self.history.assert_not_awaited()
        self.client.complete.assert_not_awaited()

    async def test_person_button_uses_database_name_and_posts_new_report(self):
        report = await self.dispatch(callback=MISHA_CALLBACK)
        self.assertIn('Спортсмен Миша выпил 12.5л', report)
        self.sportsmen.assert_awaited_once()
        self.history.assert_awaited_once_with(sportsmen='Миша', depth=7)
        self.assertNotIn('editMessageText', [method for method, _ in self.telegram.calls])

    async def test_callback_is_answered_before_llm_generation(self):
        async def generate(messages):
            self.assertEqual(self.telegram.calls[0][0], 'answerCallbackQuery')
            return 'Делает'
        self.client.complete.side_effect = generate
        await self.dispatch(callback='stats:all')

    async def test_empty_database_still_has_general_stats_button(self):
        self.sportsmen.return_value = []
        await self.dispatch('/stats')
        rows = json.loads(self.telegram.calls[-1][1]['reply_markup'])['inline_keyboard']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0]['callback_data'], 'stats:all')

    async def test_long_name_does_not_exceed_callback_limit(self):
        name = 'я' * 200
        self.sportsmen.return_value = [name]
        await self.dispatch('/stats')
        button = json.loads(self.telegram.calls[-1][1]['reply_markup'])['inline_keyboard'][1][0]
        self.assertEqual(button['text'], name)
        self.assertLessEqual(len(button['callback_data'].encode('utf-8')), 64)

    async def test_missing_sportsman_shows_alert_without_report(self):
        await self.dispatcher.feed_update(self.bot, make_callback('stats:person:' + 'f' * 32),
                                          llm=StatsLLM(LLMSettings(), self.client))
        self.assertEqual(len(self.telegram.calls), 1)
        method, request = self.telegram.calls[0]
        self.assertEqual(method, 'answerCallbackQuery')
        self.assertIn('Спортсмен не найден', request['text'])
        self.assertEqual(request['show_alert'], 'true')
        self.volume.assert_not_awaited()

    async def test_invalid_callback_data_does_not_query_database(self):
        for data in ('stats:other', 'stats:person:', 'stats:person:-1', 'stats:person:abc',
                     'stats:person:0', 'stats:person:' + 'g' * 32, 'stats:person:١'):
            with self.subTest(data=data):
                self.telegram.calls.clear()
                await self.dispatcher.feed_update(self.bot, make_callback(data),
                                                  llm=StatsLLM(LLMSettings(), self.client))
                self.assertEqual(len(self.telegram.calls), 1)
                self.assertEqual(self.telegram.calls[0][0], 'answerCallbackQuery')
        self.sportsmen.assert_not_awaited()
        self.volume.assert_not_awaited()

    async def test_callback_without_accessible_message_is_rejected(self):
        for message in (None, {'message_id': 1, 'date': 0,
                               'chat': {'id': -100123, 'type': 'supergroup'}}):
            data = make_callback('stats:all').model_dump()
            data['callback_query']['message'] = message
            update = Update.model_validate(data)
            self.telegram.calls.clear()
            await self.dispatcher.feed_update(self.bot, update, llm=StatsLLM(LLMSettings(), self.client))
            self.assertEqual([method for method, _ in self.telegram.calls], ['answerCallbackQuery'])
        self.volume.assert_not_awaited()

    async def test_command_with_bot_mention_opens_menu_in_group(self):
        await self.dispatcher.feed_update(self.bot, make_update('/stats@podhod_test_bot'),
                                          llm=StatsLLM(LLMSettings(), self.client))
        self.assertEqual(self.telegram.calls[-1][0], 'sendMessage')
        self.assertIn('reply_markup', self.telegram.calls[-1][1])
        self.sportsmen.assert_awaited_once()
