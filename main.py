from battlemetrics_requests import BattleMetricsResponse
import asyncio
from dotenv import load_dotenv
from os import getcwd
from os.path import exists as file_exists


def load_env():
    if file_exists(getcwd() + '\.env'):
        load_dotenv(getcwd() + '\.env')


# def main():
#     response: BattleMetricsResponse = BattleMetricsResponse()
#     response.initialize()
#     servers: list = response.get_all_servers()
#     for i in servers:
#         print(i, end='\n\n')


async def async_main() -> str:
    response: BattleMetricsResponse = BattleMetricsResponse()
    await response.async_initialize()
    print("Initialize: OK!")
    servers = await response.async_get_all_servers()
    while servers == [None, None]:
        if servers != [None, None]:
            print("Servers: OK!")
            formatted_servers: str = '\n\n'.join(str(i) for i in servers)
            print(*servers, sep="\n\n\n")
            break
    return formatted_servers


if __name__ == '__main__':
    # TODO: добавление задач об обновлении информации в фреймворке в бота для запуска отдельных задач
    load_env()
    response: BattleMetricsResponse = BattleMetricsResponse()
    asyncio.set_event_loop(asyncio.new_event_loop())
    loop = asyncio.get_event_loop()
    loop.run_until_complete(response.async_initialize())
    asyncio.set_event_loop(asyncio.new_event_loop())
    loop = asyncio.get_event_loop()
    servers = loop.run_until_complete(response.async_get_all_servers())
    print(*servers)
    loop.close()
    