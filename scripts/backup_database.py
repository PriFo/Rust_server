"""
Скрипт для создания бэкапа базы данных и восстановления из бэкапа

Использование:
    python backup_database.py

Поддерживаемые платформы:
    - Windows
    - Linux
    - macOS

Возможности:
    - Создание бэкапа с указанием имени
    - Восстановление из бэкапа с выбором версии
    - Просмотр списка доступных бэкапов
    - Автоматический поиск mysqldump/mysql в системе (PATH и стандартные пути)
    - Fallback на PyMySQL, если mysqldump/mysql недоступен
"""

import sys
import json
import subprocess
import shutil
import platform
from typing import Optional, Dict, List
from os import getenv
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
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


def get_backups_dir() -> Path:
    """Возвращает путь к директории с бэкапами"""
    backups_dir = Path.cwd() / 'backups'
    backups_dir.mkdir(exist_ok=True)
    return backups_dir


def get_metadata_file() -> Path:
    """Возвращает путь к файлу с метаданными бэкапов"""
    return get_backups_dir() / 'backups_metadata.json'


def load_backups_metadata() -> Dict:
    """Загружает метаданные бэкапов из JSON файла"""
    metadata_file = get_metadata_file()
    if metadata_file.exists():
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARN] Ошибка чтения метаданных: {e}")
            return {}
    return {}


def save_backups_metadata(metadata: Dict):
    """Сохраняет метаданные бэкапов в JSON файл"""
    metadata_file = get_metadata_file()
    try:
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"[ERROR] Ошибка сохранения метаданных: {e}")


def _find_mysql_tool(tool_name: str) -> Optional[str]:
    """Общая функция для поиска MySQL инструментов (mysqldump/mysql)"""
    # Сначала проверяем в PATH
    tool_path = shutil.which(tool_name)
    if tool_path:
        return tool_path
    
    # Если не найден в PATH, проверяем стандартные пути для текущей ОС
    system = platform.system()
    exe_ext = '.exe' if system == 'Windows' else ''
    common_paths = []
    
    if system == 'Windows':
        common_paths = [
            r'C:\Program Files\MySQL\MySQL Server 8.0\bin',
            r'C:\Program Files\MySQL\MySQL Server 5.7\bin',
            r'C:\Program Files (x86)\MySQL\MySQL Server 8.0\bin',
            r'C:\Program Files (x86)\MySQL\MySQL Server 5.7\bin',
            r'C:\xampp\mysql\bin',
            r'C:\wamp64\bin\mysql\mysql8.0.xx\bin',
        ]
    elif system == 'Linux':
        common_paths = [
            '/usr/bin',
            '/usr/local/bin',
            '/usr/local/mysql/bin',
            '/opt/mysql/bin',
            '/usr/lib/mysql/bin',
        ]
    elif system == 'Darwin':  # macOS
        common_paths = [
            '/usr/local/bin',
            '/usr/local/mysql/bin',
            '/opt/homebrew/bin',
            '/usr/bin',
        ]
    
    # Проверяем стандартные пути
    for base_path in common_paths:
        full_path = Path(base_path) / f"{tool_name}{exe_ext}"
        if full_path.exists():
            return str(full_path)
    
    return None


def find_mysqldump() -> Optional[str]:
    """Ищет путь к mysqldump (кроссплатформенная функция)"""
    return _find_mysql_tool('mysqldump')


