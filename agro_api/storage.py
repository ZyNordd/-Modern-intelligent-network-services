"""Хранилище результатов прогнозирования.

В лабораторной работе используется хранилище в оперативной памяти.
В дальнейшем его можно заменить на SQLite или PostgreSQL
без изменения контрактов API-эндпоинтов.
"""

from .schemas import PredictionResponse

_predictions: dict[str, PredictionResponse] = {}


def save_prediction(prediction: PredictionResponse) -> None:
    """Сохраняет результат прогнозирования по идентификатору запроса.

    Args:
        prediction: Результат оценки риска, содержащий request_id.
    """

    _predictions[prediction.request_id] = prediction


def get_prediction(
    request_id: str,
) -> PredictionResponse | None:
    """Возвращает результат прогнозирования по идентификатору.

    Args:
        request_id: Уникальный идентификатор запроса.

    Returns:
        Сохранённый результат прогнозирования или None,
        если результат с таким идентификатором отсутствует.
    """

    return _predictions.get(request_id)


def get_predictions() -> list[PredictionResponse]:
    """Возвращает все сохранённые результаты в порядке добавления.

    Returns:
        Список всех сохранённых результатов прогнозирования.
    """

    return list(_predictions.values())
