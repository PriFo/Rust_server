
from errorresponse import ErrorResponse as ER
from server import Response as resp
from requests import Response
from requests import get as session_get
from json import load as make_dict_from_file
from json import loads as make_dict_from_str
from aiohttp import ClientSession
import aiofiles
from os import getenv


class BattleMetricsResponse:

    def __init__(self) -> None:
        self._url: str = "https://api.battlemetrics.com/servers/"
        self._headers: dict = {}
        self._api_key: str = ''
        self._servers: dict = {}
    
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
                
                # TODO: добавить использование фабрики для создания сервера
                ...

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
                    url=self._url + self._servers.get(key), 
                    headers=self._headers
                ) as response:

                    # Заполнение данных в список
                    if response.status == 200:
                        server_data: dict = dict(await response.json())
                        # TODO: добавить использование фабрики для создания сервера
                    else:
                        server = ER()
                        server.initialize(
                            code=response.status, 
                            key=key, 
                            id=self._servers.get(key)
                        )
                        servers_list.append(server)

        return servers_list
    
    async def update_info(self):

        return
    
    def _isrust(self, server_data: dict) -> bool:
        return server_data.get('data').get('relationships').get('game').get('data').get('id') == 'rust'