def create_backup_mysqldump(env_vars: Dict, backup_path: Path) -> bool:
    """Создает бэкап используя mysqldump"""
    mysqldump_path = find_mysqldump()
    
    if not mysqldump_path:
        return False
    
    try:
        # Формируем команду mysqldump с оптимизациями для скорости
        # Используем переменную окружения MYSQL_PWD для безопасной передачи пароля
        # вместо --password= в аргументах командной строки
        import os
        env = os.environ.copy()
        env['MYSQL_PWD'] = env_vars['DB_PASSWORD']
        
        cmd = [
            mysqldump_path,
            f"--host={env_vars['DB_HOST']}",
            f"--port={env_vars['DB_PORT']}",
            f"--user={env_vars['DB_USER']}",
            # Пароль передается через переменную окружения MYSQL_PWD, а не через --password=
            '--single-transaction',  # Консистентный снимок без блокировок
            '--quick',  # Не буферизует данные в памяти (быстрее для больших таблиц)
            '--lock-tables=false',  # Не блокирует таблицы (уже используется single-transaction)
            '--routines',  # Сохраняет процедуры и функции
            '--triggers',  # Сохраняет триггеры
            '--events',  # Сохраняет события
            '--hex-blob',  # Бинарные данные в hex формате
            '--default-character-set=utf8mb4',  # Правильная кодировка
            env_vars['DB_NAME']
        ]
        
        # Выполняем команду и записываем вывод в файл
        # Передаем env с MYSQL_PWD для безопасной передачи пароля
        with open(backup_path, 'w', encoding='utf-8') as f:
            result = subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                env=env  # Передаем окружение с MYSQL_PWD
            )
        
        if result.returncode == 0:
            return True
        else:
            print(f"[ERROR] Ошибка mysqldump: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Ошибка при создании бэкапа через mysqldump: {e}")
        return False


def _escape_sql_value(val) -> str:
    """Экранирует значение для SQL (оптимизированная версия)"""
    if val is None:
        return 'NULL'
    elif isinstance(val, bool):
        return '1' if val else '0'
    elif isinstance(val, (int, float)):
        return str(val)
    elif isinstance(val, bytes):
        return f"0x{val.hex()}"
    elif isinstance(val, datetime):
        return f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'"
    else:
        # Используем более эффективное экранирование
        val_str = str(val)
        # Экранируем специальные символы SQL
        val_str = val_str.replace('\\', '\\\\')
        val_str = val_str.replace("'", "\\'")
        val_str = val_str.replace('\n', '\\n')
        val_str = val_str.replace('\r', '\\r')
        val_str = val_str.replace('\x00', '\\0')
        return f"'{val_str}'"


