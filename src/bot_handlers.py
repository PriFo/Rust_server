"""
Модуль с обработчиками сообщений и меню для бота
"""
from aiogram import Bot
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode

from src.repository import Repository
from src.data_classes import Profile, Server, RustServer, Player
from src.filters import RustFilter, EGames, PlayerFilter, EFilterTypes
from src.logger import Logger
import re

# Константы (дублируем из bot.py чтобы избежать циклического импорта)
ADMIN_ID = 517965582

logger = Logger("BotHandlers")

def escape_markdown_v2(text: str) -> str:
    """Экранирует специальные символы для Markdown V2"""
    special_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(special_chars)}])', r'\\\1', text)

def format_server_info_from_db(server_info: dict) -> str:
    """Форматирует информацию о сервере из БД в читаемый текст"""
    lines = [f"📊 Информация о сервере:\n"]
    lines.append(f"Название: {server_info.get('server_name', 'N/A')}")
    lines.append(f"ID: {server_info.get('id_server', 'N/A')}")
    lines.append(f"Приватный: {'Да' if server_info.get('private') else 'Нет'}")
    if server_info.get('country'):
        lines.append(f"Страна: {server_info.get('country')}")
    if server_info.get('rank'):
        lines.append(f"Ранг: {server_info.get('rank')}")
    if server_info.get('is_pve') is not None:
        lines.append(f"PVE: {'Да' if server_info.get('is_pve') else 'Нет'}")
    if server_info.get('official') is not None:
        lines.append(f"Официальный: {'Да' if server_info.get('official') else 'Нет'}")
    if server_info.get('modded') is not None:
        lines.append(f"Модифицированный: {'Да' if server_info.get('modded') else 'Нет'}")
    if server_info.get('gamemode'):
        lines.append(f"Режим игры: {server_info.get('gamemode')}")
    if server_info.get('description'):
        lines.append(f"Описание: {server_info.get('description')}")
    if server_info.get('last_wipe_date'):
        lines.append(f"Последний вайп: {server_info.get('last_wipe_date')}")
    if server_info.get('next_wipe_date'):
        lines.append(f"Следующий вайп: {server_info.get('next_wipe_date')}")
    if server_info.get('next_wipe_type'):
        lines.append(f"Тип следующего вайпа: {server_info.get('next_wipe_type')}")
    return "\n".join(lines)

def format_player_info_from_db(player_info: dict) -> str:
    """Форматирует информацию об игроке из БД в читаемый текст"""
    lines = [f"👤 Информация об игроке:\n"]
    lines.append(f"Имя: {player_info.get('nickname', 'N/A')}")
    lines.append(f"ID: {player_info.get('id_players', 'N/A')}")
    lines.append(f"Приватный профиль: {'Да' if player_info.get('private') else 'Нет'}")
    return "\n".join(lines)

# Глобальные переменные для состояний пользователей
user_states = {}  # {user_id: state}
user_data = {}  # {user_id: data}

# Кэш для Repository (синглтон, но избегаем повторных обращений)
_repo_cache = None

def get_repository():
    """Получает экземпляр Repository (кэшированный)"""
    global _repo_cache
    if _repo_cache is None:
        _repo_cache = Repository()
    return _repo_cache

def get_or_create_profile(user_id: str, from_user) -> Profile:
    """Получает или создает профиль пользователя"""
    repo = get_repository()
    profile = repo.profiles.get(user_id) or repo.load_profile(user_id)
    if not profile:
        profile = Profile(
            id=user_id,
            nickname=from_user.username or "",
            name=from_user.first_name or "",
            surname=from_user.last_name or ""
        )
        repo.add_profile(profile, user_id)
        repo._insert_profile(user_id)
    return profile

# Состояния пользователей
class UserState:
    WAITING_SERVER_ID = "waiting_server_id"
    WAITING_SERVER_NAME = "waiting_server_name"
    WAITING_PLAYER_ID = "waiting_player_id"
    WAITING_PLAYER_NAME = "waiting_player_name"
    WAITING_REPORT = "waiting_report"
    CONFIGURING_FILTER = "configuring_filter"
    SELECTING_SERVER = "selecting_server"
    ADMIN_ANSWERING_REPORT = "admin_answering_report"

def get_main_menu() -> ReplyKeyboardMarkup:
    """Создает главное меню бота"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Мои серверы"), KeyboardButton(text="➕ Добавить сервер")],
            [KeyboardButton(text="👤 Мои игроки"), KeyboardButton(text="➕ Добавить игрока")],
            [KeyboardButton(text="⚙️ Настройки фильтров"), KeyboardButton(text="📋 Список серверов")],
            [KeyboardButton(text="ℹ️ Помощь"), KeyboardButton(text="📝 Отчет")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие из меню"
    )
    return keyboard

def get_filters_main_menu() -> InlineKeyboardMarkup:
    """Создает главное меню выбора типа фильтров"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Фильтры игроков", callback_data="filter_menu_player")],
            [InlineKeyboardButton(text="🖥️ Фильтры серверов", callback_data="filter_menu_server")],
            [InlineKeyboardButton(text="🦀 Rust-специфичные фильтры", callback_data="filter_menu_rust")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="filter_cancel")]
        ]
    )
    return keyboard

def get_player_filters_menu() -> InlineKeyboardMarkup:
    """Создает меню настроек фильтров игроков"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Имя игрока", callback_data="filter_player_name"),
                InlineKeyboardButton(text="🔒 Приватность", callback_data="filter_player_private")
            ],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="filter_menu_main")]
        ]
    )
    return keyboard

def get_server_filters_menu() -> InlineKeyboardMarkup:
    """Создает меню настроек фильтров серверов (общие)"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 Минимум игроков", callback_data="filter_server_players"),
                InlineKeyboardButton(text="📊 Макс. игроки", callback_data="filter_server_max_players")
            ],
            [
                InlineKeyboardButton(text="🔄 Статус сервера", callback_data="filter_server_status"),
                InlineKeyboardButton(text="🔒 Приватный", callback_data="filter_server_private")
            ],
            [
                InlineKeyboardButton(text="🌐 IP/Порт", callback_data="filter_server_ip_port"),
                InlineKeyboardButton(text="🕐 Обновление", callback_data="filter_server_updated")
            ],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="filter_menu_main")]
        ]
    )
    return keyboard

