from asyncio import sleep as aSleep
import asyncio
from datetime import datetime as dt


async def handle_event(delay: int):
    await aSleep(delay)
    print(f'Event {delay} handled')


async def main():
    tasks = []
    start = dt.now()
    for i in range(1, 6):
        tasks.append(asyncio.Task(handle_event(i)))
    for task in tasks:
        await task
    end = dt.now()
    print(f'Events handled for {end - start} sec.')


if __name__ == '__main__':
    asyncio.run(main())
