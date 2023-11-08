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
    Класс-фабрика для создания серверов, соответствующих определенной игре
    """

    def __init__(self, id: str, data: dict) -> None:
        self._id: str = id
        self._data: dict = data
        self._name: str = self._data.get('name')
        self._


class RustServer(Server):
    # TODO: переписать класс с использование метода initialize в
    # качестве protected для метода __init__
    """
    Класс данных с основной информацией о сервере в игре Rust
    """

    def __init__(self, id: str, data: dict) -> None:
        # инициализация основной информации по серверу
        super().__init__(id, data)
        #
        self._server_name: str = ""
        self._server_status: str = ""
        self._server_address: str = ""
        self._server_ip: str = ""
        self._server_port: int = 0
        self._server_cur_players: int = 0
        self._server_max_players: int = 0
        self._server_queued_players: int = 0
        self._server_last_wipe: str = ""
        self._server_pve: bool = False
        self._server_url: str = ""
        self._server_map_url: str = ""
        self._server_map_thumbnailUrl: str = ""

        self._initialize()

    def _initialize(self) -> None:

        # Получение информации о сервере
        server_data: dict = self._data.get("data")
        if server_data != None:
            attributes: dict = server_data.get("attributes")
            if attributes != None:
                self._server_name: str = attributes.get("name")
                self._server_id: str = attributes.get("id")
                self._server_status: str = attributes.get("status")
                self._server_address: str = attributes.get("address")
                self._server_ip: str = attributes.get("ip")
                self._server_port: int = attributes.get("port")
                self._server_cur_players: int = attributes.get("players")
                self._server_max_players: int = attributes.get("maxPlayers")

            details: dict = attributes.get("details")
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
        return f'Игра: {self._server_game_id}\
            \nНазвание: {self._server_name}\
            \nСтатус: {self._server_status}\
            \nИгроки: {self._server_cur_players}/{self._server_max_players}\
            \nОчередь: {self._server_queued_players} игроков\
            \nПоследний вайп: {self._server_last_wipe}\
            \nPVE: {"ДА" if self._server_pve else "НЕТ"}\
            \n\nАдрес сайта: {self._server_url}\
            \nИнтерактивная карта сервера: {self._server_map_url}\
            \nИзображение карты: {self._server_map_thumbnailUrl}\
            \n\nКоманда для подключения: client.connect \
            {self._server_ip}:{self._server_port}\
            \nАльтернативная команда для подключения: client.connect \
            {self._server_address}'


class ServerFactory:
    def get_server(self, id: str, data: dict) -> Server:
        game_id: str = self._get_game_id(data)
        if game_id == "rust":
            return RustServer(id, data)

    def _get_game_id(self, data: dict) -> str:
        return data.get("data").get("relationships").get("game").get("data").get("id")
