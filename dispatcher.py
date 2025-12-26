import traceback
from data_classes import Profile
from filters import Filter
from repository import Repository
from asyncio import gather, create_task
from aiogram import Bot
from typing import Callable, Optional, Any


class EHandlerNames:
    """
    Класс перечисления для стандартизирования наименований существующих обработчиков
    Значения соответствуют ключам из API BattleMetrics (attributes и details)
    """

    # Server attributes (соответствуют ключам из data.attributes)
    players: str = "players"
    maxPlayers: str = "maxPlayers"
    status: str = "status"
    ip: str = "ip"
    port: str = "port"
    private: str = "private"
    queryStatus: str = "queryStatus"
    country: str = "country"
    address: str = "address"
    updatedAt: str = "updatedAt"
    createdAt: str = "createdAt"
    portQuery: str = "portQuery"
    rank: str = "rank"

    # Rust details (соответствуют ключам из data.attributes.details)
    rust_queued_players: str = "rust_queued_players"
    rust_last_wipe: str = "rust_last_wipe"
    rust_next_wipe: str = "rust_next_wipe"
    rust_next_wipe_type: str = "rust_next_wipe_type"
    pve: str = "pve"
    rust_url: str = "rust_url"
    rust_maps_url: str = "rust_maps_url"
    rust_maps_thumbnailUrl: str = "rust_maps_thumbnailUrl"
    serverSteamId: str = "serverSteamId"
    rust_modded: str = "rust_modded"
    official: str = "official"
    rust_description: str = "rust_description"
    rust_gamemode: str = "rust_gamemode"
    rust_born: str = "rust_born"
    rust_last_ent_drop: str = "rust_last_ent_drop"
    rust_world_seed: str = "rust_world_seed"
    rust_world_size: str = "rust_world_size"
    
    # Player attributes (соответствуют ключам из data.attributes)
    player_name: str = "name"
    player_private: str = "private"
    player_positiveMatch: str = "positiveMatch"
    player_createdAt: str = "createdAt"
    player_updatedAt: str = "updatedAt"
    
    # All differences
    all_diffs: str = 'differences'


