
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from os import getenv


TOKEN: str = getenv('T_API_KEY')
dp: Dispatcher = Dispatcher()


@dp.message(CommandStart())
async def start_message(message: Message):
    await message.answer(f'Привет, {message.from_user.full_name}, я бот, который \
                         который помогает с отслеживанием основной статистики \
                         серверов и их статуса ||с сайта battlemetrics.com||.\n\n\
                         Основной моей задачей на данный момент является \
                         оповещение пользователей о вайпе на добавленных \
                         в профиль серверах Rust.\n\nЗа дополнительной \
                         информацией отправь /help.')
    


async def help_message(message: Message):
    await message.answer(f'')


async def start_bot():
    bot: Bot = Bot(token=TOKEN, parse_mode=ParseMode.MARKDOWN_V2)
    await dp.start_polling(bot)
