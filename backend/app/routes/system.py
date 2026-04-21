from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_provider_registry
from app.models.api import ProvidersResponse, TtsRuntimeResponse

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/providers", response_model=ProvidersResponse)
async def providers(registry=Depends(get_provider_registry)) -> ProvidersResponse:
    return ProvidersResponse(**registry.get_provider_info())


@router.get("/tts", response_model=TtsRuntimeResponse)
async def tts_runtime_status(
    provider: str | None = None,
    registry=Depends(get_provider_registry),
) -> TtsRuntimeResponse:
    try:
        tts_runtime = registry.get_tts_runtime(provider)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return tts_runtime.get_runtime_response()
