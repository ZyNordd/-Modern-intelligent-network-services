"""FastAPI-приложение для REST API оценки аграрных рисков."""

import time
import uuid

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Request,
    status,
)

from .logging_config import (
    configure_logging,
    get_logger,
)
from .model import (
    MODEL_NAME,
    MODEL_READY,
    MODEL_TYPE,
    MODEL_VERSION,
)
from .schemas import (
    FarmRequest,
    HealthResponse,
    ModelInfoResponse,
    PredictionResponse,
)
from .services import (
    ALLOWED_RISK_LEVELS,
    create_prediction,
    validate_region,
)
from .storage import (
    get_prediction,
    get_predictions,
    save_prediction,
)

configure_logging()

logger = get_logger(__name__)


app = FastAPI(
    title="Agro Scoring API",
    description=("REST API для оценки риска сельскохозяйственных предприятий."),
    version="1.0.0",
)


@app.middleware("http")
async def add_process_time(
    request: Request,
    call_next,
):
    """Измеряет время обработки HTTP-запроса.

    Добавляет в HTTP-ответ заголовок X-Process-Time
    с длительностью обработки запроса в секундах.

    Args:
        request: Входящий HTTP-запрос.
        call_next: Следующий обработчик в цепочке middleware.

    Returns:
        HTTP-ответ с добавленным временем обработки.
    """

    start_time = time.perf_counter()

    response = await call_next(request)

    process_time = time.perf_counter() - start_time

    response.headers["X-Process-Time"] = str(round(process_time, 6))

    return response


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Проверка состояния API",
    description=("Проверяет, что REST API запущен и отвечает."),
)
def health() -> HealthResponse:
    """Проверяет доступность REST API.

    Returns:
        Ответ со статусом доступности API.
    """

    logger.info("Health check")

    return HealthResponse(status="ok")


@app.get(
    "/model-info",
    response_model=ModelInfoResponse,
    summary="Информация о модели",
    description=("Возвращает название, версию, тип и состояние модели."),
)
def model_info() -> ModelInfoResponse:
    """Возвращает информацию о модели оценки риска.

    Returns:
        Название, версию, тип и текущее состояние модели.
    """

    model_status = "ready" if MODEL_READY else "unavailable"

    logger.info(
        "Model info requested | status=%s",
        model_status,
    )

    return ModelInfoResponse(
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        model_type=MODEL_TYPE,
        status=model_status,
    )


@app.post(
    "/predict",
    response_model=PredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Оценить риск хозяйства",
    description=(
        "Принимает характеристики хозяйства, "
        "выполняет структурную и бизнес-"
        "валидацию, рассчитывает риск "
        "и возвращает результат."
    ),
)
def predict(
    request: FarmRequest,
) -> PredictionResponse:
    """Выполняет оценку риска сельскохозяйственного предприятия.

    Проверяет доступность модели и корректность региона,
    рассчитывает показатель риска, сохраняет результат
    и возвращает его клиенту.

    Args:
        request: Валидированные входные данные хозяйства.

    Raises:
        HTTPException: Если модель недоступна или указан
            недопустимый регион.

    Returns:
        Результат оценки риска с уникальным request_id.
    """

    if not MODEL_READY:
        logger.error("Prediction rejected because model is unavailable")

        raise HTTPException(
            status_code=(status.HTTP_503_SERVICE_UNAVAILABLE),
            detail=("Model is temporarily unavailable"),
        )

    try:
        validate_region(request.region)

    except ValueError as exc:
        logger.warning(
            "Business validation failed | farm_id=%s | %s",
            request.farm_id,
            exc,
        )

        raise HTTPException(
            status_code=(status.HTTP_400_BAD_REQUEST),
            detail=str(exc),
        ) from exc

    request_id = str(uuid.uuid4())

    logger.info(
        "Prediction request received | request_id=%s | farm_id=%s",
        request_id,
        request.farm_id,
    )

    prediction = create_prediction(
        request,
        request_id,
    )

    save_prediction(prediction)

    logger.info(
        "Prediction completed | request_id=%s | risk_score=%s | risk_level=%s",
        prediction.request_id,
        prediction.risk_score,
        prediction.risk_level,
    )

    return prediction


@app.get(
    "/predictions",
    response_model=list[PredictionResponse],
    summary="Получить список прогнозов",
    description=(
        "Возвращает выполненные прогнозы "
        "с ограничением количества "
        "и фильтрацией по уровню риска."
    ),
)
def list_predictions(
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description=("Максимальное количество результатов"),
    ),
    risk_level: str | None = Query(
        default=None,
        description=("Фильтр: low, medium или high"),
    ),
) -> list[PredictionResponse]:
    """Возвращает список сохранённых прогнозов.

    Поддерживает ограничение количества результатов
    и фильтрацию по уровню риска.

    Args:
        limit: Максимальное количество возвращаемых результатов.
        risk_level: Необязательный фильтр по уровню риска.

    Raises:
        HTTPException: Если указан недопустимый уровень риска.

    Returns:
        Список результатов оценки риска.
    """

    if risk_level is not None and risk_level not in ALLOWED_RISK_LEVELS:
        logger.warning(
            "Invalid risk_level query parameter | value=%s",
            risk_level,
        )

        raise HTTPException(
            status_code=(status.HTTP_400_BAD_REQUEST),
            detail=("risk_level must be 'low', 'medium' or 'high'"),
        )

    values = get_predictions()

    if risk_level is not None:
        values = [item for item in values if item.risk_level == risk_level]

    logger.info(
        "Predictions list requested | limit=%s | risk_level=%s",
        limit,
        risk_level,
    )

    return values[:limit]


@app.get(
    "/predictions/{request_id}",
    response_model=PredictionResponse,
    summary="Получить прогноз по request_id",
    description=("Возвращает сохраненный прогноз по уникальному идентификатору."),
)
def get_prediction_by_id(
    request_id: str,
) -> PredictionResponse:
    """Возвращает сохранённый прогноз по request_id.

    Args:
        request_id: Уникальный идентификатор запроса.

    Raises:
        HTTPException: Если прогноз с указанным request_id
            отсутствует в хранилище.

    Returns:
        Сохранённый результат оценки риска.
    """

    prediction = get_prediction(request_id)

    if prediction is None:
        logger.warning(
            "Prediction not found | request_id=%s",
            request_id,
        )

        raise HTTPException(
            status_code=(status.HTTP_404_NOT_FOUND),
            detail="Prediction not found",
        )

    logger.info(
        "Prediction retrieved | request_id=%s",
        request_id,
    )

    return prediction


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "agro_api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
