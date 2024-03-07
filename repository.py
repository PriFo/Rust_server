import pymysql
from data_classes import Profile
from os import getenv


class Repository(object):

    # ---Реализация синглтон---
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance
    # ---Конец реализации---
    
    def __init__(self) -> None:

        # Подключение к серверу MySQL через переменные .env файла
        self.__db_con: pymysql.Connection = pymysql.connect(
            host=getenv('DB_HOST'),
            port=int(getenv('DB_PORT')),
            user=getenv('DB_USER'),
            password=getenv('DB_PASSWORD'),
            database=getenv('DB_NAME')
        )
        
        # Установка курсора для выполнения команд в БД
        self.__db_cur: pymysql.Cursor = self.__db_con.cursor()
        self._profiles: dict = {}

    def add_profile(self, value: Profile, id: str = None) -> None:
        """
        Функция добавления профиля в БД

        :param value: объект класса Profile с полной информацией по профилю пользователя
        :param id: id пользователя телеграм для обращения к БД
        :return: None
        """
        self._profiles[str(id) if id is not None else value.id] = value

    def get_filters(self, profile_id: str):
        pass

    def insert_profile(self, profile_id: str):
        pass

    def _insert_rust_filter(self, profile_id: str):
        pass
