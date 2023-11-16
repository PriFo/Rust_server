
# TODO: Прописать метод для работы с серверами (хранение информации об /
# активных серверах без хранения всей информации о серверере)
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

    def __str__(self) -> str:
        return f'Игрок: {self._name}\n \
            Приватный профиль: {"Да" if self._private else "Нет"}\n \
            Прямое получение данных с серверов: {"Да" if self._positiveMatch else "Нет"}'


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

    @property
    def name(self) -> str:
        return self._name


class RustServer(Server):
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


class ServerFactory:
    def get_server(self, id: str, data: dict) -> Server:
        game_id: str = self._get_game_id(data)
        if game_id == "rust":
            return RustServer(id, data.get('attributes'))

    def _get_game_id(self, data: dict) -> str:
        return data.get("relationships").get("game").get("data").get("id")


class Response:
    def __init__(self, data: dict) -> None:
        self._type: str = data.get("data").get("type")
        self._id: str = data.get("data").get("id")
        self._data: dict = data.get('data')

    def get_object(self) -> (Player, Server):
        """Метод, возвращающий объект по заданному типу"""
        if self._type == "player":
            return Player(self._id, self._data)
        elif self._type == "server":
            return ServerFactory().get_server(self._id, self._data)
