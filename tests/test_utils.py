import unittest
from unittest.mock import AsyncMock, MagicMock

from app.utils import answer_long


class MessageTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_chunks_sent_including_final_remainder(self):
        for length in (1, 3999, 4000, 4001, 8000, 8001):
            with self.subTest(length=length):
                message = MagicMock(answer=AsyncMock())
                text = 'п' * length
                await answer_long(message, text)
                chunks = [call.args[0] for call in message.answer.call_args_list]
                self.assertEqual(''.join(chunks), text)
                self.assertTrue(all(0 < len(chunk) <= 4000 for chunk in chunks))
                self.assertTrue(all(call.kwargs['parse_mode'] is None
                                    for call in message.answer.call_args_list))