def create_backup_pymysql(env_vars: Dict, backup_path: Path) -> bool:
    """Создает бэкап используя PyMySQL (fallback метод, оптимизированная версия)"""
    try:
        connection: Connection = connect(
            host=env_vars['DB_HOST'],
            port=int(env_vars['DB_PORT']),
            user=env_vars['DB_USER'],
            password=env_vars['DB_PASSWORD'],
            database=env_vars['DB_NAME'],
            connect_timeout=10
        )
        
        cursor: Cursor = connection.cursor()
        
        # Размер батча для обработки данных (максимум 50 записей)
        BATCH_SIZE = 50
        
        with open(backup_path, 'w', encoding='utf-8', buffering=8192) as f:  # Буферизация для ускорения записи
            # Получаем список таблиц
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            
            f.write(f"-- Backup created at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Database: {env_vars['DB_NAME']}\n\n")
            f.write("SET FOREIGN_KEY_CHECKS=0;\n\n")
            
            # Для каждой таблицы получаем структуру и данные
            for table_idx, table in enumerate(tables, 1):
                print(f"[INFO] Обработка таблицы {table_idx}/{len(tables)}: {table}")
                
                # Получаем структуру таблицы
                cursor.execute(f"SHOW CREATE TABLE `{table}`")
                create_table = cursor.fetchone()[1]
                f.write(f"\n-- Table structure for `{table}`\n")
                f.write(f"DROP TABLE IF EXISTS `{table}`;\n")
                f.write(f"{create_table};\n\n")
                
                # Получаем количество строк для оценки прогресса
                cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                row_count = cursor.fetchone()[0]
                
                if row_count == 0:
                    print(f"[INFO] Таблица {table} пуста, пропускаем данные")
                    continue
                
                # Получаем названия колонок один раз
                cursor.execute(f"DESCRIBE `{table}`")
                columns = [col[0] for col in cursor.fetchall()]
                
                f.write(f"-- Dumping data for table `{table}` ({row_count} rows)\n")
                f.write(f"LOCK TABLES `{table}` WRITE;\n")
                
                # Обрабатываем данные батчами для экономии памяти
                cursor.execute(f"SELECT * FROM `{table}`")
                
                # Записываем начало INSERT
                f.write(f"INSERT INTO `{table}` (`{'`, `'.join(columns)}`) VALUES\n")
                
                processed_rows = 0
                first_batch = True
                batch_values = []
                
                while True:
                    # Получаем батч строк (используем fetchmany для эффективности)
                    batch = cursor.fetchmany(BATCH_SIZE)
                    if not batch:
                        # Записываем последний батч если есть
                        if batch_values:
                            if not first_batch:
                                f.write(",\n")
                            f.write(',\n'.join(batch_values))
                        break
                    
                    # Форматируем значения для SQL
                    for row in batch:
                        formatted_values = [_escape_sql_value(val) for val in row]
                        batch_values.append(f"({', '.join(formatted_values)})")
                        processed_rows += 1
                    
                    # Записываем батч
                    if batch_values:
                        if not first_batch:
                            f.write(",\n")
                        f.write(',\n'.join(batch_values))
                        batch_values = []
                        first_batch = False
                        
                        # Показываем прогресс для больших таблиц (каждые 500 строк)
                        if row_count > 100 and processed_rows % 500 == 0:
                            progress = (processed_rows / row_count) * 100
                            print(f"[INFO] Таблица {table}: обработано {processed_rows}/{row_count} строк ({progress:.1f}%)")
                
                # Завершаем INSERT
                f.write(";\n")
                
                f.write(f"UNLOCK TABLES;\n\n")
                print(f"[INFO] Таблица {table}: завершено ({processed_rows} строк)")
            
            f.write("SET FOREIGN_KEY_CHECKS=1;\n")
        
        cursor.close()
        connection.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] Ошибка при создании бэкапа через PyMySQL: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_backup(env_vars: Dict, backup_name: Optional[str] = None) -> Optional[str]:
    """Создает бэкап базы данных"""
    print("\n[INFO] Создание бэкапа базы данных...")
    print("-" * 50)
    
    # Генерируем имя файла бэкапа
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    if backup_name:
        # Очищаем имя от недопустимых символов
        safe_name = ''.join(c for c in backup_name if c.isalnum() or c in ('_', '-'))
        filename = f"{safe_name}_{timestamp}.sql"
    else:
        filename = f"backup_{timestamp}.sql"
    
    backup_path = get_backups_dir() / filename
    
    # Пытаемся создать бэкап через mysqldump (быстрее)
    print(f"[INFO] Попытка создать бэкап через mysqldump (рекомендуемый метод)...")
    success = create_backup_mysqldump(env_vars, backup_path)
    
    # Если не получилось, используем PyMySQL (медленнее, но работает везде)
    if not success:
        print(f"[WARN] mysqldump недоступен или произошла ошибка.")
        print(f"[INFO] Используем PyMySQL (может быть медленнее для больших БД)...")
        print(f"[INFO] Для ускорения установите MySQL Client Tools с mysqldump")
        success = create_backup_pymysql(env_vars, backup_path)
    
    if success:
        # Получаем размер файла
        file_size = backup_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        
        print(f"[OK] Бэкап успешно создан: {filename}")
        print(f"[INFO] Размер файла: {file_size_mb:.2f} MB")
        
        # Сохраняем метаданные
        metadata = load_backups_metadata()
        backup_id = timestamp
        
        metadata[backup_id] = {
            'filename': filename,
            'created_at': datetime.now().isoformat(),
            'name': backup_name or 'backup',
            'size_bytes': file_size,
            'size_mb': round(file_size_mb, 2),
            'database': env_vars['DB_NAME']
        }
        
        save_backups_metadata(metadata)
        
        return backup_id
    else:
        print("[ERROR] Не удалось создать бэкап")
        if backup_path.exists():
            backup_path.unlink()
        return None


