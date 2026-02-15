#!/usr/bin/env python
"""
Точка входа для запуска бота без GUI
"""
import sys
import asyncio
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Загружаем переменные окружения ПЕРЕД всеми импортами
from src.config import load_env, validate_required

load_env()
validate_required()

from src.main_no_gui import async_main, save_data_on_exit
from src.logger import Logger

logger = Logger("Main")

if __name__ == '__main__':
    logger.section("СТАРТ ПРИЛОЖЕНИЯ")
    repo = None
    try:
        from src.repository import Repository
        repo = Repository()
        asyncio.run(async_main(repository=repo))
    except KeyboardInterrupt:
        logger.warning("Программа прервана пользователем (KeyboardInterrupt)")
        if repo:
            save_data_on_exit(repo)
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if repo:
            save_data_on_exit(repo)
    finally:
        # Закрываем файлы логов при завершении
        logger.close()

