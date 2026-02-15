"""
Скрипт для добавления дополнительных индексов для оптимизации производительности
Эти индексы улучшат производительность JOIN операций и частых запросов
"""

from pymysql import connect
from os import getenv
import sys
from dotenv import load_dotenv
from pathlib import Path

# Загружаем переменные окружения из .env файла
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

# Загружаем .env до использования переменных окружения
load_env()

def add_performance_indexes(dry_run: bool = True):
    """
    Добавляет дополнительные индексы для оптимизации производительности
    
    Args:
        dry_run: Если True, только показывает SQL команды без выполнения
    """
    # Получаем переменные окружения (без значений по умолчанию для обязательных)
    db_host = getenv('DB_HOST')
    db_port_str = getenv('DB_PORT')
    db_user = getenv('DB_USER')
    db_password = getenv('DB_PASSWORD')
    db_name = getenv('DB_NAME')
    
    # Проверяем наличие обязательных переменных
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
    
    connection = connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        database=db_name
    )
    
    cursor = connection.cursor()
    
    # Список индексов для добавления
    indexes = [
        # Индексы для таблицы servers
        {
            'table': 'servers',
            'name': 'idx_server_game',
            'columns': ['fk_games_id', 'id_server'],
            'description': 'Составной индекс для фильтрации по игре и серверу'
        },
        
        # Индексы для таблицы players
        {
            'table': 'players',
            'name': 'idx_player_updated',
            'columns': ['updated_at'],
            'description': 'Индекс для сортировки по дате обновления'
        },
        
        # Индексы для таблицы players_servers
        {
            'table': 'players_servers',
            'name': 'idx_server_player_online',
            'columns': ['fk_id_server', 'is_online'],
            'description': 'Индекс для поиска онлайн игроков на сервере'
        },
        
        # Индексы для таблицы profiles
        {
            'table': 'profiles',
            'name': 'idx_profile_active',
            'columns': ['is_active', 'id_profile'],
            'description': 'Составной индекс для фильтрации активных профилей'
        },
        
        # Примечание: profiles_servers_conn и profiles_players_conn уже имеют
        # UNIQUE индексы на составных ключах, дополнительные индексы не нужны
        
        # Индексы для таблицы logs
        {
            'table': 'logs',
            'name': 'idx_log_profile_date',
            'columns': ['fk_id_profile', 'log_date'],
            'description': 'Составной индекс для фильтрации логов по профилю и дате'
        },
        
        # Индексы для таблицы suggestions
        {
            'table': 'suggestions',
            'name': 'idx_suggestion_profile_created',
            'columns': ['fk_id_profile', 'created_at'],
            'description': 'Составной индекс для фильтрации предложений по профилю и дате'
        },
    ]
    
    try:
        print("=" * 60)
        print("ДОБАВЛЕНИЕ ИНДЕКСОВ ДЛЯ ОПТИМИЗАЦИИ ПРОИЗВОДИТЕЛЬНОСТИ")
        print("=" * 60)
        print(f"Режим: {'DRY RUN (только показ команд)' if dry_run else 'ВЫПОЛНЕНИЕ'}\n")
        
        for idx_info in indexes:
            table = idx_info['table']
            name = idx_info['name']
            columns = idx_info['columns']
            description = idx_info['description']
            
            # Проверяем, существует ли уже такой индекс
            check_sql = f"""
                SELECT COUNT(*) 
                FROM information_schema.statistics 
                WHERE table_schema = '{db_name}' 
                AND table_name = '{table}' 
                AND index_name = '{name}'
            """
            cursor.execute(check_sql)
            exists = cursor.fetchone()[0] > 0
            
            if exists:
                print(f"⚠ Индекс {name} уже существует в таблице {table}, пропускаем")
                continue
            
            columns_str = ', '.join([f"`{col}`" for col in columns])
            sql = f"CREATE INDEX `{name}` ON `{table}` ({columns_str})"
            
            print(f"\n{description}")
            print(f"  Таблица: {table}")
            print(f"  Индекс: {name}")
            print(f"  Колонки: {', '.join(columns)}")
            print(f"  SQL: {sql}")
            
            if not dry_run:
                try:
                    cursor.execute(sql)
                    print(f"  ✓ Индекс создан успешно")
                except Exception as e:
                    print(f"  ✗ ОШИБКА: {e}")
                    # Продолжаем выполнение для других индексов
        
        if not dry_run:
            connection.commit()
            print("\n" + "=" * 60)
            print("✓ ИНДЕКСЫ ДОБАВЛЕНЫ УСПЕШНО")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("Это был DRY RUN. Для выполнения добавления индексов запустите:")
            print("  python add_performance_indexes.py --execute")
            print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ ОШИБКА: {e}")
        if not dry_run:
            connection.rollback()
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cursor.close()
        connection.close()

if __name__ == "__main__":
    dry_run = "--execute" not in sys.argv
    if dry_run:
        print("⚠ ВНИМАНИЕ: Это DRY RUN режим. Команды не будут выполнены.")
        print("⚠ Для выполнения добавления индексов используйте: python add_performance_indexes.py --execute\n")
    
    add_performance_indexes(dry_run=dry_run)

