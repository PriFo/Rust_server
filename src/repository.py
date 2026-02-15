# repository.py - Полностью переписан для новой схемы БД v5.1
# Версия 2.0

from typing import Union, Optional, Dict, List, Any, Tuple
from pymysql import Connection, connect
from pymysql.cursors import Cursor, DictCursor
import json
from datetime import datetime, timedelta
from collections import deque
import atexit
import time
import threading

from src.data_classes import Profile, RustServer, Server, Player
from src.filters import Filter, RustFilter, PlayerFilter
from os import getenv
from src.SQLSyntaxHelper import (
    MySQLSyntaxHelper as sqlHelper,
    ETablesBM_DB as tablesBM,
)
from src.logger import Logger


class Repository:
    """Репозиторий для работы с новой схемой БД v5.1"""
    
    # --- Реализация синглтона ---
    _instance = None
    _db_initialized = False

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance.__db_con = None
            cls._instance.__db_cur = None
            cls._instance._profiles = {}
            cls._instance._db_initialized = False
            cls._instance._write_queue = deque()
            cls._instance._profile_cache_ttl = {}
            cls._instance._default_ttl = 3600
            cls._instance._logger = Logger("Repository")
            cls._instance._id_types_cache = {}
            cls._instance._db_lock = threading.RLock()  # Блокировка для потокобезопасности (reentrant)
            cls._instance._last_clear_init_state = None  # Кэш последнего вызова clear_initialization_state
            
            # Регистрируем обработчик для сохранения очереди при выходе
            atexit.register(cls._instance._flush_queue_on_exit)
        return cls._instance
    
    def __init__(self) -> None:
        if not self._db_initialized:
            self._profiles: Dict[int, Profile] = {}
            if not hasattr(self, '_logger'):
                self._logger = Logger("Repository")
            if not hasattr(self, '_id_types_cache'):
                self._id_types_cache = {}
            if not hasattr(self, '_db_lock'):
                self._db_lock = threading.RLock()
    
    # --- Вспомогательные методы для работы с ID ---
    
    def _convert_id_for_db(self, id_value: Any, column_name: str = None) -> Any:
        """Конвертирует ID для записи в БД"""
        if id_value is None:
            return None
        
        # Если известен тип столбца, конвертируем соответствующим образом
        if column_name and column_name in self._id_types_cache:
            col_type = self._id_types_cache[column_name]
            if col_type in ['bigint', 'int', 'smallint', 'tinyint', 'mediumint']:
                try:
                    return int(id_value)
                except (ValueError, TypeError):
                    return 0
            elif col_type in ['varchar', 'char', 'text']:
                return str(id_value)
        
        # Автоопределение по названию столбца
        if column_name:
            column_lower = column_name.lower()
            if 'id_profile' in column_lower:
                try:
                    return int(id_value)
                except (ValueError, TypeError):
                    return 0
            elif any(id_keyword in column_lower for id_keyword in ['id_server', 'id_players', 'entity_id', 'server_id', 'player_id']):
                # Числовые ID
                try:
                    return int(id_value)
                except (ValueError, TypeError):
                    return 0
            elif 'fk_id_' in column_lower:
                # Внешние ключи - обычно числа
                try:
                    return int(id_value)
                except (ValueError, TypeError):
                    return 0
        
        # По умолчанию пытаемся конвертировать в int
        try:
            return int(id_value)
        except (ValueError, TypeError):
            return str(id_value)
    
    def _normalize_status(self, status: Any) -> str:
        """
        Нормализует статус сервера к допустимым значениям ENUM
        Допустимые значения: 'online', 'offline', 'unknown'
        """
        if not status:
            return 'unknown'
        
        status_str = str(status).lower().strip()
        
        # Маппинг различных значений статуса к стандартным
        if status_str in ['online', 'on', '1', 'true', 'active']:
            return 'online'
        elif status_str in ['offline', 'off', '0', 'false', 'inactive']:
            return 'offline'
        else:
            return 'unknown'
    
    def _convert_id_from_db(self, id_value: Any, column_name: str = None) -> Any:
        """Конвертирует ID из БД для использования в коде"""
        if id_value is None:
            return None
        
        # Все ID в коде — int (схема v5.1 BIGINT)
        try:
            return int(id_value)
        except (ValueError, TypeError):
            return 0
    
    def _determine_column_types(self) -> None:
        """Определяет типы столбцов ID в БД"""
        try:
            self._ensure_db_connection()
            
            # Получаем информацию о типах столбцов (%% — экранирование % для PyMySQL)
            query = """
                SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s
                AND COLUMN_NAME LIKE '%%id%%'
                AND TABLE_NAME IN ('profiles', 'servers', 'players', 'subscriptions',
                                   'server_filters', 'rust_servers_filters', 'player_filters',
                                   'servers_history', 'players_history')
            """
            db_name = self.__db_con.db
            if isinstance(db_name, bytes):
                db_name = db_name.decode()
            self.__db_cur.execute(query, (db_name,))
            rows = self.__db_cur.fetchall()
            for row in rows:
                # DictCursor: ключи как в запросе (MySQL возвращает TABLE_NAME, COLUMN_NAME, DATA_TYPE)
                table_name = row.get("TABLE_NAME") or row.get("table_name")
                column_name = row.get("COLUMN_NAME") or row.get("column_name")
                data_type = row.get("DATA_TYPE") or row.get("data_type")
                if not table_name or not column_name or not data_type:
                    continue
                key = f"{table_name}.{column_name}"
                data_type_lower = (data_type or "").lower()
                self._id_types_cache[key] = data_type_lower
                self._id_types_cache[column_name] = data_type_lower
                
            self._logger.info("Определены типы для {} столбцов".format(len(self._id_types_cache)))
            
        except Exception as e:
            self._logger.warning(f"Не удалось определить типы столбцов: {e}")
    
    # --- Основные методы подключения к БД ---
    
    def _ensure_db_connection(self) -> None:
        """Инициализирует подключение к БД если оно еще не установлено или закрыто"""
        # Используем блокировку для потокобезопасности
        with self._db_lock:
            connection_valid = False
            
            if self.__db_con is not None:
                try:
                    self.__db_cur.execute("SELECT 1")
                    connection_valid = True
                except Exception:
                    connection_valid = False
                    try:
                        if self.__db_cur:
                            self.__db_cur.close()
                    except:
                        pass
                    try:
                        if self.__db_con:
                            self.__db_con.close()
                    except:
                        pass
                    self.__db_con = None
                    self.__db_cur = None
                    self._db_initialized = False
            
            if not connection_valid:
                try:
                    db_host = getenv('DB_HOST')
                    db_port_str = getenv('DB_PORT')
                    db_user = getenv('DB_USER')
                    db_password = getenv('DB_PASSWORD')
                    db_name = getenv('DB_NAME')
                    
                    self._logger.info("Инициализация подключения к БД", {
                        'host': db_host,
                        'user': db_user,
                        'database': db_name
                    })
                    
                    if not db_host:
                        raise ValueError("DB_HOST не установлена в переменных окружения")
                    if not db_port_str:
                        db_port = 3306
                    else:
                        db_port = int(db_port_str)
                    if not db_user:
                        raise ValueError("DB_USER не установлена в переменных окружения")
                    if not db_password:
                        raise ValueError("DB_PASSWORD не установлена в переменных окружения")
                    if not db_name:
                        raise ValueError("DB_NAME не установлена в переменных окружения")
                    
                    self.__db_con: Connection = connect(
                        host=db_host,
                        port=db_port,
                        user=db_user,
                        password=db_password,
                        database=db_name,
                        autocommit=False,
                        connect_timeout=10,
                        read_timeout=30,      # <- добавить
                        write_timeout=30,     # <- добавить
                        charset='utf8mb4',
                        cursorclass=DictCursor
                    )
                    
                    self.__db_cur: Cursor = self.__db_con.cursor()
                    self._db_initialized = True
                    
                    self._logger.info("Подключение к БД установлено успешно")
                    
                    # Определяем типы столбцов
                    self._determine_column_types()
                    
                except Exception as e:
                    self._logger.error(f"Ошибка подключения к БД: {e}")
                    raise ConnectionError(f"Failed to connect to database: {e}")
    
    @property
    def db_cursor(self) -> Cursor:
        """Публичное свойство для доступа к курсору БД"""
        self._ensure_db_connection()
        return self.__db_cur
    
    @property
    def db_connection(self) -> Connection:
        """Публичное свойство для доступа к соединению БД"""
        self._ensure_db_connection()
        return self.__db_con
    
    def close(self) -> None:
        """Закрывает соединение с БД (идемпотентно, под _db_lock)."""
        with self._db_lock:
            self._flush_queue_on_exit()
            if self.__db_cur:
                try:
                    self.__db_cur.close()
                except Exception:
                    pass
                self.__db_cur = None
            if self.__db_con:
                try:
                    self.__db_con.close()
                except Exception:
                    pass
                self.__db_con = None
                self._db_initialized = False
    
    # --- Очередь записи ---
    
    def _process_write_queue(self) -> None:
        """Обрабатывает очередь записи в БД (под _db_lock, при ошибке — rollback и break)."""
        with self._db_lock:
            try:
                self._ensure_db_connection()
                processed = 0
                while self._write_queue:
                    operation = self._write_queue.popleft()
                    if operation['type'] == 'execute' and 'query' in operation:
                        try:
                            if 'params' in operation:
                                self.__db_cur.execute(operation['query'], operation['params'])
                            else:
                                self.__db_cur.execute(operation['query'])
                            processed += 1
                        except Exception as e:
                            self._logger.error(f"Ошибка при выполнении запроса из очереди: {e}")
                            self._logger.error(f"Запрос: {operation['query'][:200] if operation['query'] else 'None'}")
                            try:
                                self.__db_con.rollback()
                            except Exception:
                                pass
                            break
                    elif operation['type'] == 'commit':
                        try:
                            self.__db_con.commit()
                            if processed > 0:
                                self._logger.debug(f"Зафиксировано {processed} операций в БД")
                        except Exception as e:
                            self._logger.error(f"Ошибка при commit: {e}")
                            try:
                                self.__db_con.rollback()
                            except Exception:
                                pass
                            break
            except Exception as e:
                self._logger.error(f"Ошибка при обработке очереди записи: {e}")
    
    def _flush_queue_on_exit(self) -> None:
        """Обрабатывает оставшиеся команды при выходе"""
        self._process_write_queue()
    
    def _add_to_queue(self, query_type: str, query: str = None, params: List = None) -> None:
        """Добавляет операцию в очередь (params is not None — добавляем, в т.ч. пустой список)."""
        operation = {'type': query_type}
        if query:
            operation['query'] = query
        if params is not None:
            operation['params'] = params
        self._write_queue.append(operation)
    
    # --- Профили ---
    
    @property
    def profiles(self) -> Dict[int, Profile]:
        return self._profiles

    def _normalize_profile_id(self, profile_id: Any) -> int:
        """Приводит profile_id к int для использования как ключ."""
        if profile_id is None:
            return 0
        try:
            return int(profile_id)
        except (ValueError, TypeError):
            return 0

    def add_profile(self, value: Profile, id: Optional[Union[str, int]] = None) -> None:
        """Добавляет профиль в память"""
        profile_id = self._normalize_profile_id(id if id is not None else value.id)
        self._profiles[profile_id] = value

    def _insert_profile(self, profile_id: Union[str, int]) -> None:
        """Добавляет профиль в БД"""
        pid = self._normalize_profile_id(profile_id)
        profile = self._profiles.get(pid)
        if not profile:
            self._logger.warning(f"Попытка вставить профиль {profile_id}, но его нет в памяти")
            return

        self._ensure_db_connection()
        try:
            profile_id_db = self._convert_id_for_db(pid, 'id_profile')
            
            data = {
                'id_profile': profile_id_db,
                'profile_nickname': profile.nickname or '',
                'profile_name': profile.name or '',
                'profile_surname': profile.surname or '',
                'is_active': profile.is_active,
                'bot_banned': False
            }
            
            # Используем параметризованный запрос
            query, params = sqlHelper.insert(table=tablesBM.PROFILES, data=data)
            query += " ON DUPLICATE KEY UPDATE "
            query += ", ".join([f"`{key}` = VALUES(`{key}`)" for key in data.keys() if key != 'id_profile'])
            
            self.__db_cur.execute(query, params)
            self.__db_con.commit()
            
            self._logger.info(f"Профиль {pid} сохранен в БД")

        except Exception as e:
            self._logger.error(f"Ошибка при сохранении профиля {pid}: {e}")
            try:
                self.__db_con.rollback()
            except:
                pass
    
    def load_profile(self, profile_id: Union[str, int]) -> Optional[Profile]:
        """Загружает профиль из БД с учетом TTL"""
        pid = self._normalize_profile_id(profile_id)
        if pid in self._profile_cache_ttl:
            if time.time() < self._profile_cache_ttl[pid]:
                return self._profiles.get(pid)

        self._ensure_db_connection()
        try:
            profile_id_db = self._convert_id_for_db(pid, 'id_profile')
            
            where_sql, where_params = sqlHelper.where_params({'id_profile': profile_id_db})
            query = sqlHelper.select(
                table=tablesBM.PROFILES,
                columns=['id_profile', 'profile_nickname', 'profile_name', 
                        'profile_surname', 'is_active', 'notification_settings',
                        'bot_banned', 'last_activity'],
                where=where_sql
            )
            
            self.__db_cur.execute(query, where_params)
            row = self.__db_cur.fetchone()
            
            if row:
                # Создаем объект Profile
                profile = Profile(
                    id=self._convert_id_from_db(row['id_profile'], 'id_profile'),
                    nickname=row['profile_nickname'] or '',
                    name=row['profile_name'] or '',
                    surname=row['profile_surname'] or '',
                    is_active=bool(row['is_active']) if row['is_active'] is not None else False
                )
                
                # Загружаем подписки
                self._load_profile_subscriptions(profile_id_db, profile)
                
                # Загружаем фильтры
                self._load_profile_filters(profile_id_db, profile)
                
                # Сохраняем в кэш
                self._profiles[pid] = profile
                self._profile_cache_ttl[pid] = time.time() + self._default_ttl
                
                self._logger.debug(f"Профиль {profile_id} загружен из БД")
                return profile
                
        except Exception as e:
            self._logger.error(f"Ошибка при загрузке профиля {profile_id}: {e}")
        
        return None
    
    def update_profile(self, profile_id: Union[str, int] = None) -> None:
        """Обновляет профиль в БД"""
        if profile_id is None:
            return
        pid = self._normalize_profile_id(profile_id)
        profile = self._profiles.get(pid)
        if not profile:
            return
        
        self._ensure_db_connection()
        try:
            profile_id_db = self._convert_id_for_db(pid, 'id_profile')
            data = {
                'profile_nickname': profile.nickname or '',
                'profile_name': profile.name or '',
                'profile_surname': profile.surname or '',
                'is_active': profile.is_active,
                'last_activity': datetime.now()
            }
            where_sql, where_params = sqlHelper.where_params({'id_profile': profile_id_db})
            query, params = sqlHelper.update(
                table=tablesBM.PROFILES,
                set_values=data,
                where_conditions={'id_profile': profile_id_db}
            )
            self.__db_cur.execute(query, params)
            self.__db_con.commit()
            if pid in self._profile_cache_ttl:
                self._profile_cache_ttl[pid] = time.time() + self._default_ttl
        except Exception as e:
            self._logger.error(f"Ошибка при обновлении профиля {pid}: {e}")
            try:
                self.__db_con.rollback()
            except:
                pass
    
    def activate_profile(self, profile_id: Union[str, int]) -> bool:
        """Активирует профиль пользователя"""
        try:
            pid = self._normalize_profile_id(profile_id)
            profile_id_db = self._convert_id_for_db(pid, 'id_profile')
            
            data = {'is_active': True, 'last_activity': datetime.now()}
            where_conditions = {'id_profile': profile_id_db}
            
            query, params = sqlHelper.update(
                table=tablesBM.PROFILES,
                set_values=data,
                where_conditions=where_conditions
            )
            
            self._add_to_queue('execute', query, params)
            self._add_to_queue('commit')
            self._process_write_queue()
            
            profile = self._profiles.get(pid)
            if profile:
                profile._is_active = True
            self._logger.info(f"Профиль {pid} активирован")
            return True
        except Exception as e:
            self._logger.error(f"Ошибка при активации профиля {pid}: {e}")
            return False

    def deactivate_profile(self, profile_id: Union[str, int]) -> bool:
        """Деактивирует профиль пользователя"""
        try:
            pid = self._normalize_profile_id(profile_id)
            profile_id_db = self._convert_id_for_db(pid, 'id_profile')
            data = {'is_active': False, 'last_activity': datetime.now()}
            where_conditions = {'id_profile': profile_id_db}
            query, params = sqlHelper.update(
                table=tablesBM.PROFILES,
                set_values=data,
                where_conditions=where_conditions
            )
            self._add_to_queue('execute', query, params)
            self._add_to_queue('commit')
            self._process_write_queue()
            profile = self._profiles.get(pid)
            if profile:
                profile._is_active = False
            self._logger.info(f"Профиль {pid} деактивирован")
            return True
        except Exception as e:
            self._logger.error(f"Ошибка при деактивации профиля {pid}: {e}")
            return False

    def get_active_profiles(self) -> List[int]:
        """Получает список ID активных профилей"""
        self._ensure_db_connection()
        try:
            where_sql, where_params = sqlHelper.where_params({'is_active': True})
            query = sqlHelper.select(
                table=tablesBM.PROFILES,
                columns=['id_profile'],
                where=where_sql
            )
            
            self.__db_cur.execute(query, where_params)
            rows = self.__db_cur.fetchall()
            
            return [int(self._convert_id_from_db(row['id_profile'], 'id_profile')) for row in rows]
        except Exception as e:
            self._logger.error(f"Ошибка при получении активных профилей: {e}")
            return []

    def get_inactive_profile_ids(self) -> List[int]:
        """Возвращает список ID профилей с is_active = 0 (для уведомлений о перезапуске)."""
        self._ensure_db_connection()
        try:
            query = "SELECT id_profile FROM profiles WHERE is_active = 0"
            self.__db_cur.execute(query)
            rows = self.__db_cur.fetchall()
            return [int(self._convert_id_from_db(row['id_profile'], 'id_profile')) for row in rows]
        except Exception as e:
            self._logger.error(f"Ошибка при получении неактивных профилей: {e}")
            return []

    # --- Suggestions (отчёты пользователей) ---

    def fetch_suggestions_list(self) -> List[Dict[str, Any]]:
        """Список отчётов с JOIN profiles. Пустой список, если таблицы suggestions нет."""
        self._ensure_db_connection()
        try:
            self.__db_cur.execute("SHOW TABLES LIKE 'suggestions'")
            if not self.__db_cur.fetchone():
                return []
            self.__db_cur.execute("""
                SELECT s.id_suggestions, s.fk_id_profile, s.msg_txt, s.created_at,
                    p.profile_nickname, p.profile_name
                FROM suggestions s
                LEFT JOIN profiles p ON s.fk_id_profile = p.id_profile
                ORDER BY s.created_at DESC
            """)
            return self.__db_cur.fetchall()
        except Exception as e:
            self._logger.error(f"Ошибка при загрузке списка отчётов: {e}")
            return []

    def get_suggestion_by_id(self, suggestion_id: int) -> Optional[Dict[str, Any]]:
        """Один отчёт по id_suggestions с JOIN profiles."""
        self._ensure_db_connection()
        try:
            self.__db_cur.execute("""
                SELECT s.*, p.profile_nickname as user_nickname, p.profile_name as user_name
                FROM suggestions s
                LEFT JOIN profiles p ON s.fk_id_profile = p.id_profile
                WHERE s.id_suggestions = %s
            """, (suggestion_id,))
            return self.__db_cur.fetchone()
        except Exception as e:
            self._logger.error(f"Ошибка при загрузке отчёта {suggestion_id}: {e}")
            return None

    def mark_suggestion_answered(self, suggestion_id: int) -> bool:
        """Пометить отчёт как отвеченный."""
        self._ensure_db_connection()
        try:
            self.__db_cur.execute("""
                UPDATE suggestions SET is_answered = TRUE, answered_at = NOW()
                WHERE id_suggestions = %s
            """, (suggestion_id,))
            self.__db_con.commit()
            return True
        except Exception as e:
            self._logger.error(f"Ошибка при отметке ответа на отчёт {suggestion_id}: {e}")
            try:
                self.__db_con.rollback()
            except Exception:
                pass
            return False

    def delete_suggestion(self, suggestion_id: int) -> bool:
        """Удалить отчёт по ID."""
        self._ensure_db_connection()
        try:
            self.__db_cur.execute("DELETE FROM suggestions WHERE id_suggestions = %s", (suggestion_id,))
            self.__db_con.commit()
            return True
        except Exception as e:
            self._logger.error(f"Ошибка при удалении отчёта {suggestion_id}: {e}")
            try:
                self.__db_con.rollback()
            except Exception:
                pass
            return False

    def clear_tables_for_init(self, tables_to_clear: List[str], preserve_games: bool) -> int:
        """
        Очистка таблиц при инициализации: FK checks 0, TRUNCATE/DELETE, при preserve_games — INSERT games, FK 1, commit.
        Возвращает количество очищенных таблиц.
        """
        with self._db_lock:
            self._ensure_db_connection()
            try:
                self.__db_cur.execute("SET FOREIGN_KEY_CHECKS = 0")
                cleared = 0
                for table in tables_to_clear:
                    try:
                        self.__db_cur.execute(f"TRUNCATE TABLE `{table}`")
                        cleared += 1
                    except Exception:
                        try:
                            self.__db_cur.execute(f"DELETE FROM `{table}`")
                            cleared += 1
                        except Exception as e:
                            self._logger.warning(f"Не удалось очистить таблицу {table}: {e}")
                if preserve_games:
                    try:
                        self.__db_cur.execute("INSERT IGNORE INTO `games` (`id_game`, `game_name`) VALUES (1, 'rust')")
                        self.__db_cur.execute("INSERT IGNORE INTO `games` (`id_game`, `game_name`) VALUES (2, 'arma3')")
                    except Exception as e:
                        self._logger.warning(f"Не удалось вставить games: {e}")
                self.__db_cur.execute("SET FOREIGN_KEY_CHECKS = 1")
                self.__db_con.commit()
                return cleared
            except Exception as e:
                self._logger.error(f"Ошибка при очистке таблиц: {e}")
                try:
                    self.__db_con.rollback()
                except Exception:
                    pass
                raise

    # --- Подписки (заменяют старые таблицы связей) ---
    
    def _load_profile_subscriptions(self, profile_id: Any, profile: Profile) -> None:
        """Загружает подписки профиля из БД"""
        try:
            profile_id_db = self._convert_id_for_db(profile_id, 'id_profile')
            
            # Загружаем подписки на серверы
            where_sql, where_params = sqlHelper.where_params({
                'fk_id_profile': profile_id_db,
                'entity_type': 'server',
                'is_active': True
            })
            
            query = sqlHelper.select(
                table=tablesBM.SUBSCRIPTIONS,
                columns=['entity_id', 'notification_types'],
                where=where_sql
            )
            
            self.__db_cur.execute(query, where_params)
            server_rows = self.__db_cur.fetchall()
            
            for row in server_rows:
                server_id = self._convert_id_from_db(row['entity_id'], 'entity_id')
                # Загружаем информацию о сервере
                server = self._load_server_info(server_id)
                if server:
                    profile.add_server(server)
            
            # Загружаем подписки на игроков
            where_sql, where_params = sqlHelper.where_params({
                'fk_id_profile': profile_id_db,
                'entity_type': 'player',
                'is_active': True
            })
            
            query = sqlHelper.select(
                table=tablesBM.SUBSCRIPTIONS,
                columns=['entity_id', 'notification_types'],
                where=where_sql
            )
            
            self.__db_cur.execute(query, where_params)
            player_rows = self.__db_cur.fetchall()
            
            for row in player_rows:
                player_id = self._convert_id_from_db(row['entity_id'], 'entity_id')
                # Загружаем информацию об игроке
                player = self._load_player_info(player_id)
                if player:
                    profile.add_player(player)
                    
        except Exception as e:
            self._logger.error(f"Ошибка при загрузке подписок профиля {profile_id}: {e}")
    
    def _load_server_info(self, server_id: Any) -> Optional[Server]:
        """Загружает информацию о сервере из БД с учётом типа игры."""
        try:
            server_id_db = self._convert_id_for_db(server_id, 'id_server')
            # JOIN servers и games для получения game_name
            query = """
                SELECT s.*, g.game_name
                FROM `servers` s
                INNER JOIN `games` g ON s.fk_games_id = g.id_game
                WHERE s.id_server = %s
            """
            self.__db_cur.execute(query, (server_id_db,))
            row = self.__db_cur.fetchone()
            if not row:
                return None

            game_name = row['game_name']
            if game_name == 'rust':
                # Дополнительный JOIN для Rust
                rust_query = """
                    SELECT rs.*
                    FROM `rust_servers` rs
                    WHERE rs.fk_id_servers = %s
                """
                self.__db_cur.execute(rust_query, (server_id_db,))
                rust_row = self.__db_cur.fetchone()
                if rust_row:
                    # Объединяем данные
                    full_row = {**row, **rust_row}
                    return RustServer.from_db_dict(full_row, game_name)
            # Для не-Rust серверов или если нет доп. данных
            return Server.from_db_dict(row, game_name)
        except Exception as e:
            self._logger.error(f"Ошибка загрузки сервера {server_id}: {e}")
            return None
    
    def _load_rust_server_info(self, server_id: Any, base_info: Dict) -> Optional[RustServer]:
        """Загружает дополнительную информацию для Rust серверов"""
        try:
            server_id_db = self._convert_id_for_db(server_id, 'id_server')
            
            where_sql, where_params = sqlHelper.where_params({'fk_id_servers': server_id_db})
            query = sqlHelper.select(
                table=tablesBM.RUST_SERVERS,
                columns=['is_pve', 'official', 'description', 'modded', 'gamemode',
                        'steam_id', 'next_wipe_date', 'next_wipe_type', 'last_wipe_date',
                        'rust_url', 'map_url', 'thumbnail_url', 'queued_players'],
                where=where_sql
            )
            
            self.__db_cur.execute(query, where_params)
            rust_row = self.__db_cur.fetchone()
            
            # Собираем данные
            data = {
                'name': base_info['server_name'],
                'players': base_info['players_online'],
                'maxPlayers': base_info['players_max'],
                'status': self._normalize_status(base_info.get('status', 'unknown')),
                'private': base_info['private'],
                'country': base_info['country'],
                'rank': base_info['rank']
            }
            
            if rust_row:
                # Добавляем Rust-специфичные поля
                data.update({
                    'rust_pve': rust_row['is_pve'],
                    'rust_official': rust_row['official'],
                    'rust_description': rust_row['description'],
                    'rust_modded': rust_row['modded'],
                    'rust_gamemode': rust_row['gamemode'],
                    'serverSteamId': rust_row['steam_id'],
                    'rust_next_wipe': rust_row['next_wipe_date'].isoformat() if rust_row['next_wipe_date'] else None,
                    'rust_next_wipe_type': rust_row['next_wipe_type'],
                    'rust_last_wipe': rust_row['last_wipe_date'].isoformat() if rust_row['last_wipe_date'] else None,
                    'rust_url': rust_row['rust_url'],
                    'rust_map_url': rust_row['map_url'],
                    'rust_thumbnail_url': rust_row['thumbnail_url'],
                    'rust_queued_players': rust_row['queued_players']
                })
            
            return RustServer(
                id=self._convert_id_from_db(base_info['id_server'], 'id_server'),
                data=data,
                game_id='rust'
            )
            
        except Exception as e:
            self._logger.error(f"Ошибка при загрузке информации о Rust сервере {server_id}: {e}")
            return None
    
    def _load_player_info(self, player_id: Any) -> Optional[Player]:
        """Загружает информацию об игроке из БД"""
        try:
            player_id_db = self._convert_id_for_db(player_id, 'id_players')
            
            where_sql, where_params = sqlHelper.where_params({'id_players': player_id_db})
            query = sqlHelper.select(
                table=tablesBM.PLAYERS,
                columns=['id_players', 'nickname', 'private', 'positive_match', 
                        'created_at', 'updated_at', 'last_seen'],
                where=where_sql
            )
            
            self.__db_cur.execute(query, where_params)
            row = self.__db_cur.fetchone()
            
            if not row:
                return None
            
            data = {
                'name': row['nickname'],
                'private': row['private'],
                'positiveMatch': row['positive_match'],
                'createdAt': row['created_at'].isoformat() if row['created_at'] else None,
                'updatedAt': row['updated_at'].isoformat() if row['updated_at'] else None,
                'lastSeen': row['last_seen'].isoformat() if row['last_seen'] else None
            }
            
            return Player(
                id=self._convert_id_from_db(row['id_players'], 'id_players'),
                data=data
            )
            
        except Exception as e:
            self._logger.error(f"Ошибка при загрузке информации об игроке {player_id}: {e}")
            return None
    
    def add_server_to_profile(self, profile_id: Union[str, int], server_id: Union[str, int], server_name: str = None) -> bool:
        """Добавляет сервер к профилю пользователя"""
        try:
            pid = self._normalize_profile_id(profile_id)
            profile_id_db = self._convert_id_for_db(pid, 'id_profile')
            server_id_db = self._convert_id_for_db(server_id, 'id_server')
            
            # 1. Проверяем существование сервера в БД
            if not self.check_server_exists(server_id):
                # Добавляем сервер в БД
                self._ensure_server_exists(server_id_db, server_name)
            
            # 2. Добавляем подписку
            subscription_data = {
                'fk_id_profile': profile_id_db,
                'entity_type': 'server',
                'entity_id': server_id_db,
                'is_active': True,
                'notification_types': json.dumps({'all': True})  # Все уведомления по умолчанию
            }
            
            query, params = sqlHelper.insert(
                table=tablesBM.SUBSCRIPTIONS,
                data=subscription_data
            )
            
            # Добавляем обработку дубликатов
            query += " ON DUPLICATE KEY UPDATE is_active = VALUES(is_active)"
            
            self._add_to_queue('execute', query, params)
            self._add_to_queue('commit')
            self._process_write_queue()
            
            profile = self._profiles.get(pid)
            if profile:
                server = self._load_server_info(server_id_db)
                if server:
                    profile.add_server(server)
                    if pid in self._profile_cache_ttl:
                        del self._profile_cache_ttl[pid]
            self._logger.info(f"Сервер {server_id} добавлен к профилю {pid}")
            return True
            
        except Exception as e:
            self._logger.error(f"Ошибка при добавлении сервера {server_id} к профилю {profile_id}: {e}")
            return False
    
    def add_player_to_profile(self, profile_id: Union[str, int], player_id: Union[str, int], player_name: str = None) -> bool:
        """Добавляет игрока к профилю пользователя"""
        try:
            pid = self._normalize_profile_id(profile_id)
            profile_id_db = self._convert_id_for_db(pid, 'id_profile')
            player_id_db = self._convert_id_for_db(player_id, 'id_players')
            
            # 1. Проверяем существование игрока в БД
            if not self.check_player_exists(player_id):
                # Добавляем игрока в БД
                self._ensure_player_exists(player_id_db, player_name)
            
            # 2. Добавляем подписку
            subscription_data = {
                'fk_id_profile': profile_id_db,
                'entity_type': 'player',
                'entity_id': player_id_db,
                'is_active': True,
                'notification_types': json.dumps({'all': True})
            }
            
            query, params = sqlHelper.insert(
                table=tablesBM.SUBSCRIPTIONS,
                data=subscription_data
            )
            
            query += " ON DUPLICATE KEY UPDATE is_active = VALUES(is_active)"
            
            self._add_to_queue('execute', query, params)
            self._add_to_queue('commit')
            self._process_write_queue()
            
            profile = self._profiles.get(pid)
            if profile:
                player = self._load_player_info(player_id_db)
                if player:
                    profile.add_player(player)
                    if pid in self._profile_cache_ttl:
                        del self._profile_cache_ttl[pid]
            self._logger.info(f"Игрок {player_id} добавлен к профилю {pid}")
            return True
            
        except Exception as e:
            self._logger.error(f"Ошибка при добавлении игрока {player_id} к профилю {profile_id}: {e}")
            return False
    
    def remove_server_from_profile(self, profile_id: Union[str, int], server_id: Union[str, int]) -> bool:
        """Удаляет сервер из профиля пользователя"""
        try:
            pid = self._normalize_profile_id(profile_id)
            profile_id_db = self._convert_id_for_db(pid, 'id_profile')
            server_id_db = self._convert_id_for_db(server_id, 'id_server')
            
            # Деактивируем подписку (мягкое удаление)
            data = {'is_active': False}
            where_conditions = {
                'fk_id_profile': profile_id_db,
                'entity_type': 'server',
                'entity_id': server_id_db
            }
            
            query, params = sqlHelper.update(
                table=tablesBM.SUBSCRIPTIONS,
                set_values=data,
                where_conditions=where_conditions
            )
            
            self._add_to_queue('execute', query, params)
            self._add_to_queue('commit')
            self._process_write_queue()
            
            profile = self._profiles.get(pid)
            if profile:
                sid = self._convert_id_from_db(server_id_db, 'id_server')
                if sid in profile._servers:
                    del profile._servers[sid]
            self._logger.info(f"Сервер {server_id} удален из профиля {pid}")
            return True
            
        except Exception as e:
            self._logger.error(f"Ошибка при удалении сервера {server_id} из профиля {pid}: {e}")
            return False

    def remove_player_from_profile(self, profile_id: Union[str, int], player_id: Union[str, int]) -> bool:
        """Удаляет игрока из профиля пользователя"""
        try:
            pid = self._normalize_profile_id(profile_id)
            profile_id_db = self._convert_id_for_db(pid, 'id_profile')
            player_id_db = self._convert_id_for_db(player_id, 'id_players')
            
            # Деактивируем подписку
            data = {'is_active': False}
            where_conditions = {
                'fk_id_profile': profile_id_db,
                'entity_type': 'player',
                'entity_id': player_id_db
            }
            
            query, params = sqlHelper.update(
                table=tablesBM.SUBSCRIPTIONS,
                set_values=data,
                where_conditions=where_conditions
            )
            
            self._add_to_queue('execute', query, params)
            self._add_to_queue('commit')
            self._process_write_queue()
            
            profile = self._profiles.get(pid)
            if profile:
                plid = self._convert_id_from_db(player_id_db, 'id_players')
                if plid in profile._players:
                    del profile._players[plid]
            self._logger.info(f"Игрок {player_id} удален из профиля {pid}")
            return True
            
        except Exception as e:
            self._logger.error(f"Ошибка при удалении игрока {player_id} из профиля {pid}: {e}")
            return False

    # --- Серверы ---
    
    def _ensure_server_exists(self, server_id: Any, server_name: str = None) -> bool:
        """Обеспечивает существование сервера в БД"""
        try:
            server_id_db = self._convert_id_for_db(server_id, 'id_server')
            
            # Проверяем существование
            where_sql, where_params = sqlHelper.where_params({'id_server': server_id_db})
            query = sqlHelper.select(
                table=tablesBM.SERVERS,
                columns=['id_server'],
                where=where_sql
            )
            
            self.__db_cur.execute(query, where_params)
            if self.__db_cur.fetchone():
                return True
            
            # Создаем сервер
            server_data = {
                'id_server': server_id_db,
                'fk_games_id': 1,  # rust по умолчанию
                'server_name': server_name or f"Server {server_id_db}",
                'players_online': 0,
                'players_max': 0,
                'status': self._normalize_status('unknown'),
                'private': False
            }
            
            query, params = sqlHelper.insert(table=tablesBM.SERVERS, data=server_data)
            self._add_to_queue('execute', query, params)
            self._add_to_queue('commit')
            self._process_write_queue()
            
            return True
            
        except Exception as e:
            self._logger.error(f"Ошибка при создании сервера {server_id}: {e}")
            return False
    
    def check_server_exists(self, server_id: Union[str, int]) -> bool:
        """Проверяет существование сервера в БД"""
        self._ensure_db_connection()
        try:
            server_id_db = self._convert_id_for_db(server_id, 'id_server')
            
            where_sql, where_params = sqlHelper.where_params({'id_server': server_id_db})
            query = sqlHelper.select(
                table=tablesBM.SERVERS,
                columns=['id_server'],
                where=where_sql
            )
            
            self.__db_cur.execute(query, where_params)
            return self.__db_cur.fetchone() is not None
            
        except Exception as e:
            self._logger.error(f"Ошибка при проверке существования сервера {server_id}: {e}")
            return False
    
    def get_servers(self) -> Dict[str, int]:
        """Получает список всех серверов из БД"""
        self._ensure_db_connection()
        try:
            query = sqlHelper.select(
                table=tablesBM.SERVERS,
                columns=['server_name', 'id_server']
            )
            
            self.__db_cur.execute(query)
            rows = self.__db_cur.fetchall()
            
            result = {}
            for row in rows:
                server_id = self._convert_id_from_db(row['id_server'], 'id_server')
                result[row['server_name']] = server_id
            return result
            
        except Exception as e:
            self._logger.error(f"Ошибка при получении списка серверов: {e}")
            return {}
    
    def get_all_server_ids(self) -> List[int]:
        """Получает список всех ID серверов из БД"""
        self._ensure_db_connection()
        try:
            query = sqlHelper.select(
                table=tablesBM.SERVERS,
                columns=['id_server']
            )
            
            self.__db_cur.execute(query)
            rows = self.__db_cur.fetchall()
            
            result = []
            for row in rows:
                server_id = self._convert_id_from_db(row['id_server'], 'id_server')
                result.append(int(server_id))
            return result
            
        except Exception as e:
            self._logger.error(f"Ошибка при получении списка ID серверов: {e}")
            return []
    
    def get_servers_for_active_profiles(self, active_profile_ids: List[str]) -> Dict[str, int]:
        """Получает список серверов только для активных профилей"""
        if not active_profile_ids:
            return {}
        
        self._ensure_db_connection()
        try:
            # Конвертируем ID профилей
            profile_ids_db = [self._convert_id_for_db(pid, 'id_profile') for pid in active_profile_ids]
            
            # Используем WHERE IN через параметризованный запрос
            placeholders = ','.join(['%s'] * len(profile_ids_db))
            
            query = f"""
                SELECT DISTINCT s.server_name, s.id_server
                FROM `{tablesBM.SUBSCRIPTIONS}` sub
                INNER JOIN `{tablesBM.SERVERS}` s ON sub.entity_id = s.id_server
                INNER JOIN `{tablesBM.PROFILES}` p ON sub.fk_id_profile = p.id_profile
                WHERE sub.fk_id_profile IN ({placeholders}) 
                AND sub.entity_type = 'server'
                AND sub.is_active = 1
                AND p.is_active = 1
            """
            
            self.__db_cur.execute(query, profile_ids_db)
            rows = self.__db_cur.fetchall()
            
            result = {}
            for row in rows:
                server_id = self._convert_id_from_db(row['id_server'], 'id_server')
                result[row['server_name']] = server_id
            return result
            
        except Exception as e:
            self._logger.error(f"Ошибка при получении серверов для активных профилей: {e}")
            return {}
    
    def search_servers_by_name(self, name_pattern: str, game_id: str = 'rust', limit: int = 10) -> List[Tuple[int, str]]:
        """Ищет серверы по названию"""
        self._ensure_db_connection()
        try:
            # Получаем game_id
            where_sql, where_params = sqlHelper.where_params({'game_name': game_id})
            game_query = sqlHelper.select(
                table=tablesBM.GAMES,
                columns=['id_game'],
                where=where_sql
            )
            
            self.__db_cur.execute(game_query, where_params)
            game_row = self.__db_cur.fetchone()
            if not game_row:
                return []
            
            game_id_int = game_row['id_game']
            
            # Ищем серверы
            query = f"""
                SELECT `id_server`, `server_name`
                FROM `{tablesBM.SERVERS}`
                WHERE `fk_games_id` = %s AND `server_name` LIKE %s
                LIMIT %s
            """
            
            like_pattern = f'%{name_pattern}%'
            self.__db_cur.execute(query, (game_id_int, like_pattern, limit))
            rows = self.__db_cur.fetchall()
            
            return [(self._convert_id_from_db(row['id_server'], 'id_server'), row['server_name']) 
                    for row in rows]
            
        except Exception as e:
            self._logger.error(f"Ошибка при поиске серверов: {e}")
            return []
    
    # --- Игроки ---
    
    def _ensure_player_exists(self, player_id: Any, player_name: str = None) -> bool:
        """Обеспечивает существование игрока в БД"""
        try:
            player_id_db = self._convert_id_for_db(player_id, 'id_players')
            
            # Проверяем существование
            where_sql, where_params = sqlHelper.where_params({'id_players': player_id_db})
            query = sqlHelper.select(
                table=tablesBM.PLAYERS,
                columns=['id_players'],
                where=where_sql
            )
            
            self.__db_cur.execute(query, where_params)
            if self.__db_cur.fetchone():
                return True
            
            # Создаем игрока
            player_data = {
                'id_players': player_id_db,
                'nickname': player_name or f"Player {player_id_db}",
                'private': False,
                'positive_match': False
            }
            
            query, params = sqlHelper.insert(table=tablesBM.PLAYERS, data=player_data)
            self._add_to_queue('execute', query, params)
            self._add_to_queue('commit')
            self._process_write_queue()
            
            return True
            
        except Exception as e:
            self._logger.error(f"Ошибка при создании игрока {player_id}: {e}")
            return False
    
    def check_player_exists(self, player_id: Union[str, int]) -> bool:
        """Проверяет существование игрока в БД"""
        self._ensure_db_connection()
        try:
            player_id_db = self._convert_id_for_db(player_id, 'id_players')
            
            where_sql, where_params = sqlHelper.where_params({'id_players': player_id_db})
            query = sqlHelper.select(
                table=tablesBM.PLAYERS,
                columns=['id_players'],
                where=where_sql
            )
            
            self.__db_cur.execute(query, where_params)
            return self.__db_cur.fetchone() is not None
            
        except Exception as e:
            self._logger.error(f"Ошибка при проверке существования игрока {player_id}: {e}")
            return False
    
    def get_players(self) -> Dict[str, int]:
        """Получает список всех игроков из БД"""
        self._ensure_db_connection()
        try:
            query = sqlHelper.select(
                table=tablesBM.PLAYERS,
                columns=['nickname', 'id_players']
            )
            
            self.__db_cur.execute(query)
            rows = self.__db_cur.fetchall()
            
            result = {}
            for row in rows:
                player_id = self._convert_id_from_db(row['id_players'], 'id_players')
                result[row['nickname']] = player_id
            return result
            
        except Exception as e:
            self._logger.error(f"Ошибка при получении списка игроков: {e}")
            return {}
    
    def get_players_for_active_profiles(self, active_profile_ids: List[str]) -> List[int]:
        """Получает список ID игроков для активных профилей"""
        if not active_profile_ids:
            return []
        
        self._ensure_db_connection()
        try:
            profile_ids_db = [self._convert_id_for_db(pid, 'id_profile') for pid in active_profile_ids]
            
            placeholders = ','.join(['%s'] * len(profile_ids_db))
            
            query = f"""
                SELECT DISTINCT sub.entity_id
                FROM `{tablesBM.SUBSCRIPTIONS}` sub
                INNER JOIN `{tablesBM.PROFILES}` p ON sub.fk_id_profile = p.id_profile
                WHERE sub.fk_id_profile IN ({placeholders}) 
                AND sub.entity_type = 'player'
                AND sub.is_active = 1
                AND p.is_active = 1
            """
            
            self.__db_cur.execute(query, profile_ids_db)
            rows = self.__db_cur.fetchall()
            
            return [self._convert_id_from_db(row['entity_id'], 'entity_id') for row in rows]
            
        except Exception as e:
            self._logger.error(f"Ошибка при получении игроков для активных профилей: {e}")
            return []
    
    def search_players_by_name(self, name_pattern: str, limit: int = 10) -> List[Tuple[int, str]]:
        """Ищет игроков по имени"""
        self._ensure_db_connection()
        try:
            query = f"""
                SELECT `id_players`, `nickname`
                FROM `{tablesBM.PLAYERS}`
                WHERE `nickname` LIKE %s
                LIMIT %s
            """
            
            like_pattern = f'%{name_pattern}%'
            self.__db_cur.execute(query, (like_pattern, limit))
            rows = self.__db_cur.fetchall()
            
            return [(self._convert_id_from_db(row['id_players'], 'id_players'), row['nickname']) 
                    for row in rows]
            
        except Exception as e:
            self._logger.error(f"Ошибка при поиске игроков: {e}")
            return []
    
    # --- Фильтры ---
    
    def _load_profile_filters(self, profile_id: Any, profile: Profile) -> None:
        """Загружает фильтры профиля из БД"""
        try:
            profile_id_db = self._convert_id_for_db(profile_id, 'id_profile')
            
            # Загружаем фильтры серверов
            self._load_server_filters(profile_id_db, profile)
            
            # Загружаем фильтры игроков
            self._load_player_filters(profile_id_db, profile)
            
        except Exception as e:
            self._logger.error(f"Ошибка при загрузке фильтров профиля {profile_id}: {e}")
    
    def _load_server_filters(self, profile_id: Any, profile: Profile) -> None:
        """Загружает фильтры серверов из БД"""
        try:
            profile_id_db = self._convert_id_for_db(profile_id, 'id_profile')
            
            # Получаем server_filters
            where_sql, where_params = sqlHelper.where_params({'fk_id_profile': profile_id_db})
            query = sqlHelper.select(
                table=tablesBM.SERVER_FILTERS,
                columns=['id_filter', 'player_count_min', 'player_count_max', 
                        'check_status', 'check_ip_port', 'check_private',
                        'apply_to_all', 'specific_server_id', 'created_at'],
                where=where_sql
            )
            
            self.__db_cur.execute(query, where_params)
            server_filter_rows = self.__db_cur.fetchall()
            
            for row in server_filter_rows:
                # Создаем базовый фильтр
                from src.filters import ServerFilter
                server_filter = ServerFilter()
                
                # Заполняем поля
                server_filter.players_check = row['player_count_min'] if row['player_count_min'] is not None else -1
                server_filter.max_player_check = row['player_count_max'] if row['player_count_max'] is not None else -1
                server_filter.status_check = bool(row['check_status']) if row['check_status'] is not None else False
                server_filter.ip_port_check = bool(row['check_ip_port']) if row['check_ip_port'] is not None else False
                server_filter.private_check = bool(row['check_private']) if row['check_private'] is not None else False
                
                # Если есть specific_server_id, применяем только к этому серверу
                if row['specific_server_id']:
                    server_filter._specific_server_id = self._convert_id_from_db(
                        row['specific_server_id'], 'id_server'
                    )
                
                # Проверяем, является ли это Rust-фильтром
                if row['id_filter']:
                    rust_filter = self._load_rust_server_filter(row['id_filter'])
                    if rust_filter:
                        # Это Rust-фильтр
                        rust_filter.players_check = server_filter.players_check
                        rust_filter.max_player_check = server_filter.max_player_check
                        rust_filter.status_check = server_filter.status_check
                        rust_filter.ip_port_check = server_filter.ip_port_check
                        rust_filter.private_check = server_filter.private_check
                        profile.add_filter(rust_filter)
                    else:
                        # Обычный server_filter
                        profile.add_filter(server_filter)
                        
        except Exception as e:
            self._logger.error(f"Ошибка при загрузке фильтров серверов: {e}")
    
    def _load_rust_server_filter(self, server_filter_id: Any) -> Optional[RustFilter]:
        """Загружает Rust-специфичные параметры фильтра"""
        try:
            server_filter_id_db = self._convert_id_for_db(server_filter_id, 'id_filter')
            
            where_sql, where_params = sqlHelper.where_params({'fk_server_filters_id': server_filter_id_db})
            query = sqlHelper.select(
                table=tablesBM.RUST_SERVERS_FILTERS,
                columns=['queued_players_min', 'check_last_wipe', 'check_next_wipe',
                        'check_pve', 'check_url', 'check_map_url', 'check_map_image'],
                where=where_sql
            )
            
            self.__db_cur.execute(query, where_params)
            rust_row = self.__db_cur.fetchone()
            
            if rust_row:
                from src.filters import RustFilter
                rust_filter = RustFilter()
                
                rust_filter.queued_players_check = rust_row['queued_players_min'] if rust_row['queued_players_min'] is not None else -1
                rust_filter.last_wipe_check = bool(rust_row['check_last_wipe']) if rust_row['check_last_wipe'] is not None else False
                rust_filter.next_wipe_check = bool(rust_row['check_next_wipe']) if rust_row['check_next_wipe'] is not None else False
                rust_filter.pve_check = bool(rust_row['check_pve']) if rust_row['check_pve'] is not None else False
                rust_filter.url_check = bool(rust_row['check_url']) if rust_row['check_url'] is not None else False
                rust_filter.map_url_check = bool(rust_row['check_map_url']) if rust_row['check_map_url'] is not None else False
                rust_filter.map_thumbnailUrl_check = bool(rust_row['check_map_image']) if rust_row['check_map_image'] is not None else False
                
                return rust_filter
            
            return None
            
        except Exception as e:
            self._logger.error(f"Ошибка при загрузке Rust-фильтра {server_filter_id}: {e}")
            return None
    
    def _load_player_filters(self, profile_id: Any, profile: Profile) -> None:
        """Загружает фильтры игроков из БД"""
        try:
            profile_id_db = self._convert_id_for_db(profile_id, 'id_profile')
            
            where_sql, where_params = sqlHelper.where_params({'fk_id_profile': profile_id_db})
            query = sqlHelper.select(
                table=tablesBM.PLAYER_FILTERS,
                columns=['player_name_changed', 'player_private_changed',
                        'check_online_status', 'check_server_change',
                        'apply_to_all', 'specific_player_id'],
                where=where_sql
            )
            
            self.__db_cur.execute(query, where_params)
            player_filter_rows = self.__db_cur.fetchall()
            
            for row in player_filter_rows:
                from src.filters import PlayerFilter
                player_filter = PlayerFilter()
                
                player_filter.player_name_check = bool(row['player_name_changed']) if row['player_name_changed'] is not None else False
                player_filter.player_private_check = bool(row['player_private_changed']) if row['player_private_changed'] is not None else False
                player_filter.online_check = bool(row['check_online_status']) if row['check_online_status'] is not None else False
                player_filter.server_change_check = bool(row['check_server_change']) if row['check_server_change'] is not None else False
                
                # Если есть specific_player_id, применяем только к этому игроку
                if row['specific_player_id']:
                    player_filter._specific_player_id = self._convert_id_from_db(
                        row['specific_player_id'], 'id_players'
                    )
                
                profile.add_filter(player_filter)
                
        except Exception as e:
            self._logger.error(f"Ошибка при загрузке фильтров игроков: {e}")
    
    def add_profile_filter(self, profile_id: str, filter_obj: Filter, 
                          game_id: str = 'rust', server_id: str = '0') -> None:
        """Добавляет фильтр пользователя"""
        self._ensure_db_connection()
        try:
            profile_id_db = self._convert_id_for_db(profile_id, 'id_profile')
            
            if isinstance(filter_obj, RustFilter):
                self._add_server_filter(profile_id_db, filter_obj)
            elif isinstance(filter_obj, PlayerFilter):
                self._add_player_filter(profile_id_db, filter_obj)
            
            # Добавляем фильтр в профиль в памяти
            profile = self._profiles.get(profile_id)
            if profile:
                profile.add_filter(filter_obj)
                
        except Exception as e:
            self._logger.error(f"Ошибка при добавлении фильтра для профиля {profile_id}: {e}")
    
    def _add_server_filter(self, profile_id: Any, rust_filter: RustFilter) -> None:
        """Добавляет фильтр серверов"""
        try:
            # Создаем или обновляем server_filter
            server_filter_data = {
                'fk_id_profile': profile_id,
                'player_count_min': rust_filter.players_check if rust_filter.players_check != -1 else None,
                'player_count_max': rust_filter.max_player_check if rust_filter.max_player_check != -1 else None,
                'check_status': rust_filter.status_check,
                'check_ip_port': rust_filter.ip_port_check,
                'check_private': rust_filter.private_check,
                'apply_to_all': True  # По умолчанию применяем ко всем
            }
            
            # Проверяем существование
            where_sql, where_params = sqlHelper.where_params({'fk_id_profile': profile_id})
            check_query = sqlHelper.select(
                table=tablesBM.SERVER_FILTERS,
                columns=['id_filter'],
                where=where_sql
            )
            
            self.__db_cur.execute(check_query, where_params)
            existing = self.__db_cur.fetchone()
            
            if existing:
                # Обновляем существующий
                server_filter_id = existing['id_filter']
                where_conditions = {'id_filter': server_filter_id}
                query, params = sqlHelper.update(
                    table=tablesBM.SERVER_FILTERS,
                    set_values=server_filter_data,
                    where_conditions=where_conditions
                )
            else:
                # Создаем новый
                query, params = sqlHelper.insert(table=tablesBM.SERVER_FILTERS, data=server_filter_data)
            
            self.__db_cur.execute(query, params)
            
            # Получаем ID созданного/обновленного фильтра
            if not existing:
                server_filter_id = self.__db_cur.lastrowid
            else:
                server_filter_id = existing['id_filter']
            
            # Добавляем/обновляем rust_servers_filter
            self._add_or_update_rust_server_filter(server_filter_id, rust_filter)
            
            self.__db_con.commit()
            
        except Exception as e:
            self._logger.error(f"Ошибка при добавлении фильтра серверов: {e}")
            try:
                self.__db_con.rollback()
            except:
                pass
    
    def _add_or_update_rust_server_filter(self, server_filter_id: Any, rust_filter: RustFilter) -> None:
        """Добавляет или обновляет Rust-фильтр, используя to_db_dict() объекта."""
        try:
            # Получаем данные из объекта фильтра
            _, rust_filter_data = rust_filter.to_db_dict(0, server_filter_id)
            # Проверяем существование
            check_query = "SELECT id_filter FROM rust_servers_filters WHERE fk_server_filters_id = %s"
            self.__db_cur.execute(check_query, (server_filter_id,))
            existing = self.__db_cur.fetchone()
    
            if existing:
                # Обновляем
                update_query, params = sqlHelper.update(
                    table=tablesBM.RUST_SERVERS_FILTERS,
                    set_values=rust_filter_data,
                    where_conditions={'id_filter': existing['id_filter']}
                )
            else:
                # Вставляем
                insert_query, params = sqlHelper.insert(
                    table=tablesBM.RUST_SERVERS_FILTERS,
                    data=rust_filter_data
                )
            self.__db_cur.execute(update_query if existing else insert_query, params)
        except Exception as e:
            self._logger.error(f"Ошибка с Rust-фильтром: {e}")
            raise
    
    def _add_player_filter(self, profile_id: Any, player_filter: PlayerFilter) -> None:
        """Добавляет фильтр игроков"""
        try:
            player_filter_data = {
                'fk_id_profile': profile_id,
                'player_name_changed': player_filter.player_name_check,
                'player_private_changed': player_filter.player_private_check,
                'check_online_status': player_filter.online_check,
                'check_server_change': player_filter.server_change_check,
                'apply_to_all': True
            }
            
            # Проверяем существование
            where_sql, where_params = sqlHelper.where_params({'fk_id_profile': profile_id})
            check_query = sqlHelper.select(
                table=tablesBM.PLAYER_FILTERS,
                columns=['id_player_filter'],
                where=where_sql
            )
            
            self.__db_cur.execute(check_query, where_params)
            existing = self.__db_cur.fetchone()
            
            if existing:
                # Обновляем
                where_conditions = {'id_player_filter': existing['id_player_filter']}
                query, params = sqlHelper.update(
                    table=tablesBM.PLAYER_FILTERS,
                    set_values=player_filter_data,
                    where_conditions=where_conditions
                )
            else:
                # Создаем
                query, params = sqlHelper.insert(table=tablesBM.PLAYER_FILTERS, data=player_filter_data)
            
            self.__db_cur.execute(query, params)
            self.__db_con.commit()
            
        except Exception as e:
            self._logger.error(f"Ошибка при добавлении фильтра игроков: {e}")
            try:
                self.__db_con.rollback()
            except:
                pass
    
    # --- Массовые операции ---
    
    def bulk_insert_servers(self, servers: List[Dict], game_name: str = 'rust') -> int:
        """Массовое добавление серверов в БД"""
        if not servers:
            return 0
        with self._db_lock:
            return self._bulk_insert_servers_impl(servers, game_name)
    
    def _bulk_insert_servers_impl(self, servers: List[Dict], game_name: str) -> int:
        self._ensure_db_connection()
        try:
            # Получаем game_id
            where_sql, where_params = sqlHelper.where_params({'game_name': game_name})
            game_query = sqlHelper.select(
                table=tablesBM.GAMES,
                columns=['id_game'],
                where=where_sql
            )
            
            self.__db_cur.execute(game_query, where_params)
            game_row = self.__db_cur.fetchone()
            
            if not game_row:
                # Создаем игру
                game_data = {'game_name': game_name}
                query, params = sqlHelper.insert(table=tablesBM.GAMES, data=game_data)
                self.__db_cur.execute(query, params)
                self.__db_con.commit()
                game_id = self.__db_cur.lastrowid
            else:
                game_id = game_row['id_game']
            
            # Подготавливаем данные
            batch_data = []
            for server in servers:
                server_id = server.get('id', '')
                if not server_id:
                    continue
                
                server_data = {
                    'id_server': self._convert_id_for_db(server_id, 'id_server'),
                    'fk_games_id': game_id,
                    'server_name': server.get('name', f"Server {server_id}"),
                    'rank': server.get('rank'),
                    'private': server.get('private', False),
                    'country': server.get('country', ''),
                    'players_online': server.get('players', 0),
                    'players_max': server.get('maxPlayers', 0),
                    'status': self._normalize_status(server.get('status', 'unknown'))
                }
                batch_data.append(server_data)
            
            if not batch_data:
                return 0
            
            # Используем batch insert
            columns = ['id_server', 'fk_games_id', 'server_name', 'rank', 'private', 
                      'country', 'players_online', 'players_max', 'status']
            
            values_list = []
            for item in batch_data:
                values = []
                for col in columns:
                    value = item.get(col)
                    if value is None:
                        values.append(None)
                    else:
                        values.append(value)
                values_list.append(values)
            
            query, params = sqlHelper.insert_many(
                table=tablesBM.SERVERS,
                columns=columns,
                values_list=values_list
            )
            
            # Добавляем ON DUPLICATE KEY UPDATE
            update_columns = [col for col in columns if col != 'id_server']
            update_parts = [f"`{col}` = VALUES(`{col}`)" for col in update_columns]
            query += " ON DUPLICATE KEY UPDATE " + ", ".join(update_parts)
            
            self.__db_cur.execute(query, params)
            self.__db_con.commit()
            
            added_count = len(batch_data)
            self._logger.info(f"Добавлено {added_count} серверов в БД")
            return added_count
        except Exception as e:
            self._logger.error(f"Ошибка при массовом добавлении серверов: {e}")
            try:
                self.__db_con.rollback()
            except Exception:
                pass
            return 0
    
    def bulk_insert_players(self, players: List[Dict]) -> int:
        """Массовое добавление игроков в БД"""
        if not players:
            return 0
        with self._db_lock:
            self._ensure_db_connection()
            try:
                batch_data = []
                for player in players:
                    player_id = player.get('id', '')
                    if not player_id:
                        continue
                    player_data = {
                        'id_players': self._convert_id_for_db(player_id, 'id_players'),
                        'nickname': player.get('name', f"Player {player_id}"),
                        'positive_match': player.get('positiveMatch', False),
                        'private': player.get('private', False),
                        'last_seen': player.get('lastSeen')
                    }
                    batch_data.append(player_data)
                if not batch_data:
                    return 0
                columns = ['id_players', 'nickname', 'positive_match', 'private', 'last_seen']
                values_list = []
                for item in batch_data:
                    values = []
                    for col in columns:
                        value = item.get(col)
                        if value is None:
                            values.append(None)
                        else:
                            values.append(value)
                    values_list.append(values)
                query, params = sqlHelper.insert_many(
                    table=tablesBM.PLAYERS,
                    columns=columns,
                    values_list=values_list
                )
                update_columns = [col for col in columns if col != 'id_players']
                update_parts = [f"`{col}` = VALUES(`{col}`)" for col in update_columns]
                query += " ON DUPLICATE KEY UPDATE " + ", ".join(update_parts)
                self.__db_cur.execute(query, params)
                self.__db_con.commit()
                added_count = len(batch_data)
                self._logger.info(f"Добавлено {added_count} игроков в БД")
                return added_count
            except Exception as e:
                self._logger.error(f"Ошибка при массовом добавлении игроков: {e}")
                try:
                    self.__db_con.rollback()
                except Exception:
                    pass
                return 0
    
    def bulk_insert_rust_servers(self, servers: List[RustServer]) -> int:
        """Массовое добавление Rust серверов в БД"""
        if not servers:
            return 0
        with self._db_lock:
            return self._bulk_insert_rust_servers_impl(servers)
    
    def _bulk_insert_rust_servers_impl(self, servers: List[RustServer]) -> int:
        self._ensure_db_connection()
        try:
            batch_data = []
            for server in servers:
                if not isinstance(server, RustServer):
                    continue
                
                # Проверяем существование базового сервера
                if not self.check_server_exists(server.id):
                    continue
                
                rust_data = {
                    'fk_id_servers': self._convert_id_for_db(server.id, 'id_server'),
                    'is_pve': server.is_pve,
                    'official': server.official,
                    'description': server.description,
                    'modded': server.modded,
                    'gamemode': server.gamemode,
                    'steam_id': server.steam_id,
                    'next_wipe_date': server.next_wipe_date,
                    'next_wipe_type': server.next_wipe_type,
                    'last_wipe_date': server.last_wipe_date,
                    'rust_url': server.rust_url,
                    'map_url': server.map_url,
                    'thumbnail_url': server.thumbnail_url,
                    'queued_players': server.queued_players
                }
                batch_data.append(rust_data)
            
            if not batch_data:
                return 0
            
            # Используем batch insert
            columns = ['fk_id_servers', 'is_pve', 'official', 'description', 'modded',
                      'gamemode', 'steam_id', 'next_wipe_date', 'next_wipe_type',
                      'last_wipe_date', 'rust_url', 'map_url', 'thumbnail_url', 'queued_players']
            
            values_list = []
            for item in batch_data:
                values = []
                for col in columns:
                    value = item.get(col)
                    if value is None:
                        values.append(None)
                    else:
                        values.append(value)
                values_list.append(values)
            
            query, params = sqlHelper.insert_many(
                table=tablesBM.RUST_SERVERS,
                columns=columns,
                values_list=values_list
            )
            
            update_columns = [col for col in columns if col != 'fk_id_servers']
            update_parts = [f"`{col}` = VALUES(`{col}`)" for col in update_columns]
            query += " ON DUPLICATE KEY UPDATE " + ", ".join(update_parts)
            
            self.__db_cur.execute(query, params)
            self.__db_con.commit()
            
            added_count = len(batch_data)
            self._logger.info(f"Добавлено {added_count} Rust серверов в БД")
            return added_count
            
        except Exception as e:
            self._logger.error(f"Ошибка при массовом добавлении Rust серверов: {e}")
            try:
                self.__db_con.rollback()
            except:
                pass
            return 0
    
    # --- Обновление информации ---
    
    def update_server_info(self, server: Server) -> bool:
        """Обновляет информацию о сервере в БД"""
        if not isinstance(server, Server):
            return False
        with self._db_lock:
            return self._update_server_info_impl(server)
    
    def _update_server_info_impl(self, server: Server) -> bool:
        self._ensure_db_connection()
        try:
            server_id_db = self._convert_id_for_db(server.id, 'id_server')
            
            data = {
                'server_name': server.name,
                'players_online': server._players,
                'players_max': server._max_players,
                'status': self._normalize_status(server._status),
                'private': server._private,
                'country': server._country,
                'rank': server._rank,
                'last_updated': datetime.now()
            }
            
            where_conditions = {'id_server': server_id_db}
            query, params = sqlHelper.update(
                table=tablesBM.SERVERS,
                set_values=data,
                where_conditions=where_conditions
            )
            
            self.__db_cur.execute(query, params)
            self.__db_con.commit()
            
            # Если это Rust сервер, обновляем и rust_servers
            if isinstance(server, RustServer):
                self._update_rust_server_info_impl(server)
            
            # Добавляем запись в историю
            self._add_server_history(server)
            
            return True
            
        except Exception as e:
            self._logger.error(f"Ошибка при обновлении сервера {server.id}: {e}")
            try:
                self.__db_con.rollback()
            except:
                pass
            return False
    
    def update_rust_server_info(self, server: RustServer) -> bool:
        """Обновляет информацию о Rust сервере в БД"""
        if not isinstance(server, RustServer):
            return False
        with self._db_lock:
            return self._update_rust_server_info_impl(server)
    
    def _update_rust_server_info_impl(self, server: RustServer) -> bool:
        self._ensure_db_connection()
        try:
            server_id_db = self._convert_id_for_db(server.id, 'id_server')
            
            data = {
                'is_pve': server.is_pve,
                'official': server.official,
                'description': server.description,
                'modded': server.modded,
                'gamemode': server.gamemode,
                'steam_id': server.steam_id,
                'next_wipe_date': server.next_wipe_date,
                'next_wipe_type': server.next_wipe_type,
                'last_wipe_date': server.last_wipe_date,
                'rust_url': server.rust_url,
                'map_url': server.map_url,
                'thumbnail_url': server.thumbnail_url,
                'queued_players': server.queued_players,
                'last_updated': datetime.now()
            }
            
            where_conditions = {'fk_id_servers': server_id_db}
            query, params = sqlHelper.update(
                table=tablesBM.RUST_SERVERS,
                set_values=data,
                where_conditions=where_conditions
            )
            
            self.__db_cur.execute(query, params)
            self.__db_con.commit()
            return True
            
        except Exception as e:
            self._logger.error(f"Ошибка при обновлении Rust сервера {server.id}: {e}")
            try:
                self.__db_con.rollback()
            except:
                pass
            return False
    
    def update_player_info(self, player: Player) -> bool:
        """Обновляет информацию об игроке в БД"""
        if not isinstance(player, Player):
            return False
        
        self._ensure_db_connection()
        try:
            player_id_db = self._convert_id_for_db(player.id, 'id_players')
            
            data = {
                'nickname': player.name,
                'private': player.private,
                'positive_match': player.positiveMatch,
                'last_seen': datetime.now() if any(meta.get('online', False) 
                                                  for meta in player.player_servers_meta.values()) 
                              else player._last_seen,
                'updated_at': datetime.now()
            }
            
            where_conditions = {'id_players': player_id_db}
            query, params = sqlHelper.update(
                table=tablesBM.PLAYERS,
                set_values=data,
                where_conditions=where_conditions
            )
            
            self.__db_cur.execute(query, params)
            self.__db_con.commit()
            
            # Добавляем запись в историю
            self._add_player_history(player)
            
            # Обновляем связи игрок-сервер
            self.update_player_server_connections(player)
            
            return True
            
        except Exception as e:
            self._logger.error(f"Ошибка при обновлении игрока {player.id}: {e}")
            try:
                self.__db_con.rollback()
            except:
                pass
            return False
    
    def update_player_server_connections(self, player: Player) -> int:
        """Обновляет связи игрок-сервер в БД"""
        if not isinstance(player, Player):
            return 0
        
        try:
            player_id_db = self._convert_id_for_db(player.id, 'id_players')
            updated_count = 0
            
            for server_id, meta in player.player_servers_meta.items():
                server_id_db = self._convert_id_for_db(server_id, 'id_server')
                
                # Проверяем существование сервера
                if not self.check_server_exists(server_id_db):
                    continue
                
                data = {
                    'fk_id_players': player_id_db,
                    'fk_id_server': server_id_db,
                    'is_online': meta.get('online', False),
                    'time_played': meta.get('timePlayed', 0),
                    'last_seen': datetime.now()
                }
                
                # Используем INSERT ... ON DUPLICATE KEY UPDATE
                insert_query, insert_params = sqlHelper.insert(
                    table=tablesBM.PLAYERS_SERVERS,
                    data=data
                )
                
                update_parts = [f"`{key}` = VALUES(`{key}`)" 
                               for key in data.keys() if key not in ['fk_id_players', 'fk_id_server']]
                insert_query += " ON DUPLICATE KEY UPDATE " + ", ".join(update_parts)
                
                self._add_to_queue('execute', insert_query, insert_params)
                updated_count += 1
            
            if updated_count > 0:
                self._add_to_queue('commit')
                self._process_write_queue()
            
            return updated_count
            
        except Exception as e:
            self._logger.error(f"Ошибка при обновлении связей игрок-сервер для игрока {player.id}: {e}")
            return 0
    
    def _add_server_history(self, server: Server) -> None:
        """Добавляет запись в историю сервера"""
        try:
            server_id_db = self._convert_id_for_db(server.id, 'id_server')
            
            history_data = {
                'id_server': server_id_db,
                'players_online': server._players,
                'players_max': server._max_players,
                'status': self._normalize_status(server._status),
                'recorded_at': datetime.now()
            }
            
            query, params = sqlHelper.insert(
                table=tablesBM.SERVERS_HISTORY,
                data=history_data
            )
            
            self._add_to_queue('execute', query, params)
            
        except Exception as e:
            self._logger.error(f"Ошибка при добавлении истории сервера {server.id}: {e}")
    
    def _add_player_history(self, player: Player) -> None:
        """Добавляет запись в историю игрока"""
        try:
            player_id_db = self._convert_id_for_db(player.id, 'id_players')
            
            # Определяем текущий сервер (если есть)
            current_server_id = None
            for server_id, meta in player.player_servers_meta.items():
                if meta.get('online', False):
                    current_server_id = server_id
                    break
            
            history_data = {
                'id_player': player_id_db,
                'nickname': player.name,
                'server_id': self._convert_id_for_db(current_server_id, 'id_server') if current_server_id else None,
                'is_online': any(meta.get('online', False) for meta in player.player_servers_meta.values()),
                'recorded_at': datetime.now()
            }
            
            query, params = sqlHelper.insert(
                table=tablesBM.PLAYERS_HISTORY,
                data=history_data
            )
            
            self._add_to_queue('execute', query, params)
            
        except Exception as e:
            self._logger.error(f"Ошибка при добавлении истории игрока {player.id}: {e}")
    
    # --- Дополнительные методы ---
    
    def _create_stats_connection(self) -> Optional[Tuple[Connection, Cursor]]:
        """
        Создаёт отдельное подключение только для read-only запросов (например, сбор статистики).
        Не использует и не затрагивает общее подключение репозитория — исключает гонки с другими потоками.
        Вызывающий код обязан закрыть connection и cursor после использования.
        """
        try:
            db_host = getenv('DB_HOST')
            db_port_str = getenv('DB_PORT')
            db_user = getenv('DB_USER')
            db_password = getenv('DB_PASSWORD')
            db_name = getenv('DB_NAME')
            if not db_host or not db_user or not db_password or not db_name:
                return None
            db_port = int(db_port_str) if db_port_str else 3306
            con = connect(
                host=db_host,
                port=db_port,
                user=db_user,
                password=db_password,
                database=db_name,
                read_timeout=10,
                connect_timeout=5,
                charset='utf8mb4',
                cursorclass=DictCursor
            )
            cur = con.cursor()
            return (con, cur)
        except Exception as e:
            self._logger.warning(f"Не удалось создать отдельное подключение для статистики: {e}")
            return None
    
    def _execute_read_query(self, query: str, params: Optional[Tuple] = None) -> Optional[List[Dict]]:
        """
        Выполняет read-only запрос под _db_lock (использует общее подключение).
        Для сбора статистики предпочтительно get_service_stats() с отдельным подключением.
        """
        with self._db_lock:
            try:
                self._ensure_db_connection()
                if params:
                    self.__db_cur.execute(query, params)
                else:
                    self.__db_cur.execute(query)
                return self.__db_cur.fetchall()
            except Exception as e:
                self._logger.warning(f"Ошибка выполнения read-only запроса: {e}")
                return None
    
    def _execute_read_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict]:
        """
        Выполняет read-only запрос и возвращает одну строку (под _db_lock).
        """
        with self._db_lock:
            try:
                self._ensure_db_connection()
                if params:
                    self.__db_cur.execute(query, params)
                else:
                    self.__db_cur.execute(query)
                return self.__db_cur.fetchone()
            except Exception as e:
                self._logger.warning(f"Ошибка выполнения read-only запроса: {e}")
                return None
    
    def get_service_stats(self) -> Dict[str, Any]:
        """
        Возвращает облегчённую статистику сервиса.
        Использует отдельное подключение к БД, не трогает общее — сбор статистики не мешает
        инициализации и другим операциям (нет гонок, «Packet sequence number wrong», «read of closed file»).
        """
        stats = {}
        db_host = getenv('DB_HOST', '')
        db_port = getenv('DB_PORT', '3306')
        db_user = getenv('DB_USER', '')
        db_name = getenv('DB_NAME', '')
        stats['db_name'] = db_name
        stats['db_address'] = f"{db_host}:{db_port}" if db_host else ''
        stats['db_user'] = db_user
        stats['queue_size'] = len(self._write_queue)
        
        conn_tuple = self._create_stats_connection()
        if not conn_tuple:
            stats['db_status'] = 'offline'
            stats['db_status_reason'] = 'Не удалось создать подключение для статистики'
            stats['database_tables'] = {}
            stats['answered_suggestions'] = 0
            stats['total_suggestions'] = 0
            stats['active_users'] = 0
            stats['total_users'] = 0
            return stats
        
        conn, cur = conn_tuple
        try:
            cur.execute("SELECT 1")
            cur.fetchone()
            stats['db_status'] = 'online'
            stats['db_status_reason'] = None
        except Exception as e:
            stats['db_status'] = 'offline'
            stats['db_status_reason'] = str(e)
            stats['database_tables'] = {}
            stats['answered_suggestions'] = 0
            stats['total_suggestions'] = 0
            stats['active_users'] = 0
            stats['total_users'] = 0
            try:
                cur.close()
                conn.close()
            except Exception:
                pass
            return stats
        
        database_tables = {}
        try:
            cur.execute("""
                SELECT table_name, COALESCE(table_rows, 0) AS row_count
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                ORDER BY table_name
            """)
            for row in cur.fetchall():
                tname = row.get("TABLE_NAME") or row.get("table_name")
                rcount = row.get("row_count") or row.get("ROW_COUNT")
                if tname is not None:
                    database_tables[tname] = int(rcount) if rcount is not None else 0
        except Exception as e:
            self._logger.warning(f"Не удалось получить статистику по таблицам: {e}")
        stats['database_tables'] = database_tables
        
        try:
            cur.execute("SELECT COUNT(*) as cnt FROM `{}`".format(tablesBM.SUGGESTIONS))
            row = cur.fetchone()
            total_suggestions = row['cnt'] if row else 0
            where_sql, where_params = sqlHelper.where_params({'is_answered': True})
            query = sqlHelper.select(
                table=tablesBM.SUGGESTIONS,
                columns=['COUNT(*) as count'],
                where=where_sql
            )
            cur.execute(query, where_params)
            answered_row = cur.fetchone()
            answered_suggestions = answered_row['count'] if answered_row else 0
            stats['answered_suggestions'] = answered_suggestions
            stats['total_suggestions'] = total_suggestions
        except Exception as e:
            self._logger.warning(f"Не удалось получить статистику по отчётам: {e}")
            stats['answered_suggestions'] = 0
            stats['total_suggestions'] = 0
        
        try:
            where_sql, where_params = sqlHelper.where_params({'bot_banned': False})
            query = sqlHelper.select(
                table=tablesBM.PROFILES,
                columns=['COUNT(*) as count'],
                where=where_sql
            )
            cur.execute(query, where_params)
            total_row = cur.fetchone()
            total_users = total_row['count'] if total_row else 0
            where_sql, where_params = sqlHelper.where_params({'is_active': True, 'bot_banned': False})
            query = sqlHelper.select(
                table=tablesBM.PROFILES,
                columns=['COUNT(*) as count'],
                where=where_sql
            )
            cur.execute(query, where_params)
            active_row = cur.fetchone()
            active_users = active_row['count'] if active_row else 0
            stats['active_users'] = active_users
            stats['total_users'] = total_users
        except Exception as e:
            self._logger.warning(f"Не удалось получить статистику по пользователям: {e}")
            stats['active_users'] = 0
            stats['total_users'] = 0
        
        try:
            cur.close()
            conn.close()
        except Exception:
            pass
        return stats
    
    def get_server_full_info(self, server_id: Union[str, int]) -> Optional[Dict]:
        """Получает полную информацию о сервере"""
        self._ensure_db_connection()
        try:
            server_id_db = self._convert_id_for_db(server_id, 'id_server')
            
            # Основная информация о сервере
            where_sql, where_params = sqlHelper.where_params({'id_server': server_id_db})
            query = sqlHelper.select(
                table=tablesBM.SERVERS,
                columns=['*'],
                where=where_sql
            )
            self.__db_cur.execute(query, where_params)
            server_row = self.__db_cur.fetchone()
            
            if not server_row:
                return None
            
            # Информация о Rust сервере (если есть)
            where_sql, where_params = sqlHelper.where_params({'fk_id_servers': server_id_db})
            rust_query = sqlHelper.select(
                table=tablesBM.RUST_SERVERS,
                columns=['*'],
                where=where_sql
            )
            self.__db_cur.execute(rust_query, where_params)
            rust_row = self.__db_cur.fetchone()
            
            # Объединяем информацию
            result = dict(server_row)
            if rust_row:
                result.update(rust_row)
                # Удаляем дублирующиеся ключи
                if 'id_server' in rust_row:
                    del result['id_server']
            
            # Конвертируем ID
            result['id_server'] = self._convert_id_from_db(result['id_server'], 'id_server')
            
            return result
            
        except Exception as e:
            self._logger.error(f"Ошибка при получении информации о сервере {server_id}: {e}")
            return None
    
    def get_player_full_info(self, player_id: Union[str, int]) -> Optional[Dict]:
        """Получает полную информацию об игроке"""
        self._ensure_db_connection()
        try:
            player_id_db = self._convert_id_for_db(player_id, 'id_players')
            
            where_sql, where_params = sqlHelper.where_params({'id_players': player_id_db})
            query = sqlHelper.select(
                table=tablesBM.PLAYERS,
                columns=['*'],
                where=where_sql
            )
            
            self.__db_cur.execute(query, where_params)
            row = self.__db_cur.fetchone()
            
            if row:
                row['id_players'] = self._convert_id_from_db(row['id_players'], 'id_players')
                return row
            
            return None
            
        except Exception as e:
            self._logger.error(f"Ошибка при получении информации об игроке {player_id}: {e}")
            return None
    
    # --- Методы для обратной совместимости ---
    
    def get_profile_servers(self, profile_id: str) -> List[Dict]:
        """Получает список серверов профиля (для обратной совместимости)"""
        profile = self.load_profile(profile_id)
        if not profile:
            return []
        
        return [
            {
                'id': server.id,
                'name': server.name
            }
            for server in profile.servers.values()
        ]
    
    def get_profile_players(self, profile_id: str) -> List[Dict]:
        """Получает список игроков профиля (для обратной совместимости)"""
        profile = self.load_profile(profile_id)
        if not profile:
            return []
        
        return [
            {
                'id': player.id,
                'name': player.name
            }
            for player in profile.players.values()
        ]
    
    def log_action(self, **kwargs) -> None:
        """Логирует действие (для обратной совместимости)"""
        # Этот метод оставлен для совместимости со старым кодом
        # В новой схеме используется другая система логирования
        pass
    
    def log_system_error(self, **kwargs) -> None:
        """Логирует системную ошибку (для обратной совместимости)"""
        # Аналогично, для совместимости
        pass
    
    # --- Методы обслуживания ---
    
    def cleanup_old_data(self, days: int = 30) -> int:
        """Очищает старые данные из истории"""
        self._ensure_db_connection()
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Очищаем старую историю серверов
            where_sql, where_params = sqlHelper.where_params({
                'recorded_at': ('<', cutoff_date)
            })
            delete_query = f"DELETE FROM {tablesBM.SERVERS_HISTORY} {where_sql}"
            self.__db_cur.execute(delete_query, where_params)
            servers_deleted = self.__db_cur.rowcount
            
            # Очищаем старую историю игроков
            where_sql, where_params = sqlHelper.where_params({
                'recorded_at': ('<', cutoff_date)
            })
            delete_query = f"DELETE FROM {tablesBM.PLAYERS_HISTORY} {where_sql}"
            self.__db_cur.execute(delete_query, where_params)
            players_deleted = self.__db_cur.rowcount
            
            self.__db_con.commit()
            
            total_deleted = servers_deleted + players_deleted
            self._logger.info(f"Очищено {total_deleted} старых записей истории")
            return total_deleted
            
        except Exception as e:
            self._logger.error(f"Ошибка при очистке старых данных: {e}")
            try:
                self.__db_con.rollback()
            except:
                pass
            return 0
    
    def optimize_tables(self) -> bool:
        """Оптимизирует таблицы БД"""
        self._ensure_db_connection()
        try:
            # Получаем список таблиц
            self.__db_cur.execute("SHOW TABLES")
            tables = [row['Tables_in_' + self.__db_con.db] for row in self.__db_cur.fetchall()]
            
            optimized_count = 0
            for table in tables:
                try:
                    self.__db_cur.execute(f"OPTIMIZE TABLE `{table}`")
                    optimized_count += 1
                except Exception as e:
                    self._logger.warning(f"Не удалось оптимизировать таблицу {table}: {e}")
            
            self._logger.info(f"Оптимизировано {optimized_count} таблиц")
            return True
            
        except Exception as e:
            self._logger.error(f"Ошибка при оптимизации таблиц: {e}")
            return False
    
    # --- Методы для работы с состоянием инициализации ---
    
    def get_initialization_state(self, admin_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает состояние инициализации для администратора
        
        Args:
            admin_id: ID администратора
            
        Returns:
            Dict с информацией о состоянии инициализации или None, если состояние не найдено
            Формат: {
                'error_type': str,      # 'servers_loading' или 'players_loading'
                'error_url': str,        # URL страницы, на которой произошла ошибка
                'error_message': str,    # Сообщение об ошибке
                'created_at': datetime,  # Время создания записи
                'updated_at': datetime   # Время обновления записи
            }
        """
        try:
            self._ensure_db_connection()
            admin_id_int = int(admin_id) if isinstance(admin_id, str) else admin_id
            
            # Проверяем существование таблицы перед запросом
            self.__db_cur.execute("SHOW TABLES LIKE 'initialization_state'")
            if not self.__db_cur.fetchone():
                self._logger.debug("Таблица initialization_state не найдена, возвращаем None")
                return None
            
            # Получаем последнее состояние для данного администратора
            where_sql, where_params = sqlHelper.where_params({'admin_id': admin_id_int})
            query = sqlHelper.select(
                table=tablesBM.INITIALIZATION_STATE,
                columns=['error_type', 'error_url', 'error_message', 'created_at', 'updated_at'],
                where=where_sql,
                order_by='`updated_at` DESC',
                limit=1
            )
            self.__db_cur.execute(query, where_params)
            row = self.__db_cur.fetchone()
            
            if row:
                return {
                    'error_type': row.get('error_type'),
                    'error_url': row.get('error_url') or '',
                    'error_message': row.get('error_message') or '',
                    'created_at': row.get('created_at'),
                    'updated_at': row.get('updated_at')
                }
            return None
            
        except Exception as e:
            self._logger.warning(f"Ошибка при получении состояния инициализации: {e}")
            return None
    
    def save_initialization_state(self, error_type: str, error_url: str, error_message: str, admin_id: str) -> bool:
        """
        Сохраняет или обновляет состояние инициализации
        
        Args:
            error_type: Тип ошибки ('servers_loading' или 'players_loading')
            error_url: URL страницы, на которой произошла ошибка
            error_message: Сообщение об ошибке
            admin_id: ID администратора
            
        Returns:
            True если успешно, False в противном случае
        """
        try:
            self._ensure_db_connection()
            admin_id_int = int(admin_id) if isinstance(admin_id, str) else admin_id
            
            # Проверяем существование таблицы перед запросом
            self.__db_cur.execute("SHOW TABLES LIKE 'initialization_state'")
            if not self.__db_cur.fetchone():
                self._logger.warning("Таблица initialization_state не найдена, создание таблицы не поддерживается автоматически")
                return False
            
            # Проверяем, существует ли запись для данного admin_id и error_type
            check_query = sqlHelper.select(
                table=tablesBM.INITIALIZATION_STATE,
                columns=['id'],
                where='`admin_id` = %s AND `error_type` = %s',
                limit=1
            )
            self.__db_cur.execute(check_query, (admin_id_int, error_type))
            existing = self.__db_cur.fetchone()
            
            if existing:
                # Обновляем существующую запись
                update_query, update_params = sqlHelper.update(
                    table=tablesBM.INITIALIZATION_STATE,
                    set_values={
                        'error_url': error_url,
                        'error_message': error_message
                    },
                    where_conditions={
                        'admin_id': admin_id_int,
                        'error_type': error_type
                    }
                )
                self.__db_cur.execute(update_query, update_params)
            else:
                # Создаем новую запись
                insert_query, insert_params = sqlHelper.insert(
                    table=tablesBM.INITIALIZATION_STATE,
                    data={
                        'admin_id': admin_id_int,
                        'error_type': error_type,
                        'error_url': error_url,
                        'error_message': error_message
                    }
                )
                self.__db_cur.execute(insert_query, insert_params)
            
            self.__db_con.commit()
            self._logger.info(f"Состояние инициализации сохранено: {error_type}", {
                'admin_id': admin_id_int,
                'error_type': error_type
            })
            return True
            
        except Exception as e:
            self._logger.error(f"Ошибка при сохранении состояния инициализации: {e}")
            try:
                self.__db_con.rollback()
            except:
                pass
            return False
    
    def clear_initialization_state(self, error_type: str = None, admin_id: str = None) -> bool:
        """
        Очищает состояние инициализации
        
        Args:
            error_type: Тип ошибки для очистки (опционально, если None - очищаются все типы)
            admin_id: ID администратора (опционально, если None - очищаются все администраторы)
            
        Returns:
            True если успешно, False в противном случае
        """
        try:
            self._ensure_db_connection()
            
            # Проверяем существование таблицы перед запросом
            self.__db_cur.execute("SHOW TABLES LIKE 'initialization_state'")
            if not self.__db_cur.fetchone():
                self._logger.debug("Таблица initialization_state не найдена")
                return True  # Таблица не существует, считаем успешным
            
            where_conditions = {}
            if admin_id:
                admin_id_int = int(admin_id) if isinstance(admin_id, str) else admin_id
                where_conditions['admin_id'] = admin_id_int
            if error_type:
                where_conditions['error_type'] = error_type
            
            if where_conditions:
                delete_query, delete_params = sqlHelper.delete(
                    table=tablesBM.INITIALIZATION_STATE,
                    where_conditions=where_conditions
                )
                self.__db_cur.execute(delete_query, delete_params)
            else:
                # Удаляем все записи
                self.__db_cur.execute(f"DELETE FROM `{tablesBM.INITIALIZATION_STATE}`")
            
            self.__db_con.commit()
            
            cleared_type = error_type or 'all'
            cleared_admin = admin_id or 'all'
            self._logger.info(f"Состояние инициализации очищено: {cleared_type} для admin_id={cleared_admin}")
            return True
            
        except Exception as e:
            self._logger.error(f"Ошибка при очистке состояния инициализации: {e}")
            try:
                self.__db_con.rollback()
            except:
                pass
            return False


# Создаем глобальный экземпляр для удобства
repository = Repository()