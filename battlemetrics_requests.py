
import traceback
from typing import Any, Union
from errorresponse import ErrorResponse as ER
from data_classes import ClassFactory as cfact, Player
from data_classes import Server
from dispatcher import Dispatcher

from json import loads as make_dict_from_str

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

    async def async_initialize(self, servers: dict[str, str]) -> None:
        #TODO реализация получения информации из БД

        if isinstance(servers, dict):
            for key, value in servers.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    raise TypeError(f'Servers must be dict[str, str], not dict[{type(key)},{type(value)}]')
        else:
            raise TypeError(f'Server must be dict, not {type(servers)=}')
        self._api_key = getenv('BM_API_KEY')

        self._servers = servers

        self._headers['Authorization'] = f'Bearer {self._api_key}'
    
    async def async_get_servers_info(self, session: ClientSession) -> dict:
        
        """
        Функция получения необходимой информации по серверам в файле (в дальнейшем будет реализовано получение списка серверов из бд)

        :param session: aiohttp.ClientSession - сессия к которой необходимо обратиться
        :return: dict - словарь со всей информацией по каждому серверу с типом хранения \n \
            {название_севрера: объект_с_информацией_о_сервере}
        """

        servers_list: list = []
        servers_tasks: list = []
            
        # Создание списка отложенных задач на сбор информации по сервера через API
        for value in self._servers.values():
            servers_tasks.append(create_task(self._get_server_info(session, value)))
        servers_list = await gather(*servers_tasks)
        
        servers_dict: dict = {}
        for class_obj in servers_list:
            if isinstance(class_obj, Server):
                servers_dict[class_obj.name] = class_obj
            else:
                if servers_dict.get('errors'):
                    servers_dict['errors'].append(class_obj)
                else:
                    servers_dict['errors'] = [class_obj]

        return servers_dict
    
    async def _get_server_info(self, session: ClientSession, server_id: str):
        some_obj = None

        async with session.get(
            url=f'{self._url}{EPartitions.servers}{server_id}', 
            headers=self._headers
        ) as response:
            
            # Заполнение данных в список
            if response.status == 200:
                server_data: dict = dict(await response.json())
                return cfact.get_object(server_data)
            else:
                data = await response.read()
                some_obj = ER()
                some_obj.initialize(data=dict(make_dict_from_str(data)))
    
        return some_obj
    
    async def get_cur_server_info(self) -> Server:
        ...


class BattleMetricsController:

    def __init__(self) -> None:
        self._dp: Dispatcher = Dispatcher()
        self._servers_json_path: str = 'jsons/servers.json'
        self._bm_response: BattleMetricsResponse = BattleMetricsResponse()
        self._servers_info: dict = {}

    async def update_info(self, delay: int = 5) -> None:
        # TODO: Обрабатывать ErrorResponse
        try:
            await self._bm_response.async_initialize(self._dp._repo.get_servers())
            last_info: dict = {}
           
            async with ClientSession() as session:
                
                self._servers_info = await self._bm_response.async_get_servers_info(session)
                errors: Union[list, None] = self._servers_info.get('errors')
                if errors:
                    await self._dp.handle_errors(errors)
                last_info: dict = self._servers_info
                
                while True:
                    await aSleep(delay)
                    self._servers_info = await self._bm_response.async_get_servers_info(session)
                    differences: list = await self._find_differences_servers(last_info=last_info)
                    last_info = self._servers_info
                    await self._dp.handle_server_differences(differences=differences)
        except KeyboardInterrupt:
            self._dp.repo.log_action(
                object='BMController', 
                action='update_info', 
                comment='Stopping bot'
            )
        except RuntimeError as re:
            self._dp.repo.log_action(
                object='BMController', 
                action='update_info', 
                comment='Stopping bot', 
                is_error=True, 
                result=traceback.format_exc() + str(re)
            )
        except Exception as e:
            self._dp.repo.log_action(
                object='BMController', 
                action='update_info', 
                comment='Stopping bot', 
                is_error=True, 
                result=traceback.format_exc() + str(e)
            )


    async def _find_differences_servers(self, last_info: dict) -> list:
        tasks: list = []
        
        for key in self._servers_info:
            if key == 'errors':
                continue
            # Создание списка отложенных задач на поиск различий в словарях объектов
            if key in last_info and last_info[key] != self._servers_info[key]:
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
        
        # Поиск различий в словарях объектов
        difference_list: set = set(last_server_info.__dict__.items()) ^ set(server_info.__dict__.items())
        difference: dict = {
            'name': last_server_info.name,
            'game_id': last_server_info.game_id}
        
        # Проход по всем различиям для определения новизны данных
        if difference_list != set():
            difference['old'] = []
            difference['new'] = []
            for item in difference_list:
                if item[1] == last_server_info.__dict__[item[0]]:
                    difference['old'].append({item[0]: item[1]})
                else:
                    difference['new'].append({item[0]: item[1]})
            return difference
        return difference
