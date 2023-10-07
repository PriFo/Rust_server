from battlemetrics_requests import BattleMetricsResponse
import asyncio
import aiogram
from dotenv import load_dotenv
from os import getcwd
from os.path import exists as file_exists


def load_env():
    if file_exists(getcwd() + '\.env'):
        load_dotenv(getcwd() + '\.env')


def main():
    response: BattleMetricsResponse = BattleMetricsResponse()
    response.initialize()
    servers: list = response.get_all_servers()
    for i in servers:
        print(i, end='\n\n')


async def async_main() -> str:
    response: BattleMetricsResponse = BattleMetricsResponse()
    await response.async_initialize()
    servers: list = await response.async_get_all_servers()
    formatted_servers: str = '\n\n'.join(str(i) for i in servers)
    return formatted_servers


if __name__ == '__main__':
    load_env()
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(async_main())
    print(result)
