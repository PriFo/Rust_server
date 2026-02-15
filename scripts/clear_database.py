"""
Скрипт для очистки базы данных

Использование:
    python clear_database.py

ВНИМАНИЕ: Этот скрипт удаляет все данные из базы данных!
Все таблицы будут очищены (кроме начальных данных в games, если выбран соответствующий режим).
"""

import sys
from typing import Optional
from os import getenv
from dotenv import load_dotenv
from pathlib import Path
from pymysql import connect, Connection
from pymysql.cursors import Cursor
from pymysql.err import Error as PyMySQLError
from src.SQLSyntaxHelper import ETablesBM_DB as tables


def load_env():
    """Загружает переменные окружения из .env файла"""
    path: Path = Path.cwd() / '.env'
    if path.exists():
        load_dotenv(str(path))
        print(f"[OK] Файл .env найден: {path}")
        return True
    else:
        print(f"[WARN] Файл .env не найден: {path}")
        print("   Проверяю переменные окружения системы...")
        return False


def check_env_variables():
    """Проверяет наличие всех необходимых переменных окружения"""
    required_vars = ['DB_HOST', 'DB_PORT', 'DB_USER', 'DB_PASSWORD', 'DB_NAME']
    missing_vars = []
    env_vars = {}
    
    print("\n[INFO] Проверка переменных окружения:")
    print("-" * 50)
    
    for var in required_vars:
        value = getenv(var)
        if value:
            # Скрываем пароль при выводе
            display_value = value if var != 'DB_PASSWORD' else '*' * len(value)
            print(f"  [OK] {var}: {display_value}")
            env_vars[var] = value
        else:
            print(f"  [ERROR] {var}: НЕ УСТАНОВЛЕНА")
            missing_vars.append(var)
    
    print("-" * 50)
    
    if missing_vars:
        print(f"\n[ERROR] Отсутствуют переменные: {', '.join(missing_vars)}")
        return None
    else:
        print("\n[OK] Все необходимые переменные окружения установлены")
        return env_vars


def connect_to_db(env_vars: dict) -> Connection | None:
    """Подключается к базе данных"""
    try:
        connection: Connection = connect(
            host=env_vars['DB_HOST'],
            port=int(env_vars['DB_PORT']),
            user=env_vars['DB_USER'],
            password=env_vars['DB_PASSWORD'],
            database=env_vars['DB_NAME'],
            connect_timeout=10
        )
        return connection
    except Exception as e:
        print(f"[ERROR] Не удалось подключиться к БД: {e}")
        return None


def get_table_counts(cursor: Cursor) -> dict:
    """Получает количество записей в каждой таблице"""
    tables_list = [
        tables.LOGS,
        tables.SUGGESTIONS,
        tables.SUBSCRIPTIONS,  # Заменяет PROFILES_SERVERS_CONN и PROFILES_PLAYERS_CONN
        tables.PLAYER_FILTERS,
        tables.RUST_SERVERS_FILTERS,
        tables.SERVER_FILTERS,
        tables.PLAYERS_SERVERS,
        tables.SERVERS_HISTORY,
        tables.PLAYERS_HISTORY,
        tables.PROFILES,
        tables.RUST_SERVERS,
        tables.SERVERS,
        tables.PLAYERS,
        tables.GAMES
    ]
    
    counts = {}
    for table in tables_list:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            count = cursor.fetchone()[0]
            counts[table] = count
        except Exception as e:
            counts[table] = f"ERROR: {e}"
    
    return counts


