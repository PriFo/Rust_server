import traceback
from typing import Any, Union
from datetime import datetime

from src.errorresponse import ErrorResponse as ER
from src.data_classes import ClassFactory as cfact, Player, RustServer, Server
from src.dispatcher import Dispatcher
from src.repository import Repository

from json import loads as make_dict_from_str

from aiohttp import ClientSession, ClientError, ClientTimeout
import aiofiles
from os import getenv
from asyncio import sleep as aSleep
from asyncio import create_task, gather, Semaphore
from typing import Optional
from src.logger import Logger
from urllib.parse import urlencode, quote
import asyncio


class InitializationError(Exception):
    """Исключение для ошибок при инициализации данных с сохранением URL страницы"""
    def __init__(self, message: str, url: str = None, error_type: str = None):
        super().__init__(message)
        self.url = url
        self.error_type = error_type


class EPartitions:
    
    servers: str = '/servers/'
    players: str = '/players/'
    games: str = '/games/'


class BattleMetricsResponse:

    def __init__(self) -> None:
        self._url: str = "https://api.battlemetrics.com"
        self._headers: dict = {}
        self._api_key: str = ''
        self._servers: dict = {}
        self._logger = Logger("BattleMetricsAPI")
        # Семафор для ограничения параллельных запросов (максимум 10 одновременных)
        self._request_semaphore: Optional[Semaphore] = None
        # Таймаут для HTTP запросов
        self._timeout = ClientTimeout(total=30, connect=10)
    
    async def _make_request_with_retry(self, session: ClientSession, url: str, max_retries: int = 3) -> Any:
        """
        Выполняет HTTP запрос с повторными попытками и обработкой rate limit
        
        :param session: aiohttp.ClientSession
        :param url: URL для запроса
        :param max_retries: Максимальное количество повторных попыток
        :return: aiohttp.ClientResponse
        """
        # Инициализируем семафор при первом использовании
        if self._request_semaphore is None:
            self._request_semaphore = Semaphore(10)
        
        async with self._request_semaphore:
            for attempt in range(max_retries):
                try:
                    async with session.get(
                        url=url,
                        headers=self._headers,
                        timeout=self._timeout
                    ) as response:
                        # Проверяем rate limit headers
                        rate_limit_remaining = response.headers.get('X-RateLimit-Remaining')
                        rate_limit_reset = response.headers.get('X-RateLimit-Reset')
                        
                        if rate_limit_remaining:
                            remaining = int(rate_limit_remaining)
                            if remaining <= 5:
                                self._logger.warning(f"Приближение к лимиту rate limit: осталось {remaining} запросов")
                        
                        # Обрабатываем HTTP 429 (Rate Limit)
                        if response.status == 429:
                            if rate_limit_reset:
                                import time
                                reset_timestamp = int(rate_limit_reset)
                                current_timestamp = int(time.time())
                                wait_time = max(0, reset_timestamp - current_timestamp)
                                if wait_time > 0:
                                    self._logger.warning(f"Rate limit достигнут, ожидание {wait_time} секунд до сброса")
                                    await aSleep(wait_time + 1)  # +1 для безопасности
                                    continue
                            else:
                                # Если нет информации о сбросе, ждем экспоненциально
                                wait_time = 2 ** attempt
                                self._logger.warning(f"Rate limit достигнут, ожидание {wait_time} секунд (попытка {attempt + 1})")
                                await aSleep(wait_time)
                                continue
                        
                        # Обрабатываем HTTP 5xx ошибки с повторной попыткой
                        if 500 <= response.status < 600:
                            if attempt < max_retries - 1:
                                wait_time = 2 ** attempt  # Экспоненциальная задержка
                                self._logger.warning(f"Серверная ошибка {response.status}, повтор через {wait_time} сек (попытка {attempt + 1}/{max_retries})")
                                await aSleep(wait_time)
                                continue
                        
                        return response
                        
                except (asyncio.TimeoutError, ClientError) as e:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # Экспоненциальная задержка
                        self._logger.warning(f"Сетевая ошибка: {e}, повтор через {wait_time} сек (попытка {attempt + 1}/{max_retries})")
                        await aSleep(wait_time)
                        continue
                    else:
                        self._logger.error(f"Сетевая ошибка после {max_retries} попыток: {e}")
                        raise
                except Exception as e:
                    self._logger.error(f"Неожиданная ошибка при запросе: {e}")
                    raise
            
            # Если все попытки исчерпаны
            raise Exception(f"Не удалось выполнить запрос после {max_retries} попыток")

    async def _fetch_json_with_retry(
        self, session: "ClientSession", url: str, max_retries: int = 3
    ) -> tuple[int, dict, Any]:
        """
        Выполняет GET с ретраями/429/таймаутом, читает JSON внутри контекста.
        Возвращает (status, headers_dict, data). data — результат response.json() или None.
        """
        if self._request_semaphore is None:
            self._request_semaphore = Semaphore(10)
        async with self._request_semaphore:
            for attempt in range(max_retries):
                try:
                    async with session.get(
                        url=url,
                        headers=self._headers,
                        timeout=self._timeout
                    ) as response:
                        rate_limit_remaining = response.headers.get('X-RateLimit-Remaining')
                        rate_limit_reset = response.headers.get('X-RateLimit-Reset')
                        if rate_limit_remaining:
                            remaining = int(rate_limit_remaining)
                            if remaining <= 5:
                                self._logger.warning(f"Приближение к лимиту rate limit: осталось {remaining} запросов")
                        if response.status == 429:
                            if rate_limit_reset:
                                import time
                                reset_ts = int(rate_limit_reset)
                                wait_time = max(0, reset_ts - int(time.time()))
                                if wait_time > 0:
                                    self._logger.warning(f"Rate limit, ожидание {wait_time} сек")
                                    await aSleep(wait_time + 1)
                                    continue
                            wait_time = 2 ** attempt
                            await aSleep(wait_time)
                            continue
                        if 500 <= response.status < 600:
                            if attempt < max_retries - 1:
                                await aSleep(2 ** attempt)
                                continue
                        try:
                            data = await response.json() if response.status == 200 else None
                        except Exception:
                            data = None
                        headers = dict(response.headers) if response.headers else {}
                        return (response.status, headers, data)
                except (asyncio.TimeoutError, ClientError) as e:
                    if attempt < max_retries - 1:
                        await aSleep(2 ** attempt)
                        continue
                    self._logger.error(f"Сетевая ошибка после {max_retries} попыток: {e}")
                    raise
            raise Exception(f"Не удалось выполнить запрос после {max_retries} попыток")

    async def _async_read_file_as_dict(self, file_path: str) -> dict:
        async with aiofiles.open(file=file_path, mode='r', encoding='utf-8') as file:
            content = await file.read()
            return make_dict_from_str(content)

    async def async_initialize(self, servers: dict[str, Union[str, int]]) -> None:
        """
        Инициализирует BattleMetricsResponse
        
        :param servers: Словарь серверов {название: id} из БД (получается через Repository.get_servers())
        ID могут быть str или int, но для API конвертируются в str
        """
        if isinstance(servers, dict):
            # Конвертируем все ID в str для использования в URL API
            self._servers = {key: str(value) if isinstance(value, int) else value for key, value in servers.items()}
        else:
            raise TypeError(f'Servers must be dict, not {type(servers)=}')
        self._api_key = getenv('BM_API_KEY')

        self._headers['Authorization'] = f'Bearer {self._api_key}'
        
        # Инициализируем семафор при первом использовании API
        if self._request_semaphore is None:
            self._request_semaphore = Semaphore(10)  # Максимум 10 параллельных запросов
    
    async def async_get_servers_info(self, session: ClientSession, filters: dict = None) -> dict:
        """
        Функция получения необходимой информации по серверам с фильтрацией

        :param session: aiohttp.ClientSession - сессия к которой необходимо обратиться
        :param filters: словарь фильтров для API (например, {'game': 'rust'})
            Примечание: фильтры передаются в _get_server_info, но для конкретного сервера они обычно не нужны
        :return: dict - словарь со всей информацией по каждому серверу с типом хранения \n \
            {название_серера: объект_с_информацией_о_сервере}
        """
        if filters is None:
            filters = {}  # Для конкретного сервера фильтры не требуются
        
        servers_list: list = []
        servers_tasks: list = []
            
        # Создание списка отложенных задач на сбор информации по серверам через API
        for value in self._servers.values():
            servers_tasks.append(create_task(self._get_server_info(session, value, filters)))
        servers_list = await gather(*servers_tasks)
        
        servers_dict: dict = {}
        errors_list: list = []
        for class_obj in servers_list:
            if isinstance(class_obj, Server):
                servers_dict[class_obj.name] = class_obj
            else:
                errors_list.append(class_obj)
        
        if errors_list:
            servers_dict['errors'] = errors_list

        return servers_dict
    
    async def async_search_servers(self, session: ClientSession, name: str = None, game_id: str = 'rust', 
                                  country: str = None, status: str = None, page: int = 1) -> dict:
        """
        Поиск серверов через API BattleMetrics с фильтрацией
        
        :param session: aiohttp.ClientSession - сессия для запроса
        :param name: название сервера (частичное совпадение)
        :param game_id: ID игры (например, 'rust' или числовой ID)
        :param country: код страны (например, 'RU')
        :param status: статус сервера ('online', 'offline')
        :param page: номер страницы для пагинации
        :return: словарь с результатами поиска
        """
        filters = {}
        if game_id:
            # Если game_id - строка, пытаемся получить числовой ID
            if isinstance(game_id, str) and not game_id.isdigit():
                # Получаем числовой ID игры
                games_url = self._build_api_url(
                    endpoint=EPartitions.games.rstrip('/'),
                    filters={'name': game_id}
                )
                status, _, games_data = await self._fetch_json_with_retry(session, games_url)
                if status == 200 and games_data:
                    games = games_data.get('data', [])
                    if games:
                        game_id = str(games[0].get('id', ''))
            filters['game'] = game_id  # Используем единственное число 'game'
        if name:
            filters['search'] = name
        if country:
            filters['country'] = country
        if status:
            filters['status'] = status
        
        url = self._build_api_url(
            endpoint=EPartitions.servers.rstrip('/'),
            filters=filters,
            include=None,  # API не поддерживает include=game для серверов (только serverGroup)
            fields={'server': 'id,name,status,players,maxPlayers,ip,port,private,queryStatus,country,address,updatedAt,createdAt,portQuery,rank'},
            page=page
        )
        
        self._logger.debug("Поиск серверов", {
            'url': url,
            'filters': filters,
            'page': page
        })
        
        status, _, data = await self._fetch_json_with_retry(session, url)
        if status == 200 and data:
            servers_count = len(data.get('data', []))
            self._logger.info(f"Найдено серверов: {servers_count}", {
                'count': servers_count,
                'page': page,
                'filters': filters
            })
            return data
        error_obj = ER()
        try:
            error_obj.initialize("HTTPError", f"Status {status}" if data is None else str(data))
        except Exception:
            error_obj.initialize("HTTPError", f"Status {status}")
        self._logger.error(f"Ошибка при поиске серверов: {error_obj}", {
            'status': status,
            'error': str(error_obj),
            'filters': filters
        })
        return {'errors': [error_obj]}
    
    def _build_api_url(self, endpoint: str, filters: dict = None, include: list = None, fields: dict = None, 
                      page: int = None, page_size: int = None, sort: str = None) -> str:
        """Строит URL для API запроса с фильтрами согласно JSON:API спецификации
        
        Args:
            endpoint: endpoint API (например, /servers/123)
            filters: словарь фильтров (например, {'game': 'rust', 'status': 'online'})
            include: список связанных ресурсов для включения
            fields: словарь полей для выборки {resource: 'field1,field2'}
            page: номер страницы для пагинации (устаревший, рекомендуется использовать links из ответа)
            page_size: размер страницы (количество элементов на странице, 1-100)
            sort: сортировка (например, 'rank' для сортировки по рейтингу, '-timestamp' для убывания)
            
        Returns:
            str: полный URL с параметрами
        """
        url = f'{self._url}{endpoint}'
        params = []
        
        # Фильтры в формате filter[key]=value согласно JSON:API
        # Квадратные скобки в ключах не кодируются, только значения
        if filters:
            for key, value in filters.items():
                # Правильное URL-кодирование значения
                if isinstance(value, (int, float)):
                    encoded_value = str(value)
                else:
                    encoded_value = quote(str(value), safe='')
                # Ключ может содержать специальные символы, но обычно это просто строка
                encoded_key = quote(str(key), safe='')
                params.append(f"filter[{encoded_key}]={encoded_value}")
        
        # Include параметр: include=resource1,resource2
        if include:
            # Ресурсы разделяются запятыми, каждый ресурс кодируется отдельно
            encoded_include = ','.join(quote(str(res), safe='') for res in include)
            params.append(f"include={encoded_include}")
        
        # Fields параметр: fields[resource]=field1,field2
        if fields:
            for resource, field_list in fields.items():
                # Поля разделены запятыми, кодируем каждый отдельно, но сохраняем запятые как разделители
                if isinstance(field_list, str):
                    field_items = [f.strip() for f in field_list.split(',') if f.strip()]
                    encoded_fields = ','.join(quote(f, safe='') for f in field_items)
                else:
                    encoded_fields = ','.join(quote(str(f), safe='') for f in field_list)
                # Ресурс кодируется отдельно
                encoded_resource = quote(str(resource), safe='')
                params.append(f"fields[{encoded_resource}]={encoded_fields}")
        
        # Page size параметр: page[size]=20 (согласно документации BattleMetrics API)
        # Размер страницы: 1-100, по умолчанию 10
        if page_size is not None:
            if 1 <= page_size <= 100:
                params.append(f"page[size]={page_size}")
            else:
                self._logger.warning(f"page_size={page_size} вне допустимого диапазона (1-100), игнорируем")
        
        # Sort параметр: sort=attribute или sort=-attribute для убывания
        if sort:
            # Сортируем по атрибуту, экранируем значение
            encoded_sort = quote(str(sort), safe='-,')
            params.append(f"sort={encoded_sort}")
        
        if params:
            url += "?" + "&".join(params)
        
        return url
    
    async def _get_server_info(self, session: ClientSession, server_id: Union[str, int], filters: dict = None):
        """Получает информацию о сервере с фильтрами"""
        # Конвертируем server_id в str для URL (API работает со строками)
        server_id_str = str(server_id) if isinstance(server_id, int) else server_id
        # Запрашиваем все поля, включая details (details приходят автоматически в ответе API)
        # Не указываем fields, чтобы получить все данные включая details
        url = self._build_api_url(
            endpoint=f'{EPartitions.servers}{server_id_str}',
            filters=filters,
            include=['game']
            # Не указываем fields, чтобы получить все данные сервера включая details
        )
        status, _, data = await self._fetch_json_with_retry(session, url)
        if status == 200 and data:
            return cfact.get_object(data)
        error_obj = ER()
        try:
            error_obj.initialize("HTTPError", f"Status {status}" if data is None else str(data))
        except Exception:
            error_obj.initialize("HTTPError", f"Status {status}")
        return error_obj
    
    async def get_cur_server_info(self) -> Server:
        """Получает информацию о текущем сервере (не реализовано)"""
        raise NotImplementedError("Method get_cur_server_info is not implemented")
    
    async def async_get_player_info(self, session: ClientSession, player_id: Union[str, int], page: int = 1) -> Union[Player, ER]:
        """
        Получает информацию об игроке по ID с поддержкой пагинации
        
        :param session: aiohttp.ClientSession - сессия для запроса
        :param player_id: ID игрока на BattleMetrics (int внутри, str для API)
        :param page: номер страницы для пагинации серверов игрока
        :return: Объект Player или ErrorResponse
        """
        # Конвертируем player_id в str для URL (API работает со строками)
        player_id_str = str(player_id) if isinstance(player_id, int) else player_id
        url = self._build_api_url(
            endpoint=f'{EPartitions.players}{player_id_str}',
            include=['server'],
            fields={'server': 'name,id'},
            page=page
        )
        status, _, data = await self._fetch_json_with_retry(session, url)
        if status == 200 and data:
            return cfact.get_object(data)
        error_obj = ER()
        try:
            error_obj.initialize("HTTPError", f"Status {status}" if data is None else str(data))
        except Exception as e:
            self._logger.warning(f"Неожиданная ошибка при парсинге ошибки API: {e}")
            error_obj.initialize("HTTPError", f"Status {status}")
        return error_obj
    
    async def async_get_players_info(self, session: ClientSession, player_ids: list[Union[str, int]]) -> dict:
        """
        Получает информацию о нескольких игроках
        
        :param session: aiohttp.ClientSession - сессия для запроса
        :param player_ids: Список ID игроков (int внутри, str для API)
        :return: Словарь {player_id: Player или ErrorResponse}
        """
        players_tasks = [
            create_task(self.async_get_player_info(session, player_id))
            for player_id in player_ids
        ]
        players_list = await gather(*players_tasks)
        
        players_dict: dict = {}
        errors_list: list = []
        for i, player_obj in enumerate(players_list):
            if isinstance(player_obj, Player):
                players_dict[player_ids[i]] = player_obj
            else:
                errors_list.append(player_obj)
        
        if errors_list:
            players_dict['errors'] = errors_list
        
        return players_dict
    
    async def async_get_all_rust_servers(self, session: ClientSession, page_size: int = 100, 
                                        on_page_callback=None, resume_url: str = None) -> list[dict]:
        """
        Получает все серверы Rust с пагинацией
        
        :param session: aiohttp.ClientSession - сессия для запроса
        :param page_size: размер страницы (максимум 100 по API)
        :param on_page_callback: функция-колбэк для обработки каждой страницы данных
            Принимает список серверов со страницы и URL: callback(servers: list[dict], url: str) -> int
            Возвращает количество добавленных записей
        :param resume_url: URL для возобновления загрузки с определенной страницы (если указан, начинает с этого URL)
        :return: список всех серверов Rust в формате [{'id': str, 'name': str}, ...]
        """
        all_servers = []
        total_added = 0
        self._api_key = getenv('BM_API_KEY')
        self._headers['Authorization'] = f'Bearer {self._api_key}'
        
        self._logger.info("Начало получения всех серверов Rust", {
            'page_size': page_size,
            'endpoint': EPartitions.servers
        })
        
        # Получаем game_id для Rust
        # Endpoint /games не поддерживает фильтры, поэтому получаем все игры с пагинацией
        game_id = None
        games_url = self._build_api_url(
            endpoint=EPartitions.games.rstrip('/'),
            page_size=100  # Получаем больше игр за раз
        )
        current_url = games_url
        
        self._logger.debug("Получение всех игр для поиска Rust", {'url': current_url})
        
        while game_id is None:
            status, _, games_data = await self._fetch_json_with_retry(session, current_url)
            if status == 200 and games_data:
                games_list = games_data.get('data', [])
                self._logger.debug(f"Получено игр на странице: {len(games_list)}", {
                    'games_count': len(games_list),
                    'game_names': [g.get('attributes', {}).get('name', '') for g in games_list[:10]]
                })
                for game in games_list:
                    game_name = game.get('attributes', {}).get('name', '').lower()
                    if game_name == 'rust':
                        game_id = str(game.get('id', ''))
                        self._logger.info(f"Найден game_id для Rust: {game_id}", {'game_id': game_id})
                        break
                if game_id:
                    break
                links = games_data.get('links', {})
                next_url = links.get('next')
                if not next_url:
                    self._logger.debug("Больше страниц с играми нет")
                    break
                current_url = next_url
            else:
                self._logger.error(f"Ошибка при получении игр: {status}", {
                    'status': status,
                    'url': current_url
                })
                break
        
        # Если не удалось найти, используем известный ID из БД (Rust = 1)
        if not game_id:
            self._logger.warning("Не удалось найти game_id для Rust через API, используем известный ID: 1")
            game_id = '1'  # Известный ID для Rust в BattleMetrics (подтверждено в БД)
        
        self._logger.info(f"Используется game_id для запроса серверов: {game_id}", {'game_id': game_id})
        
        # Используем links из ответа для пагинации вместо page параметра
        # Запрашиваем все поля сервера, включая details для Rust-специфичных данных
        if resume_url:
            # Возобновляем загрузку с указанного URL
            current_url = resume_url
            self._logger.info(f"Возобновление загрузки серверов с URL: {resume_url}")
        else:
            first_url = self._build_api_url(
                endpoint=EPartitions.servers.rstrip('/'),
                filters={'game': game_id},
                include=None,  # API не поддерживает include=game для серверов
                fields={'server': 'id,name,status,players,maxPlayers,ip,port,private,queryStatus,country,address,updatedAt,createdAt,portQuery,rank,details'},
                page=None,  # Не передаем page для первой страницы
                page_size=page_size
            )
            current_url = first_url
        
        while True:
            self._logger.debug(f"Запрос серверов", {
                'url': current_url,
                'current_count': len(all_servers)
            })
            status, _, data = await self._fetch_json_with_retry(session, current_url)
            if status == 200 and data:
                servers_data = data.get('data', [])
                if not servers_data:
                    self._logger.info("Страница пуста, завершение", {
                        'response_keys': list(data.keys()),
                        'meta': data.get('meta', {}),
                        'links': data.get('links', {})
                    })
                    break
                page_servers = []
                for server in servers_data:
                    server_id = str(server.get('id', ''))
                    server_attrs = server.get('attributes', {})
                    server_name = server_attrs.get('name', '')
                    if server_id and server_name:
                        server_obj = cfact.get_object({'data': server})
                        if isinstance(server_obj, (Server, RustServer)):
                            page_servers.append(server_obj)
                            all_servers.append(server_obj)
                if on_page_callback and page_servers:
                    try:
                        added = on_page_callback(page_servers, current_url)
                        total_added += added
                        self._logger.info(f"Получено и обработано серверов: {len(page_servers)} (добавлено: {added})", {
                            'servers_on_page': len(page_servers),
                            'added_on_page': added,
                            'total_servers': len(all_servers),
                            'total_added': total_added
                        })
                    except Exception as e:
                        self._logger.error(f"Ошибка при обработке страницы серверов: {e}")
                        import traceback
                        self._logger.error(traceback.format_exc())
                else:
                    self._logger.info(f"Получено серверов: {len(page_servers)}", {
                        'servers_on_page': len(page_servers),
                        'total_servers': len(all_servers)
                    })
                # Проверяем наличие следующей страницы через links
                links = data.get('links', {})
                next_url = links.get('next')
                if not next_url:
                    self._logger.info("Следующей страницы нет, завершение")
                    break
                current_url = next_url
                await aSleep(0.1)
            else:
                error_obj = ER()
                try:
                    if data:
                        error_obj.initialize(data=data)
                    else:
                        error_obj.initialize("HTTPError", f"Status {status}")
                except Exception:
                    error_obj.initialize("HTTPError", f"Status {status}")
                self._logger.error(f"Ошибка при получении серверов: {error_obj}", {
                    'status': status,
                    'error': str(error_obj),
                    'url': current_url
                })
                raise InitializationError(
                    message=f"Ошибка при получении серверов: {error_obj}",
                    url=current_url,
                    error_type='servers_loading'
                )
        
        self._logger.info(f"Завершено получение серверов. Всего: {len(all_servers)}", {
            'total_servers': len(all_servers),
            'total_added': total_added if on_page_callback else len(all_servers)
        })
        return all_servers
    
    async def async_get_all_rust_players(self, session: ClientSession, page_size: int = 100,
                                        on_page_callback=None, resume_url: str = None) -> list[dict]:
        """
        Получает всех игроков Rust с пагинацией
        
        Примечание: API BattleMetrics может не поддерживать прямую фильтрацию игроков по игре.
        В этом случае получаем всех игроков, которые играли на Rust серверах.
        
        :param session: aiohttp.ClientSession - сессия для запроса
        :param page_size: размер страницы (максимум 100 по API)
        :param on_page_callback: функция-колбэк для обработки каждой страницы данных
            Принимает список игроков со страницы: callback(players: list[dict]) -> int
            Возвращает количество добавленных записей
        :param resume_url: URL для возобновления загрузки с определенной страницы (если указан, начинает с этого URL)
        :return: список всех игроков Rust в формате [{'id': str, 'name': str}, ...]
        """
        all_players = []
        total_added = 0
        self._api_key = getenv('BM_API_KEY')
        self._headers['Authorization'] = f'Bearer {self._api_key}'
        
        self._logger.info("Начало получения всех игроков", {
            'page_size': page_size,
            'endpoint': EPartitions.players
        })
        
        # API BattleMetrics не поддерживает фильтрацию игроков по игре
        # Получаем всех игроков без фильтра
        # Используем links из ответа для пагинации
        if resume_url:
            # Возобновляем загрузку с указанного URL
            current_url = resume_url
            self._logger.info(f"Возобновление загрузки игроков с URL: {resume_url}")
        else:
            self._logger.info("API BattleMetrics не поддерживает фильтрацию игроков по игре, получаем всех игроков")
            first_url = self._build_api_url(
                endpoint=EPartitions.players.rstrip('/'),
                filters=None,  # Не используем фильтр по игре, так как он не поддерживается
                include=['server'],  # Запрашиваем связанные серверы игроков
                fields={'player': 'id,name', 'server': 'name,id'},  # Поля для игроков и серверов
                page=None,
                page_size=page_size
            )
            current_url = first_url
        
        while True:
            self._logger.debug(f"Запрос игроков", {
                'url': current_url,
                'current_count': len(all_players)
            })
            status, _, data = await self._fetch_json_with_retry(session, current_url)
            if status == 200 and data:
                players_data = data.get('data', [])
                included_data = data.get('included', [])
                if not players_data:
                    self._logger.info("Страница пуста, завершение")
                    break
                servers_map = {}
                for item in included_data:
                    if item.get('type') == 'server':
                        server_id = str(item.get('id', ''))
                        server_name = item.get('attributes', {}).get('name', '')
                        servers_map[server_id] = {'id': server_id, 'name': server_name}
                page_players = []
                page_player_servers = []
                for player in players_data:
                    player_id = str(player.get('id', ''))
                    player_name = player.get('attributes', {}).get('name', '')
                    if player_id and player_name:
                        player_obj = cfact.get_object({'data': player})
                        if isinstance(player_obj, Player):
                            page_players.append(player_obj)
                            all_players.append(player_obj)
                        relationships = player.get('relationships', {})
                        servers_relationship = relationships.get('servers', {})
                        player_servers_data = servers_relationship.get('data', [])
                        for server_ref in player_servers_data:
                            server_type = server_ref.get('type')
                            server_id = str(server_ref.get('id', ''))
                            server_meta = server_ref.get('meta', {})
                            if server_type == 'server' and server_id in servers_map:
                                page_player_servers.append({
                                    'player_id': int(player_id) if player_id.isdigit() else player_id,
                                    'server_id': int(server_id) if server_id.isdigit() else server_id,
                                    'time_played': server_meta.get('timePlayed', 0),
                                    'is_online': server_meta.get('online', False),
                                    'first_seen': self._parse_datetime(server_meta.get('firstSeen')),
                                    'last_seen': self._parse_datetime(server_meta.get('lastSeen'))
                                })
                if on_page_callback and page_players:
                    try:
                        callback_data = {
                            'players': page_players,
                            'player_servers': page_player_servers
                        }
                        added = on_page_callback(callback_data, current_url)
                        total_added += added
                        self._logger.info(f"Получено и обработано игроков: {len(page_players)} (добавлено: {added}), связей с серверами: {len(page_player_servers)}", {
                            'players_on_page': len(page_players),
                            'added_on_page': added,
                            'player_servers_links': len(page_player_servers),
                            'total_players': len(all_players),
                            'total_added': total_added
                        })
                    except Exception as e:
                        self._logger.error(f"Ошибка при обработке страницы игроков: {e}")
                        import traceback
                        self._logger.error(traceback.format_exc())
                else:
                    self._logger.info(f"Получено игроков: {len(page_players)}, связей с серверами: {len(page_player_servers)}", {
                        'players_on_page': len(page_players),
                        'player_servers_links': len(page_player_servers),
                        'total_players': len(all_players)
                    })
                links = data.get('links', {})
                next_url = links.get('next')
                if not next_url:
                    self._logger.info("Следующей страницы нет, завершение")
                    break
                current_url = next_url
                await aSleep(0.1)
            else:
                error_obj = ER()
                try:
                    if data:
                        error_obj.initialize(data=data)
                    else:
                        error_obj.initialize("HTTPError", f"Status {status}")
                except Exception:
                    error_obj.initialize("HTTPError", f"Status {status}")
                self._logger.error(f"Ошибка при получении игроков: {error_obj}", {
                    'status': status,
                    'error': str(error_obj),
                    'url': current_url
                })
                raise InitializationError(
                    message=f"Ошибка при получении игроков: {error_obj}",
                    url=current_url,
                    error_type='players_loading'
                )
        
        self._logger.info(f"Завершено получение игроков. Всего: {len(all_players)}", {
            'total_players': len(all_players),
            'total_added': total_added if on_page_callback else len(all_players)
        })
        return all_players
    
    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Парсит строку в datetime"""
        if not dt_str:
            return None
        try:
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%fZ'):
                try:
                    return datetime.strptime(dt_str, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return None


class BattleMetricsController:

    def __init__(self, repository: Optional['Repository'] = None) -> None:
        from src.repository import Repository
        # Принимаем repository явно или создаем через Dispatcher для обратной совместимости
        if repository is None:
            self._dp: Dispatcher = Dispatcher()
            self._repo: Repository = self._dp.repo
        else:
            self._repo: Repository = repository
            self._dp: Dispatcher = Dispatcher()
            # Устанавливаем repository в Dispatcher для совместимости
            self._dp._repo = repository
        self._servers_json_path: str = 'jsons/servers.json'
        self._bm_response: BattleMetricsResponse = BattleMetricsResponse()
        self._servers_info: dict = {}
        self._players_info: dict = {}
        self._logger = Logger("BattleMetricsController")
        self._servers_to_update = set()
        self._players_to_update = set()
        self._session: Optional[ClientSession] = None
        self.stop_event: Optional[asyncio.Event] = None

    async def update_info(self, delay: int = 5, stop_event: Optional[asyncio.Event] = None) -> None:
        """
        Постоянный процесс обновления информации о серверах и игроках.
        Работает в бесконечном цикле, проверяя наличие активных пользователей и данных для мониторинга каждые 5 секунд.
        
        :param delay: Задержка между итерациями в секундах
        :param stop_event: Событие для сигнала остановки (опционально)
        """
        self.stop_event = stop_event
        self._logger.section("ЗАПУСК СЕРВИСА ОБНОВЛЕНИЯ ИНФОРМАЦИИ")
        self._logger.info("Инициализация сервиса обновления", {'delay': delay, 'mode': 'continuous'})
        
        # Создаем HTTP-сессию один раз при старте
        self._session = ClientSession()
        
        try:
            # Флаги для отслеживания состояния логирования (чтобы логировать только один раз при входе в состояние ожидания)
            no_active_users_logged = False
            no_data_to_monitor_logged = False
            
            while not (self.stop_event and self.stop_event.is_set()):
                try:
                    # Проверка 1: Есть ли активные профили?
                    active_profiles = self._repo.get_active_profiles()
                    if not active_profiles:
                        if not no_active_users_logged:
                            self._logger.info("Нет активных пользователей, процесс ушел в ожидание. Проверка каждые 5 секунд.")
                            no_active_users_logged = True
                            no_data_to_monitor_logged = False  # Сброс флага, чтобы логировать при следующем изменении
                        await aSleep(delay)
                        continue
                    
                    # Если появились активные пользователи после ожидания, сбрасываем флаг
                    if no_active_users_logged:
                        self._logger.info("Обнаружены активные пользователи, возобновляем обновление данных")
                        no_active_users_logged = False
                    
                    # Проверка 2: Есть ли у активных профилей данные для мониторинга (серверы или игроки)?
                    servers = self._repo.get_servers_for_active_profiles(active_profiles)
                    player_ids = self._repo.get_players_for_active_profiles(active_profiles)
                    
                    if not servers and not player_ids:
                        if not no_data_to_monitor_logged:
                            self._logger.info("Нет данных для мониторинга (ни серверов, ни игроков), процесс ушел в ожидание. Проверка каждые 5 секунд.")
                            no_data_to_monitor_logged = True
                        await aSleep(delay)
                        continue
                    
                    # Если появились данные после ожидания, сбрасываем флаг
                    if no_data_to_monitor_logged:
                        self._logger.info("Обнаружены данные для мониторинга, возобновляем обновление")
                        no_data_to_monitor_logged = False
                    
                    self._logger.info(f"Найдено активных пользователей: {len(active_profiles)}", {
                        'active_profiles_count': len(active_profiles),
                        'servers_count': len(servers),
                        'players_count': len(player_ids)
                    })
                    
                    # Инициализируем только если есть серверы для отслеживания
                    if servers:
                        await self._bm_response.async_initialize(servers)
                        self._logger.info("BattleMetricsResponse инициализирован")
                    
                    last_info: dict = {}
                    last_players_info: dict = {}
                    # Кэш хешей для быстрого сравнения
                    last_hashes: dict[str, int] = {}
                    last_players_hashes: dict[str, int] = {}
                   
                    # Используем созданную ранее сессию
                    session = self._session
                    # Первичная загрузка информации о серверах (только если есть серверы)
                    if servers:
                        self._logger.info("Первичная загрузка информации о серверах")
                        self._servers_info = await self._bm_response.async_get_servers_info(session)
                        errors: Union[list, None] = self._servers_info.get('errors')
                        if errors:
                            self._logger.warning(f"Обнаружено ошибок при первичной загрузке: {len(errors)}")
                            await self._dp.handle_errors(errors)
                            # Удаляем ошибки из словаря для дальнейшей обработки
                            self._servers_info.pop('errors', None)
                        
                        self._logger.info(f"Успешно загружено серверов: {len(self._servers_info)}", {
                            'servers_loaded': len(self._servers_info)
                        })
                        
                        # Обновляем информацию о серверах в БД
                        servers_updated = 0
                        for server_name, server in self._servers_info.items():
                            if server_name != 'errors' and isinstance(server, Server):
                                if self._repo.update_server_info(server):
                                    servers_updated += 1
                        
                        if servers_updated > 0:
                            self._logger.debug(f"Обновлено записей в servers: {servers_updated}", {
                                'servers_updated': servers_updated
                            })
                        
                        # Заполняем rust_servers для всех Rust серверов
                        rust_servers_to_insert = []
                        for server_name, server in self._servers_info.items():
                            if server_name != 'errors' and isinstance(server, RustServer):
                                rust_servers_to_insert.append(server)
                        
                        if rust_servers_to_insert:
                            self._logger.info(f"Заполнение rust_servers для {len(rust_servers_to_insert)} серверов")
                            inserted_count = self._repo.bulk_insert_rust_servers(rust_servers_to_insert)
                            self._logger.info(f"Добавлено/обновлено записей в rust_servers: {inserted_count}", {
                                'rust_servers_inserted': inserted_count
                            })
                            # Логируем в logs
                            self._repo.log_action(
                                object='BMController',
                                action='bulk_insert_rust_servers',
                                comment=f'Добавлено/обновлено {inserted_count} записей в rust_servers',
                                result=f'Success: {inserted_count} records'
                            )
                        
                        # Используем ссылки вместо копирования для экономии памяти
                        last_info = dict(self._servers_info)
                        # Сохраняем хеши для быстрого сравнения
                        last_hashes = {key: hash(server) for key, server in last_info.items()}
                    else:
                        self._servers_info = {}
                    
                    # Первичная загрузка информации об игроках
                    if player_ids:
                        self._logger.info("Первичная загрузка информации об игроках")
                        self._players_info = await self._bm_response.async_get_players_info(session, player_ids)
                        errors_players: Union[list, None] = self._players_info.get('errors')
                        if errors_players:
                            self._logger.warning(f"Обнаружено ошибок при первичной загрузке игроков: {len(errors_players)}")
                            await self._dp.handle_errors(errors_players)
                            self._players_info.pop('errors', None)
                        
                        self._logger.info(f"Успешно загружено игроков: {len(self._players_info)}", {
                            'players_loaded': len(self._players_info)
                        })
                        
                        # Обновляем информацию об игроках в БД
                        players_updated = 0
                        for player_id, player in self._players_info.items():
                            if isinstance(player, Player):
                                if self._repo.update_player_info(player):
                                    players_updated += 1
                        
                        if players_updated > 0:
                            self._logger.debug(f"Обновлено записей в players: {players_updated}", {
                                'players_updated': players_updated
                            })
                        
                        # Обновляем связи players_servers для всех игроков
                        players_servers_updated = 0
                        for player_id, player in self._players_info.items():
                            if isinstance(player, Player):
                                updated = self._repo.update_player_server_connections(player)
                                players_servers_updated += updated
                        
                        if players_servers_updated > 0:
                            self._logger.info(f"Обновлено связей players_servers: {players_servers_updated}", {
                                'players_servers_updated': players_servers_updated
                            })
                            # Логируем в logs
                            self._repo.log_action(
                                object='BMController',
                                action='update_players_servers',
                                comment=f'Обновлено {players_servers_updated} связей игрок-сервер',
                                result=f'Success: {players_servers_updated} links'
                            )
                        
                        last_players_info = dict(self._players_info)
                        last_players_hashes = {key: hash(player) for key, player in last_players_info.items() if isinstance(player, Player)}
                    else:
                        self._players_info = {}
                        last_players_info = {}
                        last_players_hashes = {}
                    
                    self._logger.info("Сервис обновления запущен, начало цикла обновлений")
                    
                    iteration = 0
                    while not (self.stop_event and self.stop_event.is_set()):
                        try:
                            await aSleep(delay)
                            iteration += 1
                            
                            self._logger.debug(f"Итерация обновления #{iteration}")
                            
                            
                            # Обновляем информацию о серверах
                            if servers:
                                self._servers_info = await self._bm_response.async_get_servers_info(session)
                    
                                # Обрабатываем ошибки если есть
                                errors = self._servers_info.get('errors')
                                if errors:
                                    self._logger.warning(f"Обнаружено ошибок: {len(errors)}", {
                                        'errors_count': len(errors)
                                    })
                                    await self._dp.handle_errors(errors)
                                    self._servers_info.pop('errors', None)
                                
                                # Ищем различия только среди успешно загруженных серверов
                                differences: list = await self._find_differences_servers(
                                    last_info=last_info, 
                                    last_hashes=last_hashes
                                )
                                if differences:
                                    self._logger.info(f"Обнаружено изменений: {len(differences)}", {
                                        'differences_count': len(differences)
                                    })
                                    await self._dp.handle_server_differences(differences=differences)
                                
                                # Обновляем информацию о серверах в БД
                                servers_updated = 0
                                for server_name, server in self._servers_info.items():
                                    if server_name != 'errors' and isinstance(server, Server):
                                        if self._repo.update_server_info(server):
                                            servers_updated += 1
                                
                                if servers_updated > 0:
                                    self._logger.debug(f"Обновлено записей в servers: {servers_updated}", {
                                        'servers_updated': servers_updated
                                    })
                                
                                # Обновляем rust_servers для всех Rust серверов
                                rust_servers_to_update = []
                                for server_name, server in self._servers_info.items():
                                    if server_name != 'errors' and isinstance(server, RustServer):
                                        rust_servers_to_update.append(server)
                                
                                if rust_servers_to_update:
                                    updated_count = self._repo.bulk_insert_rust_servers(rust_servers_to_update)
                                    if updated_count > 0:
                                        self._logger.debug(f"Обновлено записей в rust_servers: {updated_count}", {
                                            'rust_servers_updated': updated_count
                                        })
                                        # Логируем в logs
                                        self._repo.log_action(
                                            object='BMController',
                                            action='update_rust_servers',
                                            comment=f'Обновлено {updated_count} записей в rust_servers',
                                            result=f'Success: {updated_count} records'
                                        )
                                
                                # Обновляем ссылки и хеши для серверов
                                last_info = dict(self._servers_info)
                                last_hashes = {key: hash(server) for key, server in last_info.items()}
                    
                            # Обновляем информацию об игроках
                            if player_ids:
                                self._players_info = await self._bm_response.async_get_players_info(session, player_ids)
                                errors_players = self._players_info.get('errors')
                                if errors_players:
                                    self._logger.warning(f"Обнаружено ошибок при обновлении игроков: {len(errors_players)}")
                                    await self._dp.handle_errors(errors_players)
                                    self._players_info.pop('errors', None)
                                
                                # Ищем различия среди игроков
                                player_differences: list = await self._find_differences_players(
                                    last_info=last_players_info,
                                    last_hashes=last_players_hashes
                                )
                                if player_differences:
                                    self._logger.info(f"Обнаружено изменений у игроков: {len(player_differences)}", {
                                        'player_differences_count': len(player_differences)
                                    })
                                    await self._dp.handle_player_differences(differences=player_differences)
                                
                                # Обновляем players_servers для всех игроков
                                players_servers_updated = 0
                                for player_id, player in self._players_info.items():
                                    if isinstance(player, Player):
                                        updated = self._repo.update_player_server_connections(player)
                                        players_servers_updated += updated
                                
                                if players_servers_updated > 0:
                                    self._logger.debug(f"Обновлено связей players_servers: {players_servers_updated}", {
                                        'players_servers_updated': players_servers_updated
                                    })
                                    # Логируем в logs
                                    self._repo.log_action(
                                        object='BMController',
                                        action='update_players_servers',
                                        comment=f'Обновлено {players_servers_updated} связей игрок-сервер',
                                        result=f'Success: {players_servers_updated} links'
                                    )
                                
                                # Обновляем ссылки и хеши для игроков
                                last_players_info = dict(self._players_info)
                                last_players_hashes = {key: hash(player) for key, player in last_players_info.items() if isinstance(player, Player)}
                            
                            # Обновляем статистику
                            self._servers_to_update = set(self._servers_info.keys())
                            self._players_to_update = set(self._players_info.keys()) if player_ids else set()
                            
                            # Периодически выводим статистику (каждые 10 итераций)
                            if iteration % 10 == 0:
                                self._logger.info("Статистика сервиса обновления", {
                                    'iteration': iteration,
                                    'servers_tracked': len(self._servers_info),
                                    'servers_to_update': len(self._servers_to_update),
                                    'players_tracked': len(self._players_info) if player_ids else 0,
                                    'players_to_update': len(self._players_to_update)
                                })
                        except (ConnectionError, TimeoutError, ClientError) as e:
                            # Обработка сетевых ошибок
                            self._logger.warning(f"Сетевая ошибка в цикле обновлений (итерация #{iteration}): {e}")
                            await aSleep(delay * 2)  # Увеличиваем задержку при сетевых ошибках
                        except (ValueError, KeyError, TypeError) as e:
                            # Обработка ошибок парсинга данных
                            self._logger.error(f"Ошибка парсинга данных в цикле обновлений (итерация #{iteration}): {e}")
                            import traceback
                            self._logger.error(traceback.format_exc())
                            await aSleep(delay)
                        except Exception as e:
                            # Обработка остальных исключений внутри цикла обновлений, чтобы процесс не падал
                            self._logger.error(f"Неожиданная ошибка в цикле обновлений (итерация #{iteration}): {e}")
                            import traceback
                            self._logger.error(traceback.format_exc())
                            # Продолжаем работу после ошибки
                            await aSleep(delay)
                except KeyboardInterrupt:
                    self._logger.warning("Получен сигнал прерывания во внешнем цикле")
                    raise
                except Exception as e:
                    # Ошибка во внешнем цикле, логируем и продолжаем
                    self._logger.error(f"Ошибка во внешнем цикле обновления: {e}")
                    import traceback
                    self._logger.error(traceback.format_exc())
                    await aSleep(delay)
        except KeyboardInterrupt:
            self._logger.warning("Получен сигнал прерывания, остановка сервиса обновления")
            raise
        except Exception as e:
            # Критическая ошибка, логируем и пробрасываем дальше
            self._logger.error(f"Критическая ошибка в update_info: {e}")
            import traceback
            self._logger.error(traceback.format_exc())
            # Логируем в БД
            try:
                self._repo.log_action(
                    object='BMController',
                    action='update_info',
                    comment='Критическая ошибка в update_info',
                    is_error=True,
                    result=str(e)
                )
            except:
                pass  # Если не удалось записать в БД, просто продолжаем
        finally:
            # Закрываем HTTP-сессию при остановке
            if self._session and not self._session.closed:
                await self._session.close()
                self._logger.info("HTTP-сессия закрыта")
            self._session = None


    async def _find_differences_servers(self, last_info: dict, last_hashes: dict[str, int] = None) -> list:
        """Находит различия между текущим и предыдущим состоянием серверов (оптимизированная версия)"""
        differences: list = []
        
        # Если хеши не переданы, вычисляем их
        if last_hashes is None:
            last_hashes = {key: hash(server) for key, server in last_info.items()}
        
        # Вычисляем хеши текущего состояния батчем
        current_hashes = {}
        for key in self._servers_info:
            if key != 'errors':
                current_hashes[key] = hash(self._servers_info[key])
        
        # Проверяем различия синхронно для небольшого количества серверов
        # Используем async только для больших батчей (более 10 серверов)
        servers_to_check = []
        for key in self._servers_info:
            if key == 'errors':
                continue
            
            # Быстрая проверка через хеши (O(1) вместо O(D))
            if key not in last_hashes or last_hashes[key] != current_hashes[key]:
                # Если хеши не совпадают, проверяем детально
                if key in last_info:
                    servers_to_check.append((key, last_info[key], self._servers_info[key]))
        
        # Для небольшого количества серверов выполняем синхронно
        if len(servers_to_check) <= 10:
            for key, last_server, current_server in servers_to_check:
                diff = await self.__find_differences_in_servers(last_server, current_server)
                if diff and ('old' in diff or 'new' in diff):
                    differences.append(diff)
        else:
            # Для большого количества используем параллельную обработку
            tasks = [
                create_task(self.__find_differences_in_servers(last_server, current_server))
                for _, last_server, current_server in servers_to_check
            ]
            results = await gather(*tasks)
            differences = [diff for diff in results if diff and ('old' in diff or 'new' in diff)]
        
        return differences

    async def __find_differences_in_servers(self, last_server_info: Server, server_info: Server) -> dict:
        """
        Оптимизированное сравнение серверов с использованием кэшированных словарей
        """
        # Используем кэшированные словари (O(1) если уже вычислены)
        last_dict = last_server_info.to_dict()
        server_dict = server_info.to_dict()
        
        difference: dict = {
            'name': last_server_info.name,
            'server_id': last_server_info.id,  # Добавляем ID для точной проверки
            'game_id': last_server_info.game_id
        }
        
        # Оптимизированное сравнение: проходим только по ключам одного словаря
        # O(min(D1, D2)) вместо O(D1 + D2) для XOR операции
        all_keys = set(last_dict.keys()) | set(server_dict.keys())
        old_values = []
        new_values = []
        
        for key in all_keys:
            old_val = last_dict.get(key)
            new_val = server_dict.get(key)
            
            # Пропускаем служебные поля
            if key in ['name', 'game_id', 'type']:
                continue
            
            # Преобразуем ключи из camelCase в snake_case для обработки
            snake_key = self._camel_to_snake(key)
            
            if old_val != new_val:
                if old_val is not None:
                    old_values.append({snake_key: old_val})
                if new_val is not None:
                    new_values.append({snake_key: new_val})
        
        if old_values or new_values:
            difference['old'] = old_values
            difference['new'] = new_values
            return difference
        
        return difference
    
    def _camel_to_snake(self, name: str) -> str:
        """Преобразует camelCase в snake_case"""
        import re
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()
    
    async def _find_differences_players(self, last_info: dict, last_hashes: dict[str, int] = None) -> list:
        """Находит различия между текущим и предыдущим состоянием игроков (оптимизированная версия)"""
        differences: list = []
        
        # Если хеши не переданы, вычисляем их
        if last_hashes is None:
            last_hashes = {key: hash(player) for key, player in last_info.items() if isinstance(player, Player)}
        
        # Вычисляем хеши текущего состояния батчем
        current_hashes = {}
        for key, player in self._players_info.items():
            if key != 'errors' and isinstance(player, Player):
                current_hashes[key] = hash(player)
        
        # Собираем игроков для проверки
        players_to_check = []
        for key in self._players_info:
            if key == 'errors':
                continue
            
            player = self._players_info[key]
            if not isinstance(player, Player):
                continue
            
            # Быстрая проверка через хеши
            if key not in last_hashes or last_hashes[key] != current_hashes[key]:
                # Если хеши не совпадают, проверяем детально
                if key in last_info:
                    last_player = last_info[key]
                    if isinstance(last_player, Player):
                        players_to_check.append((key, last_player, player))
        
        # Для небольшого количества игроков выполняем синхронно
        if len(players_to_check) <= 10:
            for _, last_player, current_player in players_to_check:
                diff = await self.__find_differences_in_players(last_player, current_player)
                if diff:
                    differences.append(diff)
        else:
            # Для большого количества используем параллельную обработку
            tasks = [
                create_task(self.__find_differences_in_players(last_player, current_player))
                for _, last_player, current_player in players_to_check
            ]
            results = await gather(*tasks)
            differences = [d for d in results if d]  # Убираем пустые различия
        
        return differences
    
    async def __find_differences_in_players(self, last_player_info: Player, player_info: Player) -> dict:
        """Сравнивает два состояния игрока и возвращает различия"""
        difference: dict = {
            'player_id': player_info.id,
            'player_name': player_info.name
        }
        
        old_values = []
        new_values = []
        
        # Проверяем изменение ника
        if last_player_info.name != player_info.name:
            old_values.append({'name': last_player_info.name})
            new_values.append({'name': player_info.name})
        
        # Проверяем изменение приватности
        if last_player_info.private != player_info.private:
            old_values.append({'private': last_player_info.private})
            new_values.append({'private': player_info.private})
        
        # Проверяем изменение метаданных серверов
        last_meta = last_player_info.player_servers_meta
        current_meta = player_info.player_servers_meta
        
        # Проверяем изменения онлайн статуса на серверах
        for server_id in set(list(last_meta.keys()) + list(current_meta.keys())):
            last_server_meta = last_meta.get(server_id, {})
            current_server_meta = current_meta.get(server_id, {})
            
            last_online = last_server_meta.get('is_online', False)
            current_online = current_server_meta.get('is_online', False)
            
            if last_online != current_online:
                old_values.append({
                    'server_online': {
                        'server_id': server_id,
                        'is_online': last_online
                    }
                })
                new_values.append({
                    'server_online': {
                        'server_id': server_id,
                        'is_online': current_online
                    }
                })
        
        if old_values or new_values:
            difference['old'] = old_values
            difference['new'] = new_values
            return difference
        
        return {}