# Загружаем переменные окружения ПЕРЕД всеми импортами
from dotenv import load_dotenv
from pathlib import Path

def load_env():
    path: Path = Path.cwd() / '.env'
    if path.exists():
        load_dotenv(str(path))

# Загружаем .env до импорта модулей, которые могут использовать переменные окружения
load_env()

from src.battlemetrics_requests import BattleMetricsResponse, InitializationError
from src.data_classes import RustServer, Server
from src.repository import Repository
import asyncio
from aiohttp import ClientSession
import sys
from src.logger import Logger, LogCategory
from datetime import datetime
from os import getenv
from scripts.initialization_checker import InitializationChecker


logger = Logger("InitializeDB")

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
    bot = None
    try:
        from aiogram import Bot
        from aiogram.enums import ParseMode
        from aiogram.client.default import DefaultBotProperties
        from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
        
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
        
        try:
            await bot.send_message(chat_id=ADMIN_ID, text=message)
            logger.info(f"Уведомление администратору отправлено", {
                'admin_id': ADMIN_ID,
                'error_type': error_type
            })
        except TelegramBadRequest as e:
            # Обрабатываем ошибки Telegram API (например, "chat not found")
            if "chat not found" in str(e).lower():
                logger.warning(f"Не удалось отправить уведомление: чат с ID {ADMIN_ID} не найден. Убедитесь, что бот запущен и пользователь начал диалог с ботом.")
            else:
                logger.error(f"Ошибка Telegram API при отправке уведомления: {e}")
        except TelegramAPIError as e:
            logger.error(f"Ошибка Telegram API: {e}")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление администратору: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # Всегда закрываем сессию бота, если она была создана
        if bot and bot.session:
            try:
                await bot.session.close()
            except Exception as e:
                logger.warning(f"Ошибка при закрытии сессии бота: {e}")


