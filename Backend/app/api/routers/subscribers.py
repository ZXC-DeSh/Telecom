from fastapi import APIRouter, Path, Request

from app.api.schemas.response import ApiResponse
from app.api.schemas.subscribers import SubscriberProfile

router = APIRouter(tags=["subscribers"])


@router.get(
    "/subscribers/{msisdn_a}",
    response_model=ApiResponse[SubscriberProfile],
)
def get_subscriber(
    request: Request,
    msisdn_a: str = Path(pattern=r"^[0-9]{10}$"),
) -> ApiResponse[SubscriberProfile]:
    profile = request.app.state.container.get_subscriber_profile.execute(msisdn_a)
    return ApiResponse[SubscriberProfile](
        status_code=200,
        message="Профиль абонента получен",
        data=SubscriberProfile.model_validate(profile),
    )
