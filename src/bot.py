from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import asyncio

from src.dispatcher import Dispatcher as BMDp
from os import getenv
import re
from src.bot_handlers import (
    get_main_menu, handle_main_menu, handle_callback_query, 
    handle_text_message, UserState, user_states
)
from src.repository import Repository
from src.data_classes import Profile
from src.logger import Logger
from typing import Optional


# Константа для дебага и тестирования через телеграм
DEBUG_PROFILE_ID = getenv('DEBUG_PROFILE_ID', '517965582')
ADMIN_ID = int(getenv('ADMIN_ID', '517965582'))

# Глобальные экземпляры для Dependency Injection
_bot_instance: Optional[Bot] = None
_repo_instance: Optional[Repository] = None

def get_bot_instance() -> Bot:
    """Возвращает глобальный экземпляр Bot (создает при первом вызове)"""
    global _bot_instance
    if _bot_instance is None:
        token = str(getenv('T_API_KEY'))
        _bot_instance = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
        )
    return _bot_instance

def get_repo_instance() -> Repository:
    """Возвращает глобальный экземпляр Repository (создает при первом вызове)"""
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = Repository()
    return _repo_instance

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
    user_id = message.from_user.id
    repo = get_repo_instance()
    
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
        в профиль серверов Rust\\.\n\nЗа дополнительной \
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


@dp.message(Command('report'))
async def report_command(message: Message):
    """Обработчик команды /report"""
    user_id = message.from_user.id
    user_states[user_id] = UserState.WAITING_REPORT
    await message.answer(
        "Опишите проблему или предложение. Ваше сообщение будет отправлено администратору.",
        reply_markup=get_main_menu()
    )


@dp.message(Command('stop'))
async def stop_command(message: Message):
    """Обработчик команды /stop для деактивации профиля"""
    user_id = message.from_user.id
    repo = get_repo_instance()
    
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
    user_id = message.from_user.id if message.from_user else 0
    # Используем глобальный экземпляр Repository
    repo = get_repo_instance()
    # Используем bot из message (aiogram автоматически инжектирует его)
    bot = message.bot if hasattr(message, 'bot') else get_bot_instance()
    
    try:
        # Проверяем, является ли сообщение командой из главного меню
        if message.text in ["📊 Мои серверы", "➕ Добавить сервер", "👤 Мои игроки", "➕ Добавить игрока",
                            "⚙️ Настройки фильтров", "📋 Список серверов", "ℹ️ Помощь", "📝 Отчет"]:
            await handle_main_menu(message, bot)
        else:
            # Обрабатываем как обычное текстовое сообщение
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
            bot = get_bot_instance()
            await bot.send_message(chat_id=user_id, text="Произошла ошибка при обработке вашего сообщения. Попробуйте позже.")
        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.warning(f"Не удалось отправить сообщение об ошибке пользователю {user_id}: {e}")
        except Exception as e:
            # Логируем неожиданные ошибки, но не прерываем выполнение
            logger.error(f"Неожиданная ошибка при отправке сообщения об ошибке: {e}")


@dp.callback_query()
async def callback_handler(callback: CallbackQuery):
    """Обработчик callback запросов"""
    user_id = callback.from_user.id if callback.from_user else 0
    # Используем глобальный экземпляр Repository
    repo = get_repo_instance()
    # Используем bot из callback (aiogram автоматически инжектирует его)
    bot = callback.bot if hasattr(callback, 'bot') else get_bot_instance()
    
    try:
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
            bot = get_bot_instance()
            await bot.send_message(chat_id=user_id, text="Произошла ошибка при обработке запроса. Попробуйте позже.")
        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.warning(f"Не удалось отправить сообщение об ошибке пользователю {user_id}: {e}")
        except Exception as e:
            # Логируем неожиданные ошибки, но не прерываем выполнение
            logger.error(f"Неожиданная ошибка при отправке сообщения об ошибке: {e}")


async def send_restart_notifications():
    """Отправляет уведомления о перезапуске всем неактивным профилям"""
    # Используем глобальные экземпляры
    repo = get_repo_instance()
    bot = get_bot_instance()
    
    # Получаем все профили, которые неактивны
    try:
        inactive_profiles = repo.get_inactive_profile_ids()
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
    """Запускает бота (вызывается из main_no_gui.py)"""
    logger.section("ЗАПУСК TELEGRAM БОТА")
    token = str(getenv('T_API_KEY'))
    if not token:
        logger.critical("T_API_KEY environment variable is not set")
        raise ValueError("T_API_KEY environment variable is not set")
    
    logger.info("Инициализация бота", {'token_length': len(token)})
    # Используем глобальный экземпляр Bot
    bot = get_bot_instance()
    
    logger.info("Добавление бота в Dispatcher")
    await bmdp.add_bot(bot)
    
    # Отправляем уведомления о перезапуске
    logger.info("Отправка уведомлений о перезапуске неактивным пользователям")
    await send_restart_notifications()
    
    logger.info("Запуск polling")
    logger.info("Бот успешно запущен и готов к работе")
    await dp.start_polling(bot)