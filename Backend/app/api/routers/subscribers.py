from fastapi import APIRouter, Path, Request

from app.api.schemas.response import ApiResponse
from app.api.schemas.subscribers import SubscriberProfile

router = APIRouter(tags=["subscribers"])


@router.get(
    "/subscribers/{msisdn}",
    response_model=ApiResponse[SubscriberProfile],
)
def get_subscriber(
    request: Request,
    msisdn: str = Path(pattern=r"^[0-9]{10}$"),
) -> ApiResponse[SubscriberProfile]:
    profile = request.app.state.container.get_subscriber_profile.execute(msisdn)
    return ApiResponse[SubscriberProfile](
        status_code=200,
        message="Subscriber profile retrieved",
        data=SubscriberProfile.model_validate(profile),
    )
