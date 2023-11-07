
class ErrorResponse:
    """
        Класс данных с информацией об ошибке
    """
    def __init__(self) -> None:
        
        # объявляем список ошибок
        self._errors: list = []

    def initialize(
        self,
        data: dict
    ) -> None:
        
        # проходимся по списку ошибок внутри json-ответа
        for error in data.get('errors'):

            # добавляем информацию об ошибке в список с явной типизацией данных
            self._errors.append(dict(error))

    def __str__(self) -> str:

        # объявляем строковую переменную с информацией о каждой ошибке
        error_data: str = ''

        # проходимся по списку ошибок
        for error in self._errors:

            # добавляем данные об ошибке в строку
            error_data += f'\nStatus: {error.get("status")}\n \
                Title: {error.get("title")}\n \
                Reason: {error.get("detail")}\n'
            
        # возвращаем информацию об ошибках
        return 'ERROR!\n' + error_data
