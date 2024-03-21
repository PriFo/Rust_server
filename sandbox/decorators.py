import asyncio


# class Dispatcher:
# 
#     def __init__(self) -> None:
#         self._do_something = None
# 
#     def call_func(self):
#         self._do_something()
# 
#     def do_something(self, func):
#         self._do_something = func()


class ADispatcher:

    _instance = None

    def __new__(cls, *args, **kwargs) -> None:
        if cls._instance is None:
            cls._instance = super().__new__()

    def __init__(self) -> None:
        self._do_something = None

    async def call_func(self):
        await self._do_something()

    def do_something(self, func):

        def wrapper():
            
            #print('Я дебил')
            setattr(self, '_do_something', func)

        return wrapper()


# dp = Dispatcher()
a_dp = ADispatcher()


@a_dp.do_something
async def boo():
    print('Hello world!')


# @dp.do_something
# def foo():
#     print('Hello world!')


async def main():
    #print('зашел в главное')
    await a_dp.call_func()


if __name__ == '__main__':
    asyncio.run(main())
