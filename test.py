
from dispatcher import (
    Dispatcher as BMDp,
    EHandlerNames as EHN
)
from asyncio import run


bmdp = BMDp()


@bmdp.handler(handler=EHN.players_changed)
async def players_changed(bot, differences) -> None:
    print(f'Players: {differences}\n{bot=}')


@bmdp.handler(handler=EHN.status)
async def status_changed(bot, differences) -> None:
    print(f'Status: {differences}\n{bot=}')
    

@bmdp.handler(handler=EHN.rust_last_wipe_changed)
async def last_wipe_changed(bot, differences) -> None:
    print(f'Last wipe: {differences}\n{bot=}')


async def main() -> None:
    await bmdp.test_handle()


if __name__ == '__main__':
    run(main())