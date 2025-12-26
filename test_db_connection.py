"""
Скрипт для проверки подключения к БД
"""
import sys
from os import getenv
from dotenv import load_dotenv
from pathlib import Path
from pymysql import connect, Connection
from pymysql.cursors import Cursor
from pymysql.err import Error as PyMySQLError


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


def test_db_connection(env_vars: dict) -> tuple[bool, str, Connection | None]:
    """
    Тестирует подключение к БД
    
    Returns:
        tuple: (успешно, сообщение, connection или None)
    """
    print("\n[INFO] Попытка подключения к БД...")
    print("-" * 50)
    
    try:
        connection: Connection = connect(
            host=env_vars['DB_HOST'],
            port=int(env_vars['DB_PORT']),
            user=env_vars['DB_USER'],
            password=env_vars['DB_PASSWORD'],
            database=env_vars['DB_NAME'],
            connect_timeout=10
        )
        
        print(f"  [OK] Подключение установлено!")
        print(f"  [INFO] Хост: {env_vars['DB_HOST']}:{env_vars['DB_PORT']}")
        print(f"  [INFO] База данных: {env_vars['DB_NAME']}")
        print(f"  [INFO] Пользователь: {env_vars['DB_USER']}")
        
        # Проверяем версию MySQL
        cursor: Cursor = connection.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()[0]
        print(f"  [INFO] Версия MySQL: {version}")
        
        # Проверяем кодировку
        cursor.execute("SHOW VARIABLES LIKE 'character_set_database'")
        charset = cursor.fetchone()
        if charset:
            print(f"  [INFO] Кодировка БД: {charset[1]}")
        
        # Проверяем доступные таблицы
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"  [INFO] Количество таблиц: {len(tables)}")
        if tables:
            print("  [INFO] Таблицы:")
            for table in tables[:10]:  # Показываем первые 10
                print(f"      - {table[0]}")
            if len(tables) > 10:
                print(f"      ... и еще {len(tables) - 10} таблиц")
        
        cursor.close()
        
        return True, "Подключение успешно установлено", connection
        
    except PyMySQLError as e:
        error_code, error_msg = e.args
        return False, f"Ошибка MySQL [{error_code}]: {error_msg}", None
    except ValueError as e:
        return False, f"Ошибка значения: {e}", None
    except Exception as e:
        return False, f"Неожиданная ошибка: {type(e).__name__}: {str(e)}", None


def main():
    """Основная функция"""
    print("=" * 50)
    print("ПРОВЕРКА ПОДКЛЮЧЕНИЯ К БАЗЕ ДАННЫХ")
    print("=" * 50)
    
    # Загружаем .env файл
    env_file_exists = load_env()
    
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
    
    # Тестируем подключение
    success, message, connection = test_db_connection(env_vars)
    
    print("\n" + "=" * 50)
    if success:
        print("[SUCCESS] РЕЗУЛЬТАТ: Подключение к БД работает корректно!")
        if connection:
            connection.close()
            print("   Соединение закрыто.")
    else:
        print("[ERROR] РЕЗУЛЬТАТ: Не удалось подключиться к БД")
        print(f"   Причина: {message}")
        sys.exit(1)
    print("=" * 50)


if __name__ == '__main__':
    main()

