import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.deps import (
    get_app_settings,
    get_character_prepass_service,
    get_character_review_state_service,
    get_character_script_context_builder,
)
from app.models.characters import (
    ChapterCharacterState,
    CharacterCreateClusterRequest,
    CharacterMergeRequest,
    CharacterPanelMappingRequest,
    CharacterPrepassRequest,
    CharacterRenameRequest,
    CharacterScriptContext,
    CharacterStatusRequest,
)
from app.utils.temp_files import cleanup_temp_dir, save_uploads

router = APIRouter(prefix="/characters", tags=["characters"])


@router.post("/prepass", response_model=ChapterCharacterState)
async def character_prepass(
    payload: str = Form(...),
    files: list[UploadFile] = File(...),
    settings=Depends(get_app_settings),
    character_prepass_service=Depends(get_character_prepass_service),
) -> ChapterCharacterState:
    request = CharacterPrepassRequest.model_validate(json.loads(payload))
    if len(request.panels) != len(files):
        raise HTTPException(status_code=400, detail="Character prepass panel metadata count must match uploaded files.")

    temp_dir, saved_paths = await save_uploads(settings.temp_root, f"character-prepass-{request.chapterId}", files)
    try:
        return character_prepass_service.run(
            chapter_id=request.chapterId,
            panels=request.panels,
            file_paths=saved_paths,
            force=request.force,
        )
    finally:
        cleanup_temp_dir(temp_dir)


@router.get("/review/{chapter_id}", response_model=ChapterCharacterState)
def get_character_review_state(
    chapter_id: str,
    character_review_state_service=Depends(get_character_review_state_service),
) -> ChapterCharacterState:
    state = character_review_state_service.get(chapter_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Character state not found for chapter_id '{chapter_id}'.")
    return state


@router.post("/clusters", response_model=ChapterCharacterState)
def create_character_cluster(
    request: CharacterCreateClusterRequest,
    character_review_state_service=Depends(get_character_review_state_service),
) -> ChapterCharacterState:
    try:
        return character_review_state_service.create_manual_cluster(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/rename", response_model=ChapterCharacterState)
def rename_character_cluster(
    request: CharacterRenameRequest,
    character_review_state_service=Depends(get_character_review_state_service),
) -> ChapterCharacterState:
    try:
        return character_review_state_service.rename_cluster(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/merge", response_model=ChapterCharacterState)
def merge_character_clusters(
    request: CharacterMergeRequest,
    character_review_state_service=Depends(get_character_review_state_service),
) -> ChapterCharacterState:
    try:
        return character_review_state_service.merge_clusters(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/panel-mapping", response_model=ChapterCharacterState)
def update_character_panel_mapping(
    request: CharacterPanelMappingRequest,
    character_review_state_service=Depends(get_character_review_state_service),
) -> ChapterCharacterState:
    try:
        return character_review_state_service.update_panel_mapping(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/status", response_model=ChapterCharacterState)
def update_character_cluster_status(
    request: CharacterStatusRequest,
    character_review_state_service=Depends(get_character_review_state_service),
) -> ChapterCharacterState:
    try:
        return character_review_state_service.update_cluster_status(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/script-context/{chapter_id}", response_model=CharacterScriptContext)
def get_character_script_context(
    chapter_id: str,
    character_review_state_service=Depends(get_character_review_state_service),
    character_script_context_builder=Depends(get_character_script_context_builder),
) -> CharacterScriptContext:
    state = character_review_state_service.get(chapter_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Character state not found for chapter_id '{chapter_id}'.")
    return character_script_context_builder.build(state)
