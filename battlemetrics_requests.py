
from errorresponse import ErrorResponse as ER
from server import Response as resp
from server import Player, Server, RustServer
from requests import Response
from requests import get as session_get
from json import load as make_dict_from_file
from json import loads as make_dict_from_str
from aiohttp import ClientSession
import aiofiles
from os import getenv


class EPartitions:
    
    servers: str = '/servers/'
    players: str = '/players/'

# TODO: переписать под использование перечислений из класса EPartitions
# TODO: дописать методы для обработки информации об игроках
# TODO: написать управляющий класс для BattleMetricsResponse и разграничить модель данных с управляющей частью
# TODO: перейти к архитектуре MVC
class BattleMetricsResponse:

    def __init__(self) -> None:
        self._url: str = "https://api.battlemetrics.com"
        self._servers_url: str = "https://api.battlemetrics.com/servers/"
        self._players_url: str = "https://api.battlemetrics.com/players/"
        self._headers: dict = {}
        self._api_key: str = ''
        self._servers: dict = {}
        self._players: dict = {}
    
    async def _async_read_file_as_dict(self, file_path) -> dict:
        async with aiofiles.open(file=file_path, mode='r', encoding='utf-8') as file:
            content = await file.read()
            return make_dict_from_str(content)

    async def async_initialize(self) -> None:
        
        self._api_key = getenv('BM_API_KEY')

        self._servers = await self._async_read_file_as_dict('jsons/servers.json')

        self._headers['Authorization'] = f'Bearer {self._api_key}'

    def get_all_servers(self) -> list:
        servers_list: list = []

        for key in self._servers.keys():
            
            #Синхронный запрос данных от API
            response: Response = session_get(
                url=self._servers_url + self._servers.get(key), 
                headers=self._headers
            )

            # Заполнение данных в список
            if response.status_code == 200:
                server_data: dict = dict(response.json())
                
                # TODO: добавить использование фабрики для создания сервера
                object_getter: resp = resp(server_data)
                some_obj = resp.get_object()
                if type(some_obj) == Server:
                    if type(some_obj) == RustServer:
                        self._servers[some_obj.name] = some_obj

            else:
                # создаем объект класса ErrorResponse из-за вернувшейся ошибки
                server = ER()
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
                    url=self._servers_url + self._servers.get(key), 
                    headers=self._headers
                ) as response:

                    # Заполнение данных в список
                    if response.status == 200:
                        server_data: dict = dict(await response.json())
                        # TODO: добавить использование фабрики для создания сервера
                        object_getter: resp = resp(server_data)
                        some_obj = resp.get_object()
                        if type(some_obj) == Server:
                            if type(some_obj) == RustServer:
                                self._servers[some_obj.name] = some_obj
                    else:
                        server = ER()
                        server.initialize(
                            code=response.status, 
                            key=key, 
                            id=self._servers.get(key)
                        )
                        servers_list.append(server)

        return servers_list


class BattleMetricsController:

    def __init__(self) -> None:
        self._servers_json_path: str = 'jsons/servers.json'
        self._url: str = ''
        self._bm_response: BattleMetricsResponse = BattleMetricsResponse()

    def update_info(self) -> None:
        pass
