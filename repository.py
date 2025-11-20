from typing import Union
from pymysql import Connection, connect
from pymysql.cursors import Cursor
from data_classes import Profile
from os import getenv
from SQLSyntaxHelper import (
    MySQLSyntaxHelper as sqlHelper,
    ETablesBM_DB as tablesBM,
)


class Repository:
    #TODO реализация взаимодействия с базой данных

    # ---Реализация синглтон---
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance.__db_con = None
            cls._instance.__db_cur = None
            cls._instance._profiles = {}
            #TODO реализовать очередь запросов
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

    @property
    def profiles(self) -> dict:
        return self._profiles

    def add_profile(self, value: Profile, id = None) -> None:
        """
        Функция добавления профиля в БД

        :param value: объект класса Profile с полной информацией по профилю пользователя
        :param id: id пользователя телеграм для обращения к БД
        :return: None
        """

        self._profiles[str(id) if id is not None else value.id] = value

    def update_profile(self, id: Union[str, None] = None) -> None:
        ...

    def _select_filters(self, profile_id: str) -> None:
        pass

    def _insert_profile(self, profile_id: str) -> None:
        pass
    
    def add_profile_filter(self, profile_id: str) -> None:
        ...

    def get_servers(self) -> dict:
        self.__db_cur.execute(sqlHelper.select(
            table=tablesBM.SERVERS,
            columns=['server_name', 'id_server']
        ))
        rows = self.__db_cur.fetchall()
        result: dict[str, str] = {}
        for row in rows:
            result[row[0]] = row[1]
        return result

    def _insert_rust_filter(self, profile_id: str) -> None:
        pass

    def execute_queue(self, delay: int = 1) -> None:
        ...

    def log_action(
            self, 
            object: Union[str, None] = None,
            action: Union[str, None] = None,
            is_error: bool = False,
            comment: Union[str, None] = None,
            stage: Union[str, None] = None,
            command: Union[str, None] = None,
            result: Union[str, None] = None,
            id_profile: Union[str, None] = None
    ) -> None:
        self.__db_cur.execute(sqlHelper.insert(
            table=tablesBM.LOGS, 
            columns=['object', 'action', 'is_error', 'comment', 'stage', 'command', 'result', 'id_profile'],
            values=[object, action, '1' if is_error else '0', comment, stage, command, result, id_profile]))
        self.__db_con.commit()

    def _log_command(
            self, 
            profile_id: str, 
            object: Union[str, None] = None,
            action: Union[str, None] = None,
            is_error: bool = False,
            comment: Union[str, None] = None,
            stage: Union[str, None] = None,
            command: Union[str, None] = None,
            result: Union[str, None] = None,
            id_profile: Union[str, None] = None
    ) -> None:
        ...
