#!/usr/bin/env python3
"""
Скрипт для генерации .env файла с шаблоном конфигурации

Использование:
    python sandbox/generate_env.py

Создаст файл .env в корне проекта с шаблоном конфигурации.
"""

import os
from pathlib import Path


def generate_env_file():
    """Генерирует .env файл с шаблоном конфигурации"""
    
    # Определяем путь к .env файлу (в корне проекта)
    project_root = Path(__file__).parent.parent
    env_file_path = project_root / '.env'
    
    # Шаблон конфигурации
    env_template = """# ===================================================
# Конфигурация BattleMetrics Bot
# ===================================================
# ВАЖНО: Заполните все секретные данные перед запуском бота!
# ===================================================

# ===================================================
# Конфигурация базы данных
# ===================================================
DB_HOST=localhost
DB_PORT=3306
DB_USER=your_db_user  # ЗАПОЛНИТЕ СЕКРЕТНЫЕ ДАННЫЕ
DB_PASSWORD=your_db_password  # ЗАПОЛНИТЕ СЕКРЕТНЫЕ ДАННЫЕ
DB_NAME=bm_db

# Формирование DATABASE_URL из отдельных параметров (используется в некоторых случаях)
# DATABASE_URL=mysql+pymysql://your_db_user:your_db_password@localhost:3306/bm_db

# ===================================================
# Конфигурация Telegram бота
# ===================================================
T_API_KEY=your_telegram_bot_token  # ЗАПОЛНИТЕ СЕКРЕТНЫЕ ДАННЫЕ - токен от @BotFather
ADMIN_ID=your_admin_id  # Ваш Telegram ID (можно получить у @userinfobot)

# ===================================================
# Конфигурация BattleMetrics API
# ===================================================
BM_API_KEY=your_bm_token  # ЗАПОЛНИТЕ СЕКРЕТНЫЕ ДАННЫЕ - API ключ от BattleMetrics
# BM_API_TOKEN=your_bm_token  # Альтернативное название переменной (если используется)

# ===================================================
# Дополнительные настройки (опционально)
# ===================================================
# LOGGING_LEVEL=INFO  # Уровень логирования: DEBUG, INFO, WARNING, ERROR, CRITICAL
"""
    
    # Проверяем, существует ли уже .env файл
    if env_file_path.exists():
        response = input(f"Файл {env_file_path} уже существует. Перезаписать? (y/N): ")
        if response.lower() != 'y':
            print("Операция отменена.")
            return
    
    # Записываем шаблон в файл
    try:
        with open(env_file_path, 'w', encoding='utf-8') as f:
            f.write(env_template)
        
        print(f"✓ Файл {env_file_path} успешно создан!")
        print("\nВАЖНО: Не забудьте заполнить все секретные данные:")
        print("  - DB_USER и DB_PASSWORD (данные для подключения к MySQL)")
        print("  - T_API_KEY (токен Telegram бота)")
        print("  - ADMIN_ID (ваш Telegram ID)")
        print("  - BM_API_KEY (API ключ BattleMetrics)")
        print("\nФайл .env уже добавлен в .gitignore, поэтому не будет сохранен в репозиторий.")
        
    except Exception as e:
        print(f"Ошибка при создании файла: {e}")
        return


if __name__ == '__main__':
    generate_env_file()

