from fastapi import APIRouter, Depends

from app.models.api import ProvidersResponse
from app.deps import get_provider_registry

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/providers", response_model=ProvidersResponse)
async def providers(registry=Depends(get_provider_registry)) -> ProvidersResponse:
    return ProvidersResponse(**registry.get_provider_info())
