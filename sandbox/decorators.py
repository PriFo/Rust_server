
class Dispatcher:

    def __init__(self) -> None:
        self._do_something = None

    def call_func(self):
        self._do_something()

    def do_something(self, func):
        self._do_something = func

dp = Dispatcher()


@dp.do_something
def foo():
    print('Hello world!')

dp.call_func()
