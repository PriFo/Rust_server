
from typing import Union
from filters import Filter
from errorresponse import ErrorResponse


class Server:
    """
    Класс-родитель для всех остальных классов с информацией о сервере
    """

    def __init__(self, id: str, data: dict, game_id: str) -> None:
        self._id: str = id
        self._name: str = data.get('name')
        self._status: str = data.get('status')
        self._players: int = data.get('players')
        self._maxPlayers: int = data.get('maxPlayers')
        self._ip: str = data.get('ip')
        self._port: int = data.get('port')
        self._private: bool = data.get('private')
        self._queryStatus: str = data.get('queryStatus')
        self._country: str = data.get('country')
        self._address: str = data.get('address')
        self._updatedAt: str = data.get('updatedAt')
        self._game_id: str = game_id

    @property
    def name(self) -> str:
        return self._name
    
    @property
    def game_id(self) -> str:
        return self._game_id


class RustServer(Server):
    """
    Класс данных с основной информацией о сервере в игре Rust
    """

    def __init__(self, id: str, data: dict, game_id: str) -> None:
        # инициализация основной информации по серверу
        super().__init__(id, data, game_id)
        # инициализация данных сервера rust
        self._queued_players: int = 0
        self._last_wipe: str = ""
        self._next_wipe: str = ""
        self._next_wipe_type: str = ""
        self._pve: bool = False
        self._url: str = ""
        self._map_url: str = ""
        self._map_thumbnailUrl: str = ""
        self._steam_id: str = ""
        self._modded: bool = ""
        self._official: bool = ""
        self._description: str = ""
        self._gamemode: str = ""

        self._initialize(data)

    def _initialize(self, data: dict) -> None:

        # Получение информации о сервере

        details: dict = data.get("details")
        if details != None:
            self._queued_players = details.get("rust_queued_players")
            self._last_wipe = details.get("rust_last_wipe").replace("T", " ")
            self._pve: bool = details.get("pve")
            self._url: str = details.get("rust_url")
            self._next_wipe = details.get("rust_next_wipe").replace("T", " ")
            self._next_wipe_type = details.get("rust_wipes")[0].get("type")

            rust_maps: dict = details.get("rust_maps")
            if rust_maps != None:
                self._map_url: str = rust_maps.get("url")
                self._map_thumbnailUrl: str = rust_maps.get("thumbnailUrl")
        else:
            raise ValueError("Data details is None!")


    def __str__(self) -> str:
        return f'Игра: Rust\n\n \
            Название: {self._name}\n \
            Приватный севрер: {"Да" if self._private else "Нет"}\n \
            Страна: {self._country}\n \
            Статус: {self._status}\n \
            Игроки: {self._players}/{self._maxPlayers} ({self._queued_players})\n \
            Последний вайп: {self._last_wipe}\n \
            Следующий вайп: {self._next_wipe}\n \
            PVE: {"Да" if self._pve else "Нет"}\n\n \
            Адрес сервера: {self._url}\n \
            Интерактивная карта сервера: {self._map_url}\n \
            Изображение карты сервера: {self._map_thumbnailUrl}\n\n \
            Команда для подключения по IP: {self._ip}:{self._port}'
    
    def __eq__(self, __value: object) -> bool:
        return self.__dict__ == __value.__dict__
    
    def __ne__(self, __value: object) -> bool:
        return self.__dict__ != __value.__dict__
        

class Player:
    """
    Класс, содержащий полную информацию о игроке: \n
    - ссылка на стим (реализация отложена, Steam-API key хранится в .env) \n
    - активный сервер \n
    - последнее появление в сети и т.д.
    """

    def __init__(self, id: str, data: dict[str, str]) -> None:
        self._id: str = id
        self._data: dict = data
        self._name: str = self._data.get('name')
        self._private: bool = self._data.get('private')
        self._positiveMatch: bool = self._data.get('positiveMatch')
        self._player_servers: list[Server] = []
        self._online: bool = False
        self._online_server: Server = None
    
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
    
    def __eq__(self, __value: object) -> bool:
        return self.__dict__ == __value.__dict__
    
    def __ne__(self, __value: object) -> bool:
        return self.__dict__ != __value.__dict__

    def __str__(self) -> str:
        return f'Игрок: {self._name}\n \
            ID на сайте battlemetrics: {self._id}\n \
            Приватный профиль: {"Да" if self._private else "Нет"}\n \
            Прямое получение данных с серверов: {"Да" if self._positiveMatch else "Нет"}'


class ServerFactory:
    
    @staticmethod
    def get_server(id: str, data: dict) -> Server:
        game_id: str = ServerFactory.__get_game_id(data)
        if game_id == "rust":
            return RustServer(id, data.get('data').get('attributes'), game_id)

    @staticmethod
    def __get_game_id(data: dict) -> str:
        return data.get('data').get("relationships").get("game").get("data").get("id")


class ClassFactory:

    @staticmethod
    def get_object(data: dict) -> Union[Player, Server, ErrorResponse]:
        """Метод, возвращающий объект по заданному типу"""
        try:
            __type = data.get("data").get("type")
            __id = data.get("data").get("id")

            if __type == "player":
                return Player(__id, data)
            elif __type == "server":
                return ServerFactory.get_server(__id, data)
        except ValueError as e:
            error_resp = ErrorResponse()
            if data.get('errors'):
                error_resp.initialize(data)
            else:
                error_resp.initialize(str(ValueError), str(e))
            return error_resp


class Profile:
    
    def __init__(self, **kwargs: dict[str, str]) -> None:
        
        self._id: str = kwargs.get('id')
        self._nickname: str = kwargs.get('nickname')
        self._name: str = kwargs.get('name')
        self._surname: str = kwargs.get('surname')
        self._filters: dict = {}

    @property
    def id(self) -> str:
        return self._id
    
    def add_filter(self, input_filter: Filter) -> None:
        if not isinstance(input_filter, Filter):
            raise TypeError(f'Input filter must be Filter, not {type(input_filter)}')
        self._filters[input_filter.game_id if input_filter.game_id != '' else input_filter.filter_type] = input_filter

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
