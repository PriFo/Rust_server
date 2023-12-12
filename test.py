
from dispatcher import Dispatcher as BMDp
from asyncio import run


bmdp = BMDp()


@bmdp.handler(handler='player_min')
async def players_changed() -> None:
    print(f'Players: OK!')


@bmdp.handler(handler='status')
async def status_changed() -> None:
    print('Status: OK!')
    

@bmdp.handler(handler='last_wipe')
async def last_wipe_changed() -> None:
    print('Last wipe: OK!')


async def main() -> None:
    await bmdp.test_handle()


if __name__ == '__main__':
    run(main())