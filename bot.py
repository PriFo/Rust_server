
from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dispatcher import (
    Dispatcher as BMDp,
    EHandlerNames as EHN
)
from os import getenv
import re
from bot_handlers import (
    get_main_menu, handle_main_menu, handle_callback_query, 
    handle_text_message, UserState, user_states
)
from repository import Repository
from data_classes import Profile
from logger import Logger


# Константа для дебага и тестирования через телеграм
DEBUG_PROFILE_ID = '517965582'
ADMIN_ID = 517965582

dp: Dispatcher = Dispatcher()
bmdp: BMDp = BMDp()
logger = Logger("Bot")


def escape_markdown_v2(text: str) -> str:
    """Экранирует специальные символы для Markdown V2"""
    special_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(special_chars)}])', r'\\\1', text)


@dp.message(CommandStart())
async def start_message(message: Message):
    """Обработчик команды /start с созданием профиля"""
    user_id = str(message.from_user.id)
    repo = Repository()
    
    # Проверяем, есть ли профиль в памяти или в БД
    profile = repo.profiles.get(user_id) or repo.load_profile(user_id)
    
    if not profile:
        # Создаем новый профиль
        profile = Profile(
            id=user_id,
            nickname=message.from_user.username or "",
            name=message.from_user.first_name or "",
            surname=message.from_user.last_name or ""
        )
        repo.add_profile(profile, user_id)
        # Сохраняем в БД
        repo._insert_profile(user_id)
        logger.info(f"Создан новый профиль для пользователя {user_id}")
    else:
        # Обновляем существующий профиль (на случай изменения имени/никнейма)
        if message.from_user.username:
            profile.nickname = message.from_user.username
        if message.from_user.first_name:
            profile.name = message.from_user.first_name
        if message.from_user.last_name:
            profile.surname = message.from_user.last_name
        repo.add_profile(profile, user_id)  # Обновляем в памяти
        repo.update_profile(user_id)  # Обновляем в БД
        logger.info(f"Обновлен профиль для пользователя {user_id}")
    
    # Активируем профиль при /start (если он был деактивирован)
    if not profile.is_active:
        repo.activate_profile(user_id)
        logger.info(f"Профиль {user_id} активирован при /start")
    
    user_name = message.from_user.first_name or message.from_user.full_name or "пользователь"
    escaped_name = escape_markdown_v2(user_name)
    text = f'Привет\\, {escaped_name}\\, я бот\\, который \
        который помогает с отслеживанием основной статистики \
        серверов и их статуса ||с сайта battlemetrics\\.com||\\. \
        \n\nОсновной моей задачей на данный момент является \
        оповещение пользователей о вайпе на добавленных \
        в профиль серверах Rust\\.\n\nЗа дополнительной \
        информацией отправь \\/help\\.'
    await message.answer(text=text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=get_main_menu())
    

@dp.message(Command('help'))
async def help_message(message: Message):
    """Обработчик команды /help с информацией о возможностях бота"""
    text = (
        'Данный бот умеет следующее:\n\n'
        '1\\. Отправлять необходимые пользователю изменения о '
        'серверах, которые можно выбрать из списка, либо добавить '
        'вручную, если известен id сервера на сайте battlemetrics\\.com '
        'или его название \\(На данный момент доступны только сервера Rust\\)\\.\n\n'
        '2\\. Отправлять необходимые пользователю изменения об '
        'игроках, в том числе играют ли они сейчас или нет '
        '\\(данный функционал сейчас разрабатывается\\)\\.\n\n'
        '3\\. Фильтровать отправление изменений, вплоть до '
        'времени отключения сервера и его включения\\.\n\n'
        'Доступные команды:\n'
        '/start \\- Начать работу с ботом\n'
        '/stop \\- Остановить отслеживание изменений \\(деактивировать профиль\\)\n'
        '/help \\- Показать эту справку\n'
        '/report \\- Отправить отчет администратору\n\n'
        'Для настройки уведомлений используйте команды управления серверами и фильтрами\\.'
    )
    await message.answer(text=text, parse_mode=ParseMode.MARKDOWN_V2)


@bmdp.handler(handler=EHN.all_diffs)
async def send_diffs(bot, differences: dict, profile_id: str = DEBUG_PROFILE_ID):
    """
    Функция для отправки изменений о сервере всем игрокам, подписанным на данную рассылку
    
    :param bot: Объект бота для отправки сообщений
    :param differences: Словарь со списком изменений в информации об объектах 
    :param profile_id: ID пользователя, которому отправляются изменения (по умолчанию DEBUG_PROFILE_ID для дебага)

    :return None:
    """
    if not isinstance(differences, dict):
        raise TypeError(f'Differences must have type dict not {type(differences)}')
    
    text = _diffs_to_str(differences)
    await bot.send_message(chat_id=profile_id, text=text)


def _diffs_to_str(differences: dict) -> str:
    """Преобразует словарь различий в строку с экранированием для Markdown V2"""
    description = differences.get('description', '')
    if not description:
        return 'Нет описания изменений'
    return escape_markdown_v2(description)


@dp.message(Command('report'))
async def report_command(message: Message):
    """Обработчик команды /report"""
    user_id = str(message.from_user.id)
    user_states[user_id] = UserState.WAITING_REPORT
    await message.answer(
        "Опишите проблему или предложение. Ваше сообщение будет отправлено администратору.",
        reply_markup=get_main_menu()
    )


