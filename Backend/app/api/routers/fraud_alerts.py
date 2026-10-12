from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.schemas.fraud_alerts import FraudAlert, FraudAlertFilters, FraudAlertList
from app.api.schemas.response import ApiResponse
from app.domain.entities.search import FraudAlertSearchCriteria

router = APIRouter(tags=["fraud-alerts"])


@router.get("/fraud-alerts", response_model=ApiResponse[FraudAlertList])
def get_fraud_alerts(
    request: Request,
    filters: Annotated[FraudAlertFilters, Depends()],
) -> ApiResponse[FraudAlertList]:
    page = request.app.state.container.list_fraud_alerts.execute(
        FraudAlertSearchCriteria(
            page=filters.page,
            page_size=filters.page_size,
            risk_level=filters.risk_level,
            fraud_scenario=filters.fraud_scenario,
            msisdn=filters.msisdn,
            date_from=filters.date_from,
            date_to=filters.date_to,
        )
    )
    return ApiResponse[FraudAlertList](
        status_code=200,
        message="Fraud alerts retrieved",
        data=FraudAlertList(
            items=[FraudAlert.model_validate(alert) for alert in page.items],
            page=page.page,
            page_size=page.page_size,
            total=page.total,
            pages=page.pages,
        ),
    )
