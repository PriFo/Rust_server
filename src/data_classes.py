from typing import Union, Optional, Dict, Any, List
from datetime import datetime
from src.filters import Filter, RustFilter
from src.errorresponse import ErrorResponse


class Server:
    """
    Класс-родитель для всех остальных классов с информацией о сервере.
    Соответствует таблице `servers` в БД.
    """
    TYPE = 'server'

    def __init__(self, id: Union[str, int], data: dict, game_id: str = 'rust') -> None:
        self._id: int = int(id) if isinstance(id, str) else id
        self._name: str = data.get('name', '')
        self._status: str = data.get('status', 'unknown')
        self._players: int = data.get('players', 0)
        self._max_players: int = data.get('maxPlayers', 0)
        self._private: bool = data.get('private', False)
        self._country: str = data.get('country', '')
        self._rank: int = data.get('rank', 0)
        self._game_id: str = game_id
        # Поля из БД, не всегда приходящие из API
        self._ip: Optional[str] = data.get('ip')
        self._port: Optional[int] = data.get('port')
        # Кэш
        self._dict_cache: Optional[dict] = None
        self._hash_cache: Optional[int] = None

    @property
    def id(self) -> int:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def status(self) -> str:
        return self._status

    @property
    def players(self) -> int:
        return self._players

    @property
    def max_players(self) -> int:
        return self._max_players

    @property
    def private(self) -> bool:
        return self._private

    @property
    def country(self) -> str:
        return self._country

    @property
    def rank(self) -> int:
        return self._rank

    @property
    def game_id(self) -> str:
        return self._game_id

    @property
    def ip(self) -> Optional[str]:
        return self._ip

    @property
    def port(self) -> Optional[int]:
        return self._port

    def __str__(self) -> str:
        return (f"Название: {self._name}\n"
                f"Приватный: {'Да' if self._private else 'Нет'}\n"
                f"Страна: {self._country}\n"
                f"Статус: {'онлайн' if self._status == 'online' else 'оффлайн'}\n"
                f"Игроки: {self._players}/{self._max_players}")

    def to_dict(self) -> dict:
        if self._dict_cache is None:
            self._dict_cache = {
                'type': self.TYPE,
                'id': self._id,
                'name': self._name,
                'status': self._status,
                'players': self._players,
                'maxPlayers': self._max_players,
                'private': self._private,
                'country': self._country,
                'rank': self._rank,
                'ip': self._ip,
                'port': self._port,
                'game_id': self._game_id
            }
        return self._dict_cache.copy()

    def to_db_dict(self, game_id_int: int) -> Dict[str, Any]:
        """Подготавливает данные для вставки/обновления в таблице `servers`."""
        return {
            'id_server': self._id,
            'fk_games_id': game_id_int,
            'server_name': self._name,
            'rank': self._rank,
            'private': self._private,
            'country': self._country,
            'ip': self._ip,
            'port': self._port,
            'players_online': self._players,
            'players_max': self._max_players,
            'status': self._status
        }

    @classmethod
    def from_db_dict(cls, db_row: Dict[str, Any], game_name: str) -> 'Server':
        """Создает объект Server из строки БД (таблицы `servers`)."""
        data = {
            'name': db_row.get('server_name', ''),
            'status': db_row.get('status', 'unknown'),
            'players': db_row.get('players_online', 0),
            'maxPlayers': db_row.get('players_max', 0),
            'private': bool(db_row.get('private', False)),
            'country': db_row.get('country', ''),
            'rank': db_row.get('rank', 0),
            'ip': db_row.get('ip'),
            'port': db_row.get('port')
        }
        return cls(db_row['id_server'], data, game_name)

    def _invalidate_cache(self) -> None:
        self._dict_cache = None
        self._hash_cache = None

    def __hash__(self) -> int:
        if self._hash_cache is None:
            self._hash_cache = hash((self._id, self._status, self._players,
                                     self._max_players, self._private, self._country))
        return self._hash_cache

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Server):
            return False
        return (self._id == other._id and self._status == other._status and
                self._players == other._players and self._max_players == other._max_players and
                self._private == other._private and self._country == other._country)


