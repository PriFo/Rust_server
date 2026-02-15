"""
Скрипт для проверки, можно ли конвертировать ID из VARCHAR в BIGINT
Проверяет, все ли значения в id_server и id_players являются числовыми
"""

from pymysql import connect
from os import getenv
from typing import Tuple, Dict
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

def check_id_types() -> Dict[str, Tuple[bool, int, list]]:
    """
    Проверяет, можно ли конвертировать VARCHAR ID в BIGINT
    
    Returns:
        dict: Результаты проверки для каждой таблицы
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
    results = {}
    
    try:
        # Проверка id_server в таблице servers
        print("Проверка id_server в таблице servers...")
        cursor.execute("""
            SELECT id_server, 
                   CASE 
                       WHEN id_server REGEXP '^[0-9]+$' THEN 1 
                       ELSE 0 
                   END as is_numeric
            FROM servers
            WHERE id_server NOT REGEXP '^[0-9]+$'
            LIMIT 10
        """)
        non_numeric_servers = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) FROM servers")
        total_servers = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM servers WHERE id_server REGEXP '^[0-9]+$'")
        numeric_servers = cursor.fetchone()[0]
        
        results['servers'] = (
            len(non_numeric_servers) == 0,
            total_servers,
            [row[0] for row in non_numeric_servers[:5]]
        )
        
        print(f"  Всего серверов: {total_servers}")
        print(f"  Числовых ID: {numeric_servers}")
        print(f"  Нечисловых ID: {len(non_numeric_servers)}")
        if non_numeric_servers:
            print(f"  Примеры нечисловых ID: {[row[0] for row in non_numeric_servers[:5]]}")
        
        # Проверка id_players в таблице players
        print("\nПроверка id_players в таблице players...")
        cursor.execute("""
            SELECT id_players, 
                   CASE 
                       WHEN id_players REGEXP '^[0-9]+$' THEN 1 
                       ELSE 0 
                   END as is_numeric
            FROM players
            WHERE id_players NOT REGEXP '^[0-9]+$'
            LIMIT 10
        """)
        non_numeric_players = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) FROM players")
        total_players = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM players WHERE id_players REGEXP '^[0-9]+$'")
        numeric_players = cursor.fetchone()[0]
        
        results['players'] = (
            len(non_numeric_players) == 0,
            total_players,
            [row[0] for row in non_numeric_players[:5]]
        )
        
        print(f"  Всего игроков: {total_players}")
        print(f"  Числовых ID: {numeric_players}")
        print(f"  Нечисловых ID: {len(non_numeric_players)}")
        if non_numeric_players:
            print(f"  Примеры нечисловых ID: {[row[0] for row in non_numeric_players[:5]]}")
        
        # Проверка максимальных значений для определения размера BIGINT
        print("\nПроверка максимальных значений...")
        cursor.execute("""
            SELECT MAX(CAST(id_server AS UNSIGNED)) as max_server_id
            FROM servers
            WHERE id_server REGEXP '^[0-9]+$'
        """)
        max_server_id = cursor.fetchone()[0]
        print(f"  Максимальный id_server: {max_server_id}")
        
        cursor.execute("""
            SELECT MAX(CAST(id_players AS UNSIGNED)) as max_player_id
            FROM players
            WHERE id_players REGEXP '^[0-9]+$'
        """)
        max_player_id = cursor.fetchone()[0]
        print(f"  Максимальный id_players: {max_player_id}")
        
        # BIGINT UNSIGNED может хранить до 18,446,744,073,709,551,615
        bigint_max = 18446744073709551615
        if max_server_id and max_server_id > bigint_max:
            print(f"  ВНИМАНИЕ: max_server_id ({max_server_id}) превышает BIGINT UNSIGNED!")
        if max_player_id and max_player_id > bigint_max:
            print(f"  ВНИМАНИЕ: max_player_id ({max_player_id}) превышает BIGINT UNSIGNED!")
        
    finally:
        cursor.close()
        connection.close()
    
    return results

if __name__ == "__main__":
    print("=" * 60)
    print("Проверка типов ID в базе данных")
    print("=" * 60)
    
    try:
        results = check_id_types()
        
        print("\n" + "=" * 60)
        print("РЕЗУЛЬТАТЫ ПРОВЕРКИ:")
        print("=" * 60)
        
        can_convert_servers = results['servers'][0]
        can_convert_players = results['players'][0]
        
        print(f"\nservers.id_server: {'✓ Можно конвертировать в BIGINT' if can_convert_servers else '✗ НЕЛЬЗЯ конвертировать (есть нечисловые значения)'}")
        print(f"players.id_players: {'✓ Можно конвертировать в BIGINT' if can_convert_players else '✗ НЕЛЬЗЯ конвертировать (есть нечисловые значения)'}")
        
        if can_convert_servers and can_convert_players:
            print("\n✓ Все ID можно конвертировать в BIGINT UNSIGNED")
            print("  Можно выполнить миграцию для оптимизации производительности")
        else:
            print("\n✗ Некоторые ID нельзя конвертировать")
            print("  Необходимо проверить данные перед миграцией")
            
    except Exception as e:
        print(f"\nОШИБКА: {e}")
        import traceback
        traceback.print_exc()

