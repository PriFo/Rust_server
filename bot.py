
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from dispatcher import Dispatcher as BMDp
from os import getenv


token: str = '' #str(getenv('T_API_KEY'))
dp: Dispatcher = Dispatcher()
bmdp: BMDp = BMDp()


@dp.message(CommandStart())
async def start_message(message: Message):
    await message.answer(f'Привет, {message.from_user.full_name}, я бот, который \
                         который помогает с отслеживанием основной статистики \
                         серверов и их статуса ||с сайта battlemetrics.com||. \
                         \n\nОсновной моей задачей на данный момент является \
                         оповещение пользователей о вайпе на добавленных \
                         в профиль серверах Rust.\n\nЗа дополнительной \
                         информацией отправь /help.')
    

#TODO написать ответ пользьвоталю на команду /help
@dp.message(Command('help'))
async def help_message(message: Message):
    await message.answer(f'')

@bmdp.handler(handler='differences')
async def send_diffs(bot, differences, profile_id = '517965582'):
    print('\n\nBot trying to send message\n\n')
    await bot.send_message(chat_id=profile_id, text=str(differences))


#TODO написать обработчики ПриИзмененииДанныхОСервере
async def start_bot():
    token = str(getenv('T_API_KEY'))
    print(f'{token=}')
    bot = Bot(token=token) #, parse_mode=ParseMode.MARKDOWN_V2
    await bmdp.add_bot(bot)
    await dp.start_polling(bot)