@dp.message(Command('stop'))
async def stop_command(message: Message):
    """Обработчик команды /stop для деактивации профиля"""
    user_id = str(message.from_user.id)
    repo = Repository()
    
    # Проверяем, существует ли профиль
    profile = repo.profiles.get(user_id) or repo.load_profile(user_id)
    if not profile:
        # Создаем профиль, если его нет
        profile = Profile(
            id=user_id,
            nickname=message.from_user.username or "",
            name=message.from_user.first_name or "",
            surname=message.from_user.last_name or ""
        )
        repo.add_profile(profile, user_id)
        repo._insert_profile(user_id)
    
    # Деактивируем профиль
    if repo.deactivate_profile(user_id):
        user_name = message.from_user.first_name or message.from_user.full_name or "пользователь"
        escaped_name = escape_markdown_v2(user_name)
        text = f'Профиль деактивирован\\. Бот больше не будет отслеживать изменения для ваших серверов\\.\n\nДля повторной активации используйте команду /start\\.'
        await message.answer(text=text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=get_main_menu())
        logger.info(f"Профиль {user_id} деактивирован пользователем")
    else:
        await message.answer(
            "Произошла ошибка при деактивации профиля. Попробуйте позже или обратитесь к администратору.",
            parse_mode=None
        )
        logger.error(f"Ошибка при деактивации профиля {user_id}")


@dp.message()
async def any_message(message: Message):
    """Обработчик всех сообщений"""
    user_id = str(message.from_user.id) if message.from_user else 'unknown'
    repo = Repository()
    
    try:
        # Проверяем, является ли сообщение командой из главного меню
        if message.text in ["📊 Мои серверы", "➕ Добавить сервер", "👤 Мои игроки", "➕ Добавить игрока",
                            "⚙️ Настройки фильтров", "📋 Список серверов", "ℹ️ Помощь", "📝 Отчет"]:
            bot = Bot(
                token=str(getenv('T_API_KEY')),
                default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
            )
            await handle_main_menu(message, bot)
        else:
            # Обрабатываем как обычное текстовое сообщение
            bot = Bot(
                token=str(getenv('T_API_KEY')),
                default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
            )
            await handle_text_message(message, bot)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Ошибка при обработке сообщения: {e}", {'user_id': user_id, 'error': str(e)})
        repo.log_action(
            object='Bot',
            action='handle_message',
            is_error=True,
            result=str(e),
            comment=f'Ошибка при обработке сообщения от пользователя {user_id}: {error_trace[:500]}',
            id_profile=user_id
        )
        # Пытаемся отправить пользователю сообщение об ошибке
        try:
            bot = Bot(
                token=str(getenv('T_API_KEY')),
                default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
            )
            await bot.send_message(chat_id=user_id, text="Произошла ошибка при обработке вашего сообщения. Попробуйте позже.")
        except:
            pass  # Если не удалось отправить сообщение, просто пропускаем


@dp.callback_query()
async def callback_handler(callback: CallbackQuery):
    """Обработчик callback запросов"""
    user_id = str(callback.from_user.id) if callback.from_user else 'unknown'
    repo = Repository()
    
    try:
        bot = Bot(
            token=str(getenv('T_API_KEY')),
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
        )
        await handle_callback_query(callback, bot)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Ошибка при обработке callback: {e}", {'user_id': user_id, 'error': str(e)})
        repo.log_action(
            object='Bot',
            action='handle_callback',
            is_error=True,
            result=str(e),
            comment=f'Ошибка при обработке callback от пользователя {user_id}: {error_trace[:500]}',
            id_profile=user_id
        )
        # Пытаемся отправить пользователю сообщение об ошибке
        try:
            bot = Bot(
                token=str(getenv('T_API_KEY')),
                default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
            )
            await bot.send_message(chat_id=user_id, text="Произошла ошибка при обработке запроса. Попробуйте позже.")
        except:
            pass  # Если не удалось отправить сообщение, просто пропускаем


async def send_restart_notifications():
    """Отправляет уведомления о перезапуске всем неактивным профилям"""
    repo = Repository()
    token = str(getenv('T_API_KEY'))
    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
    )
    
    # Получаем все профили, которые неактивны
    try:
        # Используем публичный метод для получения неактивных профилей
        inactive_profiles = repo.get_inactive_profiles()
        logger.info(f"Отправка уведомлений о перезапуске", {'count': len(inactive_profiles)})
        
        if not inactive_profiles:
            logger.info("Нет неактивных профилей для уведомления")
            return
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="ДА", callback_data="activate_profile_yes")]
        ])
        
        message_text = (
            "Бот был перезапущен из-за технического сбоя, либо других неполадок, "
            "вы желаете продолжить использование бота для отслеживания информации?"
        )
        
        sent_count = 0
        for profile_id in inactive_profiles:
            try:
                await bot.send_message(
                    chat_id=profile_id,
                    text=message_text,
                    reply_markup=keyboard,
                    parse_mode=None
                )
                sent_count += 1
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление профилю {profile_id}", {'error': str(e)})
        
        logger.info(f"Отправлено уведомлений: {sent_count} из {len(inactive_profiles)}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений о перезапуске", {'error': str(e)})


async def start_bot():
    logger.section("ЗАПУСК TELEGRAM БОТА")
    token = str(getenv('T_API_KEY'))
    if not token:
        logger.critical("T_API_KEY environment variable is not set")
        raise ValueError("T_API_KEY environment variable is not set")
    
    logger.info("Инициализация бота", {'token_length': len(token)})
    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
    )
    
    logger.info("Добавление бота в Dispatcher")
    await bmdp.add_bot(bot)
    
    # Отправляем уведомления о перезапуске
    logger.info("Отправка уведомлений о перезапуске неактивным пользователям")
    await send_restart_notifications()
    
    logger.info("Запуск polling")
    logger.info("Бот успешно запущен и готов к работе")
    await dp.start_polling(bot)
