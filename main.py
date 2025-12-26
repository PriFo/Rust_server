# Загружаем переменные окружения ПЕРЕД всеми импортами
from dotenv import load_dotenv
from pathlib import Path

def load_env():
    path: Path = Path.cwd() / '.env'
    if path.exists():
        load_dotenv(str(path))

# Загружаем .env до импорта модулей, которые могут использовать переменные окружения
load_env()

from battlemetrics_requests import BattleMetricsController, BattleMetricsResponse, InitializationError
from data_classes import RustServer
from repository import Repository
import asyncio
from os.path import exists as file_exists
from bot import start_bot
from aiohttp import ClientSession
import sys
from logger import Logger
from datetime import datetime
from os import getenv


logger = Logger("Main")

ADMIN_ID = getenv('ADMIN_ID', '517965582')


def escape_markdown_v2(text: str) -> str:
    """Экранирует специальные символы для Markdown V2"""
    import re
    special_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(special_chars)}])', r'\\\1', text)


async def notify_admin(error_message: str, error_url: str = None, error_type: str = None):
    """
    Отправляет уведомление администратору через Telegram бот об ошибке при инициализации данных.
    
    :param error_message: Сообщение об ошибке
    :param error_url: URL страницы, на которой произошла ошибка
    :param error_type: Тип ошибки (например, 'servers_loading', 'players_loading')
    """
    try:
        from aiogram import Bot
        from aiogram.enums import ParseMode
        from aiogram.client.default import DefaultBotProperties
        
        token = getenv('T_API_KEY')
        if not token:
            logger.warning("T_API_KEY не установлен, невозможно отправить уведомление администратору")
            return
        
        bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
        )
        
        error_type_text = ""
        if error_type == 'servers_loading':
            error_type_text = "при загрузке серверов"
        elif error_type == 'players_loading':
            error_type_text = "при загрузке игроков"
        else:
            error_type_text = error_type or "при инициализации данных"
        
        message = f"⚠️ *Ошибка {error_type_text}*\n\n"
        message += f"*Сообщение:* {escape_markdown_v2(error_message)}\n\n"
        
        if error_url:
            message += f"*URL страницы:* `{escape_markdown_v2(error_url)}`\n\n"
        
        message += "Пожалуйста, проверьте логи для получения дополнительной информации\\."
        
        await bot.send_message(chat_id=ADMIN_ID, text=message)
        await bot.session.close()
        logger.info(f"Уведомление администратору отправлено", {
            'admin_id': ADMIN_ID,
            'error_type': error_type
        })
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление администратору: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def initialize_data() -> None:
    """
    Первичное заполнение данных: получает все серверы и игроков Rust из BattleMetrics
    и сохраняет их в БД перед запуском бота
    """
    start_time = datetime.now()
    logger.section("НАЧАЛО ПЕРВИЧНОЙ ЗАГРУЗКИ ДАННЫХ")
    
    repo = Repository()
    
    # Проверяем наличие незавершенной инициализации
    init_state = repo.get_initialization_state(ADMIN_ID)
    resume_servers_url = None
    resume_players_url = None
    
    if init_state:
        logger.warning(f"Обнаружено незавершенное состояние инициализации: {init_state['error_type']}", {
            'error_type': init_state['error_type'],
            'error_url': init_state['error_url'],
            'error_message': init_state['error_message'][:200] if init_state['error_message'] else None
        })
        
        if init_state['error_type'] == 'servers_loading':
            resume_servers_url = init_state['error_url']
            logger.info(f"Будет возобновлена загрузка серверов с URL: {resume_servers_url}")
        elif init_state['error_type'] == 'players_loading':
            resume_players_url = init_state['error_url']
            logger.info(f"Будет возобновлена загрузка игроков с URL: {resume_players_url}")
    
    # Проверяем заполненность таблиц перед загрузкой
    stats = repo.get_service_stats()
    servers_count = stats.get('total_servers', 0)
    players_count = stats.get('total_players', 0)
    
    logger.info("Проверка заполненности таблиц", {
        'servers_count': servers_count,
        'players_count': players_count
    })
    
    # Если таблицы уже заполнены, пропускаем загрузку
    if servers_count > 0 and players_count > 0:
        logger.info("Таблицы servers и players уже заполнены, пропускаем первичную загрузку", {
            'servers_count': servers_count,
            'players_count': players_count
        })
        # Очищаем состояние инициализации, если оно было
        if init_state:
            repo.clear_initialization_state(admin_id=ADMIN_ID)
        logger.section("ПЕРВИЧНАЯ ЗАГРУЗКА ДАННЫХ ЗАВЕРШЕНА (пропущена)")
        return
    
    bm_response = BattleMetricsResponse()
    
    # Инициализируем с пустым словарем серверов (для первичной загрузки)
    logger.info("Инициализация BattleMetricsResponse")
    await bm_response.async_initialize({})
    logger.info("BattleMetricsResponse инициализирован")
    
    async with ClientSession() as session:
        # Загружаем все серверы Rust (только если таблица пуста или есть состояние для возобновления)
        if servers_count == 0 or resume_servers_url:
            if resume_servers_url:
                logger.subsection("[1/2] Возобновление загрузки серверов Rust")
            else:
                logger.subsection("[1/2] Загрузка всех серверов Rust")
            logger.info("Начало загрузки серверов", {'page_size': 100})
            
            try:
                servers_start = datetime.now()
                total_added_servers = [0]  # Используем список для изменения из callback
                
                # Callback для немедленной вставки данных
                def insert_servers_page(servers_page: list[dict]) -> int:
                    """Вставляет серверы со страницы в БД, создавая RustServer объекты"""
                    if servers_page:
                        try:
                            # Создаем объекты RustServer из полученных данных
                            rust_servers = []
                            servers_for_insert = []
                            
                            for server_data in servers_page:
                                server_id = server_data.get('id')
                                if not server_id:
                                    continue
                                
                                # Создаем RustServer объект из данных
                                try:
                                    # Формируем структуру данных для RustServer
                                    server_dict = {
                                        **server_data,
                                        'details': server_data.get('details', {})
                                    }
                                    rust_server = RustServer(server_id, server_dict, 'rust')
                                    rust_servers.append(rust_server)
                                    
                                    # Также добавляем базовые данные для таблицы servers
                                    servers_for_insert.append({
                                        'id': server_id,
                                        'name': server_data.get('name', ''),
                                        'rank': server_data.get('rank'),
                                        'private': server_data.get('private', False),
                                        'country': server_data.get('country', '')
                                    })
                                except Exception as e:
                                    logger.warning(f"Ошибка при создании RustServer для {server_id}: {e}")
                                    # Все равно добавляем базовые данные
                                    servers_for_insert.append({
                                        'id': server_id,
                                        'name': server_data.get('name', ''),
                                        'rank': server_data.get('rank'),
                                        'private': server_data.get('private', False),
                                        'country': server_data.get('country', '')
                                    })
                            
                            # Вставляем базовые данные в servers
                            added_servers = 0
                            if servers_for_insert:
                                added_servers = repo.bulk_insert_servers(servers_for_insert, game_name='rust')
                            
                            # Вставляем Rust-специфичные данные в rust_servers
                            added_rust_servers = 0
                            if rust_servers:
                                added_rust_servers = repo.bulk_insert_rust_servers(rust_servers)
                            
                            # Обновляем все поля серверов
                            updated_servers = 0
                            for rust_server in rust_servers:
                                if repo.update_server_info(rust_server):
                                    updated_servers += 1
                            
                            total_added_servers[0] += added_servers
                            
                            if added_servers == 0 and len(servers_page) > 0:
                                logger.warning(f"bulk_insert_servers вернул 0 для {len(servers_page)} серверов")
                            
                            return added_servers
                        except Exception as e:
                            logger.error(f"Ошибка при вставке серверов: {e}")
                            import traceback
                            logger.error(traceback.format_exc())
                            return 0
                    return 0
                
                servers = await bm_response.async_get_all_rust_servers(
                    session, 
                    page_size=100,
                    on_page_callback=insert_servers_page,
                    resume_url=resume_servers_url
                )
                servers_time = (datetime.now() - servers_start).total_seconds()
                
                logger.info(f"Завершена загрузка серверов", {
                    'total_received': len(servers),
                    'total_added': total_added_servers[0],
                    'skipped': len(servers) - total_added_servers[0],
                    'time_seconds': round(servers_time, 2)
                })
                
                if not servers:
                    logger.warning("Серверы не найдены или произошла ошибка")
                else:
                    logger.info("Загрузка серверов завершена. Данные для servers и rust_servers заполнены одновременно")
                    # Очищаем состояние инициализации для серверов после успешного завершения
                    if resume_servers_url:
                        repo.clear_initialization_state('servers_loading', ADMIN_ID)
                        logger.info("Состояние инициализации серверов очищено")
            except InitializationError as e:
                # Ошибка при получении данных от API с сохранением URL
                error_message = str(e)
                error_url = e.url
                error_type = e.error_type or 'servers_loading'
                
                logger.critical(f"Критическая ошибка при загрузке серверов: {error_message}")
                logger.critical(f"URL страницы, на которой остановилось заполнение: {error_url}")
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(error_traceback)
                
                # Сохраняем состояние инициализации для последующего возобновления
                repo.save_initialization_state(error_type, error_url, error_message, ADMIN_ID)
                
                # Логируем в БД
                repo.log_system_error(
                    object='Main',
                    action='initialize_data_servers',
                    comment=f'Ошибка при инициализации данных: загрузка серверов остановилась. URL: {error_url}',
                    result=f'{error_message}\n\n{error_traceback}',
                    admin_id=ADMIN_ID
                )
                
                # Уведомляем администратора
                await notify_admin(error_message, error_url, error_type)
                
                # Пробрасываем исключение дальше
                raise
            except Exception as e:
                # Другие ошибки при загрузке серверов
                error_message = str(e)
                logger.error(f"Ошибка при загрузке серверов: {error_message}")
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(error_traceback)
                
                # Логируем в БД (без URL, так как это не ошибка API)
                repo.log_system_error(
                    object='Main',
                    action='initialize_data_servers',
                    comment='Ошибка при загрузке серверов при инициализации данных',
                    result=f'{error_message}\n\n{error_traceback}',
                    admin_id=ADMIN_ID
                )
                
                # Уведомляем администратора
                await notify_admin(error_message, None, 'servers_loading')
                
                # Пробрасываем исключение дальше
                raise
        else:
            logger.info("Таблица servers уже заполнена, пропускаем загрузку серверов", {
                'servers_count': servers_count
            })
        
        # Загружаем всех игроков Rust (только если таблица пуста или есть состояние для возобновления)
        if players_count == 0 or resume_players_url:
            if resume_players_url:
                logger.subsection("[2/2] Возобновление загрузки игроков Rust")
            else:
                logger.subsection("[2/2] Загрузка всех игроков Rust")
            logger.info("Начало загрузки игроков", {'page_size': 100})
            logger.warning("Это может занять ОЧЕНЬ много времени (игроков может быть очень много)")
            
            try:
                players_start = datetime.now()
                total_added_players = [0]  # Используем список для изменения из callback
                
                # Callback для немедленной вставки данных
                def insert_players_page(page_data: dict) -> int:
                    """Вставляет игроков со страницы в БД, а также их связи с серверами"""
                    if isinstance(page_data, dict):
                        players_page = page_data.get('players', [])
                        player_servers = page_data.get('player_servers', [])
                    else:
                        # Обратная совместимость: если передали список напрямую
                        players_page = page_data if isinstance(page_data, list) else []
                        player_servers = []
                    
                    added = 0
                    if players_page:
                        added = repo.bulk_insert_players(players_page)
                        total_added_players[0] += added
                    
                    # Обрабатываем связи игрок-сервер, если они есть
                    if player_servers:
                        added_links = repo.bulk_insert_player_servers(player_servers)
                        logger.debug(f"Добавлено/обновлено связей игрок-сервер: {added_links}", {
                            'links_count': added_links
                        })
                        # Логируем в logs
                        repo.log_action(
                            object='Main',
                            action='bulk_insert_player_servers_initial',
                            comment=f'Первичное заполнение: добавлено/обновлено {added_links} связей игрок-сервер',
                            result=f'Success: {added_links} links'
                        )
                    
                    return added
                
                players = await bm_response.async_get_all_rust_players(
                    session, 
                    page_size=100,
                    on_page_callback=insert_players_page,
                    resume_url=resume_players_url
                )
                players_time = (datetime.now() - players_start).total_seconds()
                
                logger.info(f"Завершена загрузка игроков", {
                    'total_received': len(players),
                    'total_added': total_added_players[0],
                    'skipped': len(players) - total_added_players[0],
                    'time_seconds': round(players_time, 2)
                })
                
                if not players:
                    logger.warning("Игроки не найдены или произошла ошибка")
                else:
                    # После загрузки базовых данных игроков, получаем полные данные для заполнения всех полей
                    logger.subsection("Обновление полных данных игроков")
                    logger.info("Получение полных данных игроков для заполнения всех полей")
                    try:
                        # Получаем список ID игроков для загрузки полных данных
                        player_ids = [p.get('id') for p in players if p.get('id')]
                        if player_ids:
                            # Обрабатываем игроков батчами для оптимизации
                            batch_size = 50  # Размер батча для получения полных данных
                            players_updated = 0
                            
                            for i in range(0, len(player_ids), batch_size):
                                batch_ids = player_ids[i:i + batch_size]
                                logger.debug(f"Обработка батча игроков {i//batch_size + 1}/{(len(player_ids) + batch_size - 1)//batch_size}", {
                                    'batch_size': len(batch_ids),
                                    'batch_start': i,
                                    'batch_end': min(i + batch_size, len(player_ids))
                                })
                                
                                # Получаем полные данные игроков для батча
                                players_info = await bm_response.async_get_players_info(session, batch_ids)
                                errors = players_info.get('errors')
                                if errors:
                                    logger.warning(f"Обнаружено ошибок при получении полных данных игроков в батче: {len(errors)}")
                                
                                # Обновляем все поля игроков в БД
                                for player_id, player in players_info.items():
                                    if player_id != 'errors':
                                        from data_classes import Player
                                        if isinstance(player, Player):
                                            if repo.update_player_info(player):
                                                players_updated += 1
                                
                                # Небольшая задержка между батчами, чтобы не перегружать API
                                if i + batch_size < len(player_ids):
                                    await asyncio.sleep(0.5)
                            
                            if players_updated > 0:
                                logger.info(f"Обновлено записей в players с полными данными: {players_updated}", {
                                    'players_updated': players_updated
                                })
                                # Логируем в logs_sql
                                repo.log_action(
                                    object='Main',
                                    action='update_players_full_data_initial',
                                    comment=f'Первичное обновление: обновлено {players_updated} записей в players с полными данными',
                                    result=f'Success: {players_updated} records'
                                )
                            else:
                                logger.warning("Не удалось получить полные данные игроков для обновления")
                    except Exception as e:
                        error_message = str(e)
                        logger.error(f"Ошибка при обновлении полных данных игроков: {error_message}")
                        import traceback
                        error_traceback = traceback.format_exc()
                        logger.error(error_traceback)
                        
                        # Логируем в БД через log_system_error (для системных ошибок)
                        repo.log_system_error(
                            object='Main',
                            action='update_players_full_data_initial',
                            comment='Ошибка при обновлении полных данных игроков при первичной загрузке',
                            result=f'{error_message}\n\n{error_traceback}',
                            admin_id=ADMIN_ID
                        )
                        
                        # Уведомляем администратора
                        await notify_admin(error_message, None, 'players_full_data_update')
            except InitializationError as e:
                # Ошибка при получении данных от API с сохранением URL
                error_message = str(e)
                error_url = e.url
                error_type = e.error_type or 'players_loading'
                
                logger.critical(f"Критическая ошибка при загрузке игроков: {error_message}")
                logger.critical(f"URL страницы, на которой остановилось заполнение: {error_url}")
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(error_traceback)
                
                # Сохраняем состояние инициализации для последующего возобновления
                repo.save_initialization_state(error_type, error_url, error_message, ADMIN_ID)
                
                # Логируем в БД
                repo.log_system_error(
                    object='Main',
                    action='initialize_data_players',
                    comment=f'Ошибка при инициализации данных: загрузка игроков остановилась. URL: {error_url}',
                    result=f'{error_message}\n\n{error_traceback}',
                    admin_id=ADMIN_ID
                )
                
                # Уведомляем администратора
                await notify_admin(error_message, error_url, error_type)
                
                # Пробрасываем исключение дальше
                raise
            except Exception as e:
                # Другие ошибки при загрузке игроков
                error_message = str(e)
                logger.error(f"Ошибка при загрузке игроков: {error_message}")
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(error_traceback)
                
                # Логируем в БД (без URL, так как это не ошибка API)
                repo.log_system_error(
                    object='Main',
                    action='initialize_data_players',
                    comment='Ошибка при загрузке игроков при инициализации данных',
                    result=f'{error_message}\n\n{error_traceback}',
                    admin_id=ADMIN_ID
                )
                
                # Уведомляем администратора
                await notify_admin(error_message, None, 'players_loading')
                
                # Пробрасываем исключение дальше
                raise
        else:
            logger.info("Таблица players уже заполнена, пропускаем загрузку игроков", {
                'players_count': players_count
            })
    
    total_time = (datetime.now() - start_time).total_seconds()
    logger.section("ПЕРВИЧНАЯ ЗАГРУЗКА ДАННЫХ ЗАВЕРШЕНА")
    logger.info(f"Общее время выполнения: {round(total_time, 2)} секунд", {
        'total_time_seconds': round(total_time, 2)
    })


async def get_tasks(delay: int = 5) -> list:
    logger.info("Создание задач для запуска сервиса", {'delay': delay})
    tasks: list = []
    controller: BattleMetricsController = BattleMetricsController()
    tasks.append(asyncio.create_task(controller.update_info(delay)))
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
        for key, value in stats.items():
            logger.info(f"{key}: {value}", {key: value})


async def async_main() -> None:
    logger.section("ЗАПУСК СЕРВИСА")
    logger.info("Инициализация сервиса", {'timestamp': datetime.now().isoformat()})
    
    # Сначала выполняем первичную загрузку данных
    try:
        await initialize_data()
    except KeyboardInterrupt:
        logger.warning("Первичная загрузка прервана пользователем")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Критическая ошибка при первичной загрузке: {e}")
        import traceback
        logger.error(traceback.format_exc())
        logger.warning("Продолжаем запуск бота без первичной загрузки...")
    
    # Выводим статистику сервиса перед запуском
    repo = Repository()
    stats = repo.get_service_stats()
    logger.section("СТАТИСТИКА СЕРВИСА ПЕРЕД ЗАПУСКОМ")
    for key, value in stats.items():
        logger.info(f"{key}: {value}", {key: value})
    
    # Запускаем периодический вывод статистики
    stats_task = asyncio.create_task(log_service_stats_periodically(repo, interval=300))  # Каждые 5 минут
    
    # Затем запускаем бота и обновление информации
    logger.info("Запуск основных задач сервиса")
    await asyncio.gather(*await get_tasks(), stats_task)
    

if __name__ == '__main__':
    logger.section("СТАРТ ПРИЛОЖЕНИЯ")
    asyncio.run(async_main())
    