from typing import Union, Optional
from pymysql import Connection, connect
from pymysql.cursors import Cursor
from data_classes import Profile, RustServer
from filters import Filter, RustFilter
from os import getenv
from SQLSyntaxHelper import (
    MySQLSyntaxHelper as sqlHelper,
    ETablesBM_DB as tablesBM,
)
from logger import Logger

from collections import deque
import atexit

class Repository:
    # ---Реализация синглтон---
    _instance = None
    _db_initialized = False

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance.__db_con = None
            cls._instance.__db_cur = None
            cls._instance._profiles = {}
            cls._instance._db_initialized = False
            cls._instance._write_queue = deque()  # Очередь для записи
            cls._instance._profile_cache_ttl = {}  # TTL для кэша профилей (в секундах)
            cls._instance._default_ttl = 3600  # 1 час по умолчанию
            cls._instance._logger = Logger("Repository")
        # Регистрируем обработчик для сохранения очереди при выходе
        atexit.register(cls._instance._flush_queue_on_exit)
        return cls._instance
    # ---Конец реализации---
    
    def __init__(self) -> None:
        if not self._db_initialized:
            # Не инициализируем подключение в __init__, делаем ленивую инициализацию
            self._profiles: dict = {}
            if not hasattr(self, '_logger'):
                self._logger = Logger("Repository")
    
    def _ensure_db_connection(self) -> None:
        """Инициализирует подключение к БД если оно еще не установлено"""
        if self.__db_con is None:
            try:
                # Проверяем наличие всех необходимых переменных окружения
                db_host = getenv('DB_HOST')
                db_port_str = getenv('DB_PORT')
                db_user = getenv('DB_USER')
                db_password = getenv('DB_PASSWORD')
                db_name = getenv('DB_NAME')
                
                self._logger.info("Инициализация подключения к БД", {
                    'host': db_host,
                    'port': db_port_str,
                    'user': db_user,
                    'database': db_name
                })
                
                if not db_host:
                    raise ValueError("DB_HOST не установлена в переменных окружения")
                if not db_port_str:
                    raise ValueError("DB_PORT не установлена в переменных окружения")
                if not db_user:
                    raise ValueError("DB_USER не установлена в переменных окружения")
                if not db_password:
                    raise ValueError("DB_PASSWORD не установлена в переменных окружения")
                if not db_name:
                    raise ValueError("DB_NAME не установлена в переменных окружения")
                
                # Преобразуем порт в int
                try:
                    db_port = int(db_port_str)
                except ValueError:
                    raise ValueError(f"DB_PORT должна быть числом, получено: {db_port_str}")
                
                self.__db_con: Connection = connect(
                    host=db_host,
                    port=db_port,
                    user=db_user,
                    password=db_password,
                    database=db_name
                )
                # Установка курсора для выполнения команд в БД
                self.__db_cur: Cursor = self.__db_con.cursor()
                self._db_initialized = True
                
                self._logger.info("Подключение к БД установлено успешно", {
                    'host': db_host,
                    'port': db_port,
                    'database': db_name
                })
                
                # Выводим метаданные БД
                self._log_database_metadata()
            except Exception as e:
                self._logger.error(f"Ошибка подключения к БД: {e}")
                raise ConnectionError(f"Failed to connect to database: {e}")
    
    def close(self) -> None:
        """Закрывает соединение с БД"""
        if self.__db_cur:
            self.__db_cur.close()
        if self.__db_con:
            self.__db_con.close()
            self.__db_con = None
            self._db_initialized = False

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
        """Обновляет профиль в БД"""
        if id is None:
            return
        profile = self._profiles.get(str(id))
        if not profile:
            return
        
        self._ensure_db_connection()
        try:
            # Экранируем одинарные кавычки для безопасности
            def escape_sql_string(value: str) -> str:
                if value is None:
                    return 'None'
                return str(value).replace("'", "''")
            
            nickname = escape_sql_string(profile.nickname)
            name = escape_sql_string(profile.name)
            surname = escape_sql_string(profile.surname)
            
            # Формируем WHERE условие без двойного WHERE
            where_clause = sqlHelper.where('id_profile', str(id)).replace('WHERE ', '')
            query = sqlHelper.update(
                table=tablesBM.PROFILES,
                set_clause=f"profile_nickname='{nickname}', profile_name='{name}', profile_surname='{surname}'",
                where=where_clause
            )
            self._write_queue.append(('execute', query))
            self._write_queue.append(('commit', None))
            self._process_write_queue()
        except Exception as e:
            self.log_action(
                object='repository',
                action='update_profile',
                is_error=True,
                result=str(e),
                id_profile=str(id)
            )

    def _select_filters(self, profile_id: str) -> list:
        """Получает все фильтры пользователя из БД (устаревший метод, используйте load_profile)"""
        # Метод оставлен для обратной совместимости, но теперь фильтры загружаются через load_profile
        # Возвращаем пустой список, так как фильтры теперь загружаются напрямую через FK в profiles
        return []

    def activate_profile(self, profile_id: str) -> bool:
        """Активирует профиль пользователя"""
        self._ensure_db_connection()
        try:
            # Формируем WHERE условие без двойного WHERE
            where_clause = sqlHelper.where('id_profile', profile_id).replace('WHERE ', '')
            query = sqlHelper.update(
                table=tablesBM.PROFILES,
                set_clause="is_active='1'",
                where=where_clause
            )
            self.__db_cur.execute(query)
            self.__db_con.commit()
            
            # Обновляем в памяти
            profile = self._profiles.get(profile_id)
            if profile:
                profile.is_active = True
            
            self.log_action(
                object='repository',
                action='activate_profile',
                comment=f'Профиль {profile_id} активирован',
                id_profile=profile_id
            )
            return True
        except Exception as e:
            self.log_action(
                object='repository',
                action='activate_profile',
                is_error=True,
                result=str(e),
                id_profile=profile_id
            )
            return False
    
    def deactivate_profile(self, profile_id: str) -> bool:
        """Деактивирует профиль пользователя"""
        self._ensure_db_connection()
        try:
            # Формируем WHERE условие без двойного WHERE
            where_clause = sqlHelper.where('id_profile', profile_id).replace('WHERE ', '')
            query = sqlHelper.update(
                table=tablesBM.PROFILES,
                set_clause="is_active='0'",
                where=where_clause
            )
            self.__db_cur.execute(query)
            self.__db_con.commit()
            
            # Обновляем в памяти
            profile = self._profiles.get(profile_id)
            if profile:
                profile.is_active = False
            
            self.log_action(
                object='repository',
                action='deactivate_profile',
                comment=f'Профиль {profile_id} деактивирован',
                id_profile=profile_id
            )
            return True
        except Exception as e:
            self.log_action(
                object='repository',
                action='deactivate_profile',
                is_error=True,
                result=str(e),
                id_profile=profile_id
            )
            return False
    
    def get_active_profiles(self) -> list[str]:
        """Получает список ID активных профилей"""
        self._ensure_db_connection()
        try:
            query = sqlHelper.select(
                table=tablesBM.PROFILES,
                columns=['id_profile'],
                where=sqlHelper.where('is_active', '1')
            )
            self.__db_cur.execute(query)
            rows = self.__db_cur.fetchall()
            return [str(row[0]) for row in rows]
        except Exception as e:
            self.log_action(
                object='repository',
                action='get_active_profiles',
                is_error=True,
                result=str(e)
            )
            return []
    
    def get_inactive_profiles(self) -> list[str]:
        """Получает список ID неактивных профилей"""
        self._ensure_db_connection()
        try:
            query = sqlHelper.select(
                table=tablesBM.PROFILES,
                columns=['id_profile'],
                where=sqlHelper.where('is_active', '0')
            )
            self.__db_cur.execute(query)
            rows = self.__db_cur.fetchall()
            return [str(row[0]) for row in rows]
        except Exception as e:
            self.log_action(
                object='repository',
                action='get_inactive_profiles',
                is_error=True,
                result=str(e)
            )
            return []
    
    def get_active_profiles_with_servers(self) -> list[str]:
        """Получает список ID активных профилей, у которых есть серверы (через profiles_servers_conn)"""
        self._ensure_db_connection()
        try:
            query = f"""
                SELECT DISTINCT p.id_profile
                FROM {tablesBM.PROFILES} p
                INNER JOIN {tablesBM.PROFILES_SERVERS_CONN} psc ON p.id_profile = psc.fk_id_profile
                WHERE p.is_active = 1
            """
            self.__db_cur.execute(query)
            rows = self.__db_cur.fetchall()
            return [str(row[0]) for row in rows]
        except Exception as e:
            self.log_action(
                object='repository',
                action='get_active_profiles_with_servers',
                is_error=True,
                result=str(e)
            )
            return []
    
    def _insert_profile(self, profile_id: str) -> None:
        """Добавляет профиль в БД (если его еще нет) или обновляет существующий"""
        profile = self._profiles.get(profile_id)
        if not profile:
            self._logger.warning(f"Попытка вставить профиль {profile_id}, но его нет в памяти")
            return
        
        self._ensure_db_connection()
        try:
            # Экранируем одинарные кавычки для безопасности
            def escape_sql_string(value: str) -> str:
                if value is None:
                    return 'None'
                return str(value).replace("'", "''")
            
            nickname = escape_sql_string(profile.nickname or '')
            name = escape_sql_string(profile.name or '')
            surname = escape_sql_string(profile.surname or '')
            
            # Проверяем, существует ли профиль в БД
            check_query = sqlHelper.select(
                table=tablesBM.PROFILES,
                columns=['id_profile'],
                where=sqlHelper.where('id_profile', profile_id)
            )
            self.__db_cur.execute(check_query)
            existing = self.__db_cur.fetchone()
            
            if existing:
                # Профиль существует, обновляем его
                self._logger.info(f"Профиль {profile_id} уже существует в БД, обновляем")
                where_clause = sqlHelper.where('id_profile', profile_id).replace('WHERE ', '')
                update_query = sqlHelper.update(
                    table=tablesBM.PROFILES,
                    set_clause=f"profile_nickname='{nickname}', profile_name='{name}', profile_surname='{surname}'",
                    where=where_clause
                )
                self._logger.debug(f"UPDATE запрос: {update_query}")
                self.__db_cur.execute(update_query)
                self.__db_con.commit()
                self._logger.info(f"Профиль {profile_id} успешно обновлен в БД")
            else:
                # Профиль не существует, создаем новый
                self._logger.info(f"Создаем новый профиль {profile_id} в БД")
                # Формируем INSERT запрос вручную (без несуществующих колонок fk_id_server_filter и fk_id_player_filter)
                query = f"""INSERT INTO {tablesBM.PROFILES} 
                    (id_profile, profile_nickname, profile_name, profile_surname, bot_banned, is_active) 
                    VALUES ('{profile_id}', '{nickname}', '{name}', '{surname}', '0', '0')"""
                self._logger.debug(f"INSERT запрос: {query}")
                try:
                    self.__db_cur.execute(query)
                    self.__db_con.commit()
                    self._logger.info(f"Профиль {profile_id} успешно создан в БД")
                except Exception as insert_error:
                    self._logger.error(f"Ошибка при выполнении INSERT для профиля {profile_id}: {insert_error}")
                    # Пробуем альтернативный способ - без NULL колонок
                    try:
                        query2 = f"""INSERT INTO {tablesBM.PROFILES} 
                            (id_profile, profile_nickname, profile_name, profile_surname, bot_banned, is_active) 
                            VALUES ('{profile_id}', '{nickname}', '{name}', '{surname}', '0', '0')"""
                        self._logger.debug(f"Пробуем альтернативный INSERT: {query2}")
                        self.__db_cur.execute(query2)
                        self.__db_con.commit()
                        self._logger.info(f"Профиль {profile_id} успешно создан в БД (альтернативный способ)")
                    except Exception as insert_error2:
                        self._logger.error(f"Ошибка при альтернативном INSERT для профиля {profile_id}: {insert_error2}")
                        raise insert_error2
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            self._logger.error(f"Ошибка при вставке/обновлении профиля {profile_id}: {e}")
            self._logger.error(f"Traceback: {error_trace}")
            self.log_action(
                object='repository',
                action='_insert_profile',
                is_error=True,
                result=str(e),
                comment=f'Ошибка при вставке профиля {profile_id}: {error_trace[:500]}',
                id_profile=profile_id
            )
    
    def add_profile_filter(self, profile_id: str, filter_obj: Filter, game_id: str = 'rust', server_id: str = '0') -> None:
        """Добавляет фильтр пользователя (прямая связь через FK в profiles)"""
        self._ensure_db_connection()
        try:
            from filters import RustFilter, PlayerFilter
            
            if isinstance(filter_obj, RustFilter):
                # Проверяем, есть ли уже фильтр для этого профиля (через fk_id_profile в server_filters)
                server_filter_check_query = sqlHelper.select(
                    table=tablesBM.SERVER_FILTERS,
                    columns=['id_filter'],
                    where=sqlHelper.where('fk_id_profile', profile_id)
                )
                self.__db_cur.execute(server_filter_check_query)
                server_filter_row = self.__db_cur.fetchone()
                
                if server_filter_row:
                    # Обновляем существующий server_filter
                    server_filter_id = server_filter_row[0]
                    where_clause = sqlHelper.where('id_filter', str(server_filter_id)).replace('WHERE ', '')
                    update_query = sqlHelper.update(
                        table=tablesBM.SERVER_FILTERS,
                        set_clause=f"player_count={filter_obj.players_check}, max_player_count={filter_obj.max_player_check}, status_check={'1' if filter_obj.status_check else '0'}, ip_port_check={'1' if filter_obj.ip_port_check else '0'}, private_check={'1' if filter_obj.private_check else '0'}",
                        where=where_clause
                    )
                    self._write_queue.append(('execute', update_query))
                else:
                    # Создаем новый server_filter с fk_id_profile
                    server_filter_query = sqlHelper.insert(
                        table=tablesBM.SERVER_FILTERS,
                        columns=['fk_id_profile', 'fk_servers_id', 'player_count', 'max_player_count', 'status_check', 'ip_port_check', 'private_check'],
                        values=[profile_id, server_id, str(filter_obj.players_check), str(filter_obj.max_player_check), 
                               '1' if filter_obj.status_check else '0', 
                               '1' if filter_obj.ip_port_check else '0',
                               '1' if filter_obj.private_check else '0']
                    )
                    self._write_queue.append(('execute', server_filter_query))
                    self._process_write_queue()
                    self.__db_cur.execute("SELECT LAST_INSERT_ID()")
                    server_filter_id = self.__db_cur.fetchone()[0]
                
                # Создаем или обновляем rust_servers_filter
                self._add_or_update_rust_server_filter(server_filter_id, filter_obj)
                
                self._write_queue.append(('commit', None))
                self._process_write_queue()
                
            elif isinstance(filter_obj, PlayerFilter):
                # Проверяем, есть ли уже фильтр для этого профиля (через fk_id_profile в player_filters)
                player_filter_check_query = sqlHelper.select(
                    table=tablesBM.PLAYER_FILTERS,
                    columns=['id_player_filter'],
                    where=sqlHelper.where('fk_id_profile', profile_id)
                )
                self.__db_cur.execute(player_filter_check_query)
                player_filter_row = self.__db_cur.fetchone()
                
                if player_filter_row:
                    # Обновляем существующий player_filter
                    player_filter_id = player_filter_row[0]
                    where_clause = sqlHelper.where('id_player_filter', str(player_filter_id)).replace('WHERE ', '')
                    update_query = sqlHelper.update(
                        table=tablesBM.PLAYER_FILTERS,
                        set_clause=f"player_name_changed={'1' if filter_obj.player_name_check else '0'}, player_private_changed={'1' if filter_obj.player_private_check else '0'}",
                        where=where_clause
                    )
                    self._write_queue.append(('execute', update_query))
                else:
                    # Создаем новый player_filter с fk_id_profile
                    player_filter_query = sqlHelper.insert(
                        table=tablesBM.PLAYER_FILTERS,
                        columns=['fk_id_profile', 'fk_id_players', 'player_name_changed', 'player_private_changed', 'proofile_link_changed'],
                        values=[profile_id, '0', '1' if filter_obj.player_name_check else '0', 
                               '1' if filter_obj.player_private_check else '0', '0']
                    )
                    self._write_queue.append(('execute', player_filter_query))
                    self._process_write_queue()
                    self.__db_cur.execute("SELECT LAST_INSERT_ID()")
                    player_filter_id = self.__db_cur.fetchone()[0]
                
                self._write_queue.append(('commit', None))
                self._process_write_queue()
            
            # Добавляем фильтр в профиль в памяти
            profile = self._profiles.get(profile_id)
            if profile:
                profile.add_filter(filter_obj)
                
        except Exception as e:
            self.log_action(
                object='repository',
                action='add_profile_filter',
                is_error=True,
                result=str(e),
                id_profile=profile_id
            )

    def get_servers(self) -> dict:
        """Получает список всех серверов из БД"""
        self._ensure_db_connection()
        self.__db_cur.execute(sqlHelper.select(
            table=tablesBM.SERVERS,
            columns=['server_name', 'id_server']
        ))
        rows = self.__db_cur.fetchall()
        result: dict[str, str] = {}
        for row in rows:
            result[row[0]] = row[1]
        return result
    
    def get_servers_for_active_profiles(self, active_profile_ids: list[str]) -> dict:
        """Получает список серверов только для активных профилей"""
        if not active_profile_ids:
            return {}
        
        self._ensure_db_connection()
        try:
            # Формируем список ID для SQL запроса
            profile_ids_str = ','.join([f"'{pid}'" for pid in active_profile_ids])
            
            query = f"""
                SELECT DISTINCT s.server_name, s.id_server
                FROM {tablesBM.SERVERS} s
                INNER JOIN {tablesBM.SERVER_FILTERS} sf ON s.id_server = sf.fk_servers_id
                INNER JOIN {tablesBM.FILTERS} f ON sf.id_filter = f.fk_server_filters_id
                INNER JOIN {tablesBM.PROFILES_FILTERS} pf ON f.id = pf.fk_filters_id
                INNER JOIN {tablesBM.PROFILES} p ON pf.fk_id_profile = p.id_profile
                WHERE p.id_profile IN ({profile_ids_str}) AND p.is_active = 1
            """
            self.__db_cur.execute(query)
            rows = self.__db_cur.fetchall()
            result: dict[str, str] = {}
            for row in rows:
                result[row[0]] = row[1]
            return result
        except Exception as e:
            self.log_action(
                object='repository',
                action='get_servers_for_active_profiles',
                is_error=True,
                result=str(e)
            )
            return {}

    def add_server_to_profile(self, profile_id: str, server_id: str, server_name: str = None) -> bool:
        """Добавляет сервер к профилю пользователя"""
        self._ensure_db_connection()
        try:
            # Проверяем существование сервера в БД
            server_exists_query = sqlHelper.select(
                table=tablesBM.SERVERS,
                columns=['id_server'],
                where=sqlHelper.where('id_server', server_id)
            )
            self.__db_cur.execute(server_exists_query)
            if not self.__db_cur.fetchone():
                # Сервер не существует в БД, нужно его добавить
                # Сначала получаем game_id для rust
                game_query = sqlHelper.select(
                    table=tablesBM.GAMES,
                    columns=['id_game'],
                    where=sqlHelper.where('game_name', "'rust'")
                )
                self.__db_cur.execute(game_query)
                game_row = self.__db_cur.fetchone()
                if not game_row:
                    # Игра rust не найдена, создаем
                    game_insert = sqlHelper.insert(
                        table=tablesBM.GAMES,
                        columns=['game_name'],
                        values=['rust']
                    )
                    self._write_queue.append(('execute', game_insert))
                    self._process_write_queue()
                    self.__db_cur.execute("SELECT LAST_INSERT_ID()")
                    game_id = self.__db_cur.fetchone()[0]
                else:
                    game_id = game_row[0]
                
                # Добавляем сервер (используем INSERT IGNORE для избежания ошибок при дублировании)
                # Экранируем название сервера
                escaped_server_name = (server_name or f"Server {server_id}").replace("'", "''")
                server_insert = sqlHelper.insert(
                    table=tablesBM.SERVERS,
                    columns=['id_server', 'fk_games_id', 'server_name'],
                    values=[server_id, str(game_id), escaped_server_name]
                )
                # Используем INSERT IGNORE для избежания ошибок при дублировании
                server_insert = server_insert.replace('INSERT INTO', 'INSERT IGNORE INTO')
                self._write_queue.append(('execute', server_insert))
                self._write_queue.append(('commit', None))
                self._process_write_queue()
            
            # Добавляем связь через profiles_servers_conn (используем метод для прямых связей)
            result = self.add_profile_server_connection(profile_id, server_id)
            if not result:
                self.log_action(
                    object='repository',
                    action='add_server_to_profile',
                    is_error=True,
                    result='add_profile_server_connection вернул False',
                    comment=f'Не удалось добавить связь профиля {profile_id} с сервером {server_id}',
                    id_profile=profile_id
                )
            return result
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            self.log_action(
                object='repository',
                action='add_server_to_profile',
                is_error=True,
                result=str(e),
                comment=f'Ошибка при добавлении сервера {server_id} к профилю {profile_id}: {error_trace[:500]}',
                id_profile=profile_id
            )
            self._logger.error(f"Ошибка при добавлении сервера {server_id} к профилю {profile_id}: {e}")
            return False
    
    def check_server_exists(self, server_id: str) -> bool:
        """Проверяет существование сервера в БД"""
        self._ensure_db_connection()
        try:
            query = sqlHelper.select(
                table=tablesBM.SERVERS,
                columns=['id_server'],
                where=sqlHelper.where('id_server', server_id)
            )
            self.__db_cur.execute(query)
            return self.__db_cur.fetchone() is not None
        except Exception as e:
            self.log_action(
                object='repository',
                action='check_server_exists',
                is_error=True,
                result=str(e)
            )
            return False
    
    def search_servers_by_name(self, name_pattern: str, game_id: str = 'rust', limit: int = 10) -> list:
        """Ищет серверы по названию с ограничением по игре"""
        self._ensure_db_connection()
        try:
            # Экранируем одинарные кавычки для безопасности
            escaped_pattern = name_pattern.replace("'", "''")
            
            # Получаем game_id
            game_query = sqlHelper.select(
                table=tablesBM.GAMES,
                columns=['id_game'],
                where=sqlHelper.where('game_name', f"'{game_id}'")
            )
            self.__db_cur.execute(game_query)
            game_row = self.__db_cur.fetchone()
            if not game_row:
                return []
            
            game_id_int = game_row[0]
            
            # Ищем серверы (используем параметризованный запрос через экранирование)
            query = sqlHelper.select(
                table=tablesBM.SERVERS,
                columns=['id_server', 'server_name'],
                where=f"WHERE fk_games_id = {game_id_int} AND server_name LIKE '%{escaped_pattern}%'",
                limit=limit
            )
            self.__db_cur.execute(query)
            rows = self.__db_cur.fetchall()
            return [(row[0], row[1]) for row in rows]  # [(server_id, server_name), ...]
        except Exception as e:
            self.log_action(
                object='repository',
                action='search_servers_by_name',
                is_error=True,
                result=str(e)
            )
            return []

    def _process_write_queue(self) -> None:
        """Обрабатывает очередь записи в БД"""
        try:
            self._ensure_db_connection()
            processed = 0
            while self._write_queue:
                operation, query = self._write_queue.popleft()
                if operation == 'execute' and query:
                    try:
                        self.__db_cur.execute(query)
                        processed += 1
                    except Exception as e:
                        self._logger.error(f"Ошибка при выполнении запроса из очереди: {e}")
                        self._logger.error(f"Запрос: {query[:200] if query else 'None'}")
                        self.log_action(
                            object='repository',
                            action='execute_queue',
                            is_error=True,
                            result=str(e),
                            command=query[:500] if query else 'None'
                        )
                elif operation == 'commit':
                    try:
                        self.__db_con.commit()
                        if processed > 0:
                            self._logger.debug(f"Зафиксировано {processed} операций в БД")
                    except Exception as e:
                        self._logger.error(f"Ошибка при commit: {e}")
                        self.log_action(
                            object='repository',
                            action='commit_queue',
                            is_error=True,
                            result=str(e)
                        )
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            self._logger.error(f"Ошибка при обработке очереди записи: {e}")
            self._logger.error(f"Traceback: {error_trace}")
            self.log_action(
                object='repository',
                action='_process_write_queue',
                is_error=True,
                result=str(e),
                comment=f'Ошибка при обработке очереди: {error_trace[:500]}'
            )
    
    def _flush_queue_on_exit(self) -> None:
        """Обрабатывает оставшиеся команды при выходе"""
        self._process_write_queue()
    
    def execute_queue(self, delay: int = 1) -> None:
        """Периодически обрабатывает очередь (для использования в отдельном потоке)"""
        import time
        while True:
            self._process_write_queue()
            time.sleep(delay)
    
    def get_recent_error_logs(self, limit: int = 10) -> list:
        """Получает последние логи с ошибками"""
        self._ensure_db_connection()
        try:
            query = sqlHelper.select(
                table=tablesBM.LOGS,
                columns=['*'],
                where=sqlHelper.where('error_status', '1'),
                order_by='log_date DESC',
                limit=limit
            )
            self.__db_cur.execute(query)
            return self.__db_cur.fetchall()
        except Exception as e:
            self.log_action(
                object='repository',
                action='get_recent_error_logs',
                is_error=True,
                result=str(e)
            )
            return []
    
    def load_profile(self, profile_id: str) -> Optional[Profile]:
        """Загружает профиль из БД с учетом TTL"""
        # Проверяем TTL
        if profile_id in self._profile_cache_ttl:
            import time
            if time.time() < self._profile_cache_ttl[profile_id]:
                return self._profiles.get(profile_id)
        
        # Загружаем из БД
        self._ensure_db_connection()
        try:
            query = sqlHelper.select(
                table=tablesBM.PROFILES,
                columns=['id_profile', 'profile_nickname', 'profile_name', 'profile_surname', 'is_active'],
                where=sqlHelper.where('id_profile', profile_id)
            )
            self.__db_cur.execute(query)
            row = self.__db_cur.fetchone()
            if row:
                profile = Profile(
                    id=str(row[0]),
                    nickname=row[1] or '',
                    name=row[2] or '',
                    surname=row[3] or '',
                    is_active=bool(row[4]) if row[4] is not None else False
                )
                # Загружаем фильтры из БД
                self._load_profile_filters(profile_id, profile)
                # Загружаем серверы профиля
                self._load_profile_servers(profile_id, profile)
                # Загружаем игроков профиля
                self._load_profile_players(profile_id, profile)
                self._profiles[profile_id] = profile
                import time
                self._profile_cache_ttl[profile_id] = time.time() + self._default_ttl
                return profile
        except Exception as e:
            self.log_action(
                object='repository',
                action='load_profile',
                is_error=True,
                result=str(e),
                id_profile=profile_id
            )
        return None
    
    def _add_or_update_rust_server_filter(self, server_filter_id: int, rust_filter: RustFilter) -> None:
        """Добавляет или обновляет Rust-специфичные параметры фильтра"""
        try:
            # Проверяем, есть ли уже rust_servers_filter для этого server_filter
            check_query = sqlHelper.select(
                table=tablesBM.RUST_SERVERS_FILTERS,
                columns=['id_filter'],
                where=sqlHelper.where('fk_server_filters_id', str(server_filter_id))
            )
            self.__db_cur.execute(check_query)
            existing = self.__db_cur.fetchone()
            
            if existing:
                # Обновляем существующий
                where_clause = sqlHelper.where('fk_server_filters_id', str(server_filter_id)).replace('WHERE ', '')
                update_query = sqlHelper.update(
                    table=tablesBM.RUST_SERVERS_FILTERS,
                    set_clause=f"queued_players_count={rust_filter.queued_players_check}, last_wipe_check={'1' if rust_filter.last_wipe_check else '0'}, next_wipe_check={'1' if rust_filter.next_wipe_check else '0'}, pve_check={'1' if rust_filter.pve_check else '0'}, url_check={'1' if rust_filter.url_check else '0'}, map_url_check={'1' if rust_filter.map_url_check else '0'}, map_image_check={'1' if rust_filter.map_thumbnailUrl_check else '0'}",
                    where=where_clause
                )
                self._write_queue.append(('execute', update_query))
            else:
                # Создаем новый
                insert_query = sqlHelper.insert(
                    table=tablesBM.RUST_SERVERS_FILTERS,
                    columns=['fk_server_filters_id', 'queued_players_count', 'last_wipe_check', 
                            'next_wipe_check', 'pve_check', 'url_check', 'map_url_check', 'map_image_check'],
                    values=[str(server_filter_id), str(rust_filter.queued_players_check),
                           '1' if rust_filter.last_wipe_check else '0',
                           '1' if rust_filter.next_wipe_check else '0',
                           '1' if rust_filter.pve_check else '0',
                           '1' if rust_filter.url_check else '0',
                           '1' if rust_filter.map_url_check else '0',
                           '1' if rust_filter.map_thumbnailUrl_check else '0']
                )
                self._write_queue.append(('execute', insert_query))
        except Exception as e:
            self.log_action(
                object='repository',
                action='_add_or_update_rust_server_filter',
                is_error=True,
                result=str(e)
            )
    
    def _load_profile_filters(self, profile_id: str, profile: Profile) -> None:
        """Загружает фильтры профиля из БД (связь через server_filters и player_filters)"""
        try:
            # Получаем server_filter по fk_id_profile
            server_filter_query = sqlHelper.select(
                table=tablesBM.SERVER_FILTERS,
                columns=['id_filter'],
                where=sqlHelper.where('fk_id_profile', profile_id)
            )
            self.__db_cur.execute(server_filter_query)
            server_filter_row = self.__db_cur.fetchone()
            
            if server_filter_row:
                server_filter_id = server_filter_row[0]
                self._load_server_filter(server_filter_id, profile)
            
            # Получаем player_filter по fk_id_profile
            player_filter_query = sqlHelper.select(
                table=tablesBM.PLAYER_FILTERS,
                columns=['id_player_filter'],
                where=sqlHelper.where('fk_id_profile', profile_id)
            )
            self.__db_cur.execute(player_filter_query)
            player_filter_row = self.__db_cur.fetchone()
            
            if player_filter_row:
                player_filter_id = player_filter_row[0]
                self._load_player_filter(player_filter_id, profile)
        except Exception as e:
            self.log_action(
                object='repository',
                action='_load_profile_filters',
                is_error=True,
                result=str(e),
                id_profile=profile_id
            )
    
    def _load_server_filter(self, server_filter_id: int, profile: Profile) -> None:
        """Загружает server_filter и rust_servers_filter из БД"""
        try:
            # Получаем server_filter
            server_filter_query = sqlHelper.select(
                table=tablesBM.SERVER_FILTERS,
                columns=['fk_servers_id', 'player_count', 'max_player_count', 'status_check', 'ip_port_check', 'private_check'],
                where=sqlHelper.where('id_filter', str(server_filter_id))
            )
            self.__db_cur.execute(server_filter_query)
            server_filter_row = self.__db_cur.fetchone()
            
            if server_filter_row:
                # Получаем rust_servers_filter
                rust_filter_query = sqlHelper.select(
                    table=tablesBM.RUST_SERVERS_FILTERS,
                    columns=['queued_players_count', 'last_wipe_check', 'next_wipe_check', 
                            'pve_check', 'url_check', 'map_url_check', 'map_image_check'],
                    where=sqlHelper.where('fk_server_filters_id', str(server_filter_id))
                )
                self.__db_cur.execute(rust_filter_query)
                rust_filter_row = self.__db_cur.fetchone()
                
                # Создаем объект RustFilter
                from filters import RustFilter, EGames
                rust_filter = RustFilter()
                rust_filter._game_id = EGames.rust
                rust_filter.players_check = int(server_filter_row[1]) if server_filter_row[1] and server_filter_row[1] != -1 else -1
                rust_filter.max_player_check = int(server_filter_row[2]) if server_filter_row[2] and server_filter_row[2] != -1 else -1
                rust_filter.status_check = bool(server_filter_row[3]) if server_filter_row[3] is not None else False
                rust_filter.ip_port_check = bool(server_filter_row[4]) if server_filter_row[4] is not None else False
                rust_filter.private_check = bool(server_filter_row[5]) if server_filter_row[5] is not None else False
                
                # Если есть rust_servers_filter, загружаем его параметры
                if rust_filter_row:
                    rust_filter.queued_players_check = int(rust_filter_row[0]) if rust_filter_row[0] and rust_filter_row[0] != -1 else -1
                    rust_filter.last_wipe_check = bool(rust_filter_row[1]) if rust_filter_row[1] is not None else False
                    rust_filter.next_wipe_check = bool(rust_filter_row[2]) if rust_filter_row[2] is not None else False
                    rust_filter.pve_check = bool(rust_filter_row[3]) if rust_filter_row[3] is not None else False
                    rust_filter.url_check = bool(rust_filter_row[4]) if rust_filter_row[4] is not None else False
                    rust_filter.map_url_check = bool(rust_filter_row[5]) if rust_filter_row[5] is not None else False
                    rust_filter.map_thumbnailUrl_check = bool(rust_filter_row[6]) if rust_filter_row[6] is not None else False
                
                profile.add_filter(rust_filter)
        except Exception as e:
            self.log_action(
                object='repository',
                action='_load_server_filter',
                is_error=True,
                result=str(e)
            )
    
    def _load_player_filter(self, player_filter_id: int, profile: Profile) -> None:
        """Загружает player_filter из БД"""
        try:
            # Получаем player_filter
            player_filter_query = sqlHelper.select(
                table=tablesBM.PLAYER_FILTERS,
                columns=['fk_id_players', 'player_name_changed', 'player_private_changed', 'proofile_link_changed'],
                where=sqlHelper.where('id_player_filter', str(player_filter_id))
            )
            self.__db_cur.execute(player_filter_query)
            player_filter_row = self.__db_cur.fetchone()
            
            if player_filter_row:
                # Создаем объект PlayerFilter
                from filters import PlayerFilter
                player_filter = PlayerFilter()
                player_filter.player_name_check = bool(player_filter_row[1]) if player_filter_row[1] is not None else False
                player_filter.player_private_check = bool(player_filter_row[2]) if player_filter_row[2] is not None else False
                
                profile.add_filter(player_filter)
        except Exception as e:
            self.log_action(
                object='repository',
                action='_load_player_filter',
                is_error=True,
                result=str(e)
            )
    
    def _load_profile_servers(self, profile_id: str, profile: Profile) -> None:
        """Загружает серверы профиля из БД через profiles_servers_conn"""
        try:
            # Очищаем существующие серверы, чтобы избежать дубликатов при повторной загрузке
            profile._servers.clear()
            
            # Используем новую структуру БД через profiles_servers_conn
            # JOIN только с таблицей servers, условие по профилю в WHERE
            join_clause = sqlHelper.join(
                tablesBM.SERVERS,
                f"{tablesBM.SERVERS}.id_server = {tablesBM.PROFILES_SERVERS_CONN}.fk_id_server",
                "INNER"
            )
            
            where_clause = sqlHelper.where('fk_id_profile', profile_id)
            
            query = sqlHelper.select(
                table=tablesBM.PROFILES_SERVERS_CONN,
                columns=[f'{tablesBM.SERVERS}.id_server', f'{tablesBM.SERVERS}.server_name'],
                join=join_clause,
                where=where_clause
            )
            self.__db_cur.execute(query)
            server_rows = self.__db_cur.fetchall()
            
            for row in server_rows:
                server_id = row[0]
                server_name = row[1]
                # Создаем объект RustServer
                from data_classes import RustServer
                server = RustServer(
                    id=server_id,
                    data={
                        'name': server_name,
                        'details': {}  # Пустые details, так как полной информации нет
                    },
                    game_id='rust'
                )
                profile.add_server(server)
        except Exception as e:
            self.log_action(
                object='repository',
                action='_load_profile_servers',
                is_error=True,
                result=str(e),
                id_profile=profile_id
            )
    
    def _load_profile_players(self, profile_id: str, profile: Profile) -> None:
        """Загружает игроков профиля из БД через profiles_players_conn"""
        try:
            # Используем новую структуру БД через profiles_players_conn
            # JOIN только с таблицей players, условие по профилю в WHERE
            join_clause = sqlHelper.join(
                tablesBM.PLAYERS,
                f"{tablesBM.PLAYERS}.id_players = {tablesBM.PROFILES_PLAYERS_CONN}.fk_id_players",
                "INNER"
            )
            
            where_clause = sqlHelper.where('fk_id_profile', profile_id)
            
            query = sqlHelper.select(
                table=tablesBM.PROFILES_PLAYERS_CONN,
                columns=[f'{tablesBM.PLAYERS}.id_players', f'{tablesBM.PLAYERS}.nickname'],
                join=join_clause,
                where=where_clause
            )
            self.__db_cur.execute(query)
            player_rows = self.__db_cur.fetchall()
            
            for row in player_rows:
                player_id = row[0]
                player_name = row[1]
                # Создаем объект Player
                from data_classes import Player
                player_data = {
                    'name': player_name,
                    'private': False,
                    'positiveMatch': False,
                    'createdAt': '',
                    'updatedAt': ''
                }
                player = Player(
                    id=player_id,
                    data=player_data
                )
                profile.add_player(player)
        except Exception as e:
            self.log_action(
                object='repository',
                action='_load_profile_players',
                is_error=True,
                result=str(e),
                id_profile=profile_id
            )

    def add_profile_server_connection(self, profile_id: str, server_id: str) -> bool:
        """Добавляет прямую связь профиля с сервером через profiles_servers_conn"""
        self._ensure_db_connection()
        try:
            # Проверяем, есть ли уже такая связь
            # Исправляем синтаксис: используем один WHERE и добавляем второе условие через AND
            where_clause = sqlHelper.where('fk_id_profile', profile_id)
            # Убираем "WHERE " из начала и добавляем второе условие
            where_clause += f" AND fk_id_server = '{server_id}'"
            check_query = sqlHelper.select(
                table=tablesBM.PROFILES_SERVERS_CONN,
                columns=['id_conn'],
                where=where_clause
            )
            self.__db_cur.execute(check_query)
            if self.__db_cur.fetchone():
                # Связь уже существует
                return True
            
            # Создаем связь
            insert_query = sqlHelper.insert(
                table=tablesBM.PROFILES_SERVERS_CONN,
                columns=['fk_id_profile', 'fk_id_server'],
                values=[profile_id, server_id]
            )
            self._write_queue.append(('execute', insert_query))
            self._write_queue.append(('commit', None))
            self._process_write_queue()
            
            # Добавляем сервер в профиль в памяти
            profile = self._profiles.get(profile_id)
            if profile:
                from data_classes import RustServer
                # Получаем имя сервера из БД
                server_name_query = sqlHelper.select(
                    table=tablesBM.SERVERS,
                    columns=['server_name'],
                    where=sqlHelper.where('id_server', server_id)
                )
                self.__db_cur.execute(server_name_query)
                server_row = self.__db_cur.fetchone()
                server_name = server_row[0] if server_row else f"Server {server_id}"
                
                server = RustServer(
                    id=server_id,
                    data={
                        'name': server_name,
                        'details': {}
                    },
                    game_id='rust'
                )
                profile.add_server(server)
                # Сбрасываем TTL кэша профиля, чтобы при следующем запросе он перезагрузился из БД
                if profile_id in self._profile_cache_ttl:
                    del self._profile_cache_ttl[profile_id]
            else:
                # Если профиля нет в памяти, сбрасываем кэш, чтобы он загрузился при следующем запросе
                if profile_id in self._profile_cache_ttl:
                    del self._profile_cache_ttl[profile_id]
            
            return True
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            self.log_action(
                object='repository',
                action='add_profile_server_connection',
                is_error=True,
                result=str(e),
                comment=f'Ошибка при добавлении связи профиля {profile_id} с сервером {server_id}: {error_trace[:500]}',
                id_profile=profile_id
            )
            self._logger.error(f"Ошибка при добавлении связи профиля {profile_id} с сервером {server_id}: {e}")
            return False
    
    def remove_profile_server_connection(self, profile_id: str, server_id: str) -> bool:
        """Удаляет прямую связь профиля с сервером"""
        self._ensure_db_connection()
        try:
            delete_query = f"""
                DELETE FROM {tablesBM.PROFILES_SERVERS_CONN}
                WHERE {sqlHelper.where('fk_id_profile', profile_id).replace('WHERE ', '')} 
                AND {sqlHelper.where('fk_id_server', server_id).replace('WHERE ', '')}
            """
            self.__db_cur.execute(delete_query)
            self.__db_con.commit()
            
            # Удаляем сервер из профиля в памяти
            profile = self._profiles.get(profile_id)
            if profile and server_id in profile._servers:
                del profile._servers[server_id]
            
            return True
        except Exception as e:
            self.log_action(
                object='repository',
                action='remove_profile_server_connection',
                is_error=True,
                result=str(e),
                id_profile=profile_id
            )
            return False
    
    def add_profile_player_connection(self, profile_id: str, player_id: str) -> bool:
        """Добавляет прямую связь профиля с игроком через profiles_players_conn"""
        self._ensure_db_connection()
        try:
            # Проверяем, есть ли уже такая связь
            # Исправляем синтаксис: используем один WHERE и добавляем второе условие через AND
            where_clause = sqlHelper.where('fk_id_profile', profile_id)
            # Убираем "WHERE " из начала и добавляем второе условие
            where_clause += f" AND fk_id_players = '{player_id}'"
            check_query = sqlHelper.select(
                table=tablesBM.PROFILES_PLAYERS_CONN,
                columns=['id_conn'],
                where=where_clause
            )
            self.__db_cur.execute(check_query)
            if self.__db_cur.fetchone():
                # Связь уже существует
                return True
            
            # Создаем связь
            insert_query = sqlHelper.insert(
                table=tablesBM.PROFILES_PLAYERS_CONN,
                columns=['fk_id_profile', 'fk_id_players'],
                values=[profile_id, player_id]
            )
            self._write_queue.append(('execute', insert_query))
            self._write_queue.append(('commit', None))
            self._process_write_queue()
            
            # Добавляем игрока в профиль в памяти
            profile = self._profiles.get(profile_id)
            if profile:
                from data_classes import Player
                # Получаем имя игрока из БД
                player_name_query = sqlHelper.select(
                    table=tablesBM.PLAYERS,
                    columns=['nickname'],
                    where=sqlHelper.where('id_players', player_id)
                )
                self.__db_cur.execute(player_name_query)
                player_row = self.__db_cur.fetchone()
                player_name = player_row[0] if player_row else f"Player {player_id}"
                
                player = Player(
                    player_id,
                    {
                        'name': player_name,
                        'private': False,
                        'positiveMatch': False,
                        'createdAt': '',
                        'updatedAt': ''
                    }
                )
                profile.add_player(player)
            
            return True
        except Exception as e:
            self.log_action(
                object='repository',
                action='add_profile_player_connection',
                is_error=True,
                result=str(e),
                id_profile=profile_id
            )
            return False
    
    def remove_profile_player_connection(self, profile_id: str, player_id: str) -> bool:
        """Удаляет прямую связь профиля с игроком"""
        self._ensure_db_connection()
        try:
            delete_query = f"""
                DELETE FROM {tablesBM.PROFILES_PLAYERS_CONN}
                WHERE {sqlHelper.where('fk_id_profile', profile_id).replace('WHERE ', '')} 
                AND {sqlHelper.where('fk_id_players', player_id).replace('WHERE ', '')}
            """
            self.__db_cur.execute(delete_query)
            self.__db_con.commit()
            
            # Удаляем игрока из профиля в памяти
            profile = self._profiles.get(profile_id)
            if profile and player_id in profile._players:
                del profile._players[player_id]
            
            return True
        except Exception as e:
            self.log_action(
                object='repository',
                action='remove_profile_player_connection',
                is_error=True,
                result=str(e),
                id_profile=profile_id
            )
            return False
    
    def get_profile_servers(self, profile_id: str) -> list[dict]:
        """Получает список серверов профиля через profiles_servers_conn"""
        self._ensure_db_connection()
        try:
            join_clause = sqlHelper.join(
                tablesBM.PROFILES_SERVERS_CONN,
                f"profiles_servers_conn.fk_id_profile = '{profile_id}'",
                "INNER"
            )
            join_clause += " " + sqlHelper.join(
                tablesBM.SERVERS,
                "servers.id_server = profiles_servers_conn.fk_id_server",
                "INNER"
            )
            
            query = sqlHelper.select(
                table=tablesBM.PROFILES_SERVERS_CONN,
                columns=['servers.id_server', 'servers.server_name'],
                join=join_clause
            )
            self.__db_cur.execute(query)
            rows = self.__db_cur.fetchall()
            return [{'id': row[0], 'name': row[1]} for row in rows]
        except Exception as e:
            self.log_action(
                object='repository',
                action='get_profile_servers',
                is_error=True,
                result=str(e),
                id_profile=profile_id
            )
            return []
    
    def get_profile_players(self, profile_id: str) -> list[dict]:
        """Получает список игроков профиля через profiles_players_conn"""
        self._ensure_db_connection()
        try:
            join_clause = sqlHelper.join(
                tablesBM.PROFILES_PLAYERS_CONN,
                f"profiles_players_conn.fk_id_profile = '{profile_id}'",
                "INNER"
            )
            join_clause += " " + sqlHelper.join(
                tablesBM.PLAYERS,
                "players.id_players = profiles_players_conn.fk_id_players",
                "INNER"
            )
            
            query = sqlHelper.select(
                table=tablesBM.PROFILES_PLAYERS_CONN,
                columns=['players.id_players', 'players.nickname'],
                join=join_clause
            )
            self.__db_cur.execute(query)
            rows = self.__db_cur.fetchall()
            return [{'id': row[0], 'name': row[1]} for row in rows]
        except Exception as e:
            self.log_action(
                object='repository',
                action='get_profile_players',
                is_error=True,
                result=str(e),
                id_profile=profile_id
            )
            return []
    
    def get_rust_server_filter(self, server_filter_id: int) -> Optional[dict]:
        """Получает Rust-специфичные параметры фильтра для server_filter"""
        self._ensure_db_connection()
        try:
            query = sqlHelper.select(
                table=tablesBM.RUST_SERVERS_FILTERS,
                columns=['queued_players_count', 'last_wipe_check', 'next_wipe_check', 
                        'pve_check', 'url_check', 'map_url_check', 'map_image_check'],
                where=sqlHelper.where('fk_server_filters_id', str(server_filter_id))
            )
            self.__db_cur.execute(query)
            row = self.__db_cur.fetchone()
            if row:
                return {
                    'queued_players_count': row[0],
                    'last_wipe_check': bool(row[1]),
                    'next_wipe_check': bool(row[2]),
                    'pve_check': bool(row[3]),
                    'url_check': bool(row[4]),
                    'map_url_check': bool(row[5]),
                    'map_image_check': bool(row[6])
                }
            return None
        except Exception as e:
            self.log_action(
                object='repository',
                action='get_rust_server_filter',
                is_error=True,
                result=str(e)
            )
            return None
    
    def update_rust_server_filter(self, server_filter_id: int, rust_filter_data: dict) -> bool:
        """Обновляет Rust-специфичные параметры фильтра"""
        self._ensure_db_connection()
        try:
            # Проверяем существование
            check_query = sqlHelper.select(
                table=tablesBM.RUST_SERVERS_FILTERS,
                columns=['id_filter'],
                where=sqlHelper.where('fk_server_filters_id', str(server_filter_id))
            )
            self.__db_cur.execute(check_query)
            if not self.__db_cur.fetchone():
                # Создаем новый
                insert_query = sqlHelper.insert(
                    table=tablesBM.RUST_SERVERS_FILTERS,
                    columns=['fk_server_filters_id', 'queued_players_count', 'last_wipe_check', 
                            'next_wipe_check', 'pve_check', 'url_check', 'map_url_check', 'map_image_check'],
                    values=[
                        str(server_filter_id),
                        str(rust_filter_data.get('queued_players_count', -1)),
                        '1' if rust_filter_data.get('last_wipe_check', False) else '0',
                        '1' if rust_filter_data.get('next_wipe_check', False) else '0',
                        '1' if rust_filter_data.get('pve_check', False) else '0',
                        '1' if rust_filter_data.get('url_check', False) else '0',
                        '1' if rust_filter_data.get('map_url_check', False) else '0',
                        '1' if rust_filter_data.get('map_image_check', False) else '0'
                    ]
                )
                self._write_queue.append(('execute', insert_query))
            else:
                # Обновляем существующий
                where_clause = sqlHelper.where('fk_server_filters_id', str(server_filter_id)).replace('WHERE ', '')
                update_query = sqlHelper.update(
                    table=tablesBM.RUST_SERVERS_FILTERS,
                    set_clause=f"queued_players_count={rust_filter_data.get('queued_players_count', -1)}, last_wipe_check={'1' if rust_filter_data.get('last_wipe_check', False) else '0'}, next_wipe_check={'1' if rust_filter_data.get('next_wipe_check', False) else '0'}, pve_check={'1' if rust_filter_data.get('pve_check', False) else '0'}, url_check={'1' if rust_filter_data.get('url_check', False) else '0'}, map_url_check={'1' if rust_filter_data.get('map_url_check', False) else '0'}, map_image_check={'1' if rust_filter_data.get('map_image_check', False) else '0'}",
                    where=where_clause
                )
                self._write_queue.append(('execute', update_query))
            
            self._write_queue.append(('commit', None))
            self._process_write_queue()
            return True
        except Exception as e:
            self.log_action(
                object='repository',
                action='update_rust_server_filter',
                is_error=True,
                result=str(e)
            )
            return False
    
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
        """
        Логирует действие в таблицу logs.
        Используются поля: message_to_bot, message_from_bot, error_status, error_log.
        Если передан result, он записывается в message_from_bot,
        если передан comment, он записывается в message_to_bot.
        Примечание: требуется id_profile, без него запись не выполняется.
        """
        try:
            self._ensure_db_connection()
            if not id_profile:
                # Если профиль не указан, пропускаем запись (logs требует fk_id_profile)
                return
            
            # Формируем сообщение для бота из переданных данных
            message_to_bot = comment or action or object or ''
            message_from_bot = result or ''
            error_status = '1' if is_error else '0'
            error_log = result if is_error else None
            
            self.__db_cur.execute(sqlHelper.insert(
                table=tablesBM.LOGS, 
                columns=['fk_id_profile', 'message_to_bot', 'message_from_bot', 'error_status', 'error_log'],
                values=[id_profile, message_to_bot, message_from_bot, error_status, error_log]))
            self.__db_con.commit()
        except Exception as e:
            # Если не удалось записать в БД, хотя бы не падаем
            pass
    
    def log_system_error(
            self,
            object: Union[str, None] = None,
            action: Union[str, None] = None,
            comment: Union[str, None] = None,
            result: Union[str, None] = None,
            admin_id: Union[str, None] = None
    ) -> None:
        """
        Логирует системную ошибку в таблицу logs, используя ADMIN_ID как профиль.
        
        :param object: Объект, где произошла ошибка
        :param action: Действие, при котором произошла ошибка
        :param comment: Комментарий/описание ошибки
        :param result: Детали ошибки (текст ошибки, traceback и т.д.)
        :param admin_id: ID администратора для логирования (по умолчанию берется из переменной окружения или используется '517965582')
        """
        try:
            self._ensure_db_connection()
            # Используем ADMIN_ID для системных ошибок
            if not admin_id:
                admin_id = getenv('ADMIN_ID', '517965582')
            
            # Формируем сообщение для бота из переданных данных
            message_to_bot = comment or action or object or 'Системная ошибка'
            message_from_bot = result or ''
            error_status = '1'  # Всегда ошибка для системных логов
            error_log = result
            
            self.__db_cur.execute(sqlHelper.insert(
                table=tablesBM.LOGS, 
                columns=['fk_id_profile', 'message_to_bot', 'message_from_bot', 'error_status', 'error_log'],
                values=[admin_id, message_to_bot, message_from_bot, error_status, error_log]))
            self.__db_con.commit()
        except Exception as e:
            # Если не удалось записать в БД, логируем в обычный логгер
            self._logger.error(f"Не удалось записать системную ошибку в БД: {e}")
    
    def save_initialization_state(
            self,
            error_type: str,
            error_url: str,
            error_message: str,
            admin_id: Union[str, None] = None
    ) -> None:
        """
        Сохраняет состояние незавершенной инициализации в БД для последующего возобновления.
        
        :param error_type: Тип ошибки ('servers_loading' или 'players_loading')
        :param error_url: URL страницы, на которой произошла ошибка
        :param error_message: Сообщение об ошибке
        :param admin_id: ID администратора (по умолчанию берется из переменной окружения)
        """
        try:
            self._ensure_db_connection()
            if not admin_id:
                admin_id = getenv('ADMIN_ID', '517965582')
            
            # Удаляем предыдущее состояние того же типа (если есть)
            self.__db_cur.execute(f"""
                DELETE FROM {tablesBM.LOGS} 
                WHERE fk_id_profile = %s 
                AND message_to_bot LIKE %s
                AND error_status = '1'
            """, (admin_id, f'INIT_STATE:{error_type}:%'))
            
            # Сохраняем новое состояние (используем специальный формат: INIT_STATE:error_type:error_url)
            message_to_bot = f'INIT_STATE:{error_type}:{error_url}'
            message_from_bot = error_message
            error_status = '1'
            error_log = error_message
            
            self.__db_cur.execute(sqlHelper.insert(
                table=tablesBM.LOGS,
                columns=['fk_id_profile', 'message_to_bot', 'message_from_bot', 'error_status', 'error_log'],
                values=[admin_id, message_to_bot, message_from_bot, error_status, error_log]))
            self.__db_con.commit()
            self._logger.info(f"Сохранено состояние инициализации: {error_type}", {'url': error_url})
        except Exception as e:
            self._logger.error(f"Не удалось сохранить состояние инициализации: {e}")
    
    def get_initialization_state(self, admin_id: Union[str, None] = None) -> Union[dict, None]:
        """
        Получает состояние незавершенной инициализации из БД.
        
        :param admin_id: ID администратора (по умолчанию берется из переменной окружения)
        :return: Словарь с информацией о состоянии {'error_type': str, 'error_url': str, 'error_message': str} или None
        """
        try:
            self._ensure_db_connection()
            if not admin_id:
                admin_id = getenv('ADMIN_ID', '517965582')
            
            # Ищем последнее состояние инициализации (сортируем по дате, берем последнее)
            query = f"""
                SELECT message_to_bot, message_from_bot, error_log, log_date
                FROM {tablesBM.LOGS}
                WHERE fk_id_profile = '{admin_id}'
                AND message_to_bot LIKE 'INIT_STATE:%'
                AND error_status = '1'
                ORDER BY log_date DESC
                LIMIT 1
            """
            self.__db_cur.execute(query)
            
            row = self.__db_cur.fetchone()
            if row:
                message_to_bot = row[0]
                error_message = row[1] or row[2] or ''
                
                # Парсим формат: INIT_STATE:error_type:error_url
                parts = message_to_bot.split(':', 2)
                if len(parts) == 3 and parts[0] == 'INIT_STATE':
                    return {
                        'error_type': parts[1],
                        'error_url': parts[2],
                        'error_message': error_message
                    }
            
            return None
        except Exception as e:
            self._logger.error(f"Не удалось получить состояние инициализации: {e}")
            return None
    
    def clear_initialization_state(self, error_type: Union[str, None] = None, admin_id: Union[str, None] = None) -> None:
        """
        Очищает состояние незавершенной инициализации после успешного завершения.
        
        :param error_type: Тип ошибки для очистки (если None, очищает все)
        :param admin_id: ID администратора (по умолчанию берется из переменной окружения)
        """
        try:
            self._ensure_db_connection()
            if not admin_id:
                admin_id = getenv('ADMIN_ID', '517965582')
            
            if error_type:
                # Удаляем состояние конкретного типа
                self.__db_cur.execute(f"""
                    DELETE FROM {tablesBM.LOGS}
                    WHERE fk_id_profile = %s
                    AND message_to_bot LIKE %s
                    AND error_status = '1'
                """, (admin_id, f'INIT_STATE:{error_type}:%'))
            else:
                # Удаляем все состояния инициализации
                self.__db_cur.execute(f"""
                    DELETE FROM {tablesBM.LOGS}
                    WHERE fk_id_profile = %s
                    AND message_to_bot LIKE 'INIT_STATE:%'
                    AND error_status = '1'
                """, (admin_id,))
            
            self.__db_con.commit()
            self._logger.info(f"Очищено состояние инициализации", {'error_type': error_type or 'all'})
        except Exception as e:
            self._logger.error(f"Не удалось очистить состояние инициализации: {e}")

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
    
    def _log_database_metadata(self) -> None:
        """Выводит метаданные базы данных: таблицы, колонки, количество записей"""
        try:
            self._logger.section("МЕТАДАННЫЕ БАЗЫ ДАННЫХ")
            
            # Получаем список всех таблиц
            self.__db_cur.execute("SHOW TABLES")
            tables = [row[0] for row in self.__db_cur.fetchall()]
            
            self._logger.info(f"Найдено таблиц: {len(tables)}", {'tables': ', '.join(tables)})
            
            # Для каждой таблицы получаем колонки и количество записей
            for table in tables:
                # Получаем колонки
                self.__db_cur.execute(f"DESCRIBE {table}")
                columns = self.__db_cur.fetchall()
                column_names = [col[0] for col in columns]
                
                # Получаем количество записей
                self.__db_cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = self.__db_cur.fetchone()[0]
                
                self._logger.info(f"Таблица: {table}", {
                    'columns': ', '.join(column_names),
                    'column_count': len(column_names),
                    'row_count': count
                })
            
            self._logger.info("Метаданные БД выведены")
        except Exception as e:
            self._logger.error(f"Ошибка при получении метаданных БД: {e}")
    
    def get_service_stats(self) -> dict:
        """Возвращает статистику сервиса"""
        try:
            self._ensure_db_connection()
            stats = {}
            
            # Количество активных пользователей (профилей)
            self.__db_cur.execute("SELECT COUNT(*) FROM profiles WHERE is_active = 1")
            stats['active_users'] = self.__db_cur.fetchone()[0]
            
            # Размер очереди БД
            stats['db_queue_size'] = len(self._write_queue)
            
            # Количество серверов
            self.__db_cur.execute("SELECT COUNT(*) FROM servers")
            stats['total_servers'] = self.__db_cur.fetchone()[0]
            
            # Количество игроков
            self.__db_cur.execute("SELECT COUNT(*) FROM players")
            stats['total_players'] = self.__db_cur.fetchone()[0]
            
            # Количество активных профилей с серверами
            self.__db_cur.execute(f"""
                SELECT COUNT(DISTINCT psc.fk_id_profile) 
                FROM {tablesBM.PROFILES_SERVERS_CONN} psc
                JOIN {tablesBM.PROFILES} p ON psc.fk_id_profile = p.id_profile
                WHERE p.is_active = 1
            """)
            stats['users_with_servers'] = self.__db_cur.fetchone()[0]
            
            # Количество активных профилей с игроками
            self.__db_cur.execute(f"""
                SELECT COUNT(DISTINCT ppc.fk_id_profile) 
                FROM {tablesBM.PROFILES_PLAYERS_CONN} ppc
                JOIN {tablesBM.PROFILES} p ON ppc.fk_id_profile = p.id_profile
                WHERE p.is_active = 1
            """)
            stats['users_with_players'] = self.__db_cur.fetchone()[0]
            
            # Количество серверов Rust
            self.__db_cur.execute("""
                SELECT COUNT(*) FROM servers s
                JOIN games g ON s.fk_games_id = g.id_game
                WHERE g.game_name = 'rust'
            """)
            stats['rust_servers'] = self.__db_cur.fetchone()[0]
            
            # Количество последних ошибок (за последний час)
            self.__db_cur.execute("""
                SELECT COUNT(*) FROM logs 
                WHERE error_status = 1 AND log_date >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
            """)
            stats['recent_errors'] = self.__db_cur.fetchone()[0]
            
            return stats
        except Exception as e:
            self._logger.error(f"Ошибка при получении статистики сервиса: {e}")
            return {}
    
    def validate_records_count(self, table_name: str, expected_count: int, stage_name: str) -> bool:
        """Проверяет количество записей в таблице после заполнения"""
        try:
            self._ensure_db_connection()
            self.__db_cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            actual_count = self.__db_cur.fetchone()[0]
            
            if actual_count != expected_count:
                error_msg = f"Расхождение в количестве записей на этапе '{stage_name}': ожидалось {expected_count}, получено {actual_count} (таблица: {table_name})"
                self._logger.error(error_msg)
                self.log_action(
                    object='repository',
                    action='validate_records_count',
                    is_error=True,
                    comment=error_msg,
                    stage=stage_name
                )
                return False
            return True
        except Exception as e:
            error_msg = f"Ошибка при проверке количества записей на этапе '{stage_name}': {e}"
            self._logger.error(error_msg)
            self.log_action(
                object='repository',
                action='validate_records_count',
                is_error=True,
                result=str(e),
                stage=stage_name
            )
            return False
    
    def bulk_insert_servers(self, servers: list[dict], game_name: str = 'rust') -> int:
        """
        Массовое добавление серверов в БД (оптимизированная версия с batch INSERT)
        
        :param servers: список словарей [{'id': str, 'name': str}, ...]
        :param game_name: название игры (по умолчанию 'rust')
        :return: количество добавленных серверов
        """
        if not servers:
            return 0
        
        self._ensure_db_connection()
        try:
            # Получаем или создаем game_id
            game_query = sqlHelper.select(
                table=tablesBM.GAMES,
                columns=['id_game'],
                where=sqlHelper.where('game_name', f"'{game_name}'")
            )
            self.__db_cur.execute(game_query)
            game_row = self.__db_cur.fetchone()
            
            if not game_row:
                # Создаем игру если не существует
                game_insert = sqlHelper.insert(
                    table=tablesBM.GAMES,
                    columns=['game_name'],
                    values=[game_name]
                )
                self.__db_cur.execute(game_insert)
                self.__db_con.commit()
                self.__db_cur.execute("SELECT LAST_INSERT_ID()")
                game_id = self.__db_cur.fetchone()[0]
            else:
                game_id = game_row[0]
            
            # Подготавливаем данные для batch INSERT
            # Используем INSERT ... ON DUPLICATE KEY UPDATE для автоматической обработки дубликатов
            batch_size = 500  # Размер батча для оптимизации
            added_count = 0
            
            for i in range(0, len(servers), batch_size):
                batch = servers[i:i + batch_size]
                values_list = []
                
                for server in batch:
                    server_id = str(server.get('id', ''))
                    server_name = server.get('name', f"Server {server_id}")
                    # При первичной загрузке эти поля могут отсутствовать, используем NULL
                    rank = server.get('rank')
                    rank_value = str(rank) if rank is not None else 'NULL'
                    private = server.get('private', False)
                    private_value = 1 if private else 0
                    country = server.get('country', '')
                    
                    if server_id:
                        # Используем правильное экранирование SQL (кавычки добавляются вокруг экранированной строки)
                        escaped_id = sqlHelper._escape_sql_string(server_id)
                        escaped_name = sqlHelper._escape_sql_string(server_name)
                        escaped_country = sqlHelper._escape_sql_string(country)
                        values_list.append(f"('{escaped_id}', {game_id}, '{escaped_name}', {rank_value}, {private_value}, '{escaped_country}')")
                
                if not values_list:
                    continue
                
                # Используем INSERT ... ON DUPLICATE KEY UPDATE для пропуска существующих записей
                # Это намного быстрее, чем проверка каждой записи отдельным SELECT
                # При первичной вставке заполняем только базовые поля, остальные будут обновлены позже
                # rank - зарезервированное слово в MySQL, экранируем обратными кавычками
                values_str = ', '.join(values_list)
                query = f"""
                    INSERT INTO {tablesBM.SERVERS} (id_server, fk_games_id, server_name, `rank`, private, country)
                    VALUES {values_str}
                    ON DUPLICATE KEY UPDATE 
                        server_name = VALUES(server_name),
                        `rank` = COALESCE(VALUES(`rank`), `rank`),
                        private = COALESCE(VALUES(private), private),
                        country = COALESCE(VALUES(country), country)
                """
                
                self.__db_cur.execute(query)
                affected = self.__db_cur.rowcount
                added_count += affected
                # Логируем, если affected = 0, но были данные для вставки
                if affected == 0 and len(batch) > 0:
                    self.log_action(
                        object='repository',
                        action='bulk_insert_servers',
                        comment=f'Warning: rowcount=0 для батча из {len(batch)} серверов',
                        result=f'rowcount=0, batch_size={len(batch)}'
                    )
            
            self.__db_con.commit()
            return added_count
        except Exception as e:
            self.__db_con.rollback()
            import traceback
            error_trace = traceback.format_exc()
            self.log_action(
                object='repository',
                action='bulk_insert_servers',
                is_error=True,
                result=str(e),
                comment=f'Ошибка при bulk_insert_servers: {error_trace[:500]}'
            )
            return 0
    
    def bulk_insert_players(self, players: list[dict]) -> int:
        """
        Массовое добавление игроков в БД (оптимизированная версия с batch INSERT)
        
        :param players: список словарей [{'id': str, 'name': str}, ...]
        :return: количество добавленных игроков
        """
        if not players:
            return 0
        
        self._ensure_db_connection()
        try:
            # Используем batch INSERT с ON DUPLICATE KEY UPDATE для оптимизации
            batch_size = 500  # Размер батча для оптимизации
            added_count = 0
            
            for i in range(0, len(players), batch_size):
                batch = players[i:i + batch_size]
                values_list = []
                
                for player in batch:
                    player_id = str(player.get('id', ''))
                    player_name = player.get('name', f"Player {player_id}")
                    # При первичной загрузке эти поля могут отсутствовать, используем NULL или значения по умолчанию
                    positive_match = player.get('positiveMatch', False)
                    positive_match_value = 1 if positive_match else 0
                    private = player.get('private', False)
                    private_value = 1 if private else 0
                    created_at = player.get('createdAt')
                    created_at_value = 'NULL'
                    if created_at:
                        try:
                            created_at_str = created_at.replace("T", " ").replace("Z", "")
                            created_at_value = f"'{created_at_str}'"
                        except:
                            created_at_value = 'NULL'
                    updated_at = player.get('updatedAt')
                    updated_at_value = 'NULL'
                    if updated_at:
                        try:
                            updated_at_str = updated_at.replace("T", " ").replace("Z", "")
                            updated_at_value = f"'{updated_at_str}'"
                        except:
                            updated_at_value = 'NULL'
                    
                    if player_id:
                        # Используем правильное экранирование SQL (кавычки добавляются вокруг экранированной строки)
                        escaped_id = sqlHelper._escape_sql_string(player_id)
                        escaped_name = sqlHelper._escape_sql_string(player_name)
                        values_list.append(f"('{escaped_id}', '{escaped_name}', {positive_match_value}, {private_value}, {created_at_value}, {updated_at_value})")
                
                if not values_list:
                    continue
                
                # Используем INSERT ... ON DUPLICATE KEY UPDATE для пропуска существующих записей
                # При первичной вставке заполняем только базовые поля, остальные будут обновлены позже
                values_str = ', '.join(values_list)
                query = f"""
                    INSERT INTO {tablesBM.PLAYERS} (id_players, nickname, positive_match, private, created_at, updated_at)
                    VALUES {values_str}
                    ON DUPLICATE KEY UPDATE 
                        nickname = VALUES(nickname),
                        positive_match = COALESCE(VALUES(positive_match), positive_match),
                        private = COALESCE(VALUES(private), private),
                        created_at = COALESCE(VALUES(created_at), created_at),
                        updated_at = COALESCE(VALUES(updated_at), updated_at)
                """
                
                self.__db_cur.execute(query)
                added_count += self.__db_cur.rowcount
            
            self.__db_con.commit()
            return added_count
        except Exception as e:
            self.__db_con.rollback()
            self.log_action(
                object='repository',
                action='bulk_insert_players',
                is_error=True,
                result=str(e)
            )
            return 0
    
    def bulk_insert_player_servers(self, player_servers: list[dict]) -> int:
        """
        Массовое добавление связей игрок-сервер в БД (оптимизированная версия с batch INSERT)
        
        :param player_servers: список словарей [{
            'player_id': str,
            'server_id': str,
            'time_played': int,
            'is_online': bool,
            'first_seen': str (опционально, не сохраняется в БД, т.к. нет поля),
            'last_seen': str (опционально, не сохраняется в БД, т.к. нет поля)
        }, ...]
        :return: количество добавленных/обновленных связей
        """
        if not player_servers:
            return 0
        
        self._ensure_db_connection()
        try:
            # Используем batch INSERT с ON DUPLICATE KEY UPDATE для оптимизации
            # Это автоматически обработает как новые записи, так и обновления существующих
            batch_size = 500  # Размер батча для оптимизации
            total_affected = 0
            
            for i in range(0, len(player_servers), batch_size):
                batch = player_servers[i:i + batch_size]
                values_list = []
                
                for link in batch:
                    player_id = str(link.get('player_id', ''))
                    server_id = str(link.get('server_id', ''))
                    time_played = int(link.get('time_played', 0))
                    is_online = 1 if link.get('is_online', False) else 0
                    
                    if player_id and server_id:
                        # Используем правильное экранирование SQL (кавычки добавляются вокруг экранированной строки)
                        escaped_player_id = sqlHelper._escape_sql_string(player_id)
                        escaped_server_id = sqlHelper._escape_sql_string(server_id)
                        values_list.append(f"('{escaped_player_id}', '{escaped_server_id}', {is_online}, {time_played})")
                
                if not values_list:
                    continue
                
                # Используем INSERT ... ON DUPLICATE KEY UPDATE
                # Это автоматически обновит существующие записи и добавит новые
                # UNIQUE индекс на (fk_id_players, fk_id_server) обеспечит уникальность
                values_str = ', '.join(values_list)
                query = f"""
                    INSERT INTO {tablesBM.PLAYERS_SERVERS} (fk_id_players, fk_id_server, is_online, time_played)
                    VALUES {values_str}
                    ON DUPLICATE KEY UPDATE 
                        is_online = VALUES(is_online),
                        time_played = VALUES(time_played)
                """
                
                self.__db_cur.execute(query)
                total_affected += self.__db_cur.rowcount
            
            self.__db_con.commit()
            return total_affected
        except Exception as e:
            self.__db_con.rollback()
            self.log_action(
                object='repository',
                action='bulk_insert_player_servers',
                is_error=True,
                result=str(e)
            )
            return 0
    
    def search_players_by_name(self, name_pattern: str, limit: int = 10) -> list:
        """Ищет игроков по имени/никнейму"""
        self._ensure_db_connection()
        try:
            query = sqlHelper.select(
                table=tablesBM.PLAYERS,
                columns=['id_players', 'nickname'],
                where=f"WHERE nickname LIKE '%{name_pattern}%'",
                limit=limit
            )
            self.__db_cur.execute(query)
            rows = self.__db_cur.fetchall()
            return [(row[0], row[1]) for row in rows]  # [(player_id, player_name), ...]
        except Exception as e:
            self.log_action(
                object='repository',
                action='search_players_by_name',
                is_error=True,
                result=str(e)
            )
            return []
    
    def add_player_to_profile(self, profile_id: str, player_id: str, player_name: str = None) -> bool:
        """Добавляет игрока к профилю пользователя (через profiles_players_conn)"""
        self._ensure_db_connection()
        try:
            # Проверяем существование игрока в БД
            player_exists_query = sqlHelper.select(
                table=tablesBM.PLAYERS,
                columns=['id_players'],
                where=sqlHelper.where('id_players', player_id)
            )
            self.__db_cur.execute(player_exists_query)
            if not self.__db_cur.fetchone():
                # Игрок не существует в БД, нужно его добавить
                player_insert = sqlHelper.insert(
                    table=tablesBM.PLAYERS,
                    columns=['id_players', 'nickname'],
                    values=[player_id, player_name or f"Player {player_id}"]
                )
                self._write_queue.append(('execute', player_insert))
                self._write_queue.append(('commit', None))
                self._process_write_queue()
            
            # Добавляем связь через profiles_players_conn (используем метод для прямых связей)
            return self.add_profile_player_connection(profile_id, player_id)
            
        except Exception as e:
            self.log_action(
                object='repository',
                action='add_player_to_profile',
                is_error=True,
                result=str(e),
                id_profile=profile_id
            )
            return False
        except Exception as e:
            self.log_action(
                object='repository',
                action='add_player_to_profile',
                is_error=True,
                result=str(e),
                id_profile=profile_id
            )
            return False
    
    def get_players_for_active_profiles(self, active_profile_ids: list[str]) -> list[str]:
        """Получает список ID игроков для активных профилей (через profiles_players_conn)"""
        if not active_profile_ids:
            return []
        
        self._ensure_db_connection()
        try:
            # Формируем список ID для SQL запроса
            profile_ids_str = ','.join([f"'{pid}'" for pid in active_profile_ids])
            
            query = f"""
                SELECT DISTINCT ppc.fk_id_players
                FROM {tablesBM.PROFILES_PLAYERS_CONN} ppc
                INNER JOIN {tablesBM.PROFILES} p ON ppc.fk_id_profile = p.id_profile
                WHERE p.id_profile IN ({profile_ids_str}) AND p.is_active = 1
            """
            self.__db_cur.execute(query)
            rows = self.__db_cur.fetchall()
            return [str(row[0]) for row in rows]
        except Exception as e:
            self.log_action(
                object='repository',
                action='get_players_for_active_profiles',
                is_error=True,
                result=str(e)
            )
            return []
    
    def update_player_info(self, player) -> bool:
        """
        Обновляет информацию об игроке в БД на основе объекта Player
        
        :param player: Объект Player
        :return: True если успешно, False в случае ошибки
        """
        from data_classes import Player
        if not isinstance(player, Player):
            return False
        
        self._ensure_db_connection()
        try:
            escaped_id = sqlHelper._escape_sql_string(player.id)
            escaped_name = sqlHelper._escape_sql_string(player.name)
            escaped_private = 1 if player.private else 0
            escaped_positive_match = 1 if player.positiveMatch else 0
            
            # Обрабатываем даты
            created_at = 'NULL'
            if player._createdAt:
                try:
                    created_at_str = player._createdAt.replace("T", " ").replace("Z", "")
                    created_at = f"'{created_at_str}'"
                except:
                    created_at = 'NULL'
            
            updated_at = 'NULL'
            if player._updatedAt:
                try:
                    updated_at_str = player._updatedAt.replace("T", " ").replace("Z", "")
                    updated_at = f"'{updated_at_str}'"
                except:
                    updated_at = 'NULL'
            
            # Используем INSERT ... ON DUPLICATE KEY UPDATE для обновления всех полей
            query = f"""
                INSERT INTO {tablesBM.PLAYERS} 
                (id_players, nickname, positive_match, private, created_at, updated_at)
                VALUES 
                ('{escaped_id}', '{escaped_name}', {escaped_positive_match}, {escaped_private}, {created_at}, {updated_at})
                ON DUPLICATE KEY UPDATE
                    nickname = VALUES(nickname),
                    positive_match = VALUES(positive_match),
                    private = VALUES(private),
                    created_at = COALESCE(VALUES(created_at), created_at),
                    updated_at = VALUES(updated_at)
            """
            
            self.__db_cur.execute(query)
            self.__db_con.commit()
            
            # Обновляем связи игрок-сервер
            try:
                self.update_players_servers_from_player(player)
            except Exception as servers_error:
                # Логируем ошибку, но не прерываем выполнение
                self._logger.warning(f"Ошибка при обновлении связей игрок-сервер для игрока {player.id}: {servers_error}")
            
            return True
        except Exception as e:
            self.__db_con.rollback()
            self.log_action(
                object='repository',
                action='update_player_info',
                is_error=True,
                result=str(e),
                comment=f'Ошибка при обновлении игрока {player.id}'
            )
            return False
    
    def update_server_info(self, server) -> bool:
        """
        Обновляет информацию о сервере в БД на основе объекта Server
        
        :param server: Объект Server или RustServer
        :return: True если успешно, False в случае ошибки
        """
        from data_classes import Server
        if not isinstance(server, Server):
            return False
        
        self._ensure_db_connection()
        try:
            escaped_id = sqlHelper._escape_sql_string(server.id)
            escaped_name = sqlHelper._escape_sql_string(server.name)
            escaped_private = 1 if server._private else 0
            escaped_country = sqlHelper._escape_sql_string(server._country or '')
            rank = server._rank if server._rank else 'NULL'
            
            # Используем INSERT ... ON DUPLICATE KEY UPDATE для обновления всех полей
            # rank - зарезервированное слово в MySQL, экранируем обратными кавычками
            query = f"""
                INSERT INTO {tablesBM.SERVERS} 
                (id_server, fk_games_id, server_name, `rank`, private, country)
                VALUES 
                ('{escaped_id}', 
                 (SELECT id_game FROM {tablesBM.GAMES} WHERE game_name = '{server.game_id}' LIMIT 1),
                 '{escaped_name}', {rank}, {escaped_private}, '{escaped_country}')
                ON DUPLICATE KEY UPDATE
                    server_name = VALUES(server_name),
                    `rank` = VALUES(`rank`),
                    private = VALUES(private),
                    country = VALUES(country)
            """
            
            self.__db_cur.execute(query)
            self.__db_con.commit()
            return True
        except Exception as e:
            self.__db_con.rollback()
            self.log_action(
                object='repository',
                action='update_server_info',
                is_error=True,
                result=str(e),
                comment=f'Ошибка при обновлении сервера {server.id}'
            )
            return False
    
    def get_players(self) -> dict:
        """Получает список всех игроков из БД"""
        self._ensure_db_connection()
        self.__db_cur.execute(sqlHelper.select(
            table=tablesBM.PLAYERS,
            columns=['nickname', 'id_players']
        ))
        rows = self.__db_cur.fetchall()
        result: dict[str, str] = {}
        for row in rows:
            result[row[0]] = row[1]
        return result
    
    def update_rust_server(self, server) -> bool:
        """
        Обновляет или вставляет запись в rust_servers для Rust сервера
        
        :param server: Объект RustServer
        :return: True если успешно, False в случае ошибки
        """
        if not isinstance(server, RustServer):
            return False
        
        self._ensure_db_connection()
        try:
            # Проверяем существование сервера в таблице servers
            server_exists_query = sqlHelper.select(
                table=tablesBM.SERVERS,
                columns=['id_server'],
                where=sqlHelper.where('id_server', server.id)
            )
            self.__db_cur.execute(server_exists_query)
            if not self.__db_cur.fetchone():
                # Сервер не существует в servers, не можем добавить в rust_servers
                self.log_action(
                    object='repository',
                    action='update_rust_server',
                    is_error=True,
                    result=f'Server {server.id} does not exist in servers table',
                    comment='Cannot insert rust_server without corresponding server'
                )
                return False
            
            # Подготавливаем данные для вставки/обновления
            # Преобразуем даты вайпов
            next_wipe_date = None
            if server._rust_next_wipe:
                try:
                    # Формат: "YYYY-MM-DD HH:MM:SS" или ISO format
                    next_wipe_str = server._rust_next_wipe.replace("T", " ").replace("Z", "")
                    next_wipe_date = f"'{next_wipe_str}'"
                except:
                    next_wipe_date = 'NULL'
            else:
                next_wipe_date = 'NULL'
            
            last_wipe_date = None
            if server._rust_last_wipe:
                try:
                    last_wipe_str = server._rust_last_wipe.replace("T", " ").replace("Z", "")
                    last_wipe_date = f"'{last_wipe_str}'"
                except:
                    last_wipe_date = 'NULL'
            else:
                last_wipe_date = 'NULL'
            
            # Экранируем строковые значения
            escaped_id = sqlHelper._escape_sql_string(server.id)
            escaped_description = sqlHelper._escape_sql_string(server._rust_description or '')
            escaped_gamemode = sqlHelper._escape_sql_string(server._rust_gamemode or '')
            escaped_next_wipe_type = sqlHelper._escape_sql_string(server._rust_next_wipe_type or '')
            escaped_steam_id = str(server._serverSteamId) if server._serverSteamId else 'NULL'
            
            # Используем INSERT ... ON DUPLICATE KEY UPDATE
            query = f"""
                INSERT INTO {tablesBM.RUST_SERVERS} 
                (fk_id_servers, is_pve, official, description, modded, gamemode, steam_id, next_wipe_date, next_wipe_type, last_wipe_date)
                VALUES 
                ('{escaped_id}', {1 if server._pve else 0}, {1 if server._official else 0}, 
                 '{escaped_description}', {1 if server._rust_modded else 0}, '{escaped_gamemode}', 
                 {escaped_steam_id}, {next_wipe_date}, '{escaped_next_wipe_type}', {last_wipe_date})
                ON DUPLICATE KEY UPDATE
                    is_pve = VALUES(is_pve),
                    official = VALUES(official),
                    description = VALUES(description),
                    modded = VALUES(modded),
                    gamemode = VALUES(gamemode),
                    steam_id = VALUES(steam_id),
                    next_wipe_date = VALUES(next_wipe_date),
                    next_wipe_type = VALUES(next_wipe_type),
                    last_wipe_date = VALUES(last_wipe_date)
            """
            
            self.__db_cur.execute(query)
            self.__db_con.commit()
            return True
        except Exception as e:
            self.__db_con.rollback()
            self.log_action(
                object='repository',
                action='update_rust_server',
                is_error=True,
                result=str(e),
                server_id=server.id
            )
            return False
    
    def bulk_insert_rust_servers(self, servers: list) -> int:
        """
        Массовое добавление/обновление Rust серверов в БД
        
        :param servers: список объектов RustServer
        :return: количество добавленных/обновленных серверов
        """
        if not servers:
            return 0
        
        self._ensure_db_connection()
        try:
            batch_size = 500
            total_affected = 0
            
            for i in range(0, len(servers), batch_size):
                batch = servers[i:i + batch_size]
                values_list = []
                
                for server in batch:
                    if not isinstance(server, RustServer):
                        continue
                    
                    # Проверяем существование сервера в servers
                    server_exists_query = sqlHelper.select(
                        table=tablesBM.SERVERS,
                        columns=['id_server'],
                        where=sqlHelper.where('id_server', server.id)
                    )
                    self.__db_cur.execute(server_exists_query)
                    if not self.__db_cur.fetchone():
                        continue  # Пропускаем, если сервер не существует в servers
                    
                    # Подготавливаем данные
                    escaped_id = sqlHelper._escape_sql_string(server.id)
                    escaped_description = sqlHelper._escape_sql_string(server._rust_description or '')
                    escaped_gamemode = sqlHelper._escape_sql_string(server._rust_gamemode or '')
                    escaped_next_wipe_type = sqlHelper._escape_sql_string(server._rust_next_wipe_type or '')
                    
                    # Обрабатываем даты
                    next_wipe_date = 'NULL'
                    if server._rust_next_wipe:
                        try:
                            next_wipe_str = server._rust_next_wipe.replace("T", " ").replace("Z", "")
                            next_wipe_date = f"'{next_wipe_str}'"
                        except:
                            next_wipe_date = 'NULL'
                    
                    last_wipe_date = 'NULL'
                    if server._rust_last_wipe:
                        try:
                            last_wipe_str = server._rust_last_wipe.replace("T", " ").replace("Z", "")
                            last_wipe_date = f"'{last_wipe_str}'"
                        except:
                            last_wipe_date = 'NULL'
                    
                    steam_id = str(server._serverSteamId) if server._serverSteamId else 'NULL'
                    
                    values_list.append(
                        f"('{escaped_id}', {1 if server._pve else 0}, {1 if server._official else 0}, "
                        f"'{escaped_description}', {1 if server._rust_modded else 0}, '{escaped_gamemode}', "
                        f"{steam_id}, {next_wipe_date}, '{escaped_next_wipe_type}', {last_wipe_date})"
                    )
                
                if not values_list:
                    continue
                
                values_str = ', '.join(values_list)
                query = f"""
                    INSERT INTO {tablesBM.RUST_SERVERS} 
                    (fk_id_servers, is_pve, official, description, modded, gamemode, steam_id, next_wipe_date, next_wipe_type, last_wipe_date)
                    VALUES {values_str}
                    ON DUPLICATE KEY UPDATE
                        is_pve = VALUES(is_pve),
                        official = VALUES(official),
                        description = VALUES(description),
                        modded = VALUES(modded),
                        gamemode = VALUES(gamemode),
                        steam_id = VALUES(steam_id),
                        next_wipe_date = VALUES(next_wipe_date),
                        next_wipe_type = VALUES(next_wipe_type),
                        last_wipe_date = VALUES(last_wipe_date)
                """
                
                self.__db_cur.execute(query)
                total_affected += self.__db_cur.rowcount
            
            self.__db_con.commit()
            return total_affected
        except Exception as e:
            self.__db_con.rollback()
            self.log_action(
                object='repository',
                action='bulk_insert_rust_servers',
                is_error=True,
                result=str(e)
            )
            return 0
    
    def update_players_servers_from_player(self, player) -> int:
        """
        Обновляет связи игрок-сервер в таблице players_servers на основе данных игрока
        
        :param player: Объект Player
        :return: количество обновленных/добавленных связей
        """
        from data_classes import Player
        if not isinstance(player, Player):
            return 0
        
        self._ensure_db_connection()
        try:
            player_servers_links = []
            
            # Обрабатываем метаданные серверов игрока
            for server_id, meta in player.player_servers_meta.items():
                time_played = meta.get('timePlayed', 0)
                is_online = 1 if meta.get('online', False) else 0
                
                player_servers_links.append({
                    'player_id': player.id,
                    'server_id': server_id,
                    'time_played': time_played,
                    'is_online': is_online
                })
            
            # Используем существующий метод bulk_insert_player_servers
            if player_servers_links:
                return self.bulk_insert_player_servers(player_servers_links)
            return 0
        except Exception as e:
            self.log_action(
                object='repository',
                action='update_players_servers_from_player',
                is_error=True,
                result=str(e),
                player_id=player.id
            )
            return 0
    
    def add_suggestion(self, profile_id: str, message_text: str) -> int:
        """
        Добавляет отчет/предложение пользователя в БД
        
        :param profile_id: ID профиля пользователя
        :param message_text: Текст отчета
        :return: ID созданного отчета или 0 в случае ошибки
        """
        self._ensure_db_connection()
        try:
            escaped_profile_id = sqlHelper._escape_sql_string(profile_id)
            escaped_message = sqlHelper._escape_sql_string(message_text)
            
            query = sqlHelper.insert(
                table=tablesBM.SUGGESTIONS,
                columns=['fk_id_profile', 'msg_txt'],
                values=[escaped_profile_id, escaped_message]
            )
            self._write_queue.append(('execute', query))
            self._write_queue.append(('commit', None))
            self._process_write_queue()
            
            # Получаем ID последней вставленной записи
            self.__db_cur.execute("SELECT LAST_INSERT_ID()")
            result = self.__db_cur.fetchone()
            return result[0] if result else 0
        except Exception as e:
            self.log_action(
                object='repository',
                action='add_suggestion',
                is_error=True,
                result=str(e),
                id_profile=profile_id
            )
            return 0
    
    def get_unanswered_suggestions(self) -> list:
        """
        Получает список неотвеченных отчетов
        
        :return: Список кортежей (id_suggestions, fk_id_profile, msg_txt, created_at, profile_nickname, profile_name)
        """
        self._ensure_db_connection()
        try:
            query = f"""
                SELECT s.id_suggestions, s.fk_id_profile, s.msg_txt, s.created_at, 
                       p.profile_nickname, p.profile_name
                FROM {tablesBM.SUGGESTIONS} s
                INNER JOIN {tablesBM.PROFILES} p ON s.fk_id_profile = p.id_profile
                WHERE s.isAnswered = 0
                ORDER BY s.created_at DESC
            """
            self.__db_cur.execute(query)
            return self.__db_cur.fetchall()
        except Exception as e:
            self.log_action(
                object='repository',
                action='get_unanswered_suggestions',
                is_error=True,
                result=str(e)
            )
            return []
    
    def answer_suggestion(self, suggestion_id: int, answer_text: str) -> bool:
        """
        Отвечает на отчет пользователя
        
        :param suggestion_id: ID отчета
        :param answer_text: Текст ответа (не сохраняется в БД, только отправляется пользователю)
        :return: True если успешно, False в случае ошибки
        """
        self._ensure_db_connection()
        try:
            from datetime import datetime
            answered_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            where_clause = sqlHelper.where('id_suggestions', str(suggestion_id)).replace('WHERE ', '')
            query = sqlHelper.update(
                table=tablesBM.SUGGESTIONS,
                set_clause=f"isAnswered = 1, answered_at = '{answered_at}'",
                where=where_clause
            )
            self._write_queue.append(('execute', query))
            self._write_queue.append(('commit', None))
            self._process_write_queue()
            return True
        except Exception as e:
            self.log_action(
                object='repository',
                action='answer_suggestion',
                is_error=True,
                result=str(e),
                comment=f'Ошибка при ответе на отчет {suggestion_id}'
            )
            return False
    
    def get_suggestion_user_id(self, suggestion_id: int) -> Optional[str]:
        """
        Получает ID пользователя для отчета
        
        :param suggestion_id: ID отчета
        :return: ID профиля пользователя или None
        """
        self._ensure_db_connection()
        try:
            query = sqlHelper.select(
                table=tablesBM.SUGGESTIONS,
                columns=['fk_id_profile'],
                where=sqlHelper.where('id_suggestions', str(suggestion_id))
            )
            self.__db_cur.execute(query)
            row = self.__db_cur.fetchone()
            return str(row[0]) if row else None
        except Exception as e:
            self.log_action(
                object='repository',
                action='get_suggestion_user_id',
                is_error=True,
                result=str(e)
            )
            return None
    
    def get_server_full_info(self, server_id: str) -> Optional[dict]:
        """
        Получает полную информацию о сервере из БД
        
        :param server_id: ID сервера
        :return: Словарь с информацией о сервере или None
        """
        self._ensure_db_connection()
        try:
            escaped_id = sqlHelper._escape_sql_string(server_id)
            query = f"""
                SELECT s.id_server, s.server_name, s.private, s.country, s.`rank`,
                       rs.is_pve, rs.official, rs.description, rs.modded, rs.gamemode, 
                       rs.steam_id, rs.next_wipe_date, rs.next_wipe_type, rs.last_wipe_date
                FROM {tablesBM.SERVERS} s
                LEFT JOIN {tablesBM.RUST_SERVERS} rs ON s.id_server = rs.fk_id_servers
                WHERE s.id_server = '{escaped_id}'
            """
            self.__db_cur.execute(query)
            row = self.__db_cur.fetchone()
            if row:
                return {
                    'id': row[0],
                    'name': row[1],
                    'private': bool(row[2]),
                    'country': row[3] or '',
                    'rank': row[4],
                    'pve': bool(row[5]) if row[5] is not None else False,
                    'official': bool(row[6]) if row[6] is not None else False,
                    'description': row[7] or '',
                    'modded': bool(row[8]) if row[8] is not None else False,
                    'gamemode': row[9] or '',
                    'steam_id': row[10] or '',
                    'next_wipe_date': row[11],
                    'next_wipe_type': row[12] or '',
                    'last_wipe_date': row[13]
                }
            return None
        except Exception as e:
            self.log_action(
                object='repository',
                action='get_server_full_info',
                is_error=True,
                result=str(e)
            )
            return None
    
    def get_player_full_info(self, player_id: str) -> Optional[dict]:
        """
        Получает полную информацию об игроке из БД
        
        :param player_id: ID игрока
        :return: Словарь с информацией об игроке или None
        """
        self._ensure_db_connection()
        try:
            query = sqlHelper.select(
                table=tablesBM.PLAYERS,
                columns=['id_players', 'nickname', 'private'],
                where=sqlHelper.where('id_players', player_id)
            )
            self.__db_cur.execute(query)
            row = self.__db_cur.fetchone()
            if row:
                return {
                    'id': row[0],
                    'name': row[1],
                    'private': bool(row[2])
                }
            return None
        except Exception as e:
            self.log_action(
                object='repository',
                action='get_player_full_info',
                is_error=True,
                result=str(e)
            )
            return None