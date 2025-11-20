import traceback
from data_classes import Profile
from filters import Filter
from repository import Repository
from asyncio import gather, create_task
from aiogram import Bot
from typing import Callable


class EHandlerNames:
    """
    Класс перечисления для стандартизирования наименований существующих обработчиков
    """

    # Server
    players: str = "_players"
    max_players: str = "_max_players"
    status: str = "_status"
    ip_port = "_ip_port"
    private = "_private"

    # Rust
    rust_queued_players: str = "_queued_players"
    rust_last_wipe: str = "_last_wipe"
    rust_next_wipe: str = "_next_wipe"
    updated: str = "_updated"
    rust_pve: str = "_pve"
    rust_url: str = "_url"
    rust_map_url: str = "_map_url"
    rust_map_thumbnailUrl: str = "_map_thumbnailUrl"
    
    # Player
    player_name: str = "_player_name"
    player_private: str = "_player_private"
    player_profile_link: str = "_player_profile_link"
    
    # All differences
    all_diffs: str = 'differences'


class Dispatcher:

    # ---Реализация синглтон---
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._handlers = {}
            cls._instance._bot = None
            # Раскомментировать при наличии реализации БД
            cls._instance._repo: Repository = Repository()
        return cls._instance
    # ---Конец реализации---

    def __init__(self) -> None:
        self._handlers: dict = self._instance._handlers

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
        tasks: list = [
            create_task(
                self.__handle_server_differences_for_profile(id_chat, profile, differences)
            ) for id_chat, profile in self._repo.profiles.items()
        ]
        await gather(*tasks)
    
    #TODO: Реализация обработки изменений для профиля по фильтрам
    async def __handle_server_differences_for_profile(self, id_chat: str, profile: Profile, diffs: list) -> None:
        for diff in diffs:
            game_id = diff.get('game_id')
            filter_obj = profile.get_filter(game_id)
            if filter_obj:
                # TODO: Реализовать фильтрацию и отправку сообщений
                ...

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

        if handler_name == '' or func == None:
            if handler_name == '':
                raise ValueError('Handler name must be filled in')
            else:
                raise TypeError('Function must not be NoneType')
        else:
            if self._handlers.get(handler_name) == None:
                print(f'{type(func)=}')
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
            except ValueError as e:
                self._repo.log_action(
                    object='dispatcher', 
                    action='handler', 
                    is_error=True, 
                    result=traceback.format_exc() + str(e), 
                    stage='wrapper',
                )
            except Exception as e:
                self._repo.log_action(
                    object='dispatcher', 
                    action='handler', 
                    is_error=True, 
                    result=traceback.format_exc() + str(e), 
                    stage='wrapper',
                )

        return wrapper
            
