
from errorresponse import ErrorResponse as ER
from data_classes import Response as resp
from data_classes import Server
from dispatcher import Dispatcher
from json import loads as make_dict_from_str

from aiohttp import ClientSession
import aiofiles
from os import getenv
from asyncio import sleep as aSleep
from asyncio import create_task, gather


class EPartitions:
    
    servers: str = '/servers/'
    players: str = '/players/'

# TODO: переписать под использование перечислений из класса EPartitions
# TODO: дописать методы для обработки информации об игроках
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
    
    async def async_get_all_servers(self) -> dict:
        servers_list: list = []
        servers_tasks: list = []
        async with ClientSession() as session:
            
            for key in self._servers.keys():
                servers_tasks.append(create_task(self._get_server_info(session, key)))

            # print("Keys: OK!")
            servers_list = await gather(*servers_tasks)
            # print(f"Servers: {servers_list}")

        servers_dict: dict = {class_obj.name: class_obj for class_obj in servers_list}

        return servers_dict
    
    async def _get_server_info(self, session, server: str) -> (Server, ER):
        some_obj = None

        async with session.get(
            url=self._servers_url + self._servers.get(server), 
            headers=self._headers
        ) as response:
            
            # Заполнение данных в список
            if response.status == 200:
                # print(f"{server}: OK!")
                server_data: dict = dict(await response.json())
                object_getter: resp = resp(server_data)
                some_obj = object_getter.get_object()
                # print(f"get_obj: ok!")
                if some_obj.game_id == 'rust':
                    return some_obj
            else:
                some_obj = ER()
                some_obj.initialize(
                    data=dict(await response.json())
                )
    
        return some_obj


class BattleMetricsController:

    def __init__(self) -> None:
        self._dp: Dispatcher = Dispatcher()
        self._servers_json_path: str = 'jsons/servers.json'
        self._url: str = ''
        self._bm_response: BattleMetricsResponse = BattleMetricsResponse()
        self._servers_info: dict = {}

    async def update_info(self, delay: int = 5) -> None:
        # TODO: Обрабатывать ErrorResponse
        await self._bm_response.async_initialize()
        self._servers_info = await self._bm_response.async_get_all_servers()

        last_info: dict = self._servers_info
        while True:
            await aSleep(delay)
            self._servers_info = await self._bm_response.async_get_all_servers()
            differences: list = await self._find_differences_servers(last_info=last_info)
            last_info = self._servers_info
            self._dp.handle_differences(differences=differences)


    async def _find_differences_servers(self, last_info: dict) -> list:
        tasks: list = []
        
        for key in self._servers_info:
            if last_info[key] != self._servers_info[key]:
                tasks.append(
                    create_task(
                        self.__find_differences_in_servers(
                            last_server_info=last_info[key], server_info=self._servers_info[key]
                        )
                    )
                )
        differences: list = await gather(*tasks)
        return differences

    async def __find_differences_in_servers(self, last_server_info: Server, server_info: Server) -> dict:
        difference_list: set = set(last_server_info.__dict__.items()) ^ set(server_info.__dict__.items())
        difference: dict = {'name': last_server_info.name}
        for item in difference_list:
            if item[1] == last_server_info.__dict__[item[0]]:
                difference['old'] = {item[0]: item[1]}
            else:
                difference['new'] = {item[0]: item[1]}
        # print(f'\033[4m\033[34m{server_info.name=}:\033[0m\033[32m {difference}\033[37m')
        return difference
