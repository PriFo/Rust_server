from filters import RustFilter
from repository import Repository
from asyncio import gather


class EHandlerNames:
    """
    Класс перечисления для стандартизирования наименований существующих обработчиков
    """
    ...


# TODO: закончить написание класса Dispatcher
class Dispatcher:

    # ---Реализация синглтон---
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)
            cls._instance._handlers = {}
            cls._instance._bot = None
        return cls._instance
    # ---Конец реализации---

    def __init__(self, *args, **kwargs) -> None:
        # Отсутствие реализации бд не позволяет его сейчас использовать
        # self._repo: Repository = Repository()
        self._handlers: dict = self._instance._handlers

    async def handle_differences(self, differences: list) -> None:
        for diff in differences:
            # Вывод различий для отладки
            #TODO запуск обработчиков и прием аргументов
            print(f'\033[4m\033[34m{diff["name"]=}:\033[0m\033[32m {diff["new"]=}\033[37m')
            print(f'{self._handlers=}')
            await self.test_handle(f'{diff["name"]=}: {diff["new"]=}')

    async def add_bot(self, bot):
        if bot is None:
            raise ValueError('Bot can not be NoneType')
        else:
            self._bot = bot
    
    async def test_handle(self, differences = ['OK']):
        handlers = [self._handlers.get(key)(self._bot, differences) for key in self._handlers.keys() if self._handlers.get(key) is not None]
        
        # Вывод справочной информации для отладки программы
        # print(*handlers)

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
            входной параметр differences для получения изменений по необходимому параметру сервера

        :param handler: Наименование обработчика, который необходимо инициализировать
        :return: None
        """

        def wrapper(func):
            # Вывод справочной информации для отладки программы
            # print(f'\ndecorator:\n\n{args=}\n{kwargs=}\n{func.__name__=}\n{func=}\n')
            
            try:
                self._add_handler(handler, func)
            except ValueError as e:
                #TODO добавления в репозиторий логов
                print(f'ValueError({func.__name__=}, {handler=}):', e.args[0])
            
            # Вывод справочной информации для отладки программы
            # print(f'\n\n{self.__dir__()}\n\n')
        return wrapper
            