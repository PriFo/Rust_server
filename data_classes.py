
from typing import Union, Optional
from filters import Filter
from errorresponse import ErrorResponse


class Server:
    """
    Класс-родитель для всех остальных классов с информацией о сервере
    """
    
    TYPE = 'server'

    def __init__(self, id: str, data: dict, game_id: str) -> None:
        self._id: str = id
        self._name: str = data.get('name')
        self._status: str = data.get('status')
        self._players: int = data.get('players', 0)
        self._maxPlayers: int = data.get('maxPlayers', 0)
        self._ip: str = data.get('ip', '')
        self._port: int = data.get('port', 0)
        self._private: bool = data.get('private', False)
        self._queryStatus: str = data.get('queryStatus', '')
        self._country: str = data.get('country', '')
        self._address: str = data.get('address', '')
        self._updatedAt: str = data.get('updatedAt', '')
        self._createdAt: str = data.get('createdAt', '')
        self._portQuery: int = data.get('portQuery', 0)
        self._rank: int = data.get('rank', 0)
        self._location: Optional[list] = data.get('location')
        self._game_id: str = game_id
        self._dict_cache: Optional[dict] = None  # Кэш для to_dict()
        self._hash_cache: Optional[int] = None  # Кэш для хеша

    @property
    def name(self) -> str:
        return self._name
    
    @property
    def id(self) -> str:
        return self._id
    
    @property
    def game_id(self) -> str:
        return self._game_id
    
    def __str__(self) -> str:
        return f"Название: {self._name}\n\
            Приватный сервер: {'Да' if self._private else 'Нет'}\n\
            Страна: {self._country}\n\
            Статус: {'онлайн' if self._status == 'online' else 'оффлайн'}\n\
            Игроки: {self._players}/{self._maxPlayers}\n\
            Команда для подключения по IP: connect {self._ip}:{self._port}"
    
    def to_dict(self) -> dict:
        """Возвращает словарь с данными сервера (с кэшированием)"""
        if self._dict_cache is None:
            self._dict_cache = {
                'type': self.TYPE,
                'id': self._id,
                'name': self._name,
                'status': self._status,
                'players': self._players,
                'maxPlayers': self._maxPlayers,
                'ip': self._ip,
                'port': self._port,
                'private': self._private,
                'queryStatus': self._queryStatus,
                'country': self._country,
                'address': self._address,
                'updatedAt': self._updatedAt,
                'createdAt': self._createdAt,
                'portQuery': self._portQuery,
                'rank': self._rank,
                'location': self._location,
                'game_id': self._game_id
            }
        return self._dict_cache
    
    def _invalidate_cache(self) -> None:
        """Инвалидирует кэш (вызывается при изменении данных)"""
        self._dict_cache = None
        self._hash_cache = None
    
    def __hash__(self) -> int:
        """Вычисляет хеш на основе ключевых полей для быстрого сравнения"""
        if self._hash_cache is None:
            # Используем только изменяемые поля для хеша
            key_fields = (
                self._id, self._status, self._players, self._maxPlayers,
                self._ip, self._port, self._private, self._queryStatus,
                self._country, self._updatedAt
            )
            self._hash_cache = hash(key_fields)
        return self._hash_cache


