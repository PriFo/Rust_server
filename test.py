
from dispatcher import Dispatcher as BMDp
from asyncio import run


bmdp = BMDp()


@bmdp.handler(handler='player_min')
async def players_changed(differences) -> None:
    print(f'Players: {differences}')


@bmdp.handler(handler='status')
async def status_changed(differences) -> None:
    print(f'Status: {differences}')
    

@bmdp.handler(handler='last_wipe')
async def last_wipe_changed(differences) -> None:
    print(f'Last wipe: {differences}')


async def main() -> None:
    await bmdp.test_handle()


if __name__ == '__main__':
    run(main())