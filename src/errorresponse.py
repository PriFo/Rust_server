
class ErrorResponse:
    """
    Класс данных с информацией об ошибке в ответе API
    """
    def __init__(self) -> None:
        self._errors: list = []

    def initialize(self, *args) -> None:
        if len(args) == 1 and isinstance(args[0], dict):
            data = args[0]
            # проходимся по списку ошибок внутри json-ответа
            for error in data.get('errors', []):
                # добавляем информацию об ошибке в список
                # ключи неизвестны заранее из-за их различий в ответе
                self._errors.append(dict(error))
        elif len(args) == 2 and all(isinstance(arg, str) for arg in args):
            type, error = args
            self._errors.append({type: error})
        else:
            raise ValueError("Invalid arguments for initialize method")

    def __str__(self) -> str:
        error_data: str = ''
        for error in self._errors:
            error_data += f'\n{str(error)}\n'
        return 'ERROR!\n' + error_data