class RustServer(Server):
    """
    Класс данных с информацией о сервере в игре Rust.
    Соответствует таблицам `servers` и `rust_servers` в БД.
    """

    def __init__(self, id: Union[str, int], data: dict, game_id: str = 'rust') -> None:
        super().__init__(id, data, game_id)
        # Поля из таблицы `rust_servers`
        details = data.get('details', {})
        self._is_pve: bool = details.get('is_pve', data.get('pve', False))
        self._official: bool = details.get('official', False)
        self._description: Optional[str] = details.get('description')
        self._modded: bool = details.get('modded', False)
        self._gamemode: Optional[str] = details.get('gamemode')
        self._steam_id: Optional[int] = details.get('steam_id')
        self._next_wipe_date: Optional[datetime] = self._parse_datetime(details.get('next_wipe_date'))
        self._next_wipe_type: Optional[str] = details.get('next_wipe_type')
        self._last_wipe_date: Optional[datetime] = self._parse_datetime(details.get('last_wipe_date'))
        self._rust_url: Optional[str] = details.get('rust_url')
        self._map_url: Optional[str] = details.get('map_url')
        self._thumbnail_url: Optional[str] = details.get('thumbnail_url')
        self._queued_players: int = details.get('queued_players', 0)

    # Свойства для Rust-полей
    @property
    def is_pve(self) -> bool:
        return self._is_pve

    @property
    def official(self) -> bool:
        return self._official

    @property
    def description(self) -> Optional[str]:
        return self._description

    @property
    def modded(self) -> bool:
        return self._modded

    @property
    def gamemode(self) -> Optional[str]:
        return self._gamemode

    @property
    def steam_id(self) -> Optional[int]:
        return self._steam_id

    @property
    def next_wipe_date(self) -> Optional[datetime]:
        return self._next_wipe_date

    @property
    def next_wipe_type(self) -> Optional[str]:
        return self._next_wipe_type

    @property
    def last_wipe_date(self) -> Optional[datetime]:
        return self._last_wipe_date

    @property
    def rust_url(self) -> Optional[str]:
        return self._rust_url

    @property
    def map_url(self) -> Optional[str]:
        return self._map_url

    @property
    def thumbnail_url(self) -> Optional[str]:
        return self._thumbnail_url

    @property
    def queued_players(self) -> int:
        return self._queued_players

    @staticmethod
    def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
        if not dt_str:
            return None
        try:
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
                try:
                    return datetime.strptime(dt_str, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return None

    def __str__(self) -> str:
        base = super().__str__()
        rust_info = (f"\nИгра: Rust\n"
                     f"PVE: {'Да' if self._is_pve else 'Нет'}\n"
                     f"Официальный: {'Да' if self._official else 'Нет'}\n"
                     f"Очередь: {self._queued_players}\n"
                     f"Последний вайп: {self._last_wipe_date or 'неизвестно'}\n"
                     f"Следующий вайп: {self._next_wipe_date or 'неизвестно'} ({self._next_wipe_type or ''})\n"
                     f"URL карты: {self._map_url or 'нет'}")
        return base + rust_info

    def to_dict(self) -> dict:
        base = super().to_dict()
        rust_data = {
            'is_pve': self._is_pve,
            'official': self._official,
            'description': self._description,
            'modded': self._modded,
            'gamemode': self._gamemode,
            'steam_id': self._steam_id,
            'next_wipe_date': self._next_wipe_date.isoformat() if self._next_wipe_date else None,
            'next_wipe_type': self._next_wipe_type,
            'last_wipe_date': self._last_wipe_date.isoformat() if self._last_wipe_date else None,
            'rust_url': self._rust_url,
            'map_url': self._map_url,
            'thumbnail_url': self._thumbnail_url,
            'queued_players': self._queued_players
        }
        base.update(rust_data)
        return base

    def to_db_dict(self, game_id_int: int) -> Dict[str, Any]:
        """Подготавливает данные для вставки/обновления в таблицах `servers` и `rust_servers`."""
        server_data = super().to_db_dict(game_id_int)
        rust_data = {
            'fk_id_servers': self._id,
            'is_pve': self._is_pve,
            'official': self._official,
            'description': self._description,
            'modded': self._modded,
            'gamemode': self._gamemode,
            'steam_id': self._steam_id,
            'next_wipe_date': self._next_wipe_date,
            'next_wipe_type': self._next_wipe_type,
            'last_wipe_date': self._last_wipe_date,
            'rust_url': self._rust_url,
            'map_url': self._map_url,
            'thumbnail_url': self._thumbnail_url,
            'queued_players': self._queued_players
        }
        return {'server': server_data, 'rust': rust_data}

    @classmethod
    def from_db_dict(cls, db_row: Dict[str, Any], game_name: str) -> 'RustServer':
        """Создает объект RustServer из объединённой строки БД (JOIN `servers` + `rust_servers`)."""
        # Сначала создаём базовый сервер
        base_server = super().from_db_dict(db_row, game_name)

        # Собираем данные для RustServer
        data = base_server.to_dict()
        data['details'] = {
            'is_pve': db_row.get('is_pve', False),
            'official': db_row.get('official', False),
            'description': db_row.get('description'),
            'modded': db_row.get('modded', False),
            'gamemode': db_row.get('gamemode'),
            'steam_id': db_row.get('steam_id'),
            'next_wipe_date': db_row.get('next_wipe_date'),
            'next_wipe_type': db_row.get('next_wipe_type'),
            'last_wipe_date': db_row.get('last_wipe_date'),
            'rust_url': db_row.get('rust_url'),
            'map_url': db_row.get('map_url'),
            'thumbnail_url': db_row.get('thumbnail_url'),
            'queued_players': db_row.get('queued_players', 0)
        }

        return cls(db_row['id_server'], data, game_name)


class Player:
    """
    Класс, содержащий информацию об игроке.
    Соответствует таблице `players` в БД.
    Связи с серверами хранятся в `player_servers_meta` в формате таблицы `players_servers`.
    """

    def __init__(self, id: Union[str, int], data: dict) -> None:
        try:
            self._id: int = int(id) if isinstance(id, str) else id
        except (ValueError, TypeError):
            raise ValueError(f"Invalid player ID format: {id}")

        self._nickname: str = data.get('name', data.get('nickname', ''))
        self._private: bool = data.get('private', False)
        self._positive_match: bool = data.get('positiveMatch', False)
        self._last_seen: Optional[datetime] = self._parse_datetime(data.get('lastSeen'))
        self._created_at: Optional[datetime] = self._parse_datetime(data.get('createdAt'))
        self._updated_at: Optional[datetime] = self._parse_datetime(data.get('updatedAt'))

        # Метаданные связей с серверами {server_id: {'is_online': bool, 'time_played': int, 'first_seen': datetime, 'last_seen': datetime}}
        self._player_servers_meta: Dict[int, Dict[str, Any]] = {}
        self._hash_cache: Optional[int] = None

    @property
    def id(self) -> int:
        return self._id

    @property
    def name(self) -> str:
        return self._nickname

    @property
    def private(self) -> bool:
        return self._private

    @property
    def positiveMatch(self) -> bool:
        return self._positive_match

    @property
    def last_seen(self) -> Optional[datetime]:
        return self._last_seen

    @property
    def created_at(self) -> Optional[datetime]:
        return self._created_at

    @property
    def updated_at(self) -> Optional[datetime]:
        return self._updated_at

    @property
    def player_servers_meta(self) -> Dict[int, Dict[str, Any]]:
        return self._player_servers_meta.copy()

    @staticmethod
    def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
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

    def add_server_meta(self, server_id: int, meta: Dict[str, Any]) -> None:
        """Добавляет или обновляет метаданные связи с сервером."""
        self._player_servers_meta[server_id] = meta
        self._hash_cache = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self._id,
            'name': self._nickname,
            'private': self._private,
            'positiveMatch': self._positive_match,
            'lastSeen': self._last_seen.isoformat() if self._last_seen else None,
            'createdAt': self._created_at.isoformat() if self._created_at else None,
            'updatedAt': self._updated_at.isoformat() if self._updated_at else None,
            'servers_meta': {str(k): v for k, v in self._player_servers_meta.items()}
        }

    def to_db_dict(self) -> Dict[str, Any]:
        """Подготавливает данные для вставки/обновления в таблице `players`."""
        return {
            'id_players': self._id,
            'nickname': self._nickname,
            'positive_match': self._positive_match,
            'private': self._private,
            'last_seen': self._last_seen,
            'created_at': self._created_at,
            'updated_at': self._updated_at
        }

    @classmethod
    def from_db_dict(cls, db_row: Dict[str, Any]) -> 'Player':
        """Создает объект Player из строки БД (таблицы `players`)."""
        data = {
            'nickname': db_row.get('nickname', ''),
            'positiveMatch': bool(db_row.get('positive_match', False)),
            'private': bool(db_row.get('private', False)),
            'lastSeen': db_row.get('last_seen'),
            'createdAt': db_row.get('created_at'),
            'updatedAt': db_row.get('updated_at')
        }
        player = cls(db_row['id_players'], data)
        return player

    def __str__(self) -> str:
        last_seen_str = self._last_seen.strftime('%Y-%m-%d %H:%M:%S') if self._last_seen else 'никогда'
        return (f"Игрок: {self._nickname}\n"
                f"ID: {self._id}\n"
                f"Приватный: {'Да' if self._private else 'Нет'}\n"
                f"Последний раз онлайн: {last_seen_str}")

    def __hash__(self) -> int:
        if self._hash_cache is None:
            self._hash_cache = hash((self._id, self._nickname, self._private, self._positive_match))
        return self._hash_cache

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Player):
            return False
        return (self._id == other._id and self._nickname == other._nickname and
                self._private == other._private and self._positive_match == other._positive_match)


class Profile:
    """
    Класс, хранящий информацию о профиле пользователя бота.
    Соответствует таблице `profiles` в БД.
    Подписки и фильтры загружаются отдельно.
    """

    TYPE: str = 'profile'

    def __init__(self, **kwargs: dict[str, Any]) -> None:
        raw_id = kwargs.get('id', 0)
        try:
            self._id: int = int(raw_id) if raw_id not in (None, '') else 0
        except (TypeError, ValueError):
            self._id = 0
        self._nickname: str = kwargs.get('nickname', '')
        self._name: str = kwargs.get('name', '')
        self._surname: str = kwargs.get('surname', '')
        self._is_active: bool = kwargs.get('is_active', False)
        self._bot_banned: bool = kwargs.get('bot_banned', False)
        self._notification_settings: Dict[str, Any] = kwargs.get('notification_settings', {})
        self._last_activity: Optional[datetime] = kwargs.get('last_activity')
        self._created_at: Optional[datetime] = kwargs.get('created_at')

        self._servers: Dict[int, Server] = {}
        self._players: Dict[int, Player] = {}
        self._filters: Dict[str, Filter] = {}

    @property
    def id(self) -> int:
        return self._id

    @property
    def nickname(self) -> str:
        return self._nickname

    @property
    def name(self) -> str:
        return self._name

    @property
    def surname(self) -> str:
        return self._surname

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def bot_banned(self) -> bool:
        return self._bot_banned

    @property
    def notification_settings(self) -> Dict[str, Any]:
        return self._notification_settings.copy()

    @property
    def last_activity(self) -> Optional[datetime]:
        return self._last_activity

    @property
    def created_at(self) -> Optional[datetime]:
        return self._created_at

    @property
    def servers(self) -> Dict[int, Server]:
        return self._servers.copy()

    @property
    def players(self) -> Dict[int, Player]:
        return self._players.copy()

    @property
    def filters(self) -> Dict[str, Filter]:
        return self._filters.copy()

    def add_server(self, server: Server) -> None:
        if not isinstance(server, Server):
            raise TypeError(f'Value must be Server, not {type(server)}')
        self._servers[server.id] = server

    def add_player(self, player: Player) -> None:
        if not isinstance(player, Player):
            raise TypeError(f'Value must be Player, not {type(player)}')
        self._players[player.id] = player

    def add_filter(self, filter_obj: Filter) -> None:
        if not isinstance(filter_obj, Filter):
            raise TypeError(f'Input filter must be Filter, not {type(filter_obj)}')
        key = filter_obj.game_id if filter_obj.game_id else filter_obj.filter_type
        self._filters[key] = filter_obj

    def get_filter(self, filter_key: str) -> Optional[Filter]:
        return self._filters.get(filter_key)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self._id,
            'nickname': self._nickname,
            'name': self._name,
            'surname': self._surname,
            'is_active': self._is_active,
            'bot_banned': self._bot_banned,
            'notification_settings': self._notification_settings,
            'last_activity': self._last_activity.isoformat() if self._last_activity else None,
            'created_at': self._created_at.isoformat() if self._created_at else None,
            'servers_count': len(self._servers),
            'players_count': len(self._players),
            'filters_count': len(self._filters)
        }

    def to_db_dict(self) -> Dict[str, Any]:
        """Подготавливает данные для вставки/обновления в таблице `profiles`."""
        import json
        return {
            'id_profile': int(self._id),
            'profile_nickname': self._nickname,
            'profile_name': self._name,
            'profile_surname': self._surname,
            'is_active': self._is_active,
            'bot_banned': self._bot_banned,
            'notification_settings': json.dumps(self._notification_settings) if self._notification_settings else None,
            'last_activity': self._last_activity,
            'created_at': self._created_at
        }

    @classmethod
    def from_db_dict(cls, db_row: Dict[str, Any]) -> 'Profile':
        """Создает объект Profile из строки БД (таблицы `profiles`)."""
        import json
        notification_settings = {}
        if db_row.get('notification_settings'):
            try:
                notification_settings = json.loads(db_row['notification_settings'])
            except (json.JSONDecodeError, TypeError):
                pass

        raw_id = db_row.get('id_profile')
        try:
            profile_id = int(raw_id) if raw_id is not None and str(raw_id).strip() != '' else 0
        except (TypeError, ValueError):
            profile_id = 0
        kwargs = {
            'id': profile_id,
            'nickname': db_row.get('profile_nickname', ''),
            'name': db_row.get('profile_name', ''),
            'surname': db_row.get('profile_surname', ''),
            'is_active': bool(db_row.get('is_active', False)),
            'bot_banned': bool(db_row.get('bot_banned', False)),
            'notification_settings': notification_settings,
            'last_activity': db_row.get('last_activity'),
            'created_at': db_row.get('created_at')
        }
        return cls(**kwargs)

    def __str__(self) -> str:
        status = "активен" if self._is_active else "неактивен"
        last_activity_str = self._last_activity.strftime('%Y-%m-%d %H:%M:%S') if self._last_activity else "никогда"
        return (f"Профиль: {self._name} {self._surname} (@{self._nickname})\n"
                f"Статус: {status}\n"
                f"Последняя активность: {last_activity_str}\n"
                f"Серверов: {len(self._servers)}\n"
                f"Игроков: {len(self._players)}")


class ServerFactory:
    @staticmethod
    def get_server(id: Union[str, int], data: dict) -> Server:
        try:
            id_int = int(id) if isinstance(id, str) else id
        except (ValueError, TypeError):
            raise ValueError(f"Invalid server ID format: {id}")

        game_id = ServerFactory._get_game_id(data)
        data_obj = data.get('data', {})
        attributes = data_obj.get('attributes', {})
        details = attributes.get('details', {})

        # Базовые данные для любого сервера
        server_data = {
            'name': attributes.get('name', ''),
            'status': attributes.get('status', ''),
            'players': attributes.get('players', 0),
            'maxPlayers': attributes.get('maxPlayers', 0),
            'private': attributes.get('private', False),
            'country': attributes.get('country', ''),
            'rank': attributes.get('rank', 0),
            'ip': attributes.get('ip'),
            'port': attributes.get('port')
        }

        if game_id == "rust":
            # Добавляем Rust-специфичные данные из details
            server_data['details'] = {
                'is_pve': details.get('pve', False),
                'official': details.get('official', False),
                'description': details.get('rust_description'),
                'modded': details.get('rust_modded', False),
                'gamemode': details.get('rust_gamemode'),
                'steam_id': details.get('serverSteamId'),
                'next_wipe_date': details.get('rust_next_wipe'),
                'next_wipe_type': details.get('rust_next_wipe_type', ''),
                'last_wipe_date': details.get('rust_last_wipe'),
                'rust_url': details.get('rust_url'),
                'map_url': details.get('rust_maps', {}).get('url') if details.get('rust_maps') else None,
                'thumbnail_url': details.get('rust_maps', {}).get('thumbnailUrl') if details.get('rust_maps') else None,
                'queued_players': details.get('rust_queued_players', 0)
            }
            return RustServer(id_int, server_data, game_id)
        else:
            # Для других игр - базовый сервер
            return Server(id_int, server_data, game_id)

    @staticmethod
    def _get_game_id(data: dict) -> str:
        try:
            relationships = data.get('data', {}).get('relationships', {})
            game_data = relationships.get('game', {}).get('data', {})
            return game_data.get('id', 'rust')
        except Exception:
            return 'rust'


