from __future__ import annotations

import json
import base64
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, Response
from starlette.concurrency import run_in_threadpool

from app.deps import get_voice_service
from app.models.api import (
    VoiceBatchGenerateRequest,
    VoiceBatchGenerateResponse,
    VoiceBatchGenerateResult,
    VoiceGenerateRequest,
    VoiceOptionsResponse,
)
from app.utils.tts_adapter import (
    merge_dialogue_into_narration,
    normalize_tts_text,
    split_into_tts_chunks,
    count_words,
)

router = APIRouter(prefix="/voice", tags=["voice"])


def _build_chunk_info(request: VoiceGenerateRequest) -> list[dict]:
    raw = merge_dialogue_into_narration(request.text, request.dialogue, request.speaker)
    normalized = normalize_tts_text(raw)
    chunks = split_into_tts_chunks(normalized)
    return [{"i": i, "w": count_words(chunk), "text": chunk} for i, chunk in enumerate(chunks, 1)]


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

    chunk_info = _build_chunk_info(request)
    chunk_header = urllib.parse.quote(json.dumps(chunk_info, ensure_ascii=False), safe="")

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={
            "X-TTS-Chunks": chunk_header,
            "Access-Control-Expose-Headers": "X-TTS-Chunks",
        },
    )


@router.post("/generate-batch", response_model=VoiceBatchGenerateResponse)
async def generate_voice_batch(
    request: VoiceBatchGenerateRequest,
    voice_service=Depends(get_voice_service),
) -> VoiceBatchGenerateResponse:
    if not request.items:
        raise HTTPException(status_code=400, detail="Voice batch must contain at least one item.")

    voice_requests = [
        VoiceGenerateRequest(
            text=item.text,
            provider=request.provider,
            voiceKey=request.voiceKey,
            speed=request.speed,
            dialogue=item.dialogue,
            speaker=item.speaker,
        )
        for item in request.items
    ]

    try:
        audio_items = await run_in_threadpool(voice_service.generate_batch_audio, voice_requests)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return VoiceBatchGenerateResponse(
        results=[
            VoiceBatchGenerateResult(
                itemId=item.itemId,
                audioBase64=base64.b64encode(audio_bytes).decode("ascii"),
                chunks=_build_chunk_info(voice_request),
            )
            for item, voice_request, audio_bytes in zip(request.items, voice_requests, audio_items)
        ]
    )
