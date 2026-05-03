from __future__ import annotations

import json
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, Response
from starlette.concurrency import run_in_threadpool

from app.deps import get_voice_service
from app.models.api import VoiceGenerateRequest, VoiceOptionsResponse
from app.utils.tts_adapter import (
    merge_dialogue_into_narration,
    normalize_tts_text,
    split_into_tts_chunks,
    count_words,
)

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

    # Build chunk debug info for the FE
    raw = merge_dialogue_into_narration(request.text, request.dialogue, request.speaker)
    normalized = normalize_tts_text(raw)
    chunks = split_into_tts_chunks(normalized)
    chunk_info = [{"i": i, "w": count_words(c), "text": c} for i, c in enumerate(chunks, 1)]
    chunk_header = urllib.parse.quote(json.dumps(chunk_info, ensure_ascii=False), safe="")

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={
            "X-TTS-Chunks": chunk_header,
            "Access-Control-Expose-Headers": "X-TTS-Chunks",
        },
    )
