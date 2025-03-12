
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from dispatcher import (
    Dispatcher as BMDp,
    EHandlerNames as EHN
)
from os import getenv


token: str = str(getenv('T_API_KEY'))
dp: Dispatcher = Dispatcher()
bmdp: BMDp = BMDp()


@dp.message(CommandStart())
async def start_message(message: Message):
    await message.answer(text=f'Привет, {message.from_user.full_name}, я бот, который \
                         который помогает с отслеживанием основной статистики \
                         серверов и их статуса ||с сайта battlemetrics.com||. \
                         \n\nОсновной моей задачей на данный момент является \
                         оповещение пользователей о вайпе на добавленных \
                         в профиль серверах Rust.\n\nЗа дополнительной \
                         информацией отправь /help.')
    

#TODO написать ответ пользьвоталю на команду /help
@dp.message(Command('help'))
async def help_message(message: Message):
    await message.answer(text=f'Данный бот умеет следующее: \n\n\
                         \t1) Отправлять необходимые пользователю изменения о \
                         серверах, которые можно выбрать из списка, либо добавить \
                         вручную, если известен id сервера на сайте battlemetrics\
                         .com.\n\
                         \t2) Отправлять необходимы пользователю изменения об \
                         игроках, в том числе играют ли они сейчас или нет \
                         (данный функционал сейчас разрабатывается).\n\
                         \t3) Фильтровать отправление изменений, вплоть до \
                         времени отключения сервера и его включения.\n\
                         Можете выбрать следующие ')


@bmdp.handler(handler=EHN.all_diffs)
async def send_diffs(bot, differences: dict, profile_id = '517965582'):
    """
    Функция для отправки изменений о сервере всем игрокам, подписанным на данную рассылку
    
    :param differences: Словарь со списком изменений в информации об объектах 
    :param profile_id: ID пользователя, которому отправляются изменения

    :return None:
    """
    if not isinstance(differences, dict):
        raise TypeError(f'Differences must have type dict not {type(differences)}')
    
    await bot.send_message(chat_id=profile_id, text=__diffs_to_str(differences))


async def __diffs_to_str(differences: dict):
    return differences['description']


#TODO написать обработчики ПриИзмененииДанныхОСервере
#TODO написать обработчики сообщений пользователя
#TODO написать обработчики менюшек
async def start_bot():
    global token
    token = str(getenv('T_API_KEY'))
    bot = Bot(token=token, parse_mode=ParseMode.MARKDOWN_V2)
    await bmdp.add_bot(bot)
    await dp.start_polling(bot)
