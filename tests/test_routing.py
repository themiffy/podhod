import unittest
from unittest.mock import AsyncMock, patch

from tests.support import make_dispatcher, make_update


class MessageRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_messages_without_text_are_ignored(self):
        dispatcher, bot, telegram = make_dispatcher()
        try:
            for extra in ({}, {'photo': [{'file_id': 'test', 'file_unique_id': 'test',
                                         'width': 100, 'height': 100}]}):
                await dispatcher.feed_update(bot, make_update(**extra))
            self.assertEqual(telegram.calls, [])
        finally:
            await bot.session.close()

    async def test_invalid_sportsmen_do_not_write_to_database(self):
        for text, expected in (
            ('#подход 0,5л', 'Не указан спортсмен'),
            ('#подход #миша #петя 0,5л', 'Тут несколько спортсменов'),
        ):
            with self.subTest(text=text), patch('routers.podhod_router.add_podhod', new_callable=AsyncMock) as add:
                dispatcher, bot, telegram = make_dispatcher()
                try:
                    await dispatcher.feed_update(bot, make_update(text))
                    add.assert_not_awaited()
                    self.assertIn(expected, telegram.calls[0][1]['text'])
                finally:
                    await bot.session.close()
