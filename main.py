from battlemetrics_requests import BattleMetricsController
import asyncio
from dotenv import load_dotenv
from os import getcwd
from os.path import exists as file_exists
from bot import start_bot


#TODO написать комментарии для пояснения работы каждой функции, где это требуется
def load_env():
    path: str = getcwd() + '\.env'
    if file_exists(path):
        load_dotenv(path)


async def get_tasks(delay: int = 5) -> list:
    # TODO: добавление задачи на запуск бота и соответствующие параметры
    tasks: list = []
    controller: BattleMetricsController = BattleMetricsController()
    tasks.append(asyncio.create_task(controller.update_info(delay)))
    tasks.append(asyncio.create_task(start_bot()))
    return tasks


async def async_main() -> str:
    await asyncio.gather(*await get_tasks())
    

if __name__ == '__main__':
    load_env()
    asyncio.run(async_main())
    