class RustServer(Server):
    """
    Класс данных с основной информацией о сервере в игре Rust
    """

    def __init__(self, id: str, data: dict, game_id: str) -> None:
        # инициализация основной информации по серверу
        super().__init__(id, data, game_id)
        # инициализация данных сервера rust
        self._rust_queued_players: int = 0
        self._rust_last_wipe: str = ""
        self._rust_next_wipe: str = ""
        self._rust_next_wipe_type: str = ""
        self._pve: bool = False
        self._rust_url: str = ""
        self._rust_maps_url: str = ""
        self._rust_maps_thumbnailUrl: str = ""
        self._serverSteamId: str = ""
        self._rust_modded: bool = False
        self._official: bool = False
        self._rust_description: str = ""
        self._rust_gamemode: str = ""
        self._rust_born: str = ""
        self._rust_last_ent_drop: str = ""
        self._rust_last_wipe_ent: int = 0
        self._rust_world_seed: int = 0
        self._rust_world_size: int = 0
        self._rust_world_levelurl: str = ""
        self._rust_build: str = ""
        self._rust_hash: str = ""
        self._rust_headerimage: str = ""
        self._rust_uptime: int = 0
        self._rust_type: str = ""
        self._map: str = ""
        self._environment: str = ""
        self._rust_maps: Optional[dict] = None
        self._rust_settings: Optional[dict] = None
        self._rust_wipes: list = []
        self._tags: list = []

        self._initialize(data)

    def _initialize(self, data: dict) -> None:
        # Получение информации о сервере
        details: dict = data.get("details")
        if details is None:
            raise ValueError("Data details is None!")
        
        # Основные поля Rust
        self._rust_queued_players: int = details.get("rust_queued_players", 0) or 0
        rust_last_wipe = details.get("rust_last_wipe")
        if rust_last_wipe:
            self._rust_last_wipe = rust_last_wipe.replace("T", " ")
        self._pve: bool = details.get("pve", False) or False
        self._rust_url: str = details.get("rust_url", "") or ""
        rust_next_wipe = details.get("rust_next_wipe")
        if rust_next_wipe:
            self._rust_next_wipe = rust_next_wipe.replace("T", " ")
        self._serverSteamId: str = str(details.get("serverSteamId", "")) or ""
        self._rust_modded: bool = details.get("rust_modded", False) or False
        self._official: bool = details.get("official", False) or False
        self._rust_description: str = details.get("rust_description", "") or ""
        self._rust_gamemode: str = details.get("rust_gamemode", "") or ""
        self._rust_born: str = details.get("rust_born", "") or ""
        self._rust_last_ent_drop: str = details.get("rust_last_ent_drop", "") or ""
        self._rust_last_wipe_ent: int = details.get("rust_last_wipe_ent", 0) or 0
        self._rust_world_seed: int = details.get("rust_world_seed", 0) or 0
        self._rust_world_size: int = details.get("rust_world_size", 0) or 0
        self._rust_world_levelurl: str = details.get("rust_world_levelurl", "") or ""
        self._rust_build: str = details.get("rust_build", "") or ""
        self._rust_hash: str = details.get("rust_hash", "") or ""
        self._rust_headerimage: str = details.get("rust_headerimage", "") or ""
        self._rust_uptime: int = details.get("rust_uptime", 0) or 0
        self._rust_type: str = details.get("rust_type", "") or ""
        self._map: str = details.get("map", "") or ""
        self._environment: str = details.get("environment", "") or ""
        self._tags: list = details.get("tags", []) or []
        self._rust_settings: dict = details.get("rust_settings") or {}
        self._rust_wipes: list = details.get("rust_wipes", []) or []

        # Обработка следующего вайпа
        if self._rust_wipes and len(self._rust_wipes) > 0:
            self._rust_next_wipe_type = self._rust_wipes[0].get("type", "")
        else:
            self._rust_next_wipe_type = ""

        # Обработка карт
        rust_maps: dict = details.get("rust_maps")
        if rust_maps is not None:
            self._rust_maps = rust_maps
            self._rust_maps_url: str = rust_maps.get("url", "") or ""
            self._rust_maps_thumbnailUrl: str = rust_maps.get("thumbnailUrl", "") or ""


    def __str__(self) -> str:
        return f'Игра: Rust\n\n \
            Название: {self._name}\n \
            Приватный сервер: {"Да" if self._private else "Нет"}\n \
            Страна: {self._country}\n \
            Статус: {self._status}\n \
            Игроки: {self._players}/{self._maxPlayers} ({self._rust_queued_players})\n \
            Последний вайп: {self._rust_last_wipe}\n \
            Следующий вайп: {self._rust_next_wipe}\n \
            PVE: {"Да" if self._pve else "Нет"}\n\n \
            Адрес сервера: {self._rust_url}\n \
            Интерактивная карта сервера: {self._rust_maps_url}\n \
            Изображение карты сервера: {self._rust_maps_thumbnailUrl}\n\n \
            Команда для подключения по IP: {self._ip}:{self._port}'
    
    def __eq__(self, __value: object) -> bool:
        if not isinstance(__value, RustServer):
            return False
        return self.to_dict() == __value.to_dict()
    
    def __ne__(self, __value: object) -> bool:
        return not self.__eq__(__value)
    
    def to_dict(self) -> dict:
        """Возвращает словарь с данными Rust сервера (с кэшированием)"""
        if self._dict_cache is None:
            result = super().to_dict()
            result.update({
                'rust_queued_players': self._rust_queued_players,
                'rust_last_wipe': self._rust_last_wipe,
                'rust_next_wipe': self._rust_next_wipe,
                'rust_next_wipe_type': self._rust_next_wipe_type,
                'pve': self._pve,
                'rust_url': self._rust_url,
                'rust_maps_url': self._rust_maps_url,
                'rust_maps_thumbnailUrl': self._rust_maps_thumbnailUrl,
                'serverSteamId': self._serverSteamId,
                'rust_modded': self._rust_modded,
                'official': self._official,
                'rust_description': self._rust_description,
                'rust_gamemode': self._rust_gamemode,
                'rust_born': self._rust_born,
                'rust_last_ent_drop': self._rust_last_ent_drop,
                'rust_last_wipe_ent': self._rust_last_wipe_ent,
                'rust_world_seed': self._rust_world_seed,
                'rust_world_size': self._rust_world_size,
                'rust_world_levelurl': self._rust_world_levelurl,
                'rust_build': self._rust_build,
                'rust_hash': self._rust_hash,
                'rust_headerimage': self._rust_headerimage,
                'rust_uptime': self._rust_uptime,
                'rust_type': self._rust_type,
                'map': self._map,
                'environment': self._environment,
                'rust_maps': self._rust_maps,
                'rust_settings': self._rust_settings,
                'rust_wipes': self._rust_wipes,
                'tags': self._tags
            })
            self._dict_cache = result
        return self._dict_cache
    
    def __hash__(self) -> int:
        """Вычисляет хеш с учетом Rust-специфичных полей"""
        if self._hash_cache is None:
            parent_hash = super().__hash__()
            rust_fields = (
                self._rust_queued_players, self._rust_last_wipe,
                self._rust_next_wipe, self._pve, self._rust_modded,
                self._official, self._rust_uptime
            )
            self._hash_cache = hash((parent_hash, rust_fields))
        return self._hash_cache
        