class Dispatcher:

    # ---Реализация синглтон---
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._handlers = {}
            cls._instance._bot = None
            cls._instance._repo: Repository = Repository()
            cls._instance._initialized = False
        return cls._instance
    # ---Конец реализации---

    def __init__(self) -> None:
        if not self._initialized:
            # Используем уже созданные в __new__ атрибуты
            self._initialized = True

    @property
    def repo(self):
        return self._repo

    async def handle_errors(self, errors) -> None:
        self._repo.log_action(
            object='BM_Controller',
            action='get server',
            is_error=True,
            result=str(errors)
        )

    async def handle_server_differences(self, differences: list) -> None:
        """
        Функция для обработки изменений и отправки этих изменений через ранее объявленные в коде обработчики
        """
        # Получаем только активные профили
        active_profile_ids = self._repo.get_active_profiles()
        tasks: list = []
        
        for profile_id in active_profile_ids:
            profile = self._repo.profiles.get(profile_id)
            if not profile:
                # Загружаем профиль из БД если его нет в памяти
                profile = self._repo.load_profile(profile_id)
            if profile and profile.is_active:
                tasks.append(
                    create_task(
                        self.__handle_server_differences_for_profile(profile_id, profile, differences)
                    )
                )
        
        if tasks:
            await gather(*tasks)
    
    async def __handle_server_differences_for_profile(self, id_chat: str, profile: Profile, diffs: list) -> None:
        """
        Обрабатывает изменения серверов для конкретного профиля с учетом фильтров
        Теперь проверяет каждое изменение и вызывает соответствующий обработчик
        """
        if not self._bot:
            return
        
        # Получаем список отслеживаемых серверов профиля
        tracked_servers = list(profile._servers.keys()) if hasattr(profile, '_servers') and profile._servers else []
        
        for diff in diffs:
            # Проверяем, отслеживает ли пользователь этот сервер
            # Сначала проверяем по ID (более точно)
            server_id = diff.get('server_id')
            if server_id:
                if server_id not in tracked_servers:
                    continue
            else:
                # Если ID нет, проверяем по имени (обратная совместимость)
                server_name = diff.get('name', '')
                if not server_name:
                    continue
                
                server_found = False
                for sid, server in profile._servers.items():
                    if hasattr(server, 'name') and server.name == server_name:
                        server_found = True
                        break
                
                if not server_found:
                    continue
            
            game_id = diff.get('game_id', 'rust')
            filter_obj = profile.get_filter(game_id)
            
            if not filter_obj:
                continue
            
            # Получаем список изменений
            new_values = diff.get('new', [])
            old_values = diff.get('old', [])
            
            # Проверяем, нужно ли отправлять изменения согласно фильтру
            if not self._check_filter(diff, filter_obj):
                continue
            
            # Собираем все изменения, которые прошли фильтр
            filtered_changes = []
            for change in new_values:
                for key, new_value in change.items():
                    if key in ['name', 'game_id']:
                        continue
                    
                    # Проверяем, нужно ли отправлять это изменение
                    should_send = self._check_single_change(key, new_value, old_values, filter_obj)
                    
                    if should_send:
                        filtered_changes.append({
                            'field': key,
                            'old_value': self._get_old_value(key, old_values),
                            'new_value': new_value
                        })
                        
                        # Вызываем конкретный обработчик для этого поля
                        handler_name = self._get_handler_name_for_field(key)
                        if handler_name:
                            handler = self._handlers.get(handler_name)
                            if handler:
                                try:
                                    change_dict = {
                                        'field': key,
                                        'old_value': self._get_old_value(key, old_values),
                                        'new_value': new_value,
                                        'name': diff.get('name', 'Unknown'),
                                        'game_id': game_id
                                    }
                                    await handler(self._bot, change_dict, id_chat)
                                except Exception as e:
                                    self._repo.log_action(
                                        object='dispatcher',
                                        action='send_diffs',
                                        is_error=True,
                                        result=str(e),
                                        stage='__handle_server_differences_for_profile',
                                        id_profile=id_chat
                                    )
            
            # Отправляем через общий обработчик только если есть изменения
            if filtered_changes:
                handler = self._handlers.get(EHandlerNames.all_diffs)
                if handler:
                    try:
                        description = self._format_differences(diff)
                        differences_dict = {
                            'description': description,
                            'name': diff.get('name', 'Unknown'),
                            'game_id': game_id,
                            'changes': filtered_changes
                        }
                        await handler(self._bot, differences_dict, id_chat)
                    except Exception as e:
                        self._repo.log_action(
                            object='dispatcher',
                            action='send_diffs',
                            is_error=True,
                            result=str(e),
                            stage='__handle_server_differences_for_profile',
                            id_profile=id_chat
                        )
    
    async def handle_player_differences(self, differences: list) -> None:
        """
        Функция для обработки изменений игроков и отправки этих изменений пользователям
        """
        # Получаем только активные профили
        active_profile_ids = self._repo.get_active_profiles()
        tasks: list = []
        
        for profile_id in active_profile_ids:
            profile = self._repo.profiles.get(profile_id)
            if not profile:
                # Загружаем профиль из БД если его нет в памяти
                profile = self._repo.load_profile(profile_id)
            if profile and profile.is_active:
                tasks.append(
                    create_task(
                        self.__handle_player_differences_for_profile(profile_id, profile, differences)
                    )
                )
        
        if tasks:
            await gather(*tasks)
    
    async def __handle_player_differences_for_profile(self, id_chat: str, profile: Profile, diffs: list) -> None:
        """
        Обрабатывает изменения игроков для конкретного профиля
        Проверяет, отслеживает ли пользователь этого игрока
        """
        if not self._bot:
            return
        
        # Получаем список отслеживаемых игроков профиля
        tracked_players = list(profile._players.keys()) if hasattr(profile, '_players') else []
        
        for diff in diffs:
            player_id = diff.get('player_id')
            player_name = diff.get('player_name', 'Unknown Player')
            
            # Проверяем, отслеживает ли пользователь этого игрока
            if player_id not in tracked_players:
                continue
            
            # Получаем список изменений
            new_values = diff.get('new', [])
            old_values = diff.get('old', [])
            
            if not new_values and not old_values:
                continue
            
            # Формируем сообщение об изменениях
            changes_text = []
            for change in new_values:
                for key, value in change.items():
                    if key == 'online':
                        old_online = self._get_old_value_from_list('online', old_values)
                        status_text = "онлайн" if value else "оффлайн"
                        old_status_text = "онлайн" if old_online else "оффлайн"
                        changes_text.append(f"Статус: {old_status_text} → {status_text}")
                    elif key == 'online_server_id':
                        old_server_id = self._get_old_value_from_list('online_server_id', old_values)
                        if old_server_id != value:
                            if value:
                                changes_text.append(f"Игрок зашел на сервер (ID: {value})")
                            else:
                                changes_text.append(f"Игрок вышел с сервера (ID: {old_server_id})")
                    elif key == 'server_online':
                        if isinstance(value, dict):
                            server_id = value.get('server_id')
                            online = value.get('online')
                            old_server_online = self._get_old_value_from_list('server_online', old_values)
                            if isinstance(old_server_online, dict) and old_server_online.get('server_id') == server_id:
                                old_online = old_server_online.get('online', False)
                                if old_online != online:
                                    status_text = "онлайн" if online else "оффлайн"
                                    changes_text.append(f"На сервере {server_id}: {status_text}")
            
            if changes_text:
                message_text = f"Изменения у игрока {player_name} (ID: {player_id}):\n" + "\n".join(changes_text)
                try:
                    await self._bot.send_message(chat_id=id_chat, text=message_text, parse_mode=None)
                except Exception as e:
                    self._repo.log_action(
                        object='dispatcher',
                        action='send_player_diffs',
                        is_error=True,
                        result=str(e),
                        stage='__handle_player_differences_for_profile',
                        id_profile=id_chat
                    )
    
    def _get_old_value_from_list(self, key: str, old_values: list) -> Optional[Any]:
        """Получает старое значение для ключа из списка изменений"""
        for change in old_values:
            if isinstance(change, dict) and key in change:
                return change[key]
        return None
    
    def _get_handler_name_for_field(self, field: str) -> Optional[str]:
        """Возвращает имя обработчика для поля"""
        field_to_handler = {
            'players': EHandlerNames.players,
            'maxPlayers': EHandlerNames.maxPlayers,
            'status': EHandlerNames.status,
            'rust_queued_players': EHandlerNames.rust_queued_players,
            'rust_last_wipe': EHandlerNames.rust_last_wipe,
            'rust_next_wipe': EHandlerNames.rust_next_wipe,
            'pve': EHandlerNames.pve,
            'private': EHandlerNames.private
        }
        return field_to_handler.get(field)
    
    def _get_old_value(self, key: str, old_values: list) -> Optional[Any]:
        """Получает старое значение для ключа"""
        for change in old_values:
            if key in change:
                return change[key]
        return None
    
    def _check_single_change(self, key: str, new_value: Any, old_values: list, filter_obj) -> bool:
        """Проверяет одно изменение по фильтру"""
        # Маппинг ключей API на атрибуты фильтра
        filter_attr_map = {
            'players': 'players_check',
            'maxPlayers': 'max_player_check',
            'status': 'status_check',
            'private': 'private_check',
            'rust_queued_players': 'queued_players_check',
            'rust_last_wipe': 'last_wipe_check',
            'rust_next_wipe': 'next_wipe_check',
            'pve': 'pve_check'
        }
        
        filter_attr = filter_attr_map.get(key)
        if filter_attr and hasattr(filter_obj, filter_attr):
            check_value = getattr(filter_obj, filter_attr, None)
            
            if check_value is None:
                return False
            
            # Для числовых фильтров
            if isinstance(check_value, int) and check_value >= 0:
                if key in ['players', 'maxPlayers', 'rust_queued_players']:
                    if isinstance(new_value, (int, float)) and new_value >= check_value:
                        return True
            
            # Для булевых фильтров
            elif isinstance(check_value, bool) and check_value:
                if key in ['status', 'rust_last_wipe', 'rust_next_wipe', 'pve', 'private']:
                    return True
        
        return False
    
    def _check_filter(self, diff: dict, filter_obj) -> bool:
        """
        Проверяет, нужно ли отправлять изменения согласно фильтру
        """
        old_values = diff.get('old', [])
        new_values = diff.get('new', [])
        
        # Проверяем каждое изменение
        for change in new_values:
            for key, new_value in change.items():
                # Пропускаем служебные поля
                if key in ['name', 'game_id']:
                    continue
                
                # Проверяем фильтры в зависимости от типа (используем ключи из API)
                # Маппинг ключей API на атрибуты фильтра
                filter_attr_map = {
                    'players': 'players_check',
                    'maxPlayers': 'max_player_check',
                    'status': 'status_check',
                    'private': 'private_check',
                    'rust_queued_players': 'queued_players_check',
                    'rust_last_wipe': 'last_wipe_check',
                    'rust_next_wipe': 'next_wipe_check',
                    'pve': 'pve_check'
                }
                
                filter_attr = filter_attr_map.get(key)
                if filter_attr and hasattr(filter_obj, filter_attr):
                    check_value = getattr(filter_obj, filter_attr, None)
                    
                    if check_value is None:
                        continue
                    
                    # Для числовых фильтров (players, maxPlayers, queued_players)
                    if isinstance(check_value, int) and check_value >= 0:
                        if key in ['players', 'maxPlayers', 'rust_queued_players']:
                            if isinstance(new_value, (int, float)) and new_value >= check_value:
                                return True
                    
                    # Для булевых фильтров
                    elif isinstance(check_value, bool) and check_value:
                        # Проверяем изменение статуса, вайпа и т.д.
                        if key in ['status', 'rust_last_wipe', 'rust_next_wipe', 'pve', 'private']:
                            return True
        
        return False
    
    def _format_differences(self, diff: dict) -> str:
        """
        Форматирует различия в читаемый текст
        """
        name = diff.get('name', 'Unknown Server')
        old_values = diff.get('old', [])
        new_values = diff.get('new', [])
        
        lines = [f"Изменения на сервере: {name}"]
        
        # Формируем описание изменений
        changes = []
        for change in new_values:
            for key, value in change.items():
                if key in ['name', 'game_id']:
                    continue
                
                # Находим старое значение
                old_value = None
                for old_change in old_values:
                    if key in old_change:
                        old_value = old_change[key]
                        break
                
                # Форматируем изменение
                key_name = self._get_field_name(key)
                if old_value is not None:
                    changes.append(f"{key_name}: {old_value} → {value}")
                else:
                    changes.append(f"{key_name}: {value}")
        
        if changes:
            lines.extend(changes)
        else:
            lines.append("Обнаружены изменения, но детали не указаны")
        
        return "\n".join(lines)
    
    def _get_field_name(self, key: str) -> str:
        """
        Возвращает читаемое имя поля
        """
        field_names = {
            'players': 'Игроки',
            'maxPlayers': 'Макс. игроки',
            'status': 'Статус',
            'rust_queued_players': 'Очередь',
            'rust_last_wipe': 'Последний вайп',
            'rust_next_wipe': 'Следующий вайп',
            'rust_next_wipe_type': 'Тип следующего вайпа',
            'pve': 'PVE',
            'private': 'Приватный',
            'rust_url': 'URL сервера',
            'rust_maps_url': 'URL карты',
            'rust_maps_thumbnailUrl': 'Миниатюра карты'
        }
        return field_names.get(key, key)

    async def add_bot(self, bot: Bot = None):
        """
        Функция для добавления бота, с помощью которого отправляются изменения пользователям (бот может быть лишь один\
            его перезапись означает смену бота для отправки сообщений)

        :param bot: Объект класса aiogram.Bot, с помощью которого происходит отправка изменений
        :return None:
        """

        if bot:
            if not isinstance(bot, Bot):
                raise TypeError(f"Argument bot must be aiogram.Bot, not {type(bot)}")
            self._bot = bot
        else:
            raise ValueError('Bot can not be NoneType')
    
    async def test_handle(self, differences = ['OK']):

        """
        Функция для тестовой обработки декорируемых функций

        :param differences: словарь с изменениями, если изменения не посылаются, то является списком с элементом OK
        :return None:
        """

        #заполнение списка обработчиков объектами типа asyncio.Future для всех ключей, где значение заполнено
        handlers = [
            create_task(
                self._handlers.get(key)(self._bot, differences)
            ) for key in self._handlers.keys() if self._handlers.get(key) is not None]

        await gather(*handlers)

    def _add_handler(self, handler_name: str = '', func: Callable = None):

        """
        Приватная функция для класса диспетчер и дочерних классов для добавления обработчиков по их наименованию

        :param handler_name: Ключ для добавления в словарь обработчиков и поиска необходимого
        :param func: Функция-обработчик для отложенного выполнения

        :return None:
        """

        if handler_name == '' or func is None:
            if handler_name == '':
                raise ValueError('Handler name must be filled in')
            else:
                raise TypeError('Function must not be NoneType')
        else:
            if self._handlers.get(handler_name) is None:
                self._handlers[handler_name] = func
            else:
                raise ValueError('Reinitialization of the handler is prohibited')

    def handler(self, handler: str) -> None:

        """
        Инициализация обработчиков диспетчера по имени \n
        Для использования данного декоратора необходим обязательный \
            входной параметр differences в декорируемой функции для получения изменений по \
                необходимому параметру сервера

        :param handler: Наименование обработчика, который необходимо инициализировать
        :return None:
        """

        def wrapper(func):
            """
            Внутренняя функция для работы декоратора

            :param func: Декорируемая функция
            :return None:
            """
            
            try:
                self._add_handler(handler, func)
            except (ValueError, TypeError) as e:
                self._repo.log_action(
                    object='dispatcher', 
                    action='handler', 
                    is_error=True, 
                    result=traceback.format_exc() + str(e), 
                    stage='wrapper',
                )
                raise
            except Exception as e:
                self._repo.log_action(
                    object='dispatcher', 
                    action='handler', 
                    is_error=True, 
                    result=traceback.format_exc() + str(e), 
                    stage='wrapper',
                )
                raise

        return wrapper
            
