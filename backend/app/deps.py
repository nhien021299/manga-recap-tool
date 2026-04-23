from fastapi import Request


def get_provider_registry(request: Request):
    return request.app.state.provider_registry

def get_job_queue(request: Request):
    return request.app.state.job_queue


def get_app_settings(request: Request):
    return request.app.state.settings


def get_gemini_script_service(request: Request):
    return request.app.state.gemini_script_service


def get_character_prepass_service(request: Request):
    return request.app.state.character_prepass_service


def get_character_review_state_service(request: Request):
    return request.app.state.character_review_state_service


def get_character_script_context_builder(request: Request):
    return request.app.state.character_script_context_builder


def get_voice_service(request: Request):
    return request.app.state.voice_service


def get_tts_runtime(request: Request):
    return request.app.state.tts_runtime


def get_render_service(request: Request):
    return request.app.state.render_service


def get_render_queue(request: Request):
    return request.app.state.render_queue
