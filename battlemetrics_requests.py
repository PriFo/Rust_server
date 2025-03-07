
from errorresponse import ErrorResponse as ER
from data_classes import ClassFactory as cfact
from data_classes import Server
from dispatcher import Dispatcher

from json import loads as make_dict_from_str
from json import dumps as make_json_from_obj

from aiohttp import ClientSession
import aiofiles
from os import getenv, path
from asyncio import sleep as aSleep
from asyncio import create_task, gather


class EPartitions:
    
    servers: str = '/servers/'
    players: str = '/players/'


# TODO: дописать методы для обработки информации об игроках
class BattleMetricsResponse:

    def __init__(self) -> None:
        self._url: str = "https://api.battlemetrics.com"
        self._headers: dict = {}
        self._api_key: str = ''
        self._servers: dict = {}
        self._players: dict = {}
    
    async def _async_read_file_as_dict(self, file_path: str) -> dict:
        async with aiofiles.open(file=file_path, mode='r', encoding='utf-8') as file:
            content = await file.read()
            return make_dict_from_str(content)

    # функция для сохранения информации в конкретный путь в файл json
    # закомментирована из-за отсутствия необходимости использовать ее после получения новой информации от API
    # с сайта battlemetrics.com
    # async def _async_save_file_as_json(self, content, file_path: str) -> bool:
    #     try:
    #         if not path.exists(file_path):
    #             content = make_json_from_obj(content)
    #             async with aiofiles.open(file=file_path, mode='w', encoding='utf-8') as file:
    #                 await file.write(content)
    #             return True
    #         else:
    #             raise Exception('File exists')
    #     except Exception as _:
    #         return False

    async def async_initialize(self) -> None:
        
        self._api_key = getenv('BM_API_KEY')

        self._servers = await self._async_read_file_as_dict('jsons/servers.json')

        self._headers['Authorization'] = f'Bearer {self._api_key}'
    
    async def async_get_all(self) -> dict:
        
        """
        Функция получения необходимой информации по серверам в файле (в дальнейшем будет реализовано получение списка серверов из бд)

        :return: dict - словарь со всей информацией по каждому серверу с типом хранения \n \
            {название_севрера: объект_с_информацией_о_сервере}
        """

        servers_list: list = []
        servers_tasks: list = []

        async with ClientSession() as session:
            
            # Создание списка отложенных задач на сбор информации по сервера через API
            for key in self._servers.keys():
                servers_tasks.append(create_task(self._get_info(session, key)))

            servers_list = await gather(*servers_tasks)

        servers_dict: dict = {class_obj.name: class_obj for class_obj in servers_list}

        return servers_dict
    
    async def _get_info(self, session: ClientSession, server: str):
        some_obj = None

        async with session.get(
            url=f'{self._url}{EPartitions.servers}{self._servers.get(server)}', 
            headers=self._headers
        ) as response:
            
            # Заполнение данных в список
            if response.status == 200:
                server_data: dict = dict(await response.json())
                # if await self._async_save_file_as_json(server_data, 'jsons/server_data_new.json'):
                #     print('\n\n=======server_data_new created=======\n\n')
                some_obj = cfact.get_object(server_data)
                if some_obj.TYPE == 'server':
                    if some_obj.game_id == 'rust':
                        return some_obj
                elif some_obj.TYPE == 'player':
                    ...
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
        self._info: dict = {}

    async def update_info(self, delay: int = 5) -> None:
        # TODO: Обрабатывать ErrorResponse
        await self._bm_response.async_initialize()
        self._info = await self._bm_response.async_get_all()

        last_info: dict = self._info
        while True:
            await aSleep(delay)
            self._info = await self._bm_response.async_get_all()
            differences: list = await self._find_differences(last_info=last_info)
            last_info = self._info
            await self._dp.handle_differences(differences=differences)


    async def _find_differences(self, last_info: dict) -> list:
        tasks: list = []
        
        for key in self._info:
            
            # Создание списка отложенных задач на поиск различий в словарях объектов
            if last_info[key] != self._info[key]:
                tasks.append(
                    create_task(
                        self.__find_differences_in_servers(
                            last_server_info=last_info[key], server_info=self._info[key]
                        )
                    )
                )
        differences: list = await gather(*tasks)
        return differences

    async def __find_differences_in_servers(self, last_server_info: Server, server_info: Server) -> dict:
        
        # Поиск различий в словарях объектов
        difference_list: set = set(last_server_info.__dict__.items()) ^ set(server_info.__dict__.items())
        difference: dict = {
            'type': last_server_info.TYPE,
            'game_id': last_server_info.game_id,
            'name': last_server_info.name,
            'description': str(last_server_info)
        }
        
        # Проход по всем различиям для определения новизны данных
        for item in difference_list:
            if item[1] == last_server_info.__dict__[item[0]]:
                difference['old'] = {item[0]: item[1]}
            else:
                difference['new'] = {item[0]: item[1]}
        # цветной вывод в консоль
        # print(f'\033[4m\033[34m{server_info.name=}:\033[0m\033[32m {difference}\033[37m')
        return difference
