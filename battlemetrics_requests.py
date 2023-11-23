
from errorresponse import ErrorResponse as ER
from server import Response as resp
from server import Player, Server, RustServer
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
    
    async def async_get_all_servers(self) -> list:
        servers_list: list = []
        servers_tasks: list = []
        async with ClientSession() as session:
            
            for key in self._servers.keys():
                servers_tasks.append(create_task(self._get_server_info(session, key)))

            # print("Keys: OK!")
            # BUG не запускает Future
            try:
                servers_list = await gather(*servers_tasks)
            except RuntimeError:
                print('Something wrong in getting servers')
            print(f"Servers: {servers_list}")

        return servers_list
    
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
                # TODO: добавить использование фабрики для создания сервера
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
        self._servers_json_path: str = 'jsons/servers.json'
        self._url: str = ''
        self._bm_response: BattleMetricsResponse = BattleMetricsResponse()
        self._servers_info: list = []

    async def _get_server_data(self, file_name: str) -> dict:
        async with aiofiles.open(file=file_name, mode='r', encoding='utf-8') as file:
            content = await file.read()
            return make_dict_from_str(content)

    async def test_find_differences(self) -> dict:
        server_info: dict = await self._get_server_data('jsons/server_data.json')
        changed_server_info: dict = await self._get_server_data('jsons/server_data_changed.json')
        return await self._find_differences_in_dicts(server_info, changed_server_info)

    async def update_info(self, delay: int = 5) -> None:
        await self._bm_response.async_initialize()
        self._servers_info = await self._bm_response.async_get_all_servers()
        last_info: list = self._servers_info
        while True:
            await aSleep(delay)
            self._servers_info = await self._bm_response.async_get_all_servers()
            if last_info != self._servers_info:
                await self._find_differences(last_info)

    async def _find_differences(self, last_info: list) -> list:
        # TODO: написать функцию поиска различий между словарями
        tasks: list = []
        for last_server_info, server_info in last_info, self._server_info:
            tasks.append(create_task(self._find_differences_in_dicts(last_server_info, server_info)))
        differences: list = await gather(*tasks)
        return differences

    async def _find_differences_in_dicts(self, last_server_info: dict, server_info: dict, steps=2) -> dict:
        
        if steps != 0:
            return {steps: await self._find_differences_in_dicts(last_server_info, server_info, steps=steps-1)}
        else:
            return {steps: last_server_info}
