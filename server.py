

class Response:

    def __init__(self) -> None:
        self._type: str = ''
        self._id: str = ''

    def get_server(self):
        return self
    

class Server(Response):

    def __init__(self) -> None:
        super().__init__()


class RustServer(Server):
    """
        Класс данных с основной информацией о сервере в игре Rust
    """
    def __init__(self) -> None:
        self._server_name = None
        self._server_id = None
        self._server_status = None
        self._server_address = None
        self._server_ip = None
        self._server_port = None
        self._server_cur_players = None
        self._server_max_players = None
        self._server_queued_players = None
        self._server_last_wipe = None
        self._server_pve = None
        self._server_url = None
        self._server_map_url = None
        self._server_map_thumbnailUrl = None
        self._server_game_type = None
        self._server_game_id = None

    def initialize(
            self,
            server_data: dict
    ) -> None:
        data: dict = server_data.get('data')
        if data != None:
            attributes: dict = data.get('attributes')
            if attributes != None:
                self._server_name: str = attributes.get('name')
                self._server_id: str = attributes.get('id')
                self._server_status: str = attributes.get('status')
                self._server_address: str = attributes.get('address')
                self._server_ip: str = attributes.get('ip')
                self._server_port: int = attributes.get('port')
                self._server_cur_players: int = attributes.get('players')
                self._server_max_players: int = attributes.get('maxPlayers')

            details: dict = attributes.get('details')
            if details != None:
                self._server_queued_players: int = details.get('rust_queued_players')
                self._server_last_wipe: str = details.get('rust_last_wipe').replace('T', ' ')
                self._server_pve: bool = details.get('pve')
                self._server_url: str = details.get('rust_url')                

            rust_maps: dict = details.get('rust_maps')
            if rust_maps != None:
                self._server_map_url: str = rust_maps.get('url')
                self._server_map_thumbnailUrl: str = rust_maps.get('thumbnailUrl')

            relationships_data: dict = data.get('relationships').get('game').get('data')
            if relationships_data != None:
                self._server_game_type: str = relationships_data.get('type')
                self._server_game_id: str = relationships_data.get('id')

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
            \n\nКоманда для подключения: client.connect {self._server_ip}:{self._server_port}\
            \nАльтернативная команда для подключения: client.connect {self._server_address}'
