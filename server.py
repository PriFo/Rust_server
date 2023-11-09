
class Response:
    def __init__(self, data: dict) -> None:
        self._type: str = data.get("data").get("type")
        self._id: str = data.get("data").get("id")
        self._data: dict = data.get('attributes')

    def get_object(self):
        """Метод, возвращающий объект по заданному типу"""
        if self._type == "player":
            return Player(self._id, self._data)
        elif self._type == "server":
            return Server(self._id, self._data).get_server()


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

    # TODO: создать методы __str__ и сопутствующие обработке информации


class Server:
    """
    Класс-родитель для всех остальных классов с информацией о сервере
    """

    def __init__(self, id: str, data: dict) -> None:
        self._id: str = id
        self._data: dict = data
        self._name: str = self._data.get('name')
        self._status: str = self._data.get('status')
        self._players: int = self._data.get('players')
        self._max_players: int = self._data.get('maxPlayers')
        self._ip: str = self._data.get('ip')
        self._port: int = self._data.get('port')
        self._private: bool = self._data.get('private')
        self._query_status: str = self._data.get('queryStatus')
        self._country: str = self._data.get('country')
        self._address: str = self._data.get('address')


class RustServer(Server):
    # TODO: переписать класс с использование метода initialize в
    # качестве protected для метода __init__
    """
    Класс данных с основной информацией о сервере в игре Rust
    """

    def __init__(self, id: str, data: dict) -> None:
        # инициализация основной информации по серверу
        super().__init__(id, data)
        # инициализация данных сервера rust
        self._server_queued_players: int = 0
        self._server_last_wipe: str = ""
        self._server_pve: bool = False
        self._server_url: str = ""
        self._server_map_url: str = ""
        self._server_map_thumbnailUrl: str = ""

        self._initialize()

    def _initialize(self) -> None:

        # Получение информации о сервере
        details: dict = self._data.get("details")
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
        return ''


class ServerFactory:
    def get_server(self, id: str, data: dict) -> Server:
        game_id: str = self._get_game_id(data)
        if game_id == "rust":
            return RustServer(id, data)

    def _get_game_id(self, data: dict) -> str:
        return data.get("data").get("relationships").get("game").get("data").get("id")
