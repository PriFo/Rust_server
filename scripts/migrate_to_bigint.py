"""
Скрипт миграции для изменения типов данных ID с VARCHAR на BIGINT UNSIGNED
Это значительно улучшит производительность запросов при больших объемах данных

ВАЖНО: Перед выполнением сделайте резервную копию базы данных!
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

def migrate_to_bigint(dry_run: bool = True):
    """
    Выполняет миграцию ID с VARCHAR на BIGINT UNSIGNED
    
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
    
    # Список SQL команд для миграции
    migration_commands = []
    
    try:
        print("=" * 60)
        print("МИГРАЦИЯ: VARCHAR -> BIGINT UNSIGNED")
        print("=" * 60)
        print(f"Режим: {'DRY RUN (только показ команд)' if dry_run else 'ВЫПОЛНЕНИЕ'}\n")
        
        # Шаг 1: Отключаем проверки внешних ключей
        migration_commands.append(("SET FOREIGN_KEY_CHECKS = 0", "Отключение проверки внешних ключей"))
        
        # Шаг 2: Удаляем внешние ключи, связанные с id_server
        print("\n1. Удаление внешних ключей для servers.id_server...")
        migration_commands.append((
            "ALTER TABLE `rust_servers` DROP FOREIGN KEY `fk_rust_servers_servers1`",
            "Удаление внешнего ключа fk_rust_servers_servers1"
        ))
        migration_commands.append((
            "ALTER TABLE `players_servers` DROP FOREIGN KEY `fk_players_servers_servers1`",
            "Удаление внешнего ключа fk_players_servers_servers1"
        ))
        migration_commands.append((
            "ALTER TABLE `profiles_servers_conn` DROP FOREIGN KEY `fk_profiles_servers_conn_servers1`",
            "Удаление внешнего ключа fk_profiles_servers_conn_servers1"
        ))
        
        # Шаг 3: Удаляем внешние ключи, связанные с id_players
        print("\n2. Удаление внешних ключей для players.id_players...")
        migration_commands.append((
            "ALTER TABLE `players_servers` DROP FOREIGN KEY `fk_players_servers_players1`",
            "Удаление внешнего ключа fk_players_servers_players1"
        ))
        migration_commands.append((
            "ALTER TABLE `profiles_players_conn` DROP FOREIGN KEY `fk_profiles_players_conn_players1`",
            "Удаление внешнего ключа fk_profiles_players_conn_players1"
        ))
        
        # Шаг 4: Изменяем типы данных в родительских таблицах
        print("\n3. Изменение типов данных в родительских таблицах...")
        migration_commands.append((
            "ALTER TABLE `servers` MODIFY COLUMN `id_server` BIGINT UNSIGNED NOT NULL",
            "Изменение servers.id_server"
        ))
        migration_commands.append((
            "ALTER TABLE `players` MODIFY COLUMN `id_players` BIGINT UNSIGNED NOT NULL",
            "Изменение players.id_players"
        ))
        
        # Шаг 5: Изменяем типы данных в дочерних таблицах
        print("\n4. Изменение типов данных в дочерних таблицах...")
        migration_commands.append((
            "ALTER TABLE `rust_servers` MODIFY COLUMN `fk_id_servers` BIGINT UNSIGNED NOT NULL",
            "Изменение rust_servers.fk_id_servers"
        ))
        migration_commands.append((
            "ALTER TABLE `players_servers` MODIFY COLUMN `fk_id_server` BIGINT UNSIGNED NOT NULL",
            "Изменение players_servers.fk_id_server"
        ))
        migration_commands.append((
            "ALTER TABLE `profiles_servers_conn` MODIFY COLUMN `fk_id_server` BIGINT UNSIGNED NOT NULL",
            "Изменение profiles_servers_conn.fk_id_server"
        ))
        migration_commands.append((
            "ALTER TABLE `players_servers` MODIFY COLUMN `fk_id_players` BIGINT UNSIGNED NOT NULL",
            "Изменение players_servers.fk_id_players"
        ))
        migration_commands.append((
            "ALTER TABLE `profiles_players_conn` MODIFY COLUMN `fk_id_players` BIGINT UNSIGNED NOT NULL",
            "Изменение profiles_players_conn.fk_id_players"
        ))
        
        # Шаг 6: Восстанавливаем внешние ключи
        print("\n5. Восстановление внешних ключей...")
        migration_commands.append((
            "ALTER TABLE `rust_servers` ADD CONSTRAINT `fk_rust_servers_servers1` FOREIGN KEY (`fk_id_servers`) REFERENCES `servers` (`id_server`) ON DELETE CASCADE ON UPDATE CASCADE",
            "Восстановление внешнего ключа fk_rust_servers_servers1"
        ))
        migration_commands.append((
            "ALTER TABLE `players_servers` ADD CONSTRAINT `fk_players_servers_servers1` FOREIGN KEY (`fk_id_server`) REFERENCES `servers` (`id_server`) ON DELETE CASCADE ON UPDATE CASCADE",
            "Восстановление внешнего ключа fk_players_servers_servers1"
        ))
        migration_commands.append((
            "ALTER TABLE `profiles_servers_conn` ADD CONSTRAINT `fk_profiles_servers_conn_servers1` FOREIGN KEY (`fk_id_server`) REFERENCES `servers` (`id_server`) ON DELETE CASCADE ON UPDATE CASCADE",
            "Восстановление внешнего ключа fk_profiles_servers_conn_servers1"
        ))
        migration_commands.append((
            "ALTER TABLE `players_servers` ADD CONSTRAINT `fk_players_servers_players1` FOREIGN KEY (`fk_id_players`) REFERENCES `players` (`id_players`) ON DELETE CASCADE ON UPDATE CASCADE",
            "Восстановление внешнего ключа fk_players_servers_players1"
        ))
        migration_commands.append((
            "ALTER TABLE `profiles_players_conn` ADD CONSTRAINT `fk_profiles_players_conn_players1` FOREIGN KEY (`fk_id_players`) REFERENCES `players` (`id_players`) ON DELETE CASCADE ON UPDATE CASCADE",
            "Восстановление внешнего ключа fk_profiles_players_conn_players1"
        ))
        
        # Шаг 7: Включаем проверки внешних ключей обратно
        migration_commands.append(("SET FOREIGN_KEY_CHECKS = 1", "Включение проверки внешних ключей"))
        
        # Выполнение или показ команд
        print("\n" + "=" * 60)
        print("КОМАНДЫ МИГРАЦИИ:")
        print("=" * 60)
        
        for i, (sql, description) in enumerate(migration_commands, 1):
            print(f"\n{i}. {description}")
            print(f"   SQL: {sql}")
            
            if not dry_run:
                try:
                    cursor.execute(sql)
                    print(f"   ✓ Выполнено успешно")
                except Exception as e:
                    print(f"   ✗ ОШИБКА: {e}")
                    connection.rollback()
                    raise
        
        if not dry_run:
            connection.commit()
            print("\n" + "=" * 60)
            print("✓ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("Это был DRY RUN. Для выполнения миграции запустите:")
            print("  python migrate_to_bigint.py --execute")
            print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ ОШИБКА МИГРАЦИИ: {e}")
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
        print("⚠ Для выполнения миграции используйте: python migrate_to_bigint.py --execute\n")
    
    migrate_to_bigint(dry_run=dry_run)