def clear_database(cursor: Cursor, connection: Connection, preserve_games: bool = True) -> bool:
    """
    Очищает все таблицы базы данных
    
    :param cursor: Курсор базы данных
    :param connection: Соединение с базой данных
    :param preserve_games: Если True, сохраняет начальные данные в games (rust, arma3)
    :return: True если успешно, False в противном случае
    """
    # Порядок очистки таблиц (сначала зависимые, потом родительские)
    # Это важно из-за внешних ключей
    tables_to_clear = [
        # Таблицы, зависящие от profiles
        tables.LOGS,
        tables.SUGGESTIONS,
        tables.SUBSCRIPTIONS,  # Заменяет PROFILES_SERVERS_CONN и PROFILES_PLAYERS_CONN
        tables.PLAYER_FILTERS,
        tables.SERVER_FILTERS,
        # Таблицы, зависящие от server_filters
        tables.RUST_SERVERS_FILTERS,
        # Таблицы, зависящие от servers и players
        tables.PLAYERS_SERVERS,
        # Таблицы истории
        tables.SERVERS_HISTORY,
        tables.PLAYERS_HISTORY,
        # Таблицы, зависящие от servers
        tables.RUST_SERVERS,
        # Родительские таблицы
        tables.PROFILES,
        tables.SERVERS,
        tables.PLAYERS,
    ]
    
    # Если не сохраняем games, добавляем в список
    if not preserve_games:
        tables_to_clear.append(tables.GAMES)
    
    try:
        # Отключаем проверки внешних ключей для ускорения
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        cleared_count = 0
        total_tables = len(tables_to_clear)
        
        print("\n[INFO] Начало очистки таблиц...")
        print("-" * 50)
        
        for table in tables_to_clear:
            try:
                cursor.execute(f"TRUNCATE TABLE `{table}`")
                cleared_count += 1
                print(f"  [{cleared_count}/{total_tables}] [OK] Очищена таблица: {table}")
            except Exception as e:
                print(f"  [{cleared_count + 1}/{total_tables}] [ERROR] Ошибка при очистке {table}: {e}")
                # Пробуем альтернативный способ - DELETE
                try:
                    cursor.execute(f"DELETE FROM `{table}`")
                    connection.commit()
                    cleared_count += 1
                    print(f"  [{cleared_count}/{total_tables}] [OK] Очищена таблица (DELETE): {table}")
                except Exception as e2:
                    print(f"  [{cleared_count + 1}/{total_tables}] [ERROR] Не удалось очистить {table}: {e2}")
        
        # Если сохраняем games, восстанавливаем начальные данные
        if preserve_games:
            try:
                cursor.execute("INSERT IGNORE INTO `games` (`id_game`, `game_name`) VALUES (1, 'rust')")
                cursor.execute("INSERT IGNORE INTO `games` (`id_game`, `game_name`) VALUES (2, 'arma3')")
                print(f"  [INFO] Восстановлены начальные данные в таблице {tables.GAMES}")
            except Exception as e:
                print(f"  [WARN] Не удалось восстановить начальные данные в {tables.GAMES}: {e}")
        
        # Включаем проверки внешних ключей обратно
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        # Коммитим все изменения
        connection.commit()
        
        print("-" * 50)
        print(f"[OK] Очистка завершена. Очищено таблиц: {cleared_count}/{total_tables}")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Критическая ошибка при очистке: {e}")
        # Включаем проверки обратно даже при ошибке
        try:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        except:
            pass
        connection.rollback()
        return False


