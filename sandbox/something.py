from asyncio import sleep as aSleep
import asyncio
from datetime import datetime as dt


async def handle_event(delay: int = 0):
    await aSleep(0)
    print(f'Event {delay} handled')


async def main():
    tasks = []
    start = dt.now()
    for i in range(1, 6):
        tasks.append(asyncio.Task(handle_event(i)))
    await asyncio.gather(*tasks)
    end = dt.now()
    print(f'Events handled for {end - start} sec.')


if __name__ == '__main__':
    asyncio.run(main())
