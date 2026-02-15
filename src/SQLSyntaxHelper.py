# SQLSyntaxHelper.py - Обновлен для работы с новой схемой БД
# Версия 2.0 (совместимость с новой схемой БД v5.1)

class ETablesBM_DB:
    """Перечисление таблиц в новой схеме БД"""
    PROFILES = 'profiles'
    GAMES = 'games'
    LOGS = 'logs'
    PLAYER_FILTERS = 'player_filters'
    PLAYERS = 'players'
    PLAYERS_SERVERS = 'players_servers'
    RUST_SERVERS_FILTERS = 'rust_servers_filters'
    RUST_SERVERS = 'rust_servers'
    SERVER_FILTERS = 'server_filters'
    SERVERS = 'servers'
    SUGGESTIONS = 'suggestions'
    SUBSCRIPTIONS = 'subscriptions'
    SERVERS_HISTORY = 'servers_history'
    PLAYERS_HISTORY = 'players_history'
    CACHE = 'cache'
    MAINTENANCE_LOG = 'maintenance_log'
    INITIALIZATION_STATE = 'initialization_state'


class EJoin:
    LEFT = 'LEFT'  # левое соединение
    RIGHT = 'RIGHT'  # правое соединение
    INNER = 'INNER'  # внутреннее соединение
    FULL = 'FULL'  # полное соединение (MySQL не поддерживает напрямую)
    CROSS = 'CROSS'  # декартовое соединение


# Списки колонок для каждой таблицы (обновлены под новую схему)
bm_games_columns: list = [
    'id_game',
    'game_name',
    'created_at',
]

bm_servers_columns: list = [
    'id_server',
    'fk_games_id',
    'server_name',
    'rank',
    'private',
    'country',
    'ip',
    'port',
    'players_online',
    'players_max',
    'status',
    'last_updated',
    'created_at',
]

bm_servers_history_columns: list = [
    'id',
    'id_server',
    'players_online',
    'players_max',
    'status',
    'recorded_at',
]

bm_rust_servers_columns: list = [
    'fk_id_servers',
    'is_pve',
    'official',
    'description',
    'modded',
    'gamemode',
    'steam_id',
    'next_wipe_date',
    'next_wipe_type',
    'last_wipe_date',
    'rust_url',
    'map_url',
    'thumbnail_url',
    'queued_players',
    'last_updated',
    'created_at',
]

bm_players_columns: list = [
    'id_players',
    'nickname',
    'positive_match',
    'private',
    'last_seen',
    'created_at',
    'updated_at',
]

bm_players_history_columns: list = [
    'id',
    'id_player',
    'nickname',
    'server_id',
    'is_online',
    'recorded_at',
]

bm_players_servers_columns: list = [
    'fk_id_server',
    'fk_id_players',
    'is_online',
    'time_played',
    'first_seen',
    'last_seen',
]

bm_profiles_columns: list = [
    'id_profile',
    'profile_nickname',
    'profile_name',
    'profile_surname',
    'bot_banned',
    'is_active',
    'notification_settings',  # JSON поле
    'created_at',
    'last_activity',
]

bm_subscriptions_columns: list = [
    'id_subscription',
    'fk_id_profile',
    'entity_type',
    'entity_id',
    'is_active',
    'notification_types',  # JSON поле
    'created_at',
    'updated_at',
]

bm_server_filters_columns: list = [
    'id_filter',
    'fk_id_profile',
    'player_count_min',
    'player_count_max',
    'check_status',
    'check_ip_port',
    'check_private',
    'apply_to_all',
    'specific_server_id',
    'created_at',
]

bm_rust_servers_filters_columns: list = [
    'id_filter',
    'fk_server_filters_id',
    'queued_players_min',
    'check_last_wipe',
    'check_next_wipe',
    'check_pve',
    'check_url',
    'check_map_url',
    'check_map_image',
    'created_at',
]

bm_player_filters_columns: list = [
    'id_player_filter',
    'fk_id_profile',
    'player_name_changed',
    'player_private_changed',
    'check_online_status',
    'check_server_change',
    'apply_to_all',
    'specific_player_id',
    'created_at',
]

bm_logs_columns: list = [
    'id_log',
    'fk_id_profile',
    'log_type',
    'message_text',
    'error_details',
    'log_date',
]

