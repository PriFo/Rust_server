
from typing import Any


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
        game_id: str = EGames.none
    ) -> None:
        self._filter_type: str = filter_type
        self._game_id: str = game_id

    @property
    def filter_type(self) -> str:
        return self._filter_type
    
    @property
    def game_id(self) -> str:
        return self._game_id
    
    def get_filter(self, attr: str) -> Any:
        """Получает значение фильтра по имени атрибута"""
        attr_name = f'_{attr}_check'
        if hasattr(self, attr_name):
            return getattr(self, attr_name)
        raise AttributeError(f"Filter has no attribute '{attr}'")

class __ServerFilter(Filter):

    def __init__(self) -> None:
        super().__init__(EFilterTypes.server)
        self._players_check: int = -1 # -1 - off, [0...9999+] - on
        self._max_player_check: int = -1 # -1 - off, [0...9999+] - on
        self._status_check: bool = False
        self._ip_port_check: bool = False
        self._private_check: bool = False
        self._updated_check: bool = False
    
    @property
    def players_check(self) -> int:
        return self._players_check
    
    @property
    def max_player_check(self) -> int:
        return self._max_player_check
    
    @property
    def status_check(self) -> bool:
        return self._status_check
    
    @property
    def private_check(self) -> bool:
        return self._private_check
    
    @property
    def ip_port_check(self) -> bool:
        return self._ip_port_check
    
    @property
    def updated_check(self) -> bool:
        return self._updated_check
    
    @players_check.setter
    def players_check(self, value: int) -> None:
        if not isinstance(value, int):
            raise TypeError('New value type must be int')
        if value < 0:
            self._players_check = -1
        else:
            self._players_check = value

    @max_player_check.setter
    def max_player_check(self, value: int) -> None:
        if not isinstance(value, int):
            raise TypeError('New value type must be int')
        if value < 0:
            self._max_player_check = -1
        else:
            self._max_player_check = value
    
    @status_check.setter
    def status_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('New value type must be bool')
        self._status_check = value

    @ip_port_check.setter
    def ip_port_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('New value type must be bool')
        self._ip_port_check = value

    @private_check.setter
    def private_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('New value type must be bool')
        self._private_check = value

    @updated_check.setter
    def updated_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('New value type must be bool')
        self._updated_check = value


class RustFilter(__ServerFilter):

    def __init__(self) -> None:
        super().__init__()
        self._queued_players_check: int = -1 # -1 - off, [0...9999+] - on
        self._last_wipe_check: bool = True
        self._next_wipe_check: bool = True # include date and type
        self._pve_check: bool = False
        self._url_check: bool = False
        self._map_url_check: bool = False
        self._map_thumbnailUrl_check: bool = False

    @property
    def queued_players_check(self) -> int:
        return self._queued_players_check

    @property
    def last_wipe_check(self) -> bool:
        return self._last_wipe_check

    @property
    def next_wipe_check(self) -> bool:
        return self._next_wipe_check

    @property
    def pve_check(self) -> bool:
        return self._pve_check

    @property
    def url_check(self) -> bool:
        return self._url_check

    @property
    def map_url_check(self) -> bool:
        return self._map_url_check

    @property
    def map_thumbnailUrl_check(self) -> bool:
        return self._map_thumbnailUrl_check
    
    @queued_players_check.setter
    def queued_players_check(self, value: int) -> None:
        if not isinstance(value, int):
            raise TypeError('New value type must be int')
        if value < 0:
            self._queued_players_check = -1
        else:
            self._queued_players_check = value
    
    @last_wipe_check.setter
    def last_wipe_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('New value type must be bool')
        self._last_wipe_check = value
    
    @next_wipe_check.setter
    def next_wipe_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('New value type must be bool')
        self._next_wipe_check = value
    
    @pve_check.setter
    def pve_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('New value type must be bool')
        self._pve_check = value
    
    @url_check.setter
    def url_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('New value type must be bool')
        self._url_check = value
    
    @map_url_check.setter
    def map_url_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('New value type must be bool')
        self._map_url_check = value
    
    @map_thumbnailUrl_check.setter
    def map_thumbnailUrl_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('New value type must be bool')
        self._map_thumbnailUrl_check = value


class PlayerFilter(Filter):
    
    def __init__(self) -> None:
        super().__init__(EFilterTypes.player)
        self._player_name_check: bool = False
        self._player_private_check: bool = False
        self._player_profile_link_check: bool = False # is not using now

    @property
    def player_name_check(self) -> bool:
        return self._player_name_check
    
    @property
    def player_private_check(self) -> bool:
        return self._player_private_check
    
    @property
    def player_profile_link_check(self) -> bool:
        return self._player_profile_link_check
    
    @player_name_check.setter
    def player_name_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('New value type must be bool')
        self._player_name_check = value

    @player_private_check.setter
    def player_private_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('New value type must be bool')
        self._player_private_check = value

    @player_profile_link_check.setter
    def player_profile_link_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError('New value type must be bool')
        self._player_profile_link_check = value