def get_rust_filters_menu() -> InlineKeyboardMarkup:
    """Создает меню настроек Rust-специфичных фильтров"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏳ Очередь (мин.)", callback_data="filter_rust_queued"),
                InlineKeyboardButton(text="🗺️ Вайп", callback_data="filter_rust_wipe")
            ],
            [
                InlineKeyboardButton(text="🛡️ PVE", callback_data="filter_rust_pve"),
                InlineKeyboardButton(text="🔗 URL", callback_data="filter_rust_url")
            ],
            [
                InlineKeyboardButton(text="🗺️ Карта URL", callback_data="filter_rust_map_url"),
                InlineKeyboardButton(text="🖼️ Миниатюра карты", callback_data="filter_rust_map_thumb")
            ],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="filter_menu_main")]
        ]
    )
    return keyboard

def get_servers_list_keyboard(page: int = 0, servers_per_page: int = 10) -> InlineKeyboardMarkup:
    """Создает клавиатуру со списком серверов с пагинацией"""
    repo = get_repository()
    servers = repo.get_servers()
    server_list = list(servers.items())
    
    # Проверка на пустой список
    if not server_list:
        # Возвращаем клавиатуру с сообщением о пустом списке
        keyboard_buttons = [[InlineKeyboardButton(text="❌ Отмена", callback_data="servers_cancel")]]
        return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    total_pages = max(1, (len(server_list) + servers_per_page - 1) // servers_per_page)
    # Ограничиваем page в допустимых пределах
    page = max(0, min(page, total_pages - 1))
    
    start_idx = page * servers_per_page
    end_idx = min(start_idx + servers_per_page, len(server_list))
    current_servers = server_list[start_idx:end_idx]
    
    keyboard_buttons = []
    for name, server_id in current_servers:
        keyboard_buttons.append([InlineKeyboardButton(
            text=name[:50],  # Ограничение длины текста
            callback_data=f"server_select_{server_id}"
        )])
    
    # Кнопки навигации (только если есть больше одной страницы)
    nav_buttons = []
    if total_pages > 1:
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"servers_page_{page-1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"Страница {page+1}/{total_pages}", callback_data="servers_info"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"servers_page_{page+1}"))
        keyboard_buttons.append(nav_buttons)
    
    keyboard_buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="servers_cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

async def handle_main_menu(message: Message, bot: Bot):
    """Обработчик главного меню"""
    text = message.text
    user_id = str(message.from_user.id)
    
    logger.info("Обработка команды главного меню", {
        'user_id': user_id,
        'command': text
    })
    
    if text == "📊 Мои серверы":
        repo = get_repository()
        # Загружаем профиль (load_profile сам проверит кэш)
        profile = repo.profiles.get(user_id) or repo.load_profile(user_id)
        if profile:
            # Всегда перезагружаем серверы из БД для актуальности данных
            repo._load_profile_subscriptions(user_id, profile)
            servers = profile.servers
            if servers:
                # Создаем клавиатуру с кнопками для каждого сервера
                keyboard_buttons = []
                for server_id, server in servers.items():
                    server_name = server.name if hasattr(server, 'name') else str(server_id)
                    keyboard_buttons.append([InlineKeyboardButton(
                        text=f"📊 {server_name[:50]}",
                        callback_data=f"view_my_server_{server_id}"
                    )])
                keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
                await message.answer("Выберите сервер для просмотра информации:", reply_markup=keyboard, parse_mode=None)
            else:
                await message.answer("У вас пока нет добавленных серверов.", parse_mode=None)
        else:
            await message.answer("Профиль не найден. Используйте /start для регистрации.", parse_mode=None)
    
    elif text == "➕ Добавить сервер":
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="По ID", callback_data="add_server_id")],
                [InlineKeyboardButton(text="По названию", callback_data="add_server_name")],
                [InlineKeyboardButton(text="Из списка", callback_data="add_server_list")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="add_server_cancel")]
            ]
        )
        await message.answer("Выберите способ добавления сервера:", reply_markup=keyboard, parse_mode=None)
    
    elif text == "⚙️ Настройки фильтров":
        keyboard = get_filters_main_menu()
        await message.answer("Выберите тип фильтров для настройки:", reply_markup=keyboard, parse_mode=None)
    
    elif text == "📋 Список серверов":
        user_data[user_id] = {'view_server_only': True}
        keyboard = get_servers_list_keyboard()
        await message.answer("Выберите сервер из списка для просмотра информации:", reply_markup=keyboard, parse_mode=None)
    
    elif text == "ℹ️ Помощь":
        help_text = (
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
        await message.answer(text=help_text, parse_mode=ParseMode.MARKDOWN_V2)
    
    elif text == "👤 Мои игроки":
        repo = get_repository()
        profile = repo.profiles.get(user_id) or repo.load_profile(user_id)
        if profile:
            players = profile.players
            if players:
                # Создаем клавиатуру с кнопками для каждого игрока
                keyboard_buttons = []
                for player_id, player in players.items():
                    player_name = player.name if hasattr(player, 'name') else str(player_id)
                    keyboard_buttons.append([InlineKeyboardButton(
                        text=f"👤 {player_name[:50]}",
                        callback_data=f"view_my_player_{player_id}"
                    )])
                keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
                await message.answer("Выберите игрока для просмотра информации:", reply_markup=keyboard, parse_mode=None)
            else:
                await message.answer("У вас пока нет добавленных игроков.", parse_mode=None)
        else:
            await message.answer("Профиль не найден. Используйте /start для регистрации.", parse_mode=None)
    
    elif text == "➕ Добавить игрока":
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="По ID", callback_data="add_player_id")],
                [InlineKeyboardButton(text="По имени", callback_data="add_player_name")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="add_player_cancel")]
            ]
        )
        await message.answer("Выберите способ добавления игрока:", reply_markup=keyboard, parse_mode=None)
    
    elif text == "📝 Отчет":
        user_states[user_id] = UserState.WAITING_REPORT
        await message.answer("Опишите проблему или предложение. Ваше сообщение будет отправлено администратору.", parse_mode=None)

async def handle_callback_query(callback: CallbackQuery, bot: Bot):
    """Обработчик callback запросов от inline кнопок"""
    data = callback.data
    user_id = str(callback.from_user.id)
    
    logger.info("Обработка callback запроса", {
        'user_id': user_id,
        'callback_data': data
    })
    
    if data == "activate_profile_yes":
        # Активация профиля после перезапуска бота
        repo = get_repository()
        if repo.activate_profile(user_id):
            await callback.message.edit_text(
                "Отлично! Ваш профиль активирован. Бот будет отслеживать изменения для ваших серверов.",
                parse_mode=None
            )
            logger.info(f"Профиль {user_id} активирован пользователем")
        else:
            await callback.message.edit_text(
                "Произошла ошибка при активации профиля. Попробуйте позже или обратитесь к администратору.",
                parse_mode=None
            )
            logger.error(f"Ошибка при активации профиля {user_id}")
    
    elif data.startswith("add_server_"):
        if data == "add_server_id":
            user_states[user_id] = UserState.WAITING_SERVER_ID
            await callback.message.edit_text("Введите ID сервера с сайта BattleMetrics.com:", parse_mode=None)
        elif data == "add_server_name":
            user_states[user_id] = UserState.WAITING_SERVER_NAME
            await callback.message.edit_text("Введите название сервера (можно частично):", parse_mode=None)
        elif data == "add_server_list":
            user_data[user_id] = {'view_server_only': False}  # Для добавления
            keyboard = get_servers_list_keyboard()
            await callback.message.edit_text("Выберите сервер из списка:", reply_markup=keyboard, parse_mode=None)
        elif data == "add_server_cancel":
            await callback.message.edit_text("Добавление сервера отменено.", parse_mode=None)
            user_states.pop(user_id, None)
    
    elif data.startswith("server_select_"):
        server_id = data.replace("server_select_", "")
        # Проверяем, является ли это выбором для добавления или просмотра
        is_view_only = user_data.get(user_id, {}).get('view_server_only', False)
        
        if is_view_only:
            # Показываем информацию о сервере
            repo = get_repository()
            server_info = repo.get_server_full_info(server_id)
            if server_info:
                # Пытаемся получить актуальную информацию через API
                from src.battlemetrics_requests import BattleMetricsResponse
                from aiohttp import ClientSession
                import asyncio
                
                async def show_server_info():
                    try:
                        bm_response = BattleMetricsResponse()
                        await bm_response.async_initialize({})
                        async with ClientSession() as session:
                            server_obj = await bm_response._get_server_info(session, server_id)
                            if isinstance(server_obj, (Server, RustServer)):
                                info_text = f"📊 Информация о сервере:\n\n{str(server_obj)}"
                                await bot.send_message(chat_id=user_id, text=escape_markdown_v2(info_text), parse_mode=ParseMode.MARKDOWN_V2)
                            else:
                                # Если не удалось получить через API, показываем из БД
                                info_text = format_server_info_from_db(server_info)
                                await bot.send_message(chat_id=user_id, text=info_text, parse_mode=None)
                    except Exception as e:
                        # Показываем информацию из БД в случае ошибки
                        info_text = format_server_info_from_db(server_info)
                        await bot.send_message(chat_id=user_id, text=info_text, parse_mode=None)
                
                asyncio.create_task(show_server_info())
                await callback.message.edit_text("Загружаю информацию о сервере...", parse_mode=None)
            else:
                await callback.message.edit_text("Сервер не найден.", parse_mode=None)
            user_data.pop(user_id, None)
        else:
            # Добавляем сервер к профилю пользователя
            repo = get_repository()
            profile = get_or_create_profile(user_id, callback.from_user)
            
            # Получаем название сервера
            servers = repo.get_servers()
            server_name = None
            for name, sid in servers.items():
                if sid == server_id:
                    server_name = name
                    break
            
            # Если название не найдено, пытаемся получить из БД напрямую
            if not server_name:
                try:
                    server_info = repo.get_server_full_info(server_id)
                    if server_info:
                        server_name = server_info.get('server_name') or f"Server {server_id}"
                    else:
                        server_name = f"Server {server_id}"
                except Exception as e:
                    logger.warning(f"Не удалось получить название сервера {server_id}: {e}")
                    server_name = f"Server {server_id}"
            
            # Добавляем сервер к профилю
            try:
                if repo.add_server_to_profile(user_id, server_id, server_name):
                    escaped_name = escape_markdown_v2(server_name)
                    await callback.message.edit_text(f"Сервер '{escaped_name}' \\(ID: {server_id}\\) успешно добавлен\\!", parse_mode=ParseMode.MARKDOWN_V2)
                else:
                    await callback.message.edit_text("Ошибка при добавлении сервера. Попробуйте позже.", parse_mode=None)
                    logger.error(f"Не удалось добавить сервер {server_id} к профилю {user_id}")
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                logger.error(f"Исключение при добавлении сервера {server_id} к профилю {user_id}: {e}", {
                    'error': str(e),
                    'traceback': error_trace[:500]
                })
                await callback.message.edit_text("Произошла ошибка при добавлении сервера. Попробуйте позже.", parse_mode=None)
        user_states.pop(user_id, None)
    
    elif data.startswith("servers_page_"):
        page = int(data.replace("servers_page_", ""))
        keyboard = get_servers_list_keyboard(page)
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    
    elif data.startswith("filter_"):
        repo = get_repository()
        profile = get_or_create_profile(user_id, callback.from_user)
        
        # Главное меню фильтров
        if data == "filter_menu_main":
            keyboard = get_filters_main_menu()
            await callback.message.edit_text("Выберите тип фильтров для настройки:", reply_markup=keyboard, parse_mode=None)
        
        # Меню фильтров игроков
        elif data == "filter_menu_player":
            keyboard = get_player_filters_menu()
            await callback.message.edit_text("Настройка фильтров игроков:", reply_markup=keyboard, parse_mode=None)
        
        # Меню фильтров серверов (общие)
        elif data == "filter_menu_server":
            keyboard = get_server_filters_menu()
            await callback.message.edit_text("Настройка фильтров серверов (общие параметры):", reply_markup=keyboard, parse_mode=None)
        
        # Меню Rust-специфичных фильтров
        elif data == "filter_menu_rust":
            keyboard = get_rust_filters_menu()
            await callback.message.edit_text("Настройка Rust-специфичных фильтров:", reply_markup=keyboard, parse_mode=None)
        
        # Отмена настройки фильтров
        elif data == "filter_cancel":
            await callback.message.edit_text("Настройка фильтров отменена.", parse_mode=None)
        
        # Фильтры игроков - переключатели (bool)
        elif data == "filter_player_name":
            player_filter = profile.get_filter(EFilterTypes.player)
            if not player_filter:
                player_filter = PlayerFilter()
            player_filter.player_name_check = not player_filter.player_name_check
            profile.add_filter(player_filter)
            repo.add_profile_filter(user_id, player_filter)
            status = "включена" if player_filter.player_name_check else "отключена"
            await callback.answer(f"Проверка имени игрока {status}", show_alert=True)
        
        elif data == "filter_player_private":
            player_filter = profile.get_filter(EFilterTypes.player)
            if not player_filter:
                player_filter = PlayerFilter()
            player_filter.player_private_check = not player_filter.player_private_check
            profile.add_filter(player_filter)
            repo.add_profile_filter(user_id, player_filter)
            status = "включена" if player_filter.player_private_check else "отключена"
            await callback.answer(f"Проверка приватности игрока {status}", show_alert=True)
        
        # Фильтры серверов - числовые значения
        elif data == "filter_server_players":
            user_states[user_id] = UserState.CONFIGURING_FILTER
            user_data[user_id] = {'filter_type': 'server_players', 'filter_category': 'server'}
            await callback.message.edit_text("Введите минимальное количество игроков (число или -1 для отключения):", parse_mode=None)
        
        elif data == "filter_server_max_players":
            user_states[user_id] = UserState.CONFIGURING_FILTER
            user_data[user_id] = {'filter_type': 'server_max_players', 'filter_category': 'server'}
            await callback.message.edit_text("Введите максимальное количество игроков (число или -1 для отключения):", parse_mode=None)
        
        # Фильтры серверов - переключатели (bool)
        elif data == "filter_server_status":
            rust_filter = profile.get_filter('rust')
            if not rust_filter:
                rust_filter = RustFilter()
                rust_filter._game_id = EGames.rust
            rust_filter.status_check = not rust_filter.status_check
            profile.add_filter(rust_filter)
            repo.add_profile_filter(user_id, rust_filter)
            status = "включена" if rust_filter.status_check else "отключена"
            await callback.answer(f"Проверка статуса сервера {status}", show_alert=True)
        
        elif data == "filter_server_private":
            rust_filter = profile.get_filter('rust')
            if not rust_filter:
                rust_filter = RustFilter()
                rust_filter._game_id = EGames.rust
            rust_filter.private_check = not rust_filter.private_check
            profile.add_filter(rust_filter)
            repo.add_profile_filter(user_id, rust_filter)
            status = "включена" if rust_filter.private_check else "отключена"
            await callback.answer(f"Проверка приватности сервера {status}", show_alert=True)
        
        elif data == "filter_server_ip_port":
            rust_filter = profile.get_filter('rust')
            if not rust_filter:
                rust_filter = RustFilter()
                rust_filter._game_id = EGames.rust
            rust_filter.ip_port_check = not rust_filter.ip_port_check
            profile.add_filter(rust_filter)
            repo.add_profile_filter(user_id, rust_filter)
            status = "включена" if rust_filter.ip_port_check else "отключена"
            await callback.answer(f"Проверка IP/Порта {status}", show_alert=True)
        
        elif data == "filter_server_updated":
            rust_filter = profile.get_filter('rust')
            if not rust_filter:
                rust_filter = RustFilter()
                rust_filter._game_id = EGames.rust
            rust_filter.updated_check = not rust_filter.updated_check
            profile.add_filter(rust_filter)
            repo.add_profile_filter(user_id, rust_filter)
            status = "включена" if rust_filter.updated_check else "отключена"
            await callback.answer(f"Проверка обновлений сервера {status}", show_alert=True)
        
        # Rust-специфичные фильтры
        elif data == "filter_rust_queued":
            user_states[user_id] = UserState.CONFIGURING_FILTER
            user_data[user_id] = {'filter_type': 'rust_queued', 'filter_category': 'rust'}
            await callback.message.edit_text("Введите минимальное количество игроков в очереди (число или -1 для отключения):", parse_mode=None)
        
        elif data == "filter_rust_wipe":
            rust_filter = profile.get_filter('rust')
            if not rust_filter:
                rust_filter = RustFilter()
                rust_filter._game_id = EGames.rust
            rust_filter.last_wipe_check = not rust_filter.last_wipe_check
            profile.add_filter(rust_filter)
            repo.add_profile_filter(user_id, rust_filter)
            status = "включена" if rust_filter.last_wipe_check else "отключена"
            await callback.answer(f"Проверка вайпа {status}", show_alert=True)
        
        elif data == "filter_rust_pve":
            rust_filter = profile.get_filter('rust')
            if not rust_filter:
                rust_filter = RustFilter()
                rust_filter._game_id = EGames.rust
            rust_filter.pve_check = not rust_filter.pve_check
            profile.add_filter(rust_filter)
            repo.add_profile_filter(user_id, rust_filter)
            status = "включена" if rust_filter.pve_check else "отключена"
            await callback.answer(f"Проверка PVE {status}", show_alert=True)
        
        elif data == "filter_rust_url":
            rust_filter = profile.get_filter('rust')
            if not rust_filter:
                rust_filter = RustFilter()
                rust_filter._game_id = EGames.rust
            rust_filter.url_check = not rust_filter.url_check
            profile.add_filter(rust_filter)
            repo.add_profile_filter(user_id, rust_filter)
            status = "включена" if rust_filter.url_check else "отключена"
            await callback.answer(f"Проверка URL {status}", show_alert=True)
        
        elif data == "filter_rust_map_url":
            rust_filter = profile.get_filter('rust')
            if not rust_filter:
                rust_filter = RustFilter()
                rust_filter._game_id = EGames.rust
            rust_filter.map_url_check = not rust_filter.map_url_check
            profile.add_filter(rust_filter)
            repo.add_profile_filter(user_id, rust_filter)
            status = "включена" if rust_filter.map_url_check else "отключена"
            await callback.answer(f"Проверка URL карты {status}", show_alert=True)
        
        elif data == "filter_rust_map_thumb":
            rust_filter = profile.get_filter('rust')
            if not rust_filter:
                rust_filter = RustFilter()
                rust_filter._game_id = EGames.rust
            rust_filter.map_thumbnailUrl_check = not rust_filter.map_thumbnailUrl_check
            profile.add_filter(rust_filter)
            repo.add_profile_filter(user_id, rust_filter)
            status = "включена" if rust_filter.map_thumbnailUrl_check else "отключена"
            await callback.answer(f"Проверка миниатюры карты {status}", show_alert=True)
    
    elif data.startswith("add_player_"):
        if data == "add_player_id":
            user_states[user_id] = UserState.WAITING_PLAYER_ID
            await callback.message.edit_text("Введите ID игрока с сайта BattleMetrics.com:", parse_mode=None)
        elif data == "add_player_name":
            user_states[user_id] = UserState.WAITING_PLAYER_NAME
            await callback.message.edit_text("Введите имя игрока (можно частично):", parse_mode=None)
        elif data == "add_player_cancel":
            await callback.message.edit_text("Добавление игрока отменено.", parse_mode=None)
            user_states.pop(user_id, None)
    
    elif data.startswith("player_select_"):
        player_id = data.replace("player_select_", "")
        # Проверяем, является ли это выбором для добавления или просмотра
        is_view_only = user_data.get(user_id, {}).get('view_player_only', False)
        
        if is_view_only:
            # Показываем информацию об игроке
            repo = get_repository()
            player_info = repo.get_player_full_info(player_id)
            if player_info:
                # Пытаемся получить актуальную информацию через API
                from src.battlemetrics_requests import BattleMetricsResponse
                from aiohttp import ClientSession
                import asyncio
                
                async def show_player_info():
                    try:
                        bm_response = BattleMetricsResponse()
                        await bm_response.async_initialize({})
                        async with ClientSession() as session:
                            player_obj = await bm_response.async_get_player_info(session, player_id)
                            if isinstance(player_obj, Player):
                                info_text = f"👤 Информация об игроке:\n\n{str(player_obj)}"
                                await bot.send_message(chat_id=user_id, text=escape_markdown_v2(info_text), parse_mode=ParseMode.MARKDOWN_V2)
                            else:
                                # Если не удалось получить через API, показываем из БД
                                info_text = format_player_info_from_db(player_info)
                                await bot.send_message(chat_id=user_id, text=info_text, parse_mode=None)
                    except Exception as e:
                        # Показываем информацию из БД в случае ошибки
                        info_text = format_player_info_from_db(player_info)
                        await bot.send_message(chat_id=user_id, text=info_text, parse_mode=None)
                
                asyncio.create_task(show_player_info())
                await callback.message.edit_text("Загружаю информацию об игроке...", parse_mode=None)
            else:
                await callback.message.edit_text("Игрок не найден.", parse_mode=None)
            user_data.pop(user_id, None)
        else:
            # Добавляем игрока к профилю пользователя
            repo = get_repository()
            profile = repo.profiles.get(user_id)
            if not profile:
                # Загружаем профиль из БД или создаем новый
                profile = repo.load_profile(user_id)
                if not profile:
                    profile = Profile(
                        id=user_id,
                        nickname=callback.from_user.username or "",
                        name=callback.from_user.first_name or "",
                        surname=callback.from_user.last_name or ""
                    )
                    repo.add_profile(profile, user_id)
                    repo._insert_profile(user_id)
            
            # Получаем имя игрока
            players = repo.get_players()
            player_name = None
            for name, pid in players.items():
                if pid == player_id:
                    player_name = name
                    break
            
            # Добавляем игрока к профилю
            if repo.add_player_to_profile(user_id, player_id, player_name):
                await callback.message.edit_text(f"Игрок добавлен! ID: {player_id}", parse_mode=None)
            else:
                await callback.message.edit_text("Ошибка при добавлении игрока. Попробуйте позже.", parse_mode=None)
        user_states.pop(user_id, None)
    
    elif data == "servers_cancel":
        await callback.message.edit_text("Выбор сервера отменен.", parse_mode=None)
        user_states.pop(user_id, None)
    
    elif data.startswith("admin_answer_"):
        # Админ выбирает отчет для ответа
        if int(user_id) != ADMIN_ID:
            await callback.answer("Доступ запрещен.", show_alert=True)
            return
        
        suggestion_id = int(data.replace("admin_answer_", ""))
        repo = get_repository()
        # В новой схеме БД таблица suggestions может отсутствовать
        # Пропускаем этот функционал для совместимости
        await callback.answer("Функционал ответов на отчеты временно недоступен.", show_alert=True)
    
    elif data.startswith("view_my_server_"):
        # Пользователь выбирает свой сервер для просмотра
        server_id = data.replace("view_my_server_", "")
        user_data[user_id] = {'view_server_only': True}
        # Используем ту же логику, что и для server_select_ - обрабатываем напрямую
        repo = get_repository()
        server_info = repo.get_server_full_info(server_id)
        if server_info:
            # Пытаемся получить актуальную информацию через API
            from src.battlemetrics_requests import BattleMetricsResponse
            from aiohttp import ClientSession
            import asyncio
            
            async def show_server_info():
                try:
                    bm_response = BattleMetricsResponse()
                    await bm_response.async_initialize({})
                    async with ClientSession() as session:
                        server_obj = await bm_response._get_server_info(session, server_id)
                        if isinstance(server_obj, (Server, RustServer)):
                            info_text = f"📊 Информация о сервере:\n\n{str(server_obj)}"
                            await bot.send_message(chat_id=user_id, text=escape_markdown_v2(info_text), parse_mode=ParseMode.MARKDOWN_V2)
                        else:
                            # Если не удалось получить через API, показываем из БД
                            info_text = format_server_info_from_db(server_info)
                            await bot.send_message(chat_id=user_id, text=info_text, parse_mode=None)
                except Exception as e:
                    # Показываем информацию из БД в случае ошибки
                    info_text = format_server_info_from_db(server_info)
                    await bot.send_message(chat_id=user_id, text=info_text, parse_mode=None)
            
            asyncio.create_task(show_server_info())
            await callback.message.edit_text("Загружаю информацию о сервере...", parse_mode=None)
        else:
            await callback.message.edit_text("Сервер не найден.", parse_mode=None)
        user_data.pop(user_id, None)
        await callback.answer()
        return
    
    elif data.startswith("view_my_player_"):
        # Пользователь выбирает своего игрока для просмотра
        player_id = data.replace("view_my_player_", "")
        user_data[user_id] = {'view_player_only': True}
        # Используем ту же логику, что и для player_select_ - обрабатываем напрямую
        repo = get_repository()
        player_info = repo.get_player_full_info(player_id)
        if player_info:
            # Пытаемся получить актуальную информацию через API
            from src.battlemetrics_requests import BattleMetricsResponse
            from aiohttp import ClientSession
            import asyncio
            
            async def show_player_info():
                try:
                    bm_response = BattleMetricsResponse()
                    await bm_response.async_initialize({})
                    async with ClientSession() as session:
                        player_obj = await bm_response.async_get_player_info(session, player_id)
                        if isinstance(player_obj, Player):
                            info_text = f"👤 Информация об игроке:\n\n{str(player_obj)}"
                            await bot.send_message(chat_id=user_id, text=escape_markdown_v2(info_text), parse_mode=ParseMode.MARKDOWN_V2)
                        else:
                            # Если не удалось получить через API, показываем из БД
                            info_text = format_player_info_from_db(player_info)
                            await bot.send_message(chat_id=user_id, text=info_text, parse_mode=None)
                except Exception as e:
                    # Показываем информацию из БД в случае ошибки
                    info_text = format_player_info_from_db(player_info)
                    await bot.send_message(chat_id=user_id, text=info_text, parse_mode=None)
            
            asyncio.create_task(show_player_info())
            await callback.message.edit_text("Загружаю информацию об игроке...", parse_mode=None)
        else:
            await callback.message.edit_text("Игрок не найден.", parse_mode=None)
        user_data.pop(user_id, None)
        await callback.answer()
        return
    
    await callback.answer()

async def handle_text_message(message: Message, bot: Bot):
    """Обработчик текстовых сообщений"""
    user_id = str(message.from_user.id)
    text = message.text
    state = user_states.get(user_id)
    
    logger.info("Обработка текстового сообщения", {
        'user_id': user_id,
        'state': state if state else None,
        'text_length': len(text) if text else 0
    })
    
    if state == UserState.WAITING_SERVER_ID:
        # Валидация ID сервера
        if text.isdigit():
            server_id = text
            repo = get_repository()
            profile = get_or_create_profile(user_id, message.from_user)
            
            # Проверяем существование сервера через API (асинхронно)
            from src.battlemetrics_requests import BattleMetricsResponse
            from aiohttp import ClientSession
            import asyncio
            
            async def check_and_add_server():
                try:
                    bm_response = BattleMetricsResponse()
                    await bm_response.async_initialize({})
                    async with ClientSession() as session:
                        server_info = await bm_response._get_server_info(session, server_id)
                        if isinstance(server_info, (Server, RustServer)):
                            # Сервер существует, добавляем
                            if repo.add_server_to_profile(user_id, server_id, server_info.name):
                                escaped_name = escape_markdown_v2(server_info.name)
                                await bot.send_message(
                                    chat_id=user_id,
                                    text=f"Сервер '{escaped_name}' \\(ID: {server_id}\\) успешно добавлен\\!",
                                    parse_mode=ParseMode.MARKDOWN_V2
                                )
                            else:
                                await bot.send_message(
                                    chat_id=user_id,
                                    text="Ошибка при добавлении сервера в базу данных\\.",
                                    parse_mode=ParseMode.MARKDOWN_V2
                                )
                        else:
                            await bot.send_message(
                                chat_id=user_id,
                                text=f"Сервер с ID {server_id} не найден на BattleMetrics\\.com\\. Проверьте ID и попробуйте снова\\.",
                                parse_mode=ParseMode.MARKDOWN_V2
                            )
                except Exception as e:
                    import traceback
                    error_trace = traceback.format_exc()
                    repo = get_repository()
                    repo.log_action(
                        object='BotHandlers',
                        action='check_and_add_server',
                        is_error=True,
                        result=str(e),
                        comment=f'Ошибка при проверке сервера {server_id} для пользователя {user_id}: {error_trace[:500]}',
                        id_profile=user_id
                    )
                    await bot.send_message(
                        chat_id=user_id,
                        text=f"Ошибка при проверке сервера: {escape_markdown_v2(str(e))}",
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
            
            # Запускаем проверку в фоне
            asyncio.create_task(check_and_add_server())
            await message.answer(f"Проверяю сервер с ID {server_id}\\.\\.\\.",
                                parse_mode=ParseMode.MARKDOWN_V2)
            user_states.pop(user_id, None)
        else:
            await message.answer("ID сервера должен быть числом. Попробуйте еще раз:", parse_mode=None)
    
    elif state == UserState.WAITING_SERVER_NAME:
        # Поиск сервера по названию
        repo = get_repository()
        try:
            # Поиск в БД с ограничением по игре rust
            matches = repo.search_servers_by_name(text, game_id='rust', limit=10)
            if matches:
                if len(matches) == 1:
                    # Один результат - добавляем сразу
                    server_id, server_name = matches[0]
                    profile = repo.profiles.get(user_id) or repo.load_profile(user_id)
                    if not profile:
                        profile = Profile(
                            id=user_id,
                            nickname=message.from_user.username or "",
                            name=message.from_user.first_name or "",
                            surname=message.from_user.last_name or ""
                        )
                        repo.add_profile(profile, user_id)
                        repo._insert_profile(user_id)
                    
                    try:
                        if repo.add_server_to_profile(user_id, server_id, server_name):
                            escaped_name = escape_markdown_v2(server_name)
                            await message.answer(f"Сервер '{escaped_name}' успешно добавлен\\!", parse_mode=ParseMode.MARKDOWN_V2)
                        else:
                            await message.answer("Ошибка при добавлении сервера. Попробуйте позже.", parse_mode=None)
                            logger.error(f"Не удалось добавить сервер {server_id} к профилю {user_id}")
                    except Exception as e:
                        import traceback
                        error_trace = traceback.format_exc()
                        logger.error(f"Исключение при добавлении сервера {server_id} к профилю {user_id}: {e}", {
                            'error': str(e),
                            'traceback': error_trace[:500]
                        })
                        await message.answer("Произошла ошибка при добавлении сервера. Попробуйте позже.", parse_mode=None)
                else:
                    # Несколько результатов - показываем список
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text=name[:50], callback_data=f"server_select_{server_id}")]
                        for server_id, name in matches[:10]  # Ограничиваем 10 результатами
                    ])
                    await message.answer(f"Найдено несколько серверов. Выберите нужный:", reply_markup=keyboard, parse_mode=None)
            else:
                await message.answer("Серверы с таким названием не найдены. Попробуйте еще раз:", parse_mode=None)
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Ошибка при поиске серверов по названию '{text}' для пользователя {user_id}: {e}", {
                'error': str(e),
                'traceback': error_trace[:500]
            })
            await message.answer("Произошла ошибка при поиске серверов. Попробуйте позже.", parse_mode=None)
        user_states.pop(user_id, None)
    
    elif state == UserState.CONFIGURING_FILTER:
        # Обработка настройки фильтра
        filter_data = user_data.get(user_id, {})
        filter_type = filter_data.get('filter_type')
        filter_category = filter_data.get('filter_category', 'server')
        repo = get_repository()
        profile = repo.profiles.get(user_id) or repo.load_profile(user_id)
        
        if not profile:
            profile = Profile(
                id=user_id,
                nickname=message.from_user.username or "",
                name=message.from_user.first_name or "",
                surname=message.from_user.last_name or ""
            )
            repo.add_profile(profile, user_id)
            repo._insert_profile(user_id)
        
        try:
            value = int(text)
            
            if filter_category == 'server':
                # Общие фильтры серверов
                rust_filter = profile.get_filter('rust')
                if not rust_filter:
                    rust_filter = RustFilter()
                    rust_filter._game_id = EGames.rust
                
                if filter_type == 'server_players':
                    rust_filter.players_check = value
                    await message.answer(f"Минимальное количество игроков установлено: {value if value >= 0 else 'отключено'}", parse_mode=None)
                elif filter_type == 'server_max_players':
                    rust_filter.max_player_check = value
                    await message.answer(f"Максимальное количество игроков установлено: {value if value >= 0 else 'отключено'}", parse_mode=None)
                
                profile.add_filter(rust_filter)
                repo.add_profile_filter(user_id, rust_filter)
                
            elif filter_category == 'rust':
                # Rust-специфичные фильтры
                rust_filter = profile.get_filter('rust')
                if not rust_filter:
                    rust_filter = RustFilter()
                    rust_filter._game_id = EGames.rust
                
                if filter_type == 'rust_queued':
                    rust_filter.queued_players_check = value
                    await message.answer(f"Минимальное количество игроков в очереди установлено: {value if value >= 0 else 'отключено'}", parse_mode=None)
                
                profile.add_filter(rust_filter)
                repo.add_profile_filter(user_id, rust_filter)
            
            user_states.pop(user_id, None)
            user_data.pop(user_id, None)
        except ValueError:
            await message.answer("Введите число или -1 для отключения фильтра:", parse_mode=None)
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            repo.log_action(
                object='BotHandlers',
                action='configure_filter',
                is_error=True,
                result=str(e),
                comment=f'Ошибка при настройке фильтра для пользователя {user_id}: {error_trace[:500]}',
                id_profile=user_id
            )
            await message.answer("Произошла ошибка при настройке фильтра. Попробуйте позже.", parse_mode=None)
    
    elif state == UserState.WAITING_PLAYER_ID:
        # Валидация ID игрока
        if text.isdigit():
            player_id = text
            repo = get_repository()
            profile = get_or_create_profile(user_id, message.from_user)
            
            # Проверяем существование игрока через API (асинхронно)
            from src.battlemetrics_requests import BattleMetricsResponse
            from aiohttp import ClientSession
            import asyncio
            
            async def check_and_add_player():
                try:
                    bm_response = BattleMetricsResponse()
                    await bm_response.async_initialize({})
                    async with ClientSession() as session:
                        player_info = await bm_response.async_get_player_info(session, player_id)
                        if isinstance(player_info, Player):
                            # Игрок существует, добавляем
                            if repo.add_player_to_profile(user_id, player_id, player_info.name):
                                escaped_name = escape_markdown_v2(player_info.name)
                                await bot.send_message(
                                    chat_id=user_id,
                                    text=f"Игрок '{escaped_name}' \\(ID: {player_id}\\) успешно добавлен\\!",
                                    parse_mode=ParseMode.MARKDOWN_V2
                                )
                            else:
                                await bot.send_message(
                                    chat_id=user_id,
                                    text="Ошибка при добавлении игрока в базу данных\\.",
                                    parse_mode=ParseMode.MARKDOWN_V2
                                )
                        else:
                            await bot.send_message(
                                chat_id=user_id,
                                text=f"Игрок с ID {player_id} не найден на BattleMetrics\\.com\\. Проверьте ID и попробуйте снова\\.",
                                parse_mode=ParseMode.MARKDOWN_V2
                            )
                except Exception as e:
                    import traceback
                    error_trace = traceback.format_exc()
                    repo = get_repository()
                    repo.log_action(
                        object='BotHandlers',
                        action='check_and_add_player',
                        is_error=True,
                        result=str(e),
                        comment=f'Ошибка при проверке игрока {player_id} для пользователя {user_id}: {error_trace[:500]}',
                        id_profile=user_id
                    )
                    await bot.send_message(
                        chat_id=user_id,
                        text=f"Ошибка при проверке игрока: {escape_markdown_v2(str(e))}",
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
            
            # Запускаем проверку в фоне
            asyncio.create_task(check_and_add_player())
            await message.answer(f"Проверяю игрока с ID {player_id}\\.\\.\\.",
                                parse_mode=ParseMode.MARKDOWN_V2)
            user_states.pop(user_id, None)
        else:
            await message.answer("ID игрока должен быть числом. Попробуйте еще раз:", parse_mode=None)
    
    elif state == UserState.WAITING_PLAYER_NAME:
        # Поиск игрока по имени
        repo = get_repository()
        # Поиск в БД
        matches = repo.search_players_by_name(text, limit=10)
        if matches:
            if len(matches) == 1:
                # Один результат - добавляем сразу
                player_id, player_name = matches[0]
                profile = repo.profiles.get(user_id) or repo.load_profile(user_id)
                if not profile:
                    profile = Profile(
                        id=user_id,
                        nickname=message.from_user.username or "",
                        name=message.from_user.first_name or "",
                        surname=message.from_user.last_name or ""
                    )
                    repo.add_profile(profile, user_id)
                    repo._insert_profile(user_id)
                
                if repo.add_player_to_profile(user_id, player_id, player_name):
                    escaped_name = escape_markdown_v2(player_name)
                    await message.answer(f"Игрок '{escaped_name}' успешно добавлен\\!", parse_mode=ParseMode.MARKDOWN_V2)
                else:
                    await message.answer("Ошибка при добавлении игрока.", parse_mode=None)
            else:
                # Несколько результатов - показываем список
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=name[:50], callback_data=f"player_select_{player_id}")]
                    for player_id, name in matches[:10]  # Ограничиваем 10 результатами
                ])
                await message.answer(f"Найдено несколько игроков. Выберите нужного:", reply_markup=keyboard, parse_mode=None)
        else:
            await message.answer("Игроки с таким именем не найдены. Попробуйте еще раз:", parse_mode=None)
        user_states.pop(user_id, None)
    
    elif state == UserState.WAITING_REPORT:
        # Отправка отчета администратору
        repo = get_repository()
        
        # В новой схеме БД таблица suggestions может отсутствовать
        # Отправляем отчет напрямую администратору
        report_text = f"Отчет от пользователя {message.from_user.id} (@{message.from_user.username or 'N/A'}):\n\n{text}"
        
        try:
            await bot.send_message(chat_id=ADMIN_ID, text=escape_markdown_v2(report_text), 
                                 parse_mode=ParseMode.MARKDOWN_V2)
            await message.answer("Ваш отчет отправлен администратору. Спасибо!", parse_mode=None)
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            repo.log_action(
                object='BotHandlers',
                action='send_report',
                is_error=True,
                result=str(e),
                comment=f'Ошибка при отправке отчета от пользователя {user_id}: {error_trace[:500]}',
                id_profile=user_id
            )
            await message.answer("Произошла ошибка при отправке отчета. Попробуйте позже.", parse_mode=None)
        
        user_states.pop(user_id, None)
    
    elif state == UserState.ADMIN_ANSWERING_REPORT:
        # Админ отвечает на отчет
        # В новой схеме БД этот функционал временно недоступен
        await message.answer("Функционал ответов на отчеты временно недоступен.", parse_mode=None)
        user_states.pop(user_id, None)
        user_data.pop(user_id, None)
    
    else:
        # Обычное сообщение - показываем главное меню
        await message.answer("Используйте меню для навигации.", reply_markup=get_main_menu(), parse_mode=None)