def confirm_action(db_name: str, table_counts: dict) -> Optional[str]:
    """Запрашивает подтверждение у пользователя
    
    Returns:
        'full' - полная очистка (включая games)
        'preserve_games' - очистка с сохранением начальных данных в games
        None - операция отменена
    """
    print("\n" + "=" * 60)
    print("ВНИМАНИЕ: БУДУТ УДАЛЕНЫ ВСЕ ДАННЫЕ ИЗ БАЗЫ ДАННЫХ!")
    print("=" * 60)
    print(f"База данных: {db_name}")
    print("\nТекущее состояние таблиц:")
    print("-" * 60)
    
    total_records = 0
    for table, count in sorted(table_counts.items()):
        if isinstance(count, int):
            total_records += count
            status = f"{count} записей"
        else:
            status = str(count)
        print(f"  {table:30} : {status}")
    
    print("-" * 60)
    print(f"Всего записей во всех таблицах: {total_records}")
    print("=" * 60)
    
    print("\nВыберите режим очистки:")
    print("  1. Полная очистка (включая games)")
    print("  2. Очистка с сохранением начальных данных в games (rust, arma3)")
    print("  3. Отмена")
    
    while True:
        choice = input("\nВаш выбор (1/2/3): ").strip()
        if choice == '1':
            print("\n[WARN] Будет выполнена ПОЛНАЯ очистка всех таблиц!")
            confirm = input("Вы уверены? Введите 'YES' для подтверждения: ").strip()
            if confirm == 'YES':
                return 'full'
            else:
                print("[INFO] Операция отменена")
                return None
        elif choice == '2':
            print("\n[INFO] Будет выполнена очистка с сохранением начальных данных в games")
            confirm = input("Вы уверены? Введите 'YES' для подтверждения: ").strip()
            if confirm == 'YES':
                return 'preserve_games'
            else:
                print("[INFO] Операция отменена")
                return None
        elif choice == '3':
            print("[INFO] Операция отменена пользователем")
            return None
        else:
            print("[ERROR] Неверный выбор. Введите 1, 2 или 3")


def main():
    """Основная функция"""
    print("=" * 60)
    print("СКРИПТ ОЧИСТКИ БАЗЫ ДАННЫХ")
    print("=" * 60)
    
    # Загружаем .env файл
    load_env()
    
    # Проверяем переменные окружения
    env_vars = check_env_variables()
    if env_vars is None:
        print("\n[ERROR] Невозможно продолжить без всех необходимых переменных")
        print("\n[INFO] Создайте файл .env в корне проекта со следующим содержимым:")
        print("   DB_HOST=localhost")
        print("   DB_PORT=3306")
        print("   DB_USER=your_user")
        print("   DB_PASSWORD=your_password")
        print("   DB_NAME=your_database")
        sys.exit(1)
    
    # Подключаемся к БД
    print("\n[INFO] Подключение к базе данных...")
    connection = connect_to_db(env_vars)
    if not connection:
        print("\n[ERROR] Не удалось подключиться к базе данных")
        sys.exit(1)
    
    print(f"[OK] Подключение установлено: {env_vars['DB_HOST']}:{env_vars['DB_PORT']}/{env_vars['DB_NAME']}")
    
    try:
        cursor: Cursor = connection.cursor()
        
        # Получаем информацию о таблицах
        print("\n[INFO] Получение информации о таблицах...")
        table_counts = get_table_counts(cursor)
        
        # Запрашиваем подтверждение
        mode = confirm_action(env_vars['DB_NAME'], table_counts)
        
        if mode is None:
            print("\n[INFO] Операция отменена")
            connection.close()
            sys.exit(0)
        
        # Выполняем очистку
        preserve_games = (mode == 'preserve_games')
        success = clear_database(cursor, connection, preserve_games=preserve_games)
        
        if success:
            # Показываем финальное состояние
            print("\n[INFO] Финальное состояние таблиц:")
            print("-" * 60)
            final_counts = get_table_counts(cursor)
            for table, count in sorted(final_counts.items()):
                if isinstance(count, int):
                    status = f"{count} записей"
                else:
                    status = str(count)
                print(f"  {table:30} : {status}")
            print("-" * 60)
            
            print("\n" + "=" * 60)
            print("[SUCCESS] База данных успешно очищена!")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("[ERROR] Произошла ошибка при очистке базы данных")
            print("=" * 60)
            sys.exit(1)
            
    except Exception as e:
        print(f"\n[ERROR] Неожиданная ошибка: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if connection:
            connection.close()
            print("\n[INFO] Соединение с базой данных закрыто")


if __name__ == '__main__':
    main()

