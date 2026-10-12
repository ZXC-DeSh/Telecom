from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.api.mappers import to_call_detail, to_call_list_item
from app.api.schemas.calls import CallDetail, CallFilters, CallListData
from app.api.schemas.response import ApiResponse
from app.domain.entities.search import CallSearchCriteria

router = APIRouter(tags=["calls"])


@router.get("/calls", response_model=ApiResponse[CallListData])
def get_calls(
    request: Request,
    filters: Annotated[CallFilters, Depends()],
) -> ApiResponse[CallListData]:
    page = request.app.state.container.list_calls.execute(
        CallSearchCriteria(
            page=filters.page,
            page_size=filters.page_size,
            date_from=filters.date_from,
            date_to=filters.date_to,
            call_type=filters.call_type,
            msisdn=filters.msisdn,
            risk_level=filters.risk_level,
        )
    )
    return ApiResponse[CallListData](
        status_code=200,
        message="Calls retrieved",
        data=CallListData(
            items=[to_call_list_item(call) for call in page.items],
            page=page.page,
            page_size=page.page_size,
            total=page.total,
            pages=page.pages,
        ),
    )


@router.get("/calls/{call_id}", response_model=ApiResponse[CallDetail])
def get_call(
    request: Request,
    call_id: UUID,
) -> ApiResponse[CallDetail]:
    call = request.app.state.container.get_call.execute(call_id)
    return ApiResponse[CallDetail](
        status_code=200,
        message="Call retrieved",
        data=to_call_detail(call),
    )
