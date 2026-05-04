"""
Core TTS engine modules
"""

from .model_config import ModelConfig, TTSConfig, MODEL_GENDER, MODEL_GROUP, MODEL_AREA, MODEL_EMOTION
from .model import ModelSessionManager
from .tts_engine import TTSEngine
from .text_processor import TextProcessor
from .audio_processor import AudioProcessor

__all__ = [
    "ModelConfig",
    "TTSConfig",  # Backward compatibility
    "ModelSessionManager",
    "TTSEngine",
    "TextProcessor",
    "AudioProcessor",
    "MODEL_GENDER",
    "MODEL_GROUP",
    "MODEL_AREA",
    "MODEL_EMOTION",
] 