from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from starlette.concurrency import run_in_threadpool

from app.deps import get_voice_service
from app.models.api import VoiceGenerateRequest, VoiceOptionsResponse

router = APIRouter(prefix="/voice", tags=["voice"])


@router.get("/options", response_model=VoiceOptionsResponse)
async def get_voice_options(voice_service=Depends(get_voice_service)) -> VoiceOptionsResponse:
    return voice_service.get_options()


@router.post("/generate")
async def generate_voice(
    request: VoiceGenerateRequest,
    voice_service=Depends(get_voice_service),
) -> Response:
    try:
        audio_bytes = await run_in_threadpool(voice_service.generate_audio, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return Response(content=audio_bytes, media_type="audio/wav")
