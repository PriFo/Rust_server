from filters import RustFilter
from repository import Repository
from asyncio import gather


# TODO: закончить написание класса Dispatcher
class Dispatcher(object):

    # ---Реализация синглтон---
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance
    # ---Конец реализации---

    def __init__(self, *args, **kwargs) -> None:
        # Отсутствие реализации бд не позволяет его сейчас использовать
        # self._repo: Repository = Repository()
        self._player_min_handler = None
        self._status_handler = None
        self._private_handler = None
        self._ip_port_handler = None
        self._queued_players_handler = None
        self._last_wipe_handler = None
        self._pve_handler = None
        self._url_handler = None

    async def handle_differences(self, differences: list) -> None:
        for diff in differences:
            # Вывод различий для отладки
            #TODO запуск обработчиков и прием аргументов
            print(f'\033[4m\033[34m{diff["name"]=}:\033[0m\033[32m {diff["new"]=}\033[37m')
    
    async def test_handle(self):
        handlers: list = [
            self._ip_port_handler, self._last_wipe_handler, 
            self._player_min_handler, self._private_handler,
            self._pve_handler, self._queued_players_handler,
            self._status_handler, self._url_handler
        ]
        handlers = [x('OK') for x in handlers if x is not None]
        
        # Вывод справочной информации для отладки программы
        # print(*handlers)
        await gather(*handlers)

    def handler(self, handler: str) -> None:
        """
        Инициализация обработчиков диспетчера по имени \n
        Для использования данного декоратора необходим обязательный \
            входной параметр differences для получения изменений по необходимому параметру сервера

        :param handler: Наименование обработчика, который необходимо инициализировать
        :return: None
        """
        def wrapper(func, *args, **kwargs):
            # Вывод справочной информации для отладки программы
            # print(f'\ndecorator:\n\n{args=}\n{kwargs=}\n{func.__name__=}\n{func=}\n')
            
            # Установка значения для аттребута объекта (переназначение запрещено)
            if getattr(self, f'_{handler}_handler') == None:
                setattr(self, f'_{handler}_handler', func)
            else:
                raise ValueError('Reinitialization of objects is prohibited')
            
            # Вывод справочной информации для отладки программы
            # print(f'\n\n{self.__dir__()}\n\n')
        return wrapper
            