class ClassFactory:
    @staticmethod
    def get_object(data: dict) -> Union[Player, Server, ErrorResponse]:
        try:
            if data.get('errors'):
                error_resp = ErrorResponse()
                error_resp.initialize(data)
                return error_resp

            data_obj = data.get("data")
            if not data_obj:
                error_resp = ErrorResponse()
                error_resp.initialize("MissingData", "Missing 'data' field in response")
                return error_resp

            obj_type = data_obj.get("type")
            obj_id = data_obj.get("id")

            if not obj_type or not obj_id:
                error_resp = ErrorResponse()
                error_resp.initialize("MissingFields", f"Missing 'type' or 'id' in data. type={obj_type}, id={obj_id}")
                return error_resp

            try:
                obj_id_int = int(obj_id) if isinstance(obj_id, str) else obj_id
            except (ValueError, TypeError):
                error_resp = ErrorResponse()
                error_resp.initialize("InvalidId", f"Invalid ID format: {obj_id}")
                return error_resp

            if obj_type == "player":
                attributes = data_obj.get('attributes', {})
                return Player(obj_id_int, attributes)
            elif obj_type == "server":
                return ServerFactory.get_server(obj_id_int, data)
            else:
                error_resp = ErrorResponse()
                error_resp.initialize("UnknownType", f"Unknown object type: {obj_type}")
                return error_resp
        except (ValueError, KeyError, AttributeError) as e:
            error_resp = ErrorResponse()
            if data.get('errors'):
                error_resp.initialize(data)
            else:
                error_resp.initialize("ValueError", str(e))
            return error_resp