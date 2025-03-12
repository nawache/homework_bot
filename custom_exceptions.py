class APIRequestError(Exception):
    """Исключение, вызываемое при ошибке запроса к API."""

    pass


class APIResponseError(Exception):
    """Исключение, вызываемое при некорректном ответе API."""

    pass


class HomeworkStatusUnknown(Exception):
    """Исключение, вызываемое при неизвестном статусе домашней работы."""

    pass