bm_suggestions_columns: list = [
    'id_suggestions',
    'fk_id_profile',
    'msg_txt',
    'is_answered',
    'is_accepted',
    'created_at',
    'answered_at',
    'accepted_at',
]

bm_cache_columns: list = [
    'cache_key',
    'cache_value',
    'expires_at',
    'created_at',
    'updated_at',
]

bm_maintenance_log_columns: list = [
    'id_maintenance',
    'operation_type',
    'table_name',
    'records_affected',
    'duration_ms',
    'status',
    'details',
    'performed_at',
]

bm_initialization_state_columns: list = [
    'id',
    'admin_id',
    'error_type',
    'error_url',
    'error_message',
    'created_at',
    'updated_at',
]


class MySQLSyntaxHelper:
    """Хелпер для генерации SQL запросов с параметризацией"""

    @staticmethod
    def select(
        table: str,
        columns: list[str],
        where: str = None,
        join: str = None,
        group_by: str = None,
        having: str = None,
        order_by: str = None,
        limit: int = None,
        offset: int = None
    ) -> str:
        """
        Генератор SELECT-запросов с параметризацией
        
        Args:
            table (str): таблица из которой берутся данные
            columns (list[str]): список столбцов, которые необходимы в запросе
            where (str, optional): условие запроса с плейсхолдерами %s
            join (str, optional): условие присоединения другой таблицы
            group_by (str, optional): условие группировки
            having (str, optional): условие HAVING
            order_by (str, optional): условие сортировки
            limit (int, optional): лимит количества возвращаемых строк
            offset (int, optional): смещение для пагинации
        
        Returns:
            str: SELECT-запрос с плейсхолдерами
        """
        if not isinstance(table, str):
            raise TypeError("Table name must be a string")
        if not isinstance(columns, list) or not all(isinstance(col, str) for col in columns):
            raise TypeError("Columns must be a list of strings")
        if where and not isinstance(where, str):
            raise TypeError("WHERE clause must be a string")
        if join and not isinstance(join, str):
            raise TypeError("JOIN clause must be a string")
        if group_by and not isinstance(group_by, str):
            raise TypeError("GROUP BY clause must be a string")
        if having and not isinstance(having, str):
            raise TypeError("HAVING clause must be a string")
        if order_by and not isinstance(order_by, str):
            raise TypeError("ORDER BY clause must be a string")
        if limit and not isinstance(limit, int):
            raise TypeError("LIMIT must be an integer")
        if offset and not isinstance(offset, int):
            raise TypeError("OFFSET must be an integer")
        
        # Безопасное формирование запроса с плейсхолдерами
        query = f"SELECT {', '.join(columns)} FROM `{table}`"
        
        if join:
            # Заменяем простые имена таблиц на обратные кавычки
            join = join.replace(" JOIN ", " JOIN `").replace(" ON ", "` ON ")
            query += f" {join}"
        
        if where:
            query += f" {where}"
        
        if group_by:
            query += f" GROUP BY {group_by}"
        
        if having:
            query += f" HAVING {having}"
        
        if order_by:
            query += f" ORDER BY {order_by}"
        
        if limit is not None:
            query += f" LIMIT {limit}"
            if offset is not None:
                query += f" OFFSET {offset}"
        
        return query
    
    @staticmethod
    def join(
        table: str,
        on_condition: str,
        join_type: str = ''
    ) -> str:
        """
        Генератор JOIN-условия для запросов
        
        Args:
            table (str): присоединяемая таблица
            on_condition (str): условие соединения с плейсхолдерами
            join_type (str, optional): тип присоединения
        
        Returns:
            str: JOIN-условие
        """
        if not isinstance(table, str):
            raise TypeError("Table2 name must be a string")
        if not isinstance(join_type, str):
            raise TypeError("Join type must be a string")
        if not isinstance(on_condition, str):
            raise TypeError("ON condition must be a string")
        
        # Убираем лишние пробелы и формируем JOIN
        join_type = join_type.strip().upper()
        if join_type and join_type not in ['LEFT', 'RIGHT', 'INNER', 'FULL', 'CROSS']:
            raise ValueError(f"Invalid join type: {join_type}")
        
        return f"{join_type} JOIN `{table}` ON {on_condition}" if join_type else f"JOIN `{table}` ON {on_condition}"
    
    @staticmethod
    def where_params(conditions: dict, table_prefix: str = None) -> tuple[str, list]:
        """
        Генератор параметризованного WHERE-условия
        
        Args:
            conditions (dict): Словарь условий {column_name: value}
            table_prefix (str, optional): Префикс для имен столбцов
        
        Returns:
            tuple[str, list]: (SQL_часть_с_плейсхолдерами, значения_для_подстановки)
        """
        if not conditions:
            return "", []
        
        parts = []
        values = []
        
        for key, value in conditions.items():
            if value is None:
                parts.append(f"`{key}` IS NULL")
            elif isinstance(value, (list, tuple)):
                if not value:
                    continue
                placeholders = ', '.join(['%s'] * len(value))
                parts.append(f"`{key}` IN ({placeholders})")
                values.extend(value)
            else:
                parts.append(f"`{key}` = %s")
                values.append(value)
        
        sql_part = "WHERE " + " AND ".join(parts)
        
        # Добавляем префикс таблицы если указан
        if table_prefix:
            sql_part = sql_part.replace("`", f"`{table_prefix}`.")
            sql_part = sql_part.replace(f"`{table_prefix}`.`", f"`{table_prefix}`.`")
        
        return sql_part, values
    
    @staticmethod
    def update(table: str, set_values: dict, where_conditions: dict = None) -> tuple[str, list]:
        """
        Генератор UPDATE-запроса с параметризацией
        
        Args:
            table (str): таблица для обновления
            set_values (dict): словарь значений для SET {column: value}
            where_conditions (dict, optional): условия WHERE
        
        Returns:
            tuple[str, list]: (SQL_запрос, значения_для_подстановки)
        """
        if not isinstance(table, str):
            raise TypeError("Table name must be a string")
        if not isinstance(set_values, dict):
            raise TypeError("SET values must be a dict")
        
        # Формируем SET часть
        set_parts = []
        values = []
        
        for column, value in set_values.items():
            set_parts.append(f"`{column}` = %s")
            values.append(value)
        
        query = f"UPDATE `{table}` SET {', '.join(set_parts)}"
        
        # Добавляем WHERE если есть условия
        if where_conditions:
            where_sql, where_values = MySQLSyntaxHelper.where_params(where_conditions)
            query += f" {where_sql}"
            values.extend(where_values)
        
        return query, values
    
    @staticmethod
    def insert(table: str, data: dict | list[dict]) -> tuple[str, list]:
        """
        Генератор INSERT-запроса с параметризацией
        
        Args:
            table (str): таблица для вставки
            data (dict | list[dict]): данные для вставки
        
        Returns:
            tuple[str, list]: (SQL_запрос, значения_для_подстановки)
        """
        if not isinstance(table, str):
            raise TypeError("Table name must be a string")
        
        # Определяем, это одиночная или множественная вставка
        if isinstance(data, dict):
            data_list = [data]
            single_insert = True
        elif isinstance(data, list):
            data_list = data
            single_insert = False
        else:
            raise TypeError("Data must be dict or list of dicts")
        
        if not data_list:
            raise ValueError("No data provided for insert")
        
        # Получаем колонки из первого элемента
        columns = list(data_list[0].keys())
        if not columns:
            raise ValueError("No columns in data")
        
        # Проверяем, что у всех элементов одинаковые ключи
        for i, item in enumerate(data_list):
            if set(item.keys()) != set(columns):
                raise ValueError(f"Data item {i} has different columns")
        
        # Формируем VALUES часть
        placeholders = []
        values = []
        
        for item in data_list:
            row_placeholders = []
            for column in columns:
                row_placeholders.append("%s")
                values.append(item[column])
            placeholders.append(f"({', '.join(row_placeholders)})")
        
        columns_str = ', '.join(f'`{col}`' for col in columns)
        values_str = ', '.join(placeholders)
        
        query = f"INSERT INTO `{table}` ({columns_str}) VALUES {values_str}"
        
        # Добавляем ON DUPLICATE KEY UPDATE для одиночной вставки
        if single_insert:
            update_parts = [f"`{col}` = VALUES(`{col}`)" for col in columns]
            query += f" ON DUPLICATE KEY UPDATE {', '.join(update_parts)}"
        
        return query, values
    
    @staticmethod
    def insert_many(table: str, columns: list[str], values_list: list[list]) -> tuple[str, list]:
        """
        Генератор INSERT для множественной вставки с параметризацией
        
        Args:
            table (str): таблица для вставки
            columns (list[str]): список колонок
            values_list (list[list]): список списков значений
        
        Returns:
            tuple[str, list]: (SQL_запрос, значения_для_подстановки)
        """
        if not isinstance(table, str):
            raise TypeError("Table name must be a string")
        if not isinstance(columns, list) or not all(isinstance(col, str) for col in columns):
            raise TypeError("Columns must be a list of strings")
        if not isinstance(values_list, list):
            raise TypeError("Values must be a list of lists")
        
        # Проверяем структуру данных
        for i, values in enumerate(values_list):
            if not isinstance(values, (list, tuple)):
                raise TypeError(f"Values item {i} must be list or tuple")
            if len(values) != len(columns):
                raise ValueError(f"Values item {i} has {len(values)} values, expected {len(columns)}")
        
        # Формируем запрос
        columns_str = ', '.join(f'`{col}`' for col in columns)
        placeholders = ', '.join(['%s'] * len(columns))
        values_placeholders = ', '.join([f'({placeholders})' for _ in range(len(values_list))])
        
        # Собираем все значения в плоский список
        flat_values = []
        for values in values_list:
            flat_values.extend(values)
        
        query = f"INSERT INTO `{table}` ({columns_str}) VALUES {values_placeholders}"
        return query, flat_values
    
    @staticmethod
    def delete(table: str, where_conditions: dict = None) -> tuple[str, list]:
        """
        Генератор DELETE-запроса с параметризацией
        
        Args:
            table (str): таблица для удаления
            where_conditions (dict, optional): условия WHERE
        
        Returns:
            tuple[str, list]: (SQL_запрос, значения_для_подстановки)
        """
        if not isinstance(table, str):
            raise TypeError("Table name must be a string")
        
        query = f"DELETE FROM `{table}`"
        values = []
        
        if where_conditions:
            where_sql, where_values = MySQLSyntaxHelper.where_params(where_conditions)
            query += f" {where_sql}"
            values.extend(where_values)
        
        return query, values
    
    @staticmethod
    def escape_value(value) -> str:
        """
        Экранирование значения для безопасной вставки в SQL (только для отладки!)
        
        Warning: Используйте параметризованные запросы в продакшене!
        """
        if value is None:
            return 'NULL'
        elif isinstance(value, bool):
            return '1' if value else '0'
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            # Базовая экранизация для отладки
            escaped_value = value.replace("'", "''")
            return f"'{escaped_value}'"
        else:
            escaped_value = str(value).replace("'", "''")
            return f"'{escaped_value}'"
    
    @staticmethod
    def generate_set_clause(data: dict) -> str:
        """
        Генерирует SET часть для UPDATE запроса (для обратной совместимости)
        
        Args:
            data (dict): словарь значений для обновления
        
        Returns:
            str: SET часть запроса
        """
        if not isinstance(data, dict):
            raise TypeError("Data must be a dict")
        
        set_parts = []
        for key, value in data.items():
            set_parts.append(f"`{key}` = {MySQLSyntaxHelper.escape_value(value)}")
        
        return ', '.join(set_parts)
    
    @staticmethod
    def build_in_condition(column: str, values: list) -> tuple[str, list]:
        """
        Генератор условия IN для WHERE с параметризацией
        
        Args:
            column (str): имя колонки
            values (list): список значений
        
        Returns:
            tuple[str, list]: (SQL_часть, значения)
        """
        if not values:
            return "FALSE", []  # Пустой список = нет совпадений
        
        placeholders = ', '.join(['%s'] * len(values))
        return f"`{column}` IN ({placeholders})", values
    
    @staticmethod
    def build_between_condition(column: str, min_value, max_value) -> tuple[str, list]:
        """
        Генератор условия BETWEEN для WHERE с параметризацией
        
        Args:
            column (str): имя колонки
            min_value: минимальное значение
            max_value: максимальное значение
        
        Returns:
            tuple[str, list]: (SQL_часть, значения)
        """
        return f"`{column}` BETWEEN %s AND %s", [min_value, max_value]
    
    @staticmethod
    def build_like_condition(column: str, pattern: str) -> tuple[str, list]:
        """
        Генератор условия LIKE для WHERE с параметризацией
        
        Args:
            column (str): имя колонки
            pattern (str): шаблон поиска (с % и _)
        
        Returns:
            tuple[str, list]: (SQL_часть, значения)
        """
        return f"`{column}` LIKE %s", [pattern]