
class ETablesBM_DB:
    PROFILES = 'profiles'
    GAMES = 'games'
    FILTERS = 'filters'
    LOGS = 'logs'
    LOGS_SQL = 'logs_sql'
    PLAYER_FILTERS = 'player_filters'
    PLAYERS = 'players'
    PLAYERS_SERVERS = 'players_servers'
    PROFILES_FILTERS = 'profiles_filters'
    RUST_FILTERS = 'rust_filters'
    RUST_SERVERS = 'rust_servers'
    SERVER_FILTERS = 'server_filters'
    SERVERS = 'servers'
    SUGGESTIONS = 'suggestions'


class EJoin:
    LEFT = 'LEFT' # левое соединение
    RIGHT = 'RIGHT' # правое соединение
    INNER = 'INNER' # внутреннее соединение
    FULL = 'FULL' # полное соединение
    CROSS = 'CROSS' # декартовое соединение


class MySQLSyntaxHelper:

    @staticmethod
    def select(
        table: str, 
        columns: list[str], 
        where: str = None, 
        join: str = None, 
        group_by: str = None, 
        having: str = None, 
        order_by: str = None, 
        limit: int = None
    ) -> str:
        """Генератор SELECT-запросов

        Args:
            table (str): таблица из которой берутся данные (описаны в ETables)
            columns (list[str]): список столбцов, которые необходимы в запросе
            where (str, optional): условие запроса. Defaults to None. Может быть сгенерировано с помощью метода where
            join (str, optional): условие присоединения другой таблицы. Defaults to None. Может быть сгенерировано с помощью метода join
            group_by (str, optional): условие группировки. Defaults to None.
            having (str, optional): хз условие. Defaults to None.
            order_by (str, optional): условие сортировки. Defaults to None.
            limit (int, optional): лимит количества возвращаемых строк. Defaults to None.

        Raises:
            TypeError: Неверные типы входных параметров

        Returns:
            str: SELECT-запрос
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
        
        query = f"SELECT {', '.join(columns)} FROM {table}"
        if join:
            query += f" {join}"
        if where:
            query += f" {where}"
        if group_by:
            query += f" GROUP BY {group_by}"
        if having:
            query += f" HAVING {having}"
        if order_by:
            query += f" ORDER BY {order_by}"
        if limit:
            query += f" LIMIT {limit}"
        return query
    
    @staticmethod
    def join(
        table: str, 
        on_condition: str, 
        join_type: str = ''
    ) -> str:
        """Генератор JOIN-условия для запросов

        Args:
            table (str): присоединяемая таблица (описаны в ETables)
            on_condition (str): условие соединения
            join_type (str, optional): тип присоединения (описаны в EJoin). Defaults to ''.

        Raises:
            TypeError: Неверные типы входных параметров

        Returns:
            str: JOIN-условие
        """
        if not isinstance(table, str):
            raise TypeError("Table2 name must be a string")
        if not isinstance(join_type, str):
            raise TypeError("Join type must be a string")
        if not isinstance(on_condition, str):
            raise TypeError("ON condition must be a string")
        join_clause = f"{join_type} JOIN {table} ON {on_condition}"
        return join_clause
    
    @staticmethod
    def where(arg1: str, arg2: str, condition: str = '=') -> str:
        """Генератор WHERE-условия

        Args:
            arg1 (str): первый аргумент условия
            arg2 (str): второй аргумент условия
            condition (str, optional): оператор условия. Defaults to '='.

        Raises:
            TypeError: Неверные типы входных параметров

        Returns:
            str: WHERE-условие
        """
        if not isinstance(condition, str):
            raise TypeError("Condition must be a string")
        if not isinstance(arg1, str):
            raise TypeError("Arg1 must be a string")
        if not isinstance(arg2, str):
            raise TypeError("Arg2 must be a string")
        where_clause = f"WHERE {arg1} {condition} {arg2}"
        return where_clause
    
    @staticmethod
    def update(table: str, set_clause: str, where: str = None) -> str:
        """Генератор UPDATE-запроса

        Args:
            table (str): таблица для записи (описаны в ETables)
            set_clause (str): столбцы, в которых необходимо произвести изменения с самими изменениями
            where (str, optional): условие для изменения конкретных данных. Defaults to None. Может быть сгенерировано с помощью метода where

        Raises:
            TypeError: Неверные типы входных параметров

        Returns:
            str: UPDATE-запрос
        """
        if not isinstance(table, str):
            raise TypeError("Table name must be a string")
        if not isinstance(set_clause, str):
            raise TypeError("SET clause must be a string")
        if where and not isinstance(where, str):
            raise TypeError("WHERE clause must be a string")
        query = f"UPDATE {table} SET {set_clause}"
        if where:
            query += f" WHERE {where}"
        return query

    @staticmethod
    def insert(table: str, columns: list[str], values: list[str]) -> str:
        """Генератор INSERT-запроса

        Args:
            table (str): основная таблица (описаны в ETables)
            columns (list[str]): список столбцов, которые будут содержать данные
            values (list[str]): значения, которые необходимо добавить в таблицу

        Raises:
            TypeError: Неверные типы входных параметров
            ValueError: Разница в количестве столбцов и значений

        Returns:
            str: INSERT-запрос
        """
        if not isinstance(table, str):
            raise TypeError("Table name must be a string")
        if not isinstance(columns, list) or not all(isinstance(col, str) for col in columns):
            raise TypeError("Columns must be a list of strings")
        if not isinstance(values, list):
            raise TypeError("Values must be a list")
        if not all(isinstance(val, str) for val in values):
            if not all(isinstance(val, list) for val in values) or not all(isinstance(val, str) for sublist in values for val in sublist):
                raise TypeError("Values must be a list of strings or list of list of strings")
            else:
                max_len_sublist = -1
                for sublist in values:
                    if max_len_sublist < len(sublist):
                        max_len_sublist = len(sublist)
                if max_len_sublist != len(columns):
                    raise ValueError("The number of columns and values must be equal")
        elif len(values) != len(columns):
            raise ValueError("The number of columns and values must be equal")
        columns_str = ", ".join(columns)
        values_str = None
        values_list = None
        if all(isinstance(val, list) for val in values):
            values_list = []
            for sublist in values:
                part_str = ", ".join(f"'{val}'" for val in sublist)
                values_list.append(f'({part_str})')
        else:
            values_str = ", ".join(f"'{val}'" for val in values)
        query = f"INSERT INTO {table} ({columns_str}) VALUES {f'({values_str})' if values_str else ', '.join(str(val) for val in values_list)}"
        return query
    
    @staticmethod
    def delete(table: str, where: str = None) -> str:
        """Генератор DELETE-запроса

        Args:
            table (str): таблица в которой необходимо удалить данные (описаны в ETables)
            where (str, optional): условие удаления. Defaults to None. Может быть сгенерировано с помощью метода where

        Raises:
            TypeError: Неверные типы входных параметров

        Returns:
            str: DELETE-запрос
        """
        if not isinstance(table, str):
            raise TypeError("Table name must be a string")
        if where and not isinstance(where, str):
            raise TypeError("WHERE clause must be a string")
        query = f"DELETE FROM {table}"
        if where:
            query += f" WHERE {where}"
        return query
