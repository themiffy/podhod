"""Real aiogram dispatch and Telegram requests; only DB/LLM are replaced."""

import json
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import Update

from app.llm import StatsLLM, UNAVAILABLE_COMMENT
from app.llm_client import LLMError
from app.llm_config import LLMSettings
from app.report_limit import ReportRateLimit
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
        self.time = 0
        self.limit = ReportRateLimit(clock=lambda: self.time)
        self.dispatcher, self.bot, self.telegram = make_dispatcher(self.limit)
        self.client = MagicMock(complete=AsyncMock(return_value='Это плавность'))

    async def asyncTearDown(self):
        await self.bot.session.close()

    async def dispatch(self, text=None, enabled=True, callback=None):
        await self.dispatcher.feed_update(
            self.bot, make_callback(callback) if callback is not None else make_update(text),
            llm=StatsLLM(LLMSettings(enabled=enabled), self.client),
        )
        methods = (['answerCallbackQuery', 'sendMessage', 'editMessageText'] if callback is not None else
                   ['sendMessage', 'editMessageText'] if text and len(text.split()) > 1 else ['sendMessage'])
        self.assertEqual([method for method, _ in self.telegram.calls], methods)
        method, request = self.telegram.calls[-1]
        self.assertEqual(method, methods[-1])
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
        self.assertNotEqual(self.telegram.calls[-1][1]['message_id'], '1001')

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

    async def test_callback_progress_and_result_identify_actual_requester(self):
        await self.dispatch(callback='stats:all')
        ack, progress, result = self.telegram.calls
        self.assertEqual(ack[1]['text'], 'Готовлю отчёт…')
        self.assertIn('готовлю отчёт', progress[1]['text'])
        self.assertEqual(json.loads(progress[1]['reply_parameters'])['message_id'], 1001)
        self.assertEqual(json.loads(result[1]['entities'])[0]['user']['id'], 999)
        self.assertIn('Другой участник, твой отчёт:', result[1]['text'])

    async def test_direct_report_replies_to_user_command(self):
        await self.dispatch('/stats Миша')
        progress = self.telegram.calls[0][1]
        self.assertEqual(json.loads(progress['reply_parameters'])['message_id'], 1)
        self.assertEqual(json.loads(progress['entities'])[0]['user']['id'], 456)

    async def test_menu_owner_gets_reply_to_own_command(self):
        data = make_callback('stats:all', user_id=456).model_dump()
        data['callback_query']['message']['reply_to_message'] = make_update('/stats', message_id=12).message.model_dump()
        await self.dispatcher.feed_update(self.bot, Update.model_validate(data),
                                          llm=StatsLLM(LLMSettings(), self.client))
        self.assertEqual(json.loads(self.telegram.calls[1][1]['reply_parameters'])['message_id'], 12)

    async def test_other_user_is_not_replied_to_menu_owners_command(self):
        data = make_callback('stats:all').model_dump()
        data['callback_query']['message']['reply_to_message'] = make_update('/stats', message_id=12).message.model_dump()
        await self.dispatcher.feed_update(self.bot, Update.model_validate(data),
                                          llm=StatsLLM(LLMSettings(), self.client))
        self.assertEqual(json.loads(self.telegram.calls[1][1]['reply_parameters'])['message_id'], 1001)

    async def test_clicks_and_direct_commands_share_limit_across_chats(self):
        await self.dispatch('/stats Миша')
        self.telegram.calls.clear()
        self.volume.reset_mock()
        self.sportsmen.reset_mock()
        await self.dispatcher.feed_update(self.bot, make_callback(MISHA_CALLBACK, user_id=456, chat_id=-222),
                                          llm=StatsLLM(LLMSettings(), self.client))
        self.assertEqual([method for method, _ in self.telegram.calls], ['answerCallbackQuery'])
        self.assertIn('5 мин 0 сек', self.telegram.calls[-1][1]['text'])
        self.volume.assert_not_awaited()
        self.sportsmen.assert_not_awaited()

    async def test_different_users_can_request_reports_independently(self):
        await self.dispatch(callback='stats:all')
        self.volume.side_effect = [10, 1]
        await self.dispatcher.feed_update(self.bot, make_callback('stats:all', user_id=1000),
                                          llm=StatsLLM(LLMSettings(), self.client))
        self.assertEqual(self.client.complete.await_count, 2)

    async def test_cooldown_expires_after_exactly_five_minutes(self):
        await self.dispatch(callback='stats:all')
        self.time = 299
        await self.dispatcher.feed_update(self.bot, make_callback('stats:all'),
                                          llm=StatsLLM(LLMSettings(), self.client))
        self.assertIn('0 мин 1 сек', self.telegram.calls[-1][1]['text'])
        self.time = 300
        self.volume.side_effect = [10, 1]
        await self.dispatcher.feed_update(self.bot, make_callback('stats:all'),
                                          llm=StatsLLM(LLMSettings(), self.client))
        self.assertEqual(self.client.complete.await_count, 2)

    async def test_custom_cooldown_controls_expiry_and_message(self):
        self.limit = ReportRateLimit(cooldown_seconds=75, clock=lambda: self.time)
        self.dispatcher['report_limit'] = self.limit
        await self.dispatch(callback='stats:all')
        self.time = 15
        await self.dispatcher.feed_update(self.bot, make_callback('stats:all'),
                                          llm=StatsLLM(LLMSettings(), self.client))
        self.assertIn('1 мин 0 сек', self.telegram.calls[-1][1]['text'])
        self.time = 75
        self.volume.side_effect = [10, 1]
        await self.dispatcher.feed_update(self.bot, make_callback('stats:all'),
                                          llm=StatsLLM(LLMSettings(), self.client))
        self.assertEqual(self.client.complete.await_count, 2)

    async def test_simultaneous_click_does_not_start_second_generation(self):
        started, finish = asyncio.Event(), asyncio.Event()

        async def generate(messages):
            started.set()
            await finish.wait()
            return 'Делает'

        self.client.complete.side_effect = generate
        first = asyncio.create_task(self.dispatcher.feed_update(
            self.bot, make_callback('stats:all'), llm=StatsLLM(LLMSettings(), self.client)))
        try:
            await asyncio.wait_for(started.wait(), timeout=2)
            self.assertIn('готовлю отчёт', self.telegram.calls[-1][1]['text'])
            # Even if generation lasts longer than the cooldown, the same user cannot overlap it.
            self.time = 400
            await self.dispatcher.feed_update(self.bot, make_callback(MISHA_CALLBACK),
                                              llm=StatsLLM(LLMSettings(), self.client))
            self.assertIn('уже готовится', self.telegram.calls[-1][1]['text'])
            self.assertEqual(self.client.complete.await_count, 1)
        finally:
            finish.set()
            await first

    async def test_generation_failure_updates_status_and_releases_limit(self):
        self.volume.side_effect = RuntimeError('database unavailable')
        with self.assertRaisesRegex(RuntimeError, 'database unavailable'):
            await self.dispatcher.feed_update(self.bot, make_callback('stats:all'),
                                              llm=StatsLLM(LLMSettings(), self.client))
        self.assertIn('не удалось подготовить', self.telegram.calls[-1][1]['text'])
        self.assertEqual(self.limit.acquire(999), 0)

    async def test_stale_button_does_not_consume_cooldown(self):
        self.sportsmen.return_value = []
        await self.dispatcher.feed_update(self.bot, make_callback(MISHA_CALLBACK),
                                          llm=StatsLLM(LLMSettings(), self.client))
        self.assertEqual(self.limit.acquire(999), 0)

    async def test_long_report_continues_as_reply_to_attributed_result(self):
        self.client.complete.return_value = 'x' * 9000
        await self.dispatcher.feed_update(self.bot, make_callback('stats:all'),
                                          llm=StatsLLM(LLMSettings(), self.client))
        result = next(request for method, request in self.telegram.calls if method == 'editMessageText')
        tails = [request for method, request in self.telegram.calls[3:] if method == 'sendMessage']
        self.assertEqual(len(tails), 2)
        self.assertTrue(all(str(json.loads(request['reply_parameters'])['message_id']) == result['message_id']
                            for request in tails))
        self.assertEqual((result['text'] + ''.join(request['text'] for request in tails)).count('x'), 9000)