class Player:
    """
    Класс, содержащий полную информацию о игроке: \n
    - ссылка на стим (реализация отложена, Steam-API key хранится в .env) \n
    - активный сервер \n
    - последнее появление в сети и т.д.
    """

    def __init__(self, id: str, data: dict, included: list = None) -> None:
        self._id: str = id
        self._name: str = data.get('name', '')
        self._private: bool = data.get('private', False)
        self._positiveMatch: bool = data.get('positiveMatch', False)
        self._createdAt: str = data.get('createdAt', '')
        self._updatedAt: str = data.get('updatedAt', '')
        self._player_servers: list[Server] = []
        self._player_servers_meta: dict = {}  # {server_id: {timePlayed, firstSeen, lastSeen, online}}
        self._online: bool = False
        self._online_server: Optional[Server] = None
        
        # Обрабатываем included массив с серверами и их метаданными
        if included:
            self._process_included_servers(included)
    
    @property
    def id(self) -> str:
        return self._id
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def private(self) -> bool:
        return self._private
    
    @property
    def positiveMatch(self) -> bool:
        return self._positiveMatch
    
    @property
    def online(self) -> bool:
        return self._online
    
    @property
    def online_server(self) -> Server:
        return self._online_server
    
    @property
    def player_servers(self) -> list:
        return self._player_servers
    
    @player_servers.setter
    def player_servers(self, value: list[Server]) -> None:
        if not isinstance(value, list):
            raise TypeError("Value must have type list[Server]")
        else:
            for subvalue in value:
                if not isinstance(subvalue, Server):
                    raise TypeError("Value must have type list[Server]")
        self._player_servers = value

    @online.setter
    def online(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("New value type must be bool")
        self._online = value

    @online_server.setter
    def online_server(self, value: Server) -> None:
        if not isinstance(value, Server):
            raise TypeError("New value type must be data_classes.Server")
        self._online_server = value
    
    def _process_included_servers(self, included: list) -> None:
        """Обрабатывает массив included с серверами и их метаданными"""
        for item in included:
            if item.get('type') == 'server':
                server_id = str(item.get('id', ''))
                server_attrs = item.get('attributes', {})
                server_name = server_attrs.get('name', '')
                server_meta = item.get('meta', {})
                
                if server_id and server_name:
                    # Создаем объект сервера (используем базовый класс Server для избежания циклических импортов)
                    # В реальности это будет RustServer, но для простоты используем базовый класс
                    server_data = {
                        'name': server_name,
                        'id': server_id,
                        'status': 'unknown',
                        'players': 0,
                        'maxPlayers': 0,
                        'ip': '',
                        'port': 0,
                        'private': False,
                        'queryStatus': '',
                        'country': '',
                        'address': '',
                        'updatedAt': '',
                        'createdAt': '',
                        'portQuery': 0,
                        'rank': 0
                    }
                    server = Server(server_id, server_data, 'rust')
                    self._player_servers.append(server)
                    
                    # Сохраняем метаданные
                    self._player_servers_meta[server_id] = {
                        'timePlayed': server_meta.get('timePlayed', 0),
                        'firstSeen': server_meta.get('firstSeen'),
                        'lastSeen': server_meta.get('lastSeen'),
                        'online': server_meta.get('online', False)
                    }
                    
                    # Обновляем онлайн статус игрока
                    if server_meta.get('online', False):
                        self._online = True
                        self._online_server = server
    
    @property
    def player_servers_meta(self) -> dict:
        """Возвращает метаданные серверов игрока"""
        return self._player_servers_meta
    
    def get_server_meta(self, server_id: str) -> Optional[dict]:
        """Получает метаданные для конкретного сервера"""
        return self._player_servers_meta.get(server_id)
    
    def __eq__(self, __value: object) -> bool:
        if not isinstance(__value, Player):
            return False
        return vars(self) == vars(__value)
    
    def __ne__(self, __value: object) -> bool:
        return not self.__eq__(__value)

    def __str__(self) -> str:
        return f'Игрок: {self._name}\n \
            ID на сайте battlemetrics: {self._id}\n \
            Приватный профиль: {"Да" if self._private else "Нет"}\n \
            Прямое получение данных с серверов: {"Да" if self._positiveMatch else "Нет"}'
    
    def to_dict(self) -> dict:
        """Возвращает словарь с данными игрока"""
        return {
            'id': self._id,
            'name': self._name,
            'private': self._private,
            'positiveMatch': self._positiveMatch,
            'createdAt': self._createdAt,
            'updatedAt': self._updatedAt,
            'online': self._online,
            'online_server_id': self._online_server.id if self._online_server else None,
            'servers_count': len(self._player_servers),
            'servers_meta': self._player_servers_meta
        }


class ServerFactory:
    
    @staticmethod
    def get_server(id: str, data: dict) -> Server:
        game_id: str = ServerFactory.__get_game_id(data)
        if game_id == "rust":
            # Передаем весь объект data, чтобы RustServer мог получить и attributes, и details
            # RustServer ожидает data с полями 'name', 'status' и т.д. в корне, и 'details' для Rust-специфичных данных
            attributes = data.get('data', {}).get('attributes', {})
            # Формируем структуру данных для RustServer
            server_data = {
                **attributes,  # Копируем все атрибуты
                'details': attributes.get('details', {})  # Details находятся внутри attributes
            }
            return RustServer(id, server_data, game_id)
        else:
            raise ValueError(f"Unsupported game_id: {game_id}")

    @staticmethod
    def __get_game_id(data: dict) -> str:
        return data.get('data').get("relationships").get("game").get("data").get("id")


class ClassFactory:

    @staticmethod
    def get_object(data: dict) -> Union[Player, Server, ErrorResponse]:
        """Метод, возвращающий объект по заданному типу"""
        try:
            if data.get('errors'):
                error_resp = ErrorResponse()
                error_resp.initialize(data)
                return error_resp
            
            __type = data.get("data").get("type")
            __id = data.get("data").get("id")

            if __type == "player":
                # Передаем included массив для обработки серверов
                included = data.get('included', [])
                return Player(__id, data.get('data').get('attributes'), included)
            elif __type == "server":
                return ServerFactory.get_server(__id, data)
            else:
                error_resp = ErrorResponse()
                error_resp.initialize("UnknownType", f"Unknown object type: {__type}")
                return error_resp
        except (ValueError, KeyError, AttributeError) as e:
            error_resp = ErrorResponse()
            if data.get('errors'):
                error_resp.initialize(data)
            else:
                error_resp.initialize("ValueError", str(e))
            return error_resp


class Profile:
    """
    Класс, хранящий информацию о профиле пользователя, работающего с ботом

    :param id: Идентификатор пользователя в телеграме типа str
    :param nickname: Никнейм пользователя в телеграме типа str
    :param name: Имя пользователя в телеграме типа str
    :param surname: Фамилия пользователя в телеграме типа str
    :param filters: Фильтры пользователя для фильтрации отправляемых изменений типа dict
    """

    TYPE: str = 'profile'

    def __init__(self, **kwargs: dict[str, str]) -> None:
        
        self._id: str = kwargs.get('id')
        self._nickname: str = kwargs.get('nickname')
        self._name: str = kwargs.get('name')
        self._surname: str = kwargs.get('surname')
        self._is_active: bool = kwargs.get('is_active', False)  # По умолчанию неактивен
        self._filters: dict = {}
        self._servers: dict = {}
        self._players: dict = {}

    @property
    def id(self) -> str:
        return self._id
    
    def add_filter(self, input_filter: Filter) -> None:
        if not isinstance(input_filter, Filter):
            raise TypeError(f'Input filter must be Filter, not {type(input_filter)}')
        self._filters[input_filter.game_id if input_filter.game_id != '' else input_filter.filter_type] = input_filter

    def add_server(self, value: Server) -> None:
        """Добавляет сервер к профилю"""
        if not isinstance(value, Server):
            raise TypeError(f'Value must be Server, not {type(value)}')
        self._servers[value.id] = value

    def add_player(self, value: Player) -> None:
        """Добавляет игрока к профилю"""
        if not isinstance(value, Player):
            raise TypeError(f'Value must be Player, not {type(value)}')
        self._players[value.id] = value

    def get_filter(self, filter_key: str) -> Filter:
        if not isinstance(filter_key, str):
            raise TypeError(f'Filter key must be str, not {type(filter_key)}')
        return self._filters.get(filter_key)

    @property
    def nickname(self) -> str:
        return self._nickname
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def surname(self) -> str:
        return self._surname
    
    @id.setter
    def id(self, value: str) -> None:
        self._id = str(value)

    @nickname.setter
    def nickname(self, value: str) -> None:
        self._nickname = str(value)

    @name.setter
    def name(self, value: str) -> None:
        self._name = str(value)

    @surname.setter
    def surname(self, value: str) -> None:
        self._surname = str(value)
    
    @property
    def is_active(self) -> bool:
        return self._is_active
    
    @is_active.setter
    def is_active(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError(f'Value must be bool, not {type(value)}')
        self._is_active = value