async def initialize_data() -> None:
    """
    Первичное заполнение данных: получает все серверы и игроков Rust из BattleMetrics
    и сохраняет их в БД перед запуском бота
    """
    start_time = datetime.now()
    logger.section("НАЧАЛО ПЕРВИЧНОЙ ЗАГРУЗКИ ДАННЫХ")
    
    repo = Repository()
    
    # Проверяем ошибки инициализации через InitializationChecker
    checker = InitializationChecker()
    errors_info = checker.check_all_errors()
    
    resume_servers_url = None
    resume_players_url = None
    error_source = None
    
    # Обрабатываем ошибки инициализации
    init_error = errors_info.get('initialization_error')
    if init_error:
        error_source = init_error.get('source', 'unknown')
        error_type = init_error.get('error_type')
        error_url = init_error.get('error_url', '')
        error_message = init_error.get('error_message', '')
        
        logger.warning(f"Обнаружена ошибка инициализации (источник: {error_source}): {error_type}", {
            'error_type': error_type,
            'error_url': error_url,
            'error_message': error_message[:200] if error_message else None,
            'source': error_source
        }, category=LogCategory.INITIALIZATION)
        
        if error_type == 'servers_loading':
            resume_servers_url = error_url
            logger.info(f"Будет возобновлена загрузка серверов с URL: {resume_servers_url}", 
                       category=LogCategory.INITIALIZATION)
        elif error_type == 'players_loading':
            resume_players_url = error_url
            logger.info(f"Будет возобновлена загрузка игроков с URL: {resume_players_url}",
                       category=LogCategory.INITIALIZATION)
    
    # Обрабатываем ошибки записи в БД
    db_write_errors = errors_info.get('db_write_errors', [])
    if db_write_errors:
        logger.warning(f"Обнаружено {len(db_write_errors)} ошибок записи в БД", {
            'errors_count': len(db_write_errors)
        }, category=LogCategory.DBWRITE)
        
        # Выводим первые 5 ошибок для информации
        for i, error in enumerate(db_write_errors[:5], 1):
            logger.error(f"Ошибка записи в БД #{i}: {error.get('error_message', '')[:100]}", {
                'log_file': error.get('log_file'),
                'line_number': error.get('line_number')
            }, category=LogCategory.DBWRITE)
    
    # Используем информацию для возобновления из checker
    resume_info = errors_info.get('resume_info', {})
    if resume_info.get('servers_url'):
        resume_servers_url = resume_info['servers_url']
    if resume_info.get('players_url'):
        resume_players_url = resume_info['players_url']
    if resume_info.get('source'):
        error_source = resume_info['source']
    
    # Проверяем заполненность таблиц перед загрузкой
    stats = repo.get_service_stats()
    servers_count = stats.get('total_servers', 0)
    players_count = stats.get('total_players', 0)
    
    logger.info("Проверка заполненности таблиц", {
        'servers_count': servers_count,
        'players_count': players_count,
        'resume_servers_url': resume_servers_url is not None,
        'resume_players_url': resume_players_url is not None
    })
    
    # Если таблицы уже заполнены И нет URL для возобновления, пропускаем загрузку
    if servers_count > 0 and players_count > 0 and not resume_servers_url and not resume_players_url:
        logger.info("Таблицы servers и players уже заполнены, пропускаем первичную загрузку", {
            'servers_count': servers_count,
            'players_count': players_count
        })
        # Очищаем состояние инициализации, если оно было
        if init_error:
            repo.clear_initialization_state(admin_id=ADMIN_ID)
        logger.section("ПЕРВИЧНАЯ ЗАГРУЗКА ДАННЫХ ЗАВЕРШЕНА (пропущена)")
        return
    
    # Если есть URL для возобновления, но таблицы заполнены, все равно пытаемся возобновить
    if (resume_servers_url or resume_players_url) and (servers_count > 0 or players_count > 0):
        logger.warning("Обнаружен URL для возобновления загрузки, но таблицы уже заполнены. Пытаемся возобновить загрузку с сохраненного URL", {
            'servers_count': servers_count,
            'players_count': players_count,
            'resume_servers_url': resume_servers_url is not None,
            'resume_players_url': resume_players_url is not None
        }, category=LogCategory.INITIALIZATION)
    
    bm_response = BattleMetricsResponse()
    
    # Инициализируем с пустым словарем серверов (для первичной загрузки)
    logger.info("Инициализация BattleMetricsResponse")
    await bm_response.async_initialize({})
    logger.info("BattleMetricsResponse инициализирован")
    
    # Получаем все существующие server_id из БД для проверки перед вставкой в players_servers
    existing_server_ids = set(repo.get_all_server_ids())
    logger.info(f"Загружено {len(existing_server_ids)} server_id из БД для проверки", {
        'servers_in_db': len(existing_server_ids)
    })
    
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
                def insert_servers_page(servers_page: list, current_url: str = None) -> int:
                    """Вставляет серверы со страницы в БД, работая с RustServer объектами"""
                    if servers_page:
                        try:
                            # servers_page содержит объекты RustServer, а не словари
                            rust_servers = []
                            servers_for_insert = []
                            
                            for server_obj in servers_page:
                                # Проверяем, что это объект RustServer или Server
                                if not isinstance(server_obj, (RustServer, Server)):
                                    continue
                                
                                server_id = server_obj.id
                                if not server_id:
                                    continue
                                
                                # Добавляем server_id в множество существующих серверов
                                existing_server_ids.add(str(server_id))
                                
                                # Используем уже созданный объект RustServer
                                if isinstance(server_obj, RustServer):
                                    rust_servers.append(server_obj)
                                
                                # Также добавляем базовые данные для таблицы servers
                                servers_for_insert.append({
                                    'id': server_id,
                                    'name': server_obj.name,
                                    'rank': server_obj.rank,
                                    'private': server_obj.private,
                                    'country': server_obj.country
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
                                logger.warning(f"bulk_insert_servers вернул 0 для {len(servers_page)} серверов",
                                             category=LogCategory.DBWRITE)
                            
                            return added_servers
                        except Exception as e:
                            logger.error(f"Ошибка при вставке серверов: {e}", category=LogCategory.DBWRITE)
                            import traceback
                            error_traceback = traceback.format_exc()
                            logger.error(error_traceback, category=LogCategory.DBWRITE)
                            
                            # Сохраняем состояние инициализации с URL текущей страницы для возобновления
                            if current_url:
                                try:
                                    error_message = f"Ошибка при вставке серверов: {e}"
                                    repo.save_initialization_state('servers_loading', current_url, error_message, ADMIN_ID)
                                    logger.critical(f"URL страницы, на которой произошла ошибка: {current_url}",
                                                  category=LogCategory.INITIALIZATION)
                                except Exception as db_error:
                                    logger.error(f"Не удалось сохранить состояние инициализации: {db_error}",
                                               category=LogCategory.DBWRITE)
                            
                            return 0
                    return 0
                
                servers = await bm_response.async_get_all_rust_servers(
                    session, 
                    page_size=100,
                    on_page_callback=insert_servers_page,
                    resume_url=resume_servers_url
                )
                servers_time = (datetime.now() - servers_start).total_seconds()
                
                # Обновляем список существующих server_id после загрузки серверов
                existing_server_ids = set(repo.get_all_server_ids())
                logger.info(f"Обновлено множество server_id после загрузки серверов: {len(existing_server_ids)}", {
                    'servers_in_db': len(existing_server_ids)
                })
                
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
                
                logger.critical(f"Критическая ошибка при загрузке серверов: {error_message}",
                               category=LogCategory.INITIALIZATION)
                logger.critical(f"URL страницы, на которой остановилось заполнение: {error_url}",
                               category=LogCategory.INITIALIZATION)
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(error_traceback, category=LogCategory.INITIALIZATION)
                
                # Сохраняем состояние инициализации для последующего возобновления
                try:
                    repo.save_initialization_state(error_type, error_url, error_message, ADMIN_ID)
                except Exception as db_error:
                    logger.error(f"Не удалось сохранить состояние инициализации в БД: {db_error}",
                               category=LogCategory.DBWRITE)
                
                # Логируем в БД
                try:
                    repo.log_system_error(
                        object='InitializeDB',
                        action='initialize_data_servers',
                        comment=f'Ошибка при инициализации данных: загрузка серверов остановилась. URL: {error_url}',
                        result=f'{error_message}\n\n{error_traceback}',
                        admin_id=ADMIN_ID
                    )
                except Exception as db_error:
                    logger.error(f"Не удалось записать системную ошибку в БД: {db_error}",
                               category=LogCategory.DBWRITE)
                
                # Уведомляем администратора
                await notify_admin(error_message, error_url, error_type)
                
                # Пробрасываем исключение дальше
                raise
            except Exception as e:
                # Другие ошибки при загрузке серверов
                error_message = str(e)
                logger.error(f"Ошибка при загрузке серверов: {error_message}",
                           category=LogCategory.INITIALIZATION)
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(error_traceback, category=LogCategory.INITIALIZATION)
                
                # Логируем в БД (без URL, так как это не ошибка API)
                try:
                    repo.log_system_error(
                        object='InitializeDB',
                        action='initialize_data_servers',
                        comment='Ошибка при загрузке серверов при инициализации данных',
                        result=f'{error_message}\n\n{error_traceback}',
                        admin_id=ADMIN_ID
                    )
                except Exception as db_error:
                    logger.error(f"Не удалось записать системную ошибку в БД: {db_error}",
                               category=LogCategory.DBWRITE)
                
                # Уведомляем администратора
                await notify_admin(error_message, None, 'servers_loading')
                
                # Пробрасываем исключение дальше
                raise
        else:
            logger.info("Таблица servers уже заполнена, пропускаем загрузку серверов", {
                'servers_count': servers_count
            })
            # Обновляем список существующих server_id из БД
            existing_server_ids = set(repo.get_all_server_ids())
            logger.info(f"Загружено {len(existing_server_ids)} server_id из БД", {
                'servers_in_db': len(existing_server_ids)
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
                def insert_players_page(page_data: dict, current_url: str = None) -> int:
                    """Вставляет игроков со страницы в БД, а также их связи с серверами"""
                    if isinstance(page_data, dict):
                        players_page = page_data.get('players', [])
                        player_servers = page_data.get('player_servers', [])
                    else:
                        # Обратная совместимость: если передали список напрямую
                        players_page = page_data if isinstance(page_data, list) else []
                        player_servers = []
                    
                    try:
                        added = 0
                        if players_page:
                            added = repo.bulk_insert_players(players_page)
                            total_added_players[0] += added
                        
                        # Обрабатываем связи игрок-сервер, если они есть
                        # Фильтруем только те связи, где server_id существует в БД
                        if player_servers:
                            # Фильтруем player_servers, оставляя только те, где server_id существует в БД
                            valid_player_servers = []
                            skipped_count = 0
                            for link in player_servers:
                                server_id = str(link.get('server_id', ''))
                                if server_id in existing_server_ids:
                                    valid_player_servers.append(link)
                                else:
                                    skipped_count += 1
                            
                            if skipped_count > 0:
                                logger.debug(f"Пропущено {skipped_count} связей игрок-сервер (server_id не найден в БД)", {
                                    'skipped_links': skipped_count,
                                    'valid_links': len(valid_player_servers)
                                })
                            
                            if valid_player_servers:
                                added_links = repo.bulk_insert_player_servers(valid_player_servers)
                                logger.debug(f"Добавлено/обновлено связей игрок-сервер: {added_links}", {
                                    'links_count': added_links
                                })
                                # Логируем в logs
                                repo.log_action(
                                    object='InitializeDB',
                                    action='bulk_insert_player_servers_initial',
                                    comment=f'Первичное заполнение: добавлено/обновлено {added_links} связей игрок-сервер',
                                    result=f'Success: {added_links} links'
                                )
                        
                        return added
                    except Exception as e:
                        logger.error(f"Ошибка при вставке игроков: {e}", category=LogCategory.DBWRITE)
                        import traceback
                        error_traceback = traceback.format_exc()
                        logger.error(error_traceback, category=LogCategory.DBWRITE)
                        
                        # Сохраняем состояние инициализации с URL текущей страницы для возобновления
                        if current_url:
                            try:
                                error_message = f"Ошибка при вставке игроков: {e}"
                                repo.save_initialization_state('players_loading', current_url, error_message, ADMIN_ID)
                                logger.critical(f"URL страницы, на которой произошла ошибка: {current_url}",
                                              category=LogCategory.INITIALIZATION)
                            except Exception as db_error:
                                logger.error(f"Не удалось сохранить состояние инициализации: {db_error}",
                                           category=LogCategory.DBWRITE)
                        
                        return 0
                
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
                                        from src.data_classes import Player
                                        if isinstance(player, Player):
                                            if repo.update_player_info(player):
                                                players_updated += 1
                                            
                                            # Также обновляем связи игрок-сервер из полных данных игрока
                                            if player.player_servers_meta:
                                                links_updated = repo.update_players_servers_from_player(player)
                                                if links_updated > 0:
                                                    logger.debug(f"Обновлено {links_updated} связей игрок-сервер для игрока {player_id}")
                                
                                # Небольшая задержка между батчами, чтобы не перегружать API
                                if i + batch_size < len(player_ids):
                                    await asyncio.sleep(0.5)
                            
                            if players_updated > 0:
                                logger.info(f"Обновлено записей в players с полными данными: {players_updated}", {
                                    'players_updated': players_updated
                                })
                                # Логируем в logs_sql
                                repo.log_action(
                                    object='InitializeDB',
                                    action='update_players_full_data_initial',
                                    comment=f'Первичное обновление: обновлено {players_updated} записей в players с полными данными',
                                    result=f'Success: {players_updated} records'
                                )
                            else:
                                logger.warning("Не удалось получить полные данные игроков для обновления")
                    except Exception as e:
                        error_message = str(e)
                        logger.error(f"Ошибка при обновлении полных данных игроков: {error_message}",
                                   category=LogCategory.INITIALIZATION)
                        import traceback
                        error_traceback = traceback.format_exc()
                        logger.error(error_traceback, category=LogCategory.INITIALIZATION)
                        
                        # Логируем в БД через log_system_error (для системных ошибок)
                        try:
                            repo.log_system_error(
                                object='InitializeDB',
                                action='update_players_full_data_initial',
                                comment='Ошибка при обновлении полных данных игроков при первичной загрузке',
                                result=f'{error_message}\n\n{error_traceback}',
                                admin_id=ADMIN_ID
                            )
                        except Exception as db_error:
                            logger.error(f"Не удалось записать системную ошибку в БД: {db_error}",
                                       category=LogCategory.DBWRITE)
                        
                        # Уведомляем администратора
                        await notify_admin(error_message, None, 'players_full_data_update')
            except InitializationError as e:
                # Ошибка при получении данных от API с сохранением URL
                error_message = str(e)
                error_url = e.url
                error_type = e.error_type or 'players_loading'
                
                logger.critical(f"Критическая ошибка при загрузке игроков: {error_message}",
                              category=LogCategory.INITIALIZATION)
                logger.critical(f"URL страницы, на которой остановилось заполнение: {error_url}",
                              category=LogCategory.INITIALIZATION)
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(error_traceback, category=LogCategory.INITIALIZATION)
                
                # Сохраняем состояние инициализации для последующего возобновления
                try:
                    repo.save_initialization_state(error_type, error_url, error_message, ADMIN_ID)
                except Exception as db_error:
                    logger.error(f"Не удалось сохранить состояние инициализации в БД: {db_error}",
                               category=LogCategory.DBWRITE)
                
                # Логируем в БД
                try:
                    repo.log_system_error(
                        object='InitializeDB',
                        action='initialize_data_players',
                        comment=f'Ошибка при инициализации данных: загрузка игроков остановилась. URL: {error_url}',
                        result=f'{error_message}\n\n{error_traceback}',
                        admin_id=ADMIN_ID
                    )
                except Exception as db_error:
                    logger.error(f"Не удалось записать системную ошибку в БД: {db_error}",
                               category=LogCategory.DBWRITE)
                
                # Уведомляем администратора
                await notify_admin(error_message, error_url, error_type)
                
                # Пробрасываем исключение дальше
                raise
            except Exception as e:
                # Другие ошибки при загрузке игроков
                error_message = str(e)
                logger.error(f"Ошибка при загрузке игроков: {error_message}",
                           category=LogCategory.INITIALIZATION)
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(error_traceback, category=LogCategory.INITIALIZATION)
                
                # Логируем в БД (без URL, так как это не ошибка API)
                try:
                    repo.log_system_error(
                        object='InitializeDB',
                        action='initialize_data_players',
                        comment='Ошибка при загрузке игроков при инициализации данных',
                        result=f'{error_message}\n\n{error_traceback}',
                        admin_id=ADMIN_ID
                    )
                except Exception as db_error:
                    logger.error(f"Не удалось записать системную ошибку в БД: {db_error}",
                               category=LogCategory.DBWRITE)
                
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


if __name__ == '__main__':
    """
    Скрипт для инициализации базы данных.
    Запускается отдельно, не автоматически при старте основного приложения.
    
    Использование:
        python initialize_database.py
    """
    logger.section("СТАРТ ИНИЦИАЛИЗАЦИИ БАЗЫ ДАННЫХ")
    try:
        asyncio.run(initialize_data())
        logger.section("ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ЗАВЕРШЕНА УСПЕШНО")
    except KeyboardInterrupt:
        logger.warning("Инициализация прервана пользователем (KeyboardInterrupt)")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Критическая ошибка при инициализации: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        # Закрываем файлы логов при завершении
        logger.close()

