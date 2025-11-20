
from errorresponse import ErrorResponse as ER
from data_classes import ClassFactory as cfact, Player
from data_classes import Server
from dispatcher import Dispatcher

from json import loads as make_dict_from_str
#from json import dumps as make_json_from_obj

from aiohttp import ClientSession
import aiofiles
from os import getenv
from asyncio import sleep as aSleep
from asyncio import create_task, gather


# TODO: дописать методы фильтрации API-запроса
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
        
        self._players = await self._async_read_file_as_dict('jsons/players.json')

        self._headers['Authorization'] = f'Bearer {self._api_key}'
    
    async def async_get_all(self) -> dict:
        
        """
        Функция получения необходимой информации по серверам и игрокам в файле (в дальнейшем будет реализовано получение списка серверов и игроков из бд)

        :return objects_dict: словарь со всей информацией по каждому серверу с типом хранения \
            {название_севрера: объект_с_информацией_о_сервере}
        """

        obj_list: list = []
        obj_tasks: list = []

        async with ClientSession() as session:
            
            # Создание списка отложенных задач на сбор информации по сервера через API
            for key in self._servers.keys():
                obj_tasks.append(create_task(self._get_server_info(session, key)))
            
            for key in self._players.keys():
                obj_tasks.append(create_task(self._get_player_info(session, key)))

            obj_list = await gather(*obj_tasks)

        for index, obj in enumerate(obj_list):
            if isinstance(obj, ER):
                obj_list.pop(index)
                print(obj)

        objects_dict: dict = {class_obj.name: class_obj for class_obj in obj_list}

        return objects_dict
    
    async def _get_server_info(self, session: ClientSession, id_obj: str):
        some_obj = None

        async with session.get(
            url=f'{self._url}{EPartitions.servers}{self._servers.get(id_obj)}', 
            headers=self._headers
        ) as response:
            
            # Заполнение данных в список
            if response.status == 200:
                data = await response.read()
                some_obj = await self._get_object(dict(make_dict_from_str(data)))
            else:
                data = await response.read()
                some_obj = await self._get_error(dict(make_dict_from_str(data)))
    
        return some_obj
    
    async def _get_player_info(self, session: ClientSession, id_obj: str):
        some_obj = None

        async with session.get(
            url=f'{self._url}{EPartitions.players}{self._players.get(id_obj)}', 
            headers=self._headers
        ) as response:
            
            # Заполнение данных в список
            if response.status == 200:
                data = await response.read()
                some_obj = await self._get_object(dict(make_dict_from_str(data)))
            else:
                data = await response.read()
                some_obj = await self._get_error(dict(make_dict_from_str(data)))
    
        return some_obj

    async def _get_error(self, data: dict) -> ER:
        error = ER()
        error.initialize(
            data=data
        )
        return error

    async def _get_object(self, data: dict) -> tuple[Server, Player]:
        return cfact.get_object(data)


class BattleMetricsController:

    def __init__(self) -> None:
        self._dp: Dispatcher = Dispatcher()
        self._servers_json_path: str = 'jsons/servers.json'
        self._bm_response: BattleMetricsResponse = BattleMetricsResponse()
        self._info: dict = {}

    async def update_info(self, delay: int = 5) -> None:
        # TODO: Обрабатывать ErrorResponse
        await self._bm_response.async_initialize()
        self._info = await self._bm_response.async_get_all()

        print('Информация для обновления подготовлена...')

        last_info: dict = self._info
        while True:
            await aSleep(delay)
            self._info = await self._bm_response.async_get_all()
            differences: list = await self._find_differences(last_info=last_info)
            print('Обновление успешно!')
            last_info = self._info
            await self._dp.handle_differences(differences=differences)

    async def _find_differences(self, last_info: dict) -> list:
        tasks: list = []
        
        for key in self._info:
            
            # Создание списка отложенных задач на поиск различий в словарях объектов
            if not last_info[key] == self._info[key]:
                tasks.append(
                    create_task(
                        self.__find_differences(
                            last_info=last_info[key], new_info=self._info[key]
                        )
                    )
                )
        differences: list = await gather(*tasks)
        return differences

    """async def __find_differences(
            self, 
            last_info: tuple[Server, Player], 
            new_info: tuple[Server, Player]
        ) -> dict:
        
        last_info_dict: dict = last_info.__dict__()
        new_info_dict: dict = new_info.__dict__()

        print(f'\n\n{last_info_dict=}\n\n{new_info_dict=}\n\n')

        # Поиск различий в словарях объектов
        difference_list: set = set(last_info_dict.items()) ^ set(new_info_dict.items())
        difference: dict = {
            'type': last_info.TYPE,
            'name': last_info.name,
            'description': str(last_info),
            'old': {},
            'new': {}
        }

        if type(last_info) is type(Server):
            difference['game_id'] = last_info.game_id
        
        # Проход по всем различиям для определения новизны данных
        for item in difference_list:
            if item[1] == last_info.__dict__()[item[0]]:
                difference['old'].update({item[0]: item[1]})
            else:
                difference['new'].update({item[0]: item[1]})
        # цветной вывод в консоль
        # print(f'\033[4m\033[34m{server_info.name=}:\033[0m\033[32m {difference}\033[37m')
        return difference"""

    async def __find_differences(
            self,
            last_info: tuple[Server, Player],
            new_info: tuple[Server, Player]
    ) -> dict:
        
        last_info_dict: dict = last_info.__dict__()
        new_info_dict: dict = new_info.__dict__()
        
        differences: dict = {
            'type': last_info.TYPE,
            'name': last_info.name,
            'description': str(last_info),
            'old': {},
            'new': {}
        }

        if isinstance(last_info, Server):
            differences['game_id'] = last_info.game_id

        for key, value in new_info_dict.items():
            if last_info_dict[key] != value:
                differences['old'].update({key: last_info_dict[key]})
                differences['new'].update({key: value})

        print(f'\n{last_info_dict=}\n\n{new_info_dict=}\n\n{differences=}\n')
        return differences