def list_backups() -> List[Dict]:
    """Возвращает список доступных бэкапов"""
    metadata = load_backups_metadata()
    backups_dir = get_backups_dir()
    
    backups = []
    for backup_id, info in metadata.items():
        backup_path = backups_dir / info['filename']
        if backup_path.exists():
            backups.append({
                'id': backup_id,
                **info
            })
        else:
            # Файл бэкапа не найден, удаляем из метаданных
            del metadata[backup_id]
    
    # Сохраняем обновленные метаданные
    if len(metadata) != len(backups):
        save_backups_metadata(metadata)
    
    # Сортируем по дате создания (новые первыми)
    backups.sort(key=lambda x: x['created_at'], reverse=True)
    return backups


def display_backups(backups: List[Dict]):
    """Выводит список бэкапов на экран"""
    if not backups:
        print("\n[INFO] Бэкапы не найдены")
        return
    
    print("\n[INFO] Доступные бэкапы:")
    print("-" * 80)
    print(f"{'№':<4} {'ID':<20} {'Имя':<20} {'Дата создания':<20} {'Размер (MB)':<12}")
    print("-" * 80)
    
    for idx, backup in enumerate(backups, 1):
        created_at = datetime.fromisoformat(backup['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        print(f"{idx:<4} {backup['id']:<20} {backup['name']:<20} {created_at:<20} {backup['size_mb']:<12}")
    
    print("-" * 80)


def find_mysql() -> Optional[str]:
    """Ищет путь к mysql клиенту (кроссплатформенная функция)"""
    return _find_mysql_tool('mysql')


def restore_backup_mysql(env_vars: Dict, backup_path: Path) -> bool:
    """Восстанавливает бэкап используя mysql клиент"""
    mysql_path = find_mysql()
    
    if not mysql_path:
        return False
    
    try:
        # Используем переменную окружения MYSQL_PWD для безопасной передачи пароля
        import os
        env = os.environ.copy()
        env['MYSQL_PWD'] = env_vars['DB_PASSWORD']
        
        # Формируем команду mysql
        cmd = [
            mysql_path,
            f"--host={env_vars['DB_HOST']}",
            f"--port={env_vars['DB_PORT']}",
            f"--user={env_vars['DB_USER']}",
            # Пароль передается через переменную окружения MYSQL_PWD, а не через --password=
            env_vars['DB_NAME']
        ]
        
        # Читаем SQL файл и передаем в mysql
        with open(backup_path, 'r', encoding='utf-8') as f:
            result = subprocess.run(
                cmd,
                stdin=f,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                env=env  # Передаем окружение с MYSQL_PWD
            )
        
        if result.returncode == 0:
            return True
        else:
            print(f"[ERROR] Ошибка восстановления через mysql: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Ошибка при восстановлении через mysql: {e}")
        return False


def restore_backup_pymysql(env_vars: Dict, backup_path: Path) -> bool:
    """Восстанавливает бэкап используя PyMySQL (fallback метод)"""
    try:
        connection: Connection = connect(
            host=env_vars['DB_HOST'],
            port=int(env_vars['DB_PORT']),
            user=env_vars['DB_USER'],
            password=env_vars['DB_PASSWORD'],
            database=env_vars['DB_NAME'],
            connect_timeout=10
        )
        
        cursor: Cursor = connection.cursor()
        
        # Читаем SQL файл порциями для экономии памяти
        BATCH_SIZE = 1024 * 1024  # 1MB порции
        statements = []
        current_statement = []
        in_string = False
        string_char = None
        escape_next = False
        
        with open(backup_path, 'r', encoding='utf-8', buffering=8192) as f:
            while True:
                chunk = f.read(BATCH_SIZE)
                if not chunk:
                    break
                
                for char in chunk:
                    if escape_next:
                        escape_next = False
                        current_statement.append(char)
                        continue
                    
                    if char == '\\':
                        escape_next = True
                        current_statement.append(char)
                        continue
                    
                    if char in ('"', "'") and not escape_next:
                        if not in_string:
                            in_string = True
                            string_char = char
                        elif char == string_char:
                            in_string = False
                            string_char = None
                        current_statement.append(char)
                    elif char == ';' and not in_string:
                        statement = ''.join(current_statement).strip()
                        if statement and not statement.startswith('--') and not statement.startswith('/*'):
                            statements.append(statement)
                        current_statement = []
                    else:
                        current_statement.append(char)
        
        # Добавляем последнюю команду, если она есть
        if current_statement:
            statement = ''.join(current_statement).strip()
            if statement and not statement.startswith('--') and not statement.startswith('/*'):
                statements.append(statement)
        
        # Выполняем команды батчами
        executed = 0
        errors = 0
        EXEC_BATCH_SIZE = 100  # Выполняем по 100 команд за раз
        
        for i in range(0, len(statements), EXEC_BATCH_SIZE):
            batch = statements[i:i + EXEC_BATCH_SIZE]
            for statement in batch:
                statement = statement.strip()
                if not statement or statement.startswith('--') or statement.startswith('/*'):
                    continue
                
                try:
                    cursor.execute(statement)
                    executed += 1
                except PyMySQLError as e:
                    error_msg = str(e)
                    # Игнорируем некоторые ошибки
                    if 'Unknown table' not in error_msg and 'already exists' not in error_msg.lower():
                        errors += 1
                        if errors <= 5:  # Показываем только первые 5 ошибок
                            print(f"[WARN] Ошибка выполнения команды: {error_msg[:100]}")
            
            # Коммитим после каждого батча
            try:
                connection.commit()
            except Exception as e:
                print(f"[WARN] Ошибка commit после батча: {e}")
        cursor.close()
        connection.close()
        
        print(f"[INFO] Выполнено команд: {executed}, ошибок: {errors}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Ошибка при восстановлении через PyMySQL: {e}")
        import traceback
        traceback.print_exc()
        return False


def recreate_backup(env_vars: Dict, backup_id: str) -> Optional[str]:
    """Пересоздает бэкап: восстанавливает из старого и создает новый с оптимизированным форматом"""
    print(f"\n[INFO] Пересоздание бэкапа...")
    print("-" * 50)
    
    metadata = load_backups_metadata()
    
    if backup_id not in metadata:
        print(f"[ERROR] Бэкап с ID '{backup_id}' не найден в метаданных")
        return None
    
    old_backup_info = metadata[backup_id]
    old_backup_path = get_backups_dir() / old_backup_info['filename']
    
    if not old_backup_path.exists():
        print(f"[ERROR] Файл бэкапа не найден: {old_backup_info['filename']}")
        return None
    
    print(f"[INFO] Старый бэкап: {old_backup_info['name']} ({old_backup_info['filename']})")
    print(f"[INFO] Дата создания: {old_backup_info['created_at']}")
    print("-" * 50)
    
    # Подтверждение
    print("\n[WARNING] Пересоздание бэкапа восстановит данные из старого бэкапа в БД!")
    print(f"[WARNING] База данных: {env_vars['DB_NAME']}")
    print("[INFO] После восстановления будет создан новый оптимизированный бэкап")
    response = input("\nПродолжить? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y', 'да']:
        print("[INFO] Пересоздание отменено")
        return None
    
    # Восстанавливаем из старого бэкапа
    print(f"\n[INFO] Шаг 1: Восстановление из старого бэкапа...")
    restore_success = restore_backup(env_vars, backup_id, skip_confirmation=True)
    
    if not restore_success:
        print("[ERROR] Не удалось восстановить из старого бэкапа")
        return None
    
    # Проверяем и применяем миграцию если необходимо
    print(f"\n[INFO] Шаг 2: Проверка версии схемы БД...")
    apply_migration_if_needed(env_vars)
    
    # Создаем новый бэкап
    print(f"\n[INFO] Шаг 3: Создание нового оптимизированного бэкапа...")
    new_backup_name = f"{old_backup_info['name']}_recreated"
    new_backup_id = create_backup(env_vars, new_backup_name)
    
    if new_backup_id:
        print(f"\n[OK] Бэкап успешно пересоздан!")
        print(f"[INFO] Старый бэкап: {old_backup_info['filename']}")
        print(f"[INFO] Новый бэкап ID: {new_backup_id}")
        return new_backup_id
    else:
        print("[ERROR] Не удалось создать новый бэкап")
        return None


def check_schema_version(env_vars: Dict) -> str:
    """Проверяет версию схемы БД (VARCHAR или BIGINT для ID)
    
    Returns:
        'v3' если используется VARCHAR(50) для id_server/id_players
        'v4' если используется BIGINT UNSIGNED для id_server/id_players
        'unknown' если не удалось определить
    """
    try:
        connection: Connection = connect(
            host=env_vars['DB_HOST'],
            port=int(env_vars['DB_PORT']),
            user=env_vars['DB_USER'],
            password=env_vars['DB_PASSWORD'],
            database=env_vars['DB_NAME'],
            connect_timeout=10
        )
        cursor: Cursor = connection.cursor()
        
        # Проверяем тип id_server в таблице servers
        cursor.execute("DESCRIBE `servers`")
        columns = cursor.fetchall()
        for col in columns:
            if col[0] == 'id_server':
                col_type = col[1].upper()
                if 'BIGINT' in col_type and 'UNSIGNED' in col_type:
                    cursor.close()
                    connection.close()
                    return 'v4'
                elif 'VARCHAR' in col_type:
                    cursor.close()
                    connection.close()
                    return 'v3'
        
        cursor.close()
        connection.close()
        return 'unknown'
    except Exception as e:
        print(f"[WARN] Не удалось проверить версию схемы: {e}")
        return 'unknown'


def apply_migration_if_needed(env_vars: Dict) -> bool:
    """Применяет миграцию VARCHAR -> BIGINT если необходимо
    
    Returns:
        True если миграция применена или не требуется, False при ошибке
    """
    schema_version = check_schema_version(env_vars)
    
    if schema_version == 'v4':
        print("[INFO] Схема БД уже использует BIGINT UNSIGNED (v4), миграция не требуется")
        return True
    elif schema_version == 'v3':
        print("[INFO] Обнаружена старая схема БД (v3 с VARCHAR), применяем миграцию...")
        try:
            # Импортируем функцию миграции
            import sys
            from pathlib import Path
            scripts_dir = Path(__file__).parent
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))
            
            from migrate_to_bigint import migrate_to_bigint
            migrate_to_bigint(dry_run=False)
            print("[OK] Миграция применена успешно")
            return True
        except Exception as e:
            print(f"[ERROR] Ошибка при применении миграции: {e}")
            print("[WARN] БД восстановлена, но миграция не применена. Рекомендуется выполнить миграцию вручную.")
            return False
    else:
        print("[WARN] Не удалось определить версию схемы БД")
        return True  # Продолжаем, так как это не критично


def restore_backup(env_vars: Dict, backup_id: str, skip_confirmation: bool = False) -> bool:
    """Восстанавливает базу данных из бэкапа
    
    Args:
        env_vars: Словарь с переменными окружения для подключения к БД
        backup_id: ID бэкапа для восстановления
        skip_confirmation: Если True, пропускает интерактивное подтверждение (для GUI)
    """
    metadata = load_backups_metadata()
    
    if backup_id not in metadata:
        print(f"[ERROR] Бэкап с ID '{backup_id}' не найден в метаданных")
        return False
    
    backup_info = metadata[backup_id]
    backup_path = get_backups_dir() / backup_info['filename']
    
    if not backup_path.exists():
        print(f"[ERROR] Файл бэкапа не найден: {backup_info['filename']}")
        return False
    
    print(f"\n[INFO] Восстановление из бэкапа: {backup_info['name']}")
    print(f"[INFO] Файл: {backup_info['filename']}")
    print(f"[INFO] Дата создания: {backup_info['created_at']}")
    print("-" * 50)
    
    # Подтверждение (пропускается если skip_confirmation=True)
    if not skip_confirmation:
        print("\n[WARNING] Восстановление из бэкапа перезапишет текущую базу данных!")
        print(f"[WARNING] База данных: {env_vars['DB_NAME']}")
        response = input("\nВы уверены? (yes/no): ").strip().lower()
        
        if response not in ['yes', 'y', 'да']:
            print("[INFO] Восстановление отменено")
            return False
    
    # Пытаемся восстановить через mysql клиент
    print(f"[INFO] Попытка восстановить через mysql клиент...")
    success = restore_backup_mysql(env_vars, backup_path)
    
    # Если не получилось, используем PyMySQL
    if not success:
        print(f"[INFO] mysql клиент недоступен, используем PyMySQL...")
        success = restore_backup_pymysql(env_vars, backup_path)
    
    if success:
        print("[OK] База данных успешно восстановлена из бэкапа")
        
        # Проверяем и применяем миграцию если необходимо
        print("\n[INFO] Проверка версии схемы БД...")
        apply_migration_if_needed(env_vars)
        
        return True
    else:
        print("[ERROR] Не удалось восстановить базу данных")
        return False


def main():
    """Главная функция"""
    print("=" * 80)
    print("Скрипт для создания бэкапа и восстановления базы данных")
    print("=" * 80)
    
    # Выводим информацию о платформе
    system = platform.system()
    system_name = {'Windows': 'Windows', 'Linux': 'Linux', 'Darwin': 'macOS'}.get(system, system)
    print(f"[INFO] Платформа: {system_name} ({platform.machine()})")
    
    # Загружаем переменные окружения
    load_env()
    
    # Проверяем переменные окружения
    env_vars = check_env_variables()
    if not env_vars:
        print("\n[ERROR] Не удалось загрузить переменные окружения")
        sys.exit(1)
    
    while True:
        print("\n" + "=" * 80)
        print("Выберите действие:")
        print("1. Создать бэкап")
        print("2. Восстановить из бэкапа")
        print("3. Просмотреть список бэкапов")
        print("4. Пересоздать бэкап (восстановить и создать новый)")
        print("5. Выход")
        print("=" * 80)
        
        choice = input("\nВаш выбор (1-4): ").strip()
        
        if choice == '1':
            # Создание бэкапа
            print("\n[INFO] Создание нового бэкапа")
            backup_name = input("Введите имя бэкапа (или нажмите Enter для имени по умолчанию): ").strip()
            backup_name = backup_name if backup_name else None
            
            backup_id = create_backup(env_vars, backup_name)
            if backup_id:
                print(f"\n[OK] Бэкап успешно создан с ID: {backup_id}")
            else:
                print("\n[ERROR] Не удалось создать бэкап")
        
        elif choice == '2':
            # Восстановление из бэкапа
            backups = list_backups()
            
            if not backups:
                print("\n[INFO] Нет доступных бэкапов для восстановления")
                continue
            
            display_backups(backups)
            
            while True:
                try:
                    backup_num = input(f"\nВыберите номер бэкапа для восстановления (1-{len(backups)}) или 'q' для отмены: ").strip()
                    
                    if backup_num.lower() == 'q':
                        break
                    
                    backup_num = int(backup_num)
                    if 1 <= backup_num <= len(backups):
                        selected_backup = backups[backup_num - 1]
                        restore_backup(env_vars, selected_backup['id'])
                        break
                    else:
                        print(f"[ERROR] Введите число от 1 до {len(backups)}")
                except ValueError:
                    print("[ERROR] Введите корректное число или 'q' для отмены")
        
        elif choice == '3':
            # Просмотр списка бэкапов
            backups = list_backups()
            display_backups(backups)
        
        elif choice == '4':
            # Пересоздание бэкапа
            backups = list_backups()
            
            if not backups:
                print("\n[INFO] Нет доступных бэкапов для пересоздания")
                continue
            
            display_backups(backups)
            
            while True:
                try:
                    backup_num = input(f"\nВыберите номер бэкапа для пересоздания (1-{len(backups)}) или 'q' для отмены: ").strip()
                    
                    if backup_num.lower() == 'q':
                        break
                    
                    backup_num = int(backup_num)
                    if 1 <= backup_num <= len(backups):
                        selected_backup = backups[backup_num - 1]
                        recreate_backup(env_vars, selected_backup['id'])
                        break
                    else:
                        print(f"[ERROR] Введите число от 1 до {len(backups)}")
                except ValueError:
                    print("[ERROR] Введите корректное число или 'q' для отмены")
        
        elif choice == '5':
            print("\n[INFO] Выход из программы")
            break
        
        else:
            print("\n[ERROR] Неверный выбор. Введите число от 1 до 4")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INFO] Прервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

