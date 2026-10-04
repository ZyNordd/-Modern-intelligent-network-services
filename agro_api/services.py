"""Сервисная логика оценки и валидации аграрных рисков."""

from .model import MODEL_VERSION, calculate_risk
from .schemas import FarmRequest, PredictionResponse

ALLOWED_REGIONS = {"Krasnodar", "Rostov", "Stavropol"}
ALLOWED_RISK_LEVELS = {"low", "medium", "high"}


def get_risk_level(score: float) -> str:
    """Определяет категорию риска по числовому значению.

    Args:
        score: Числовой показатель риска.

    Returns:
        Категория риска: low, medium или high.
    """

    if score < 0.3:
        return "low"

    if score < 0.7:
        return "medium"

    return "high"


def get_recommendation(level: str) -> str:
    """Формирует рекомендацию на основе категории риска.

    Args:
        level: Категория риска.

    Returns:
        Текстовая рекомендация для дальнейшего рассмотрения заявки.
    """

    if level == "low":
        return "Стандартное рассмотрение"

    if level == "medium":
        return "Требуется дополнительная проверка"

    return "Высокий риск. Требуется ручное рассмотрение"


def validate_region(region: str) -> None:
    """Проверяет принадлежность региона к списку разрешённых регионов.

    Args:
        region: Название региона.

    Raises:
        ValueError: Если регион отсутствует в списке разрешённых.
    """

    if region not in ALLOWED_REGIONS:
        allowed = ", ".join(sorted(ALLOWED_REGIONS))
        raise ValueError(f"Unknown region: {region}. Allowed regions: {allowed}")


def create_prediction(
    request: FarmRequest,
    request_id: str,
) -> PredictionResponse:
    """Формирует полный результат оценки риска.

    Args:
        request: Валидированные входные данные предприятия.
        request_id: Уникальный идентификатор запроса.

    Returns:
        Результат оценки с показателем риска, его категорией
        и рекомендацией.
    """

    score = calculate_risk(request)
    level = get_risk_level(score)
    recommendation = get_recommendation(level)

    return PredictionResponse(
        request_id=request_id,
        farm_id=request.farm_id,
        risk_score=score,
        risk_level=level,
        recommendation=recommendation,
        model_version=MODEL_VERSION,
    )
