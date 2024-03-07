from filters import RustFilter


class Player:
    """
    Класс, содержащий полную информацию о игроке: \n
    - ссылка на стим (еще не проверял) \n
    - активный сервер \n
    - последнее появление в сети и т.д.
    """

    def __init__(self, id: str, data: dict) -> None:
        self._id: str = id
        self._data: dict = data
        self._name: str = self._data.get('name')
        self._private: bool = self._data.get('private')
        self._positiveMatch: bool = self._data.get('positiveMatch')
        self._player_servers: list = []

    def __str__(self) -> str:
        return f'Игрок: {self._name}\n \
            Приватный профиль: {"Да" if self._private else "Нет"}\n \
            Прямое получение данных с серверов: {"Да" if self._positiveMatch else "Нет"}'


class Server:
    """
    Класс-родитель для всех остальных классов с информацией о сервере
    """

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
        return f'Игра: Rust\n\n \
            Название: {self._name}\n \
            Приватный севрер: {"Да" if self._private else "Нет"}\n \
            Страна: {self._country}\n \
            Статус: {self._status}\n \
            Игроки: {self._players}/{self._max_players} ({self._server_queued_players})\n \
            Последний вайп: {self._server_last_wipe}\n \
            PVE: {"Да" if self._server_pve else "Нет"}\n\n \
            Адрес сервера: {self._server_url}\n \
            Интерактивная карта сервера: {self._server_map_url}\n \
            Изображение карты сервера: {self._server_map_thumbnailUrl}\n\n \
            Команда для подключения по IP: {self._ip}:{self._port}'
    
    def __eq__(self, __value: object) -> bool:
        return self.__dict__ == __value.__dict__
    
    def __ne__(self, __value: object) -> bool:
        return self.__dict__ != __value.__dict__
        

class ServerFactory:
    def get_server(self, id: str, data: dict) -> Server:
        game_id: str = self._get_game_id(data)
        if game_id == "rust":
            return RustServer(id, data.get('attributes'), game_id)

    def _get_game_id(self, data: dict) -> str:
        return data.get("relationships").get("game").get("data").get("id")


class Response:
    def __init__(self, data: dict) -> None:
        self._type: str = data.get("data").get("type")
        self._id: str = data.get("data").get("id")
        self._data: dict = data.get('data')

    def get_object(self):
        """Метод, возвращающий объект по заданному типу"""
        if self._type == "player":
            return Player(self._id, self._data)
        elif self._type == "server":
            return ServerFactory().get_server(self._id, self._data)


class Profile:
    
    def __init__(self, *args, **kwargs) -> None:
        
        self._rustFilter: RustFilter = None
        self._id: str = kwargs.get('id')
        self._nickname: str = kwargs.get('nickname')
        self._name: str = kwargs.get('name')
        self._surname: str = kwargs.get('surname')

    @property
    def id(self) -> str:
        return self._id
    
    @property
    def rustFilter(self) -> RustFilter:
        return self._rustFilter
    
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
    
    @rustFilter.setter
    def rustFilter(self, value: RustFilter) -> None:
        if type(value) is not RustFilter:
            raise TypeError('The rustFilter field must be an object of the RustFilter class!')
        else:
            self._rustFilter = value

    @nickname.setter
    def nickname(self, value: str) -> None:
        self._nickname = str(value)

    @name.setter
    def name(self, value: str) -> None:
        self._name = str(value)

    @surname.setter
    def surname(self, value: str) -> None:
        self._surname = str(value)
