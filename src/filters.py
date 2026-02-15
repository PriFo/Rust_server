from typing import Any, Optional, Dict


class EFilterTypes:
    server = 'server_filter'
    player = 'player_filter'
    none = ''


class EGames:
    rust = 'rust'
    arma3 = 'arma3'
    none = ''


class Filter:
    def __init__(self,
                 filter_type: str = EFilterTypes.none,
                 game_id: str = EGames.none) -> None:
        self._filter_type: str = filter_type
        self._game_id: str = game_id
        # Поля, соответствующие БД
        self._apply_to_all: bool = True
        self._specific_entity_id: Optional[int] = None

    @property
    def filter_type(self) -> str:
        return self._filter_type

    @property
    def game_id(self) -> str:
        return self._game_id

    @property
    def apply_to_all(self) -> bool:
        return self._apply_to_all

    @property
    def specific_entity_id(self) -> Optional[int]:
        return self._specific_entity_id

    @apply_to_all.setter
    def apply_to_all(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('Value must be bool')
        self._apply_to_all = value

    @specific_entity_id.setter
    def specific_entity_id(self, value: Optional[int]) -> None:
        if value is not None and not isinstance(value, int):
            raise TypeError('Value must be int or None')
        self._specific_entity_id = value

    def get_filter(self, attr: str) -> Any:
        """Получает значение фильтра по имени атрибута."""
        attr_name = f'_{attr}_check'
        if hasattr(self, attr_name):
            return getattr(self, attr_name)
        raise AttributeError(f"Filter has no attribute '{attr}'")

    def to_db_dict(self, profile_id: int) -> Dict[str, Any]:
        """Базовый метод для подготовки данных фильтра для БД. Переопределяется в дочерних классах."""
        raise NotImplementedError("Subclasses must implement this method")


class ServerFilter(Filter):
    """Фильтр для серверов. Соответствует таблице `server_filters`."""

    def __init__(self) -> None:
        super().__init__(EFilterTypes.server)
        # Поля, соответствующие столбцам БД. NULL в БД означает "отключено".
        self._player_count_min: Optional[int] = None  # NULL = отключено
        self._player_count_max: Optional[int] = None  # NULL = отключено
        self._check_status: bool = False
        self._check_ip_port: bool = False
        self._check_private: bool = False

    @property
    def players_check(self) -> Optional[int]:
        """Возвращает значение или None (если отключено). Для обратной совместимости: -1 -> None."""
        return None if self._player_count_min is None else self._player_count_min

    @property
    def max_player_check(self) -> Optional[int]:
        return None if self._player_count_max is None else self._player_count_max

    @property
    def status_check(self) -> bool:
        return self._check_status

    @property
    def ip_port_check(self) -> bool:
        return self._check_ip_port

    @property
    def private_check(self) -> bool:
        return self._check_private

    @players_check.setter
    def players_check(self, value: Optional[int]) -> None:
        if value is None or value < 0:
            self._player_count_min = None
        else:
            self._player_count_min = value

    @max_player_check.setter
    def max_player_check(self, value: Optional[int]) -> None:
        if value is None or value < 0:
            self._player_count_max = None
        else:
            self._player_count_max = value

    @status_check.setter
    def status_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('Value must be bool')
        self._check_status = value

    @ip_port_check.setter
    def ip_port_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('Value must be bool')
        self._check_ip_port = value

    @private_check.setter
    def private_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('Value must be bool')
        self._check_private = value

    def to_db_dict(self, profile_id: int) -> Dict[str, Any]:
        return {
            'fk_id_profile': profile_id,
            'player_count_min': self._player_count_min,
            'player_count_max': self._player_count_max,
            'check_status': self._check_status,
            'check_ip_port': self._check_ip_port,
            'check_private': self._check_private,
            'apply_to_all': self._apply_to_all,
            'specific_server_id': self._specific_entity_id
        }


class RustFilter(ServerFilter):
    """Фильтр для Rust серверов. Соответствует таблице `rust_servers_filters`.
       Связан с записью в `server_filters` через внешний ключ."""

    def __init__(self) -> None:
        super().__init__()
        self._game_id = EGames.rust
        # Поля, соответствующие столбцам БД
        self._queued_players_min: Optional[int] = None  # NULL = отключено
        self._check_last_wipe: bool = False
        self._check_next_wipe: bool = False
        self._check_pve: bool = False
        self._check_url: bool = False
        self._check_map_url: bool = False
        self._check_map_image: bool = False

    @property
    def queued_players_check(self) -> Optional[int]:
        return None if self._queued_players_min is None else self._queued_players_min

    @property
    def last_wipe_check(self) -> bool:
        return self._check_last_wipe

    @property
    def next_wipe_check(self) -> bool:
        return self._check_next_wipe

    @property
    def pve_check(self) -> bool:
        return self._check_pve

    @property
    def url_check(self) -> bool:
        return self._check_url

    @property
    def map_url_check(self) -> bool:
        return self._check_map_url

    @property
    def map_thumbnailUrl_check(self) -> bool:
        return self._check_map_image

    @queued_players_check.setter
    def queued_players_check(self, value: Optional[int]) -> None:
        if value is None or value < 0:
            self._queued_players_min = None
        else:
            self._queued_players_min = value

    @last_wipe_check.setter
    def last_wipe_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('Value must be bool')
        self._check_last_wipe = value

    @next_wipe_check.setter
    def next_wipe_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('Value must be bool')
        self._check_next_wipe = value

    @pve_check.setter
    def pve_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('Value must be bool')
        self._check_pve = value

    @url_check.setter
    def url_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('Value must be bool')
        self._check_url = value

    @map_url_check.setter
    def map_url_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('Value must be bool')
        self._check_map_url = value

    @map_thumbnailUrl_check.setter
    def map_thumbnailUrl_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('Value must be bool')
        self._check_map_image = value

    def to_db_dict(self, profile_id: int, server_filter_id: Optional[int] = None) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Возвращает два словаря: для server_filters и rust_servers_filters.
        Если передан server_filter_id, используется для связи.
        """
        server_filter_data = super().to_db_dict(profile_id)
        rust_filter_data = {
            'fk_server_filters_id': server_filter_id,  # Может быть None при создании
            'queued_players_min': self._queued_players_min,
            'check_last_wipe': self._check_last_wipe,
            'check_next_wipe': self._check_next_wipe,
            'check_pve': self._check_pve,
            'check_url': self._check_url,
            'check_map_url': self._check_map_url,
            'check_map_image': self._check_map_image
        }
        return server_filter_data, rust_filter_data


class PlayerFilter(Filter):
    """Фильтр для игроков. Соответствует таблице `player_filters`."""

    def __init__(self) -> None:
        super().__init__(EFilterTypes.player)
        # Поля, соответствующие столбцам БД
        self._player_name_changed: bool = False
        self._player_private_changed: bool = False
        self._check_online_status: bool = False
        self._check_server_change: bool = False

    @property
    def player_name_check(self) -> bool:
        return self._player_name_changed

    @property
    def player_private_check(self) -> bool:
        return self._player_private_changed

    @property
    def check_online_status(self) -> bool:
        return self._check_online_status

    @property
    def check_server_change(self) -> bool:
        return self._check_server_change

    @player_name_check.setter
    def player_name_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('Value must be bool')
        self._player_name_changed = value

    @player_private_check.setter
    def player_private_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('Value must be bool')
        self._player_private_changed = value

    @check_online_status.setter
    def check_online_status(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('Value must be bool')
        self._check_online_status = value

    @check_server_change.setter
    def check_server_change(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('Value must be bool')
        self._check_server_change = value

    def to_db_dict(self, profile_id: int) -> Dict[str, Any]:
        return {
            'fk_id_profile': profile_id,
            'player_name_changed': self._player_name_changed,
            'player_private_changed': self._player_private_changed,
            'check_online_status': self._check_online_status,
            'check_server_change': self._check_server_change,
            'apply_to_all': self._apply_to_all,
            'specific_player_id': self._specific_entity_id
        }