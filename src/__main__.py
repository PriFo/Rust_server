# Запуск no-gui режима: python -m src

import asyncio
import sys
from pathlib import Path

# Корень проекта в path (при запуске python -m src текущая директория может быть любой)
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.config import load_env, validate_required
from src.main_no_gui import async_main, save_data_on_exit
from src.logger import Logger

logger = Logger("Main")

if __name__ == "__main__":
    load_env()
    validate_required()
    logger.section("СТАРТ ПРИЛОЖЕНИЯ (python -m src)")
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
        logger.close()
