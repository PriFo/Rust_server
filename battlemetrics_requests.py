
from requests import Response
from requests import get as session_get
from json import load as make_dict_from_file
from json import loads as make_dict_from_str
from aiohttp import ClientSession
import aiofiles
from os import getenv


class NullServer:
    """
        Класс данных с информацией о несуществующем сервере
    """
    def __init__(self) -> None:
        self._response_code: int = 0
        self._server_key: str = ''
        self._server_id: str = ''

    def initialize(
        self,
        code: int,
        key: str,
        id: str
    ) -> None:
        self._response_code = code
        self._server_key = key
        self._server_id = id

    def __str__(self) -> str:
        return f'Ошибка запроса данных по серверу: \
            \n\tKey: {self._server_key}\
            \n\tID: {self._server_id}\
            \n\tResponse status code: {self._response_code}\
            \n\nСледующие данные могут содержать ошибки: API-токен сайта battlemetrics.com, ID сервера'


class RustServer:
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


class BattleMetricsResponse:

    def __init__(self) -> None:
        self._url: str = "https://api.battlemetrics.com/servers/"
        self._headers: dict = {}
        self._api_key: str = ''
        self._servers: dict = {}

    def _read_file_as_dict(self, file_path: str) -> dict:
        with open(file=file_path, mode='r', encoding='utf-8') as file: 
            return make_dict_from_file(file)

    def initialize(self) -> None:
        self._api_key = getenv('BM_API_KEY')

        self._servers = self._read_file_as_dict('servers.json')

        self._headers['Authorization'] = f'Bearer {self._api_key}'

    async def _async_read_file_as_dict(self, file_path) -> dict:
        async with aiofiles.open(file=file_path, mode='r', encoding='utf-8') as file:
            content = await file.read()
            return make_dict_from_str(content)

    async def async_initialize(self) -> None:
        
        self._api_key = getenv('BM_API_KEY')

        self._servers = await self._async_read_file_as_dict('servers.json')

        self._headers['Authorization'] = f'Bearer {self._api_key}'

    def get_all_servers(self) -> list:
        servers_list: list = []

        for key in self._servers.keys():
            
            #Синхронный запрос данных от API
            response: Response = session_get(
                url=self._url + self._servers.get(key), 
                headers=self._headers
            )

            # Заполнение данных в список
            if response.status_code == 200:
                server_data: dict = dict(response.json())
                
                #При необходимости можно расширить список создаваемых серверов
                if self._isrust(server_data=server_data):
                    server = RustServer()
                    server.initialize(server_data=server_data)
                    servers_list.append(server)
            else:
                #Если API не вернула OK, то создаем нулевой сервер
                server = NullServer()
                server.initialize(
                    code=response.status_code, 
                    key=key, 
                    id=self._servers.get(key)
                )
                servers_list.append(server)

        return servers_list
    
    async def async_get_all_servers(self) -> list:
        servers_list: list = []

        for key in self._servers.keys():
            async with ClientSession() as session:
                async with session.get(
                    url=self._url + self._servers.get(key), 
                    headers=self._headers
                ) as response:

                    # Заполнение данных в список
                    if response.status == 200:
                        server_data: dict = dict(await response.json())
                        if self._isrust(server_data=server_data):
                            server = RustServer()
                            server.initialize(server_data=server_data)
                            servers_list.append(server)
                    else:
                        server = NullServer()
                        server.initialize(
                            code=response.status, 
                            key=key, 
                            id=self._servers.get(key)
                        )
                        servers_list.append(server)

        return servers_list
    
    def _isrust(self, server_data: dict) -> bool:
        return server_data.get('data').get('relationships').get('game').get('data').get('id') == 'rust'
