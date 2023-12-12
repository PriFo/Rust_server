import sqlite3
from data_classes import Profile

PROFILES_DB_PATH = ''

class Repository(object):

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance
    
    def __init__(self) -> None:
        self.__db_con: sqlite3.Connection = sqlite3.connect(database=PROFILES_DB_PATH)
        self.__db_cur: sqlite3.Cursor = self.__db_con.cursor()
        self._profiles: dict = {}

    def add_profile(self, value: Profile, id: str = None) -> None:
        self._profiles[str(id) if id is not None else value.id] = value

    def get_filters(self, profile_id: str):
        pass

    def insert_profile(self, profile_id: str):
        pass

    def _insert_rust_filter(self, profile_id: str):
        pass
