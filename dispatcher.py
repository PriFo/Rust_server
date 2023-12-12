from filters import RustFilter
from repository import Repository


# TODO: закончить написание класса Dispatcher
class Dispatcher(object):

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, *args, **kwargs) -> None:
        self._repo: Repository = Repository()
        self._player_min_handler = None
        self._status_handler = None
        self._private_handler = None
        self._ip_port_handler = None
        self._queued_players_handler = None
        self._last_wipe_handler = None
        self._pve_handler = None
        self._url = None

    async def handle_differences(self, differences: list) -> None:
        for diff in differences:
            print(f'\033[4m\033[34m{diff["name"]=}:\033[0m\033[32m {diff["new"]=}\033[37m')

    def handler(self, *args, **kwargs) -> None:
        def decorator(func):
            print(f'decorator:\n\n{args=}\n{kwargs=}\n{func.__name__=}')
            setattr(self, f'_{kwargs["handler"]}_handler', func)
            return func
        return decorator
            