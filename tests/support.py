"""Telegram API boundary for offline tests. Real handlers and aiogram are used."""

import json

from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import AnswerCallbackQuery, EditMessageText, GetMe, SendMessage
from aiogram.types import Update

from routers import create_router
from app.report_limit import ReportRateLimit


class RecordingTelegramSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.message_id = 1000

    async def close(self):
        pass

    async def stream_content(self, *args, **kwargs):
        raise AssertionError('Downloads are not supported by the offline Telegram session')
        yield b''

    async def make_request(self, bot, method, timeout=None):
        # Exercise the same serialization used by the real Telegram session.
        request = {
            key: self.prepare_value(value, bot, files={})
            for key, value in method.model_dump(warnings=False).items()
        }
        self.calls.append((method.__api_method__, request))
        if isinstance(method, (SendMessage, EditMessageText)):
            if isinstance(method, SendMessage) and method.reply_parameters:
                self.message_id = max(self.message_id, method.reply_parameters.message_id)
            self.message_id += 1
            result = {
                'message_id': (method.message_id if isinstance(method, EditMessageText)
                               else self.message_id),
                'date': 1700000000,
                'chat': {'id': method.chat_id, 'type': 'supergroup'},
                'text': method.text,
            }
            if request.get('reply_markup'):
                result['reply_markup'] = json.loads(request['reply_markup'])
        elif isinstance(method, AnswerCallbackQuery):
            result = True
        elif isinstance(method, GetMe):
            result = {'id': 123456, 'is_bot': True, 'first_name': 'Подход Бот',
                      'username': 'podhod_test_bot'}
        else:
            raise AssertionError(f'Unexpected Telegram method: {method.__api_method__}')
        response = self.check_response(bot, method, 200, json.dumps({'ok': True, 'result': result}))
        return response.result


def make_dispatcher(report_limit=None):
    dispatcher = Dispatcher(report_limit=report_limit or ReportRateLimit())
    dispatcher.include_router(create_router())
    session = RecordingTelegramSession()
    bot = Bot(token='123456:OFFLINE_TEST_TOKEN', session=session)
    return dispatcher, bot, session


def make_update(text=None, message_id=1, chat_id=-100123, edited=False,
                caption=None, date=1700000000, **extra):
    message = {
        'message_id': message_id, 'date': date,
        'chat': {'id': chat_id, 'type': 'supergroup'},
        'from': {'id': 456, 'is_bot': False, 'first_name': 'Test'},
        **extra,
    }
    if text is not None:
        message['text'] = text
    if caption is not None:
        message['caption'] = caption
    return Update.model_validate({
        'update_id': message_id,
        'edited_message' if edited else 'message': message,
    })


def make_callback(data, message_id=1001, chat_id=-100123, user_id=999):
    return Update.model_validate({
        'update_id': 100,
        'callback_query': {
            'id': 'callback-test', 'chat_instance': 'test-chat', 'data': data,
            'from': {'id': user_id, 'is_bot': False, 'first_name': 'Другой участник'},
            'message': {
                'message_id': message_id, 'date': 1700000000,
                'chat': {'id': chat_id, 'type': 'supergroup'},
                'from': {'id': 123456, 'is_bot': True, 'first_name': 'Подход Бот'},
                'text': 'Чью статистику показать?',
            },
        },
    })
