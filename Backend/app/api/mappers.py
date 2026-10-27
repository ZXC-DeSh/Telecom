from app.api.schemas.calls import CallDetail, CallListItem
from app.api.schemas.predictions import PredictionResult
from app.domain.entities.call import Call
from app.domain.entities.prediction import Prediction


def to_prediction_result(prediction: Prediction) -> PredictionResult:
    return PredictionResult.model_validate(prediction)


def to_call_list_item(call: Call) -> CallListItem:
    assessment = call.assessment
    data = {
        "id": call.id,
        "call_type": call.call_type,
        "imsi_a": call.imsi_a,
        "msisdn_a": call.msisdn_a,
        "msisdn_b": call.msisdn_b,
        "call_time": call.call_time,
        "duration_seconds": call.duration_seconds,
        "msisdn_c": call.msisdn_c,
        "risk_score": assessment.risk_score if assessment else None,
        "risk_level": assessment.risk_level if assessment else None,
        "is_fraud": assessment.is_fraud if assessment else None,
        "fraud_scenario": assessment.fraud_scenario if assessment else None,
    }
    return CallListItem.model_validate(data)


def to_call_detail(call: Call) -> CallDetail:
    item = to_call_list_item(call)
    assessment = call.assessment
    return CallDetail.model_validate(
        {
            **item.model_dump(),
            "reasons": assessment.reasons if assessment else (),
            "recommendation": assessment.recommendation if assessment else None,
            "operator_message": assessment.operator_message if assessment else None,
        }
    )
