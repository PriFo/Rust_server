from battlemetrics_requests import BattleMetricsController
import asyncio
from dotenv import load_dotenv
from os import getcwd
from os.path import exists as file_exists


def load_env():
    if file_exists(getcwd() + '\.env'):
        load_dotenv(getcwd() + '\.env')


async def get_tasks(delay: int = 5) -> list:
    # TODO: добавление задачи на запуск бота и соответствующие параметры
    tasks: list = []
    controller: BattleMetricsController = BattleMetricsController()
    # print("Initialize: OK!")
    tasks.append(asyncio.create_task(controller.update_info(delay)))
    return tasks


async def async_main() -> str:
    # print("Servers: OK!")
    # asyncio.gather(*await get_tasks())
    controller = BattleMetricsController()
    result = await controller.test_find_differences()
    print(result)


if __name__ == '__main__':
    load_env()
    asyncio.run(async_main())
    