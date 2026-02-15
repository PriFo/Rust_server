# Загружаем переменные окружения ПЕРЕД всеми импортами
from src.config import load_env

load_env()

from src.battlemetrics_requests import BattleMetricsController
from src.repository import Repository
import asyncio
from src.bot import start_bot
from src.logger import Logger
from datetime import datetime
from typing import Optional


logger = Logger("Main")

async def get_tasks(delay: int = 5, stop_event: Optional[asyncio.Event] = None, repository: Optional[Repository] = None) -> list:
    logger.info("Создание задач для запуска сервиса", {'delay': delay})
    tasks: list = []
    # Используем переданный repository или создаем новый
    if repository is None:
        repository = Repository()
    controller: BattleMetricsController = BattleMetricsController(repository=repository)
    tasks.append(asyncio.create_task(controller.update_info(delay, stop_event=stop_event)))
    tasks.append(asyncio.create_task(start_bot()))
    logger.info(f"Создано задач: {len(tasks)}")
    return tasks


async def log_service_stats_periodically(repo: Repository, interval: int = 60):
    """Периодически выводит статистику сервиса"""
    import asyncio
    while True:
        await asyncio.sleep(interval)
        stats = repo.get_service_stats()
        logger.section("СТАТИСТИКА СЕРВИСА")
        
        # Обрабатываем обычную статистику
        for key, value in stats.items():
            logger.info(f"{key}: {value}", {key: value})


async def update_profiles_periodically(repo: Repository, interval: int = 300):
    """
    Периодически обновляет все профили в БД
    
    :param repo: Экземпляр Repository
    :param interval: Интервал обновления в секундах (по умолчанию 5 минут = 300 секунд)
    """
    import asyncio
    logger.info(f"Запущена периодическая задача обновления профилей (интервал: {interval} сек)")
    
    while True:
        try:
            await asyncio.sleep(interval)
            logger.info("Начало периодического обновления профилей в БД", {
                'interval_seconds': interval
            })
            # В новой схеме БД метод update_all_profiles может отсутствовать
            # Вместо этого обновляем все профили из памяти
            updated_count = 0
            for profile_id, profile in repo.profiles.items():
                try:
                    repo.update_profile(profile_id)
                    updated_count += 1
                except Exception as e:
                    logger.error(f"Ошибка при обновлении профиля {profile_id}: {e}")
            
            logger.info(f"Периодическое обновление профилей завершено: обновлено {updated_count} профилей", {
                'updated_count': updated_count
            })
        except Exception as e:
            logger.error(f"Ошибка при периодическом обновлении профилей: {e}")
            import traceback
            logger.error(traceback.format_exc())


def save_data_on_exit(repo: Repository):
    """Сохраняет данные при выходе из программы"""
    try:
        logger.info("Сохранение данных при выходе из программы...")
        # Обрабатываем оставшуюся очередь
        repo._process_write_queue()
        
        # Обновляем все профили из памяти
        updated_count = 0
        for profile_id, profile in repo.profiles.items():
            try:
                repo.update_profile(profile_id)
                updated_count += 1
            except Exception as e:
                logger.error(f"Ошибка при сохранении профиля {profile_id}: {e}")
        
        logger.info(f"Сохранено профилей при выходе: {updated_count}")
        logger.info("Данные успешно сохранены при выходе")
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных при выходе: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def async_main(stop_event: Optional[asyncio.Event] = None, repository: Optional[Repository] = None) -> None:
    logger.section("ЗАПУСК СЕРВИСА")
    logger.info("Инициализация сервиса", {'timestamp': datetime.now().isoformat()})
    
    repo = repository if repository is not None else Repository()
    
    # Регистрируем atexit для гарантированного сохранения при выходе
    import atexit
    atexit.register(save_data_on_exit, repo)
    
    # Выводим статистику сервиса перед запуском
    stats = repo.get_service_stats()
    logger.section("СТАТИСТИКА СЕРВИСА ПЕРЕД ЗАПУСКОМ")
    for key, value in stats.items():
        logger.info(f"{key}: {value}", {key: value})
    
    # Запускаем периодический вывод статистики (каждые 5 минут)
    stats_task = asyncio.create_task(log_service_stats_periodically(repo, interval=300))
    
    # Запускаем периодическое обновление профилей (каждые 5 минут)
    profiles_task = asyncio.create_task(update_profiles_periodically(repo, interval=300))
    
    # Затем запускаем бота и обновление информации
    logger.info("Запуск основных задач сервиса")
    try:
        main_tasks = await get_tasks(stop_event=stop_event, repository=repo)
        await asyncio.gather(*main_tasks, stats_task, profiles_task)
    except KeyboardInterrupt:
        logger.warning("Получен сигнал прерывания (KeyboardInterrupt)")
        save_data_on_exit(repo)
        raise
    except Exception as e:
        logger.error(f"Критическая ошибка в async_main: {e}")
        import traceback
        logger.error(traceback.format_exc())
        save_data_on_exit(repo)
        raise
    

if __name__ == '__main__':
    logger.section("СТАРТ ПРИЛОЖЕНИЯ")
    repo = None
    try:
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