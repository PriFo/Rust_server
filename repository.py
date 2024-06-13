from pymysql import Connection, connect
from pymysql.cursors import Cursor
from data_classes import Profile
from os import getenv


class Repository:
    #TODO добавление логов для базы данных
    #TODO реализация взаимодействия с базой данных

    # ---Реализация синглтон---
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance.__db_con = None
            cls._instance.__db_cur = None
            cls._instance._profiles = {}
            cls._instance._queue_requests = []
        return cls._instance
    # ---Конец реализации---
    
    def __init__(self) -> None:

        # Подключение к серверу MySQL через переменные .env файла
        if self.__db_con is None:
            self.__db_con: Connection = connect(
                host=getenv('DB_HOST'),
                port=int(getenv('DB_PORT')),
                user=getenv('DB_USER'),
                password=getenv('DB_PASSWORD'),
                database=getenv('DB_NAME')
            )
            
            # Установка курсора для выполнения команд в БД
            self.__db_cur: Cursor = self.__db_con.cursor()
            self._profiles: dict = {}

    async def add_profile(self, value: Profile, id = None) -> None:
        """
        Функция добавления профиля в БД

        :param value: объект класса Profile с полной информацией по профилю пользователя
        :param id: id пользователя телеграм для обращения к БД
        :return: None
        """

        self._profiles[str(id) if id is not None else value.id] = value

    async def update_profile(self, id = None):
        ...

    async def _select_filters(self, profile_id):
        pass

    async def _insert_profile(self, profile_id):
        pass

    async def _insert_rust_filter(self, profile_id):
        pass

    async def execute_queue(self, delay=1) -> None:
        ...