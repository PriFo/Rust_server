
class ErrorResponse:
    """
        Класс данных с информацией об ошибке в ответе API
    """
    def __init__(self) -> None:
        self._errors: list = []

    def initialize(
        self,
        data: dict
    ) -> None:
        
        # проходимся по списку ошибок внутри json-ответа
        for error in data.get('errors'):

            # добавляем информацию об ошибке в список
            # ключи неизвестны заранее из-за их различий в ответе
            self._errors.append(dict(error))

    def __str__(self) -> str:
        error_data: str = ''
        for error in self._errors:
            error_data += f'\n{str(error)}\n'
        return 'ERROR!\n' + error_data
