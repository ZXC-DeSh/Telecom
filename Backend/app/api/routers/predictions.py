from fastapi import APIRouter, Request

from app.api.schemas.predictions import (
    BatchPredictionRequest,
    BatchPredictionResult,
    PredictionRequest,
    PredictionResult,
)
from app.api.schemas.response import ApiResponse
from app.domain.entities.call import Call

router = APIRouter(tags=["predictions"])


def _to_call(payload) -> Call:
    return Call(
        id=None,
        call_type=payload.call_type,
        imsi_a=payload.imsi_a,
        msisdn_a=payload.msisdn_a,
        msisdn_b=payload.msisdn_b,
        call_time=payload.call_time,
        duration_seconds=payload.duration_seconds,
        msisdn_c=payload.msisdn_c,
    )


@router.post(
    "/predict",
    response_model=ApiResponse[PredictionResult | BatchPredictionResult],
)
def predict(
    payload: PredictionRequest | BatchPredictionRequest,
    request: Request,
) -> ApiResponse[PredictionResult | BatchPredictionResult]:
    use_case = request.app.state.container.predict_fraud
    if isinstance(payload, BatchPredictionRequest):
        predictions = use_case.execute_batch(tuple(_to_call(call) for call in payload.calls))
        result = BatchPredictionResult(
            items=[PredictionResult.model_validate(item) for item in predictions],
            total=len(predictions),
            processed=len(predictions),
        )
        return ApiResponse(status_code=200, message="Batch prediction completed", data=result)

    prediction = use_case.execute(
        call_id=payload.call_id,
        call=_to_call(payload.call) if payload.call is not None else None,
    )
    return ApiResponse(
        status_code=200,
        message="Prediction completed",
        data=PredictionResult.model_validate(prediction),
    )
