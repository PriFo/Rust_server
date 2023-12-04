
# TODO: прописать заготовленные фильтры для диспетчера

class ServerFilter:

    def __init__(self) -> None:
        self._players_min_check: int = -1
        self._status_check: bool = True
        self._ip_port_check: bool = True

    def get_filters(self) -> dict:
        return {
            'players': self._players_min_check,
            'status': self._status_check,
            'ip_port': self._ip_port_check
        }
    
    @property
    def players_min_check(self) -> int:
        return self._players_min_check
    
    @property
    def status_check(self) -> bool:
        return self._status_check
    
    @property
    def ip_port_check(self) -> bool:
        return self._ip_port_check

    def change_players(self, value: int) -> None:
        self._players_min_check = value
