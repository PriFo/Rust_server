from filters import RustFilter
from repository import Repository
from asyncio import gather, create_task


class EHandlerNames:
    """
    Класс перечисления для стандартизирования наименований существующих обработчиков
    """
    players_changed: str = "players_min"
    status: str = "status"
    rust_last_wipe_changed: str = "rust_last_wipe_changed"
    rust_next_wipe_changed: str = "rust_next_wipe_changed"
    updated: str = "updated"
    rust_queued_players_changed: str = "rust_queued_players_changed"
    rust_map_url_changed: str = 'rust_map_url_changed'
    rust_map_thumbnailUrl_changed: str = 'rust_map_thumbnailUrl_changed'


# TODO: закончить написание класса Dispatcher
class Dispatcher:

    # ---Реализация синглтон---
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._handlers = {}
            cls._instance._bot = None
            # Раскомментировать при наличии реализации БД
            # cls._repo: Repository = Repository()
        return cls._instance
    # ---Конец реализации---

    def __init__(self, *args, **kwargs) -> None:
        self._handlers: dict = self._instance._handlers

    async def handle_differences(self, differences: list) -> None:
        """
        Функция для обработки изменений и отправки этих изменений через 
        """
        
        for diff in differences:
            # Вывод различий для отладки
            #TODO запуск обработчиков и прием аргументов
            print(f'\033[4m\033[34m{diff["name"]=}:\033[0m\033[32m {diff["new"]=}\033[37m')
            print(f'{self._handlers=}')
            await self.test_handle(f'{diff["name"]=}: {diff["new"]=}')

    async def add_bot(self, bot):
        """
        Функция для добавления бота, с помощью которого отправляются изменения пользователям (бот может быть лишь один\
            его перезапись означает смену бота для отправки сообщений)

        :param bot: Объект класса aiogram.Bot, с помощью которого происходит отправка изменений
        :return: None
        """

        if bot is None:
            raise ValueError('Bot can not be NoneType')
        else:
            self._bot = bot
    
    async def test_handle(self, differences = ['OK']):

        """
        Функция для тестовой обработки декорируемых функций

        :param differences: словарь с изменениями, если изменения не посылаются, то является списком с элементом OK
        :return: None
        """

        #заполнение списка обработчиков объектами типа asyncio.Future для всех ключей, где значение заполнено
        handlers = [
            create_task(
                self._handlers.get(key)(self._bot, differences)
            ) for key in self._handlers.keys() if self._handlers.get(key) is not None]

        await gather(*handlers)

    def _add_handler(self, handler_name: str = '', func = None):

        """
        Приватная функция для класса диспетчер и дочерних классов для добавления обработчиков по их наименованию

        :param handler_name: Ключ для добавления в словарь обработчиков и поиска необходимого
        :param func: Функция-обработчик Future для отложенного выполнения

        :return: None
        """

        if handler_name == '' or func == None:
            if handler_name == '':
                raise ValueError('Handler name must be filled in')
            else:
                raise ValueError('Function must not be NoneType')
        else:
            if self._handlers.get(handler_name) == None:
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
        :return: None
        """

        def wrapper(func):
            """
            Внутренняя функция для работы декоратора

            :param func: Декорируемая функция
            :return: None
            """
            
            try:
                self._add_handler(handler, func)
            except ValueError as e:
                #TODO добавления в репозиторий логов
                print(f'ValueError({func.__name__=}, {handler=}):', e.args[0])

        return wrapper
            