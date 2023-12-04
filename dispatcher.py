
class Dispatcher:

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, *args, **kwargs) -> None:
        self._filters: dict = {}

    async def handle_differences(self, differences: list) -> None:
        for diff in differences:
            print(f'\033[4m\033[34m{diff["name"]=}:\033[0m\033[32m {diff["new"]=}\033[37m')        
