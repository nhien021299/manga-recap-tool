import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.deps import get_app_settings, get_caption_service
from app.models.api import CaptionBatchRequest
from app.utils.temp_files import cleanup_temp_dir, save_uploads

router = APIRouter(prefix="/caption", tags=["caption"])


@router.post("/batch")
async def caption_batch(
    context: str = Form(...),
    panels: str = Form(...),
    files: list[UploadFile] = File(...),
    settings=Depends(get_app_settings),
    caption_service=Depends(get_caption_service),
):
    request = CaptionBatchRequest(
        context=json.loads(context),
        panels=json.loads(panels),
    )
    if len(request.panels) != len(files):
        raise HTTPException(status_code=400, detail="Panel metadata count must match uploaded files.")

    temp_dir, saved_paths = await save_uploads(settings.temp_root, "caption-preview", files)
    try:
        result = await caption_service.generate_understandings(
            context=request.context,
            panels=request.panels,
            file_paths=saved_paths,
            on_log=lambda *_args, **_kwargs: None,
            check_cancel=lambda: None,
        )
        return {
            "understandings": [item.model_dump() for item in result.understandings],
            "rawOutput": result.raw_output,
            "elapsedMs": result.caption_ms,
            "ocrMs": result.ocr_ms,
            "mergeMs": result.merge_ms,
            "avgPanelMs": result.avg_panel_ms,
            "captionSource": result.caption_source,
        }
    finally:
        cleanup_temp_dir(temp_dir)
