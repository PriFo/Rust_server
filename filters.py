from enum import Enum

class EFilterTypes(Enum):
    server = 'server_filter'
    rust_server = 'rust_filter'
    player = 'player_filter'
    none = 'null'


class Filter:
    
    def __init__(self, filter_type = EFilterTypes.none) -> None:
        if filter_type not in EFilterTypes:
            raise ValueError('Filter type must be in EFiltersTypes')
        self._filter_type: str = filter_type
        self._send_in_one_msg: bool = True

    @property
    def filter_type(self) -> str:
        return self._filter_type
    
    @property
    def send_in_one_msg(self) -> bool:
        return self._send_in_one_msg
    
    @send_in_one_msg.setter
    def send_in_one_msg(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError(f'Value of parametr send_in_one_msg must be bool not {type(value)}')
        self._send_in_one_msg = value
    
    @filter_type.setter
    def filter_type(self, value = EFilterTypes.none) -> None:
        if value not in EFilterTypes:
            raise TypeError('Value of parametr filter_type must be in EFiltersType')
        self._filter_type = value

    def get_filters(self) -> dict:
        return {
            'type': self._filter_type,
            'send_in_one_msg': self._send_in_one_msg
        }


class ServerFilter(Filter):

    def __init__(self, filter_type = EFilterTypes.none) -> None:
        super().__init__(filter_type)
        self._min_players_count_check: int = -1
        self._max_player_count_check: int = -1
        self._status_check: bool = True
        self._ip_port_check: bool = True
        self._private_check: bool = True

    def get_filters(self) -> dict:
        return super().get_filters() + {
            'min_players': self._min_players_count_check,
            'max_players': self._max_player_count_check,
            'status': self._status_check,
            'ip_port': self._ip_port_check, 
            'private': self._private_check
        }
    
    @property
    def players_min_check(self) -> int:
        return self._min_players_count_check
    
    @property
    def status_check(self) -> bool:
        return self._status_check
    
    @property
    def private_check(self) -> bool:
        return self._private_check
    
    @property
    def ip_port_check(self) -> bool:
        return self._ip_port_check
    
    @players_min_check.setter
    def players_min_check(self, value: int) -> None:
        if not isinstance(value, int):
            raise TypeError(f'Value type must be int not {type(value)}')
        if value < 0:
            self._min_players_count_check = -1
        else:
            self._min_players_count_check = value
    
    @status_check.setter
    def status_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError(f'Value type must be bool not {type(value)}')
        self._status_check = value

    @ip_port_check.setter
    def ip_port_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError(f'Value type must be bool not {type(value)}')
        self._status_check = value

    @private_check.setter
    def private_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError(f'Value type must be bool not {type(value)}')
        self._private_check = value

    def change_players(self, value: int) -> None:
        if not isinstance(value, bool):
            raise TypeError(f'Value type must be bool not {type(value)}')
        self._min_players_count_check = value


class RustFilter(ServerFilter):

    def __init__(self, filter_type = EFilterTypes.none) -> None:
        super().__init__(filter_type)
        self._queued_players_check: int = 0
        self._last_wipe_check: bool = True
        self._pve_check: bool = True
        self._url_check: bool = True
        self._map_url_check: bool = True
        self._map_thumbnailUrl_check: bool = True

    @property
    def queued_players_check(self) -> int:
        return self._queued_players_check

    @property
    def last_wipe_check(self) -> bool:
        return self._last_wipe_check

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
    
    def get_filters(self) -> dict:
        return super().get_filters() + {
            'queued_players_check': self._queued_players_check,
            'last_wipe_check': self._last_wipe_check,
            'pve_check': self._pve_check,
            'url_check': self._url_check,
            'map_url_check': self._map_url_check,
            'map_thumbnailUrl_check': self._map_thumbnailUrl_check
        }
    
    @queued_players_check.setter
    def queued_players_check(self, value: int) -> None:
        if not isinstance(value, int):
            raise TypeError(f'Value type must be int not {type(value)}')
        self._queued_players_check = value
    
    @last_wipe_check.setter
    def last_wipe_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError(f'Value type must be bool not {type(value)}')
        self._last_wipe_check = value
    
    @pve_check.setter
    def pve_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError(f'Value type must be bool not {type(value)}')
        self._pve_check = value
    
    @url_check.setter
    def url_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError(f'Value type must be bool not {type(value)}')
        self._url_check = value
    
    @map_url_check.setter
    def map_url_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError(f'Value type must be bool not {type(value)}')
        self._map_url_check = value
    
    @map_thumbnailUrl_check.setter
    def map_thumbnailUrl_check(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError(f'Value type must be bool not {type(value)}')
        self._map_thumbnailUrl_check = value

#TODO: разобраться с тем, какие данные необходимо хранить
class PlayerFilter(Filter):
    
    def __init__(self, filter_type = EFilterTypes.none):
        super().__init__(filter_type)
        

class FilterFactory:

    @staticmethod
    def get_filter(filter_type = EFilterTypes.none) -> Filter:
        if filter_type == EFilterTypes.none:
            return Filter(filter_type)
        elif filter_type == EFilterTypes.server:
            return ServerFilter(filter_type)
        elif filter_type == EFilterTypes.player:
            return PlayerFilter(filter_type)
        elif filter_type == EFilterTypes.rust_server:
            return RustFilter(filter_type)
