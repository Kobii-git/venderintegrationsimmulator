from app.api.deps import get_oauth_token_service
from app.inbound.oauth import OAuthTokenService
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["oauth"])


@router.post("/oauth2/token")
async def oauth2_token(
    request: Request,
    service: OAuthTokenService = Depends(get_oauth_token_service),
) -> JSONResponse:
    """OAuth2 client-credentials token endpoint for pull-based simulations."""
    return await service.handle_token_request(request)
