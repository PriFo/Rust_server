from filters import Filter


class Server:
    """
    Класс-родитель для всех остальных классов с информацией о сервере

    
    """
    
    TYPE = 'server'

    def __init__(self, id: str, data: dict, game_id: str) -> None:
        self._id: str = id
        self._name: str = data.get('name')
        self._status: str = data.get('status')
        self._players: int = data.get('players')
        self._max_players: int = data.get('maxPlayers')
        self._ip: str = data.get('ip')
        self._port: int = data.get('port')
        self._private: bool = data.get('private')
        self._query_status: str = data.get('queryStatus')
        self._country: str = data.get('country')
        self._address: str = data.get('address')
        self._game_id: str = game_id

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
            Приватный севрер: {'Да' if self._private else 'Нет'}\n\
            Страна: {self._country}\n\
            Статус: {'онлайн' if self._status == 'online' else 'оффлайн'}\n\
            Игроки: {self._players}/{self._max_players}\n\
            Команда для подключения по IP: connect {self._ip}:{self._port}"
    
    def __dict__(self) -> dict:
        return {
            'type': self.TYPE,
            'id': self._id,
            'name': self._name,
            'status': self._status,
            'players': self._players,
            'max_players': self._max_players,
            'ip': self._ip,
            'port': self._port,
            'private': self._private,
            'query_status': self._query_status,
            'country': self._country,
            'address': self._address,
            'game_id': self._game_id
        }


class RustServer(Server):
    """
    Класс данных с основной информацией о сервере в игре Rust
    """

    def __init__(self, id: str, data: dict, game_id: str) -> None:
        # инициализация основной информации по серверу
        super().__init__(id, data, game_id)
        # инициализация данных сервера rust
        self._server_queued_players: int = 0
        self._server_last_wipe: str = ""
        self._server_pve: bool = False
        self._server_url: str = ""
        self._server_map_url: str = ""
        self._server_map_thumbnailUrl: str = ""

        self._initialize(data)

    def _initialize(self, data: dict) -> None:

        # Получение информации о сервере
        details: dict = data.get("details")
        if details != None:
            self._server_queued_players: int = details.get("rust_queued_players")
            self._server_last_wipe: str = details.get("rust_last_wipe").replace(
                "T", " "
            )
            self._server_pve: bool = details.get("pve")
            self._server_url: str = details.get("rust_url")

        rust_maps: dict = details.get("rust_maps")
        if rust_maps != None:
            self._server_map_url: str = rust_maps.get("url")
            self._server_map_thumbnailUrl: str = rust_maps.get("thumbnailUrl")

    def __str__(self) -> str:
        return str(super()) + f'\nИгра: Rust\n\
            Игроков в очереди: {self._server_queued_players}\n\
            Последний вайп: {self._server_last_wipe}\n\
            PVE: {"Да" if self._server_pve else "Нет"}\n\
            Адрес сервера: {self._server_url}\n\
            Интерактивная карта сервера: {self._server_map_url}\n\
            Изображение карты сервера: {self._server_map_thumbnailUrl}\n'
    
    def __eq__(self, __value: object) -> bool:
        return self.__dict__() == __value.__dict__()
    
    def __ne__(self, __value: object) -> bool:
        return self.__dict__() != __value.__dict__()
    
    def __dict__(self) -> dict:
        return super().__dict__().update({
            'server_queued_players': self._server_queued_players,
            'server_last_wipe': self._server_last_wipe,
            'server_pve': self._server_pve,
            'server_url': self._server_url,
            'server_map_url': self._server_map_url,
            'server_map_thubnailUrl': self._server_map_thumbnailUrl
        })
        

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
    def get_object(data: dict):
        """Метод, возвращающий объект по заданному типу"""
        
        __type = data.get("data").get("type")
        __id = data.get("data").get("id")

        if __type == "player":
            return Player(__id, data.get('data').get('attributes'))
        elif __type == "server":
            return ServerFactory.get_server(__id, data)


class Player:
    #TODO сделать возможность добавления сервера (сервер, информация об игроке)
    """
    Класс, содержащий полную информацию о игроке: \n
    - ссылка на стим (еще не проверял) \n
    - активный сервер \n
    - последнее появление в сети и т.д.
    """

    TYPE = 'player'

    def __init__(self, id: str, data: dict) -> None:
        self._id: str = id
        self._name: str = data.get('name')
        self._private: bool = data.get('private')
        self._positiveMatch: bool = data.get('positiveMatch')
        self._online_server: Server = None
        self._player_servers: dict = {}

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
    def online_server(self) -> Server:
        return self._online_server
    
    @property
    def player_servers(self) -> list:
        return self._player_servers
    
    def get_server_keys(self) -> list:
        return self._player_servers.keys()
    
    @id.setter
    def id(self, value: tuple[str, int]) -> None:
        if not isinstance(value, str) or not isinstance(value, int):
            raise TypeError(f'Player id must be int or str not {type(value)}')
        self._id = str(value)

    @name.setter
    def name(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError(f'Player name must be str not {type(value)}')
        self._name = value

    @private.setter
    def private(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError(f'Player private status must be bool not {type(value)}')
        self._private = value

    @positiveMatch.setter
    def positiveMatch(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError(f'Player positive match status must be bool not {type(value)}')
        self._positiveMatch = value

    @online_server.setter
    def online_server(self, value: Server) -> None:
        if not isinstance(value, Server):
            raise TypeError(f'Player online server must be Server not {type(value)}')
        self._online_server = value

    def add_server(self, value: Server) -> None:
        if not isinstance(value, Server):
            raise TypeError(f'Player server must be instance of Server not {type(value)}')
        self._player_servers[value.id] = value

    def __eq__(self, __value: object) -> bool:
        return self.__dict__() == __value.__dict__()
    
    def __ne__(self, __value: object) -> bool:
        return self.__dict__() != __value.__dict__()

    def __str__(self) -> str:
        return f'Игрок: {self._name}\n\
            Приватный профиль: {"Да" if self._private else "Нет"}\n\
            Положительное совпадение: {"Да" if self._positiveMatch else "Нет"}\n\
            "Активный сервер:" {self._online_server if self._online_server else ""}'
    
    def __dict__(self):
        return {
            'type': self.TYPE,
            'id': self._id,
            'name': self._name,
            'private': self._private,
            'positiveMatch': self._positiveMatch,
            'online_server': self._online_server,
            'player_servers': {server.name: server for server in self._player_servers}
        }


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

    def __init__(self, **kwargs) -> None:
        
        self._id: str = kwargs.get('id')
        self._nickname: str = kwargs.get('nickname')
        self._name: str = kwargs.get('name')
        self._surname: str = kwargs.get('surname')
        self._filters: dict = {}
        self._servers: dict = {}
        self._players: dict = {}

    @property
    def id(self) -> str:
        return self._id
    
    def add_filter(self, input_filter: Filter) -> None:
        if isinstance(input_filter, Filter):
            raise ValueError('Input filter is not Filter')
        self._filters[input_filter.filter_type] = input_filter

    def add_server(self, value: Server) -> None:
        ...

    def add_player(self, value: Player) -> None:
        ...

    def get_filter(self, filter_key: str) -> Filter:
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
