from __future__ import annotations

from dataclasses import dataclass


SAMPLE_BASE_URL = "/assets/voice-samples"


@dataclass(frozen=True)
class VoicePresetMeta:
    label: str
    description: str
    style_tag: str
    sample_url: str


VIENEU_PRESET_CATALOG: dict[str, VoicePresetMeta] = {
    "Bích Ngọc (Nữ - Miền Bắc)": VoicePresetMeta(
        label="Nữ kể cuốn",
        description="Giọng nữ miền Bắc sáng và gọn nhịp, hợp kiểu review truyện mở đầu cuốn người nghe.",
        style_tag="review cuốn",
        sample_url=f"{SAMPLE_BASE_URL}/vieneu/nu-ke-cuon.wav",
    ),
    "Phạm Tuyên (Nam - Miền Bắc)": VoicePresetMeta(
        label="Nam dẫn truyện",
        description="Giọng nam miền Bắc chắc và rõ, hợp kiểu tóm tắt truyện mạch lạc, có lực.",
        style_tag="dẫn truyện",
        sample_url=f"{SAMPLE_BASE_URL}/vieneu/nam-dan-truyen.wav",
    ),
    "Thục Đoan (Nữ - Miền Nam)": VoicePresetMeta(
        label="Nữ tâm tình",
        description="Giọng nữ miền Nam mềm hơn, hợp các đoạn kể chuyện cảm xúc và hồi tưởng.",
        style_tag="kể chuyện",
        sample_url=f"{SAMPLE_BASE_URL}/vieneu/nu-tam-tinh.wav",
    ),
    "Xuân Vĩnh (Nam - Miền Nam)": VoicePresetMeta(
        label="Nam cao trào",
        description="Giọng nam miền Nam nhấn nhá mạnh hơn, hợp các đoạn twist, combat và chốt cliffhanger.",
        style_tag="cao trào",
        sample_url=f"{SAMPLE_BASE_URL}/vieneu/nam-cao-trao.wav",
    ),
}


F5_PRESET_CATALOG: dict[str, VoicePresetMeta] = {
    "nu_review_cuon": VoicePresetMeta(
        label="Nữ review cuốn",
        description="Bản clone sáng, nhịp nhanh, hợp video review truyện giữ độ cuốn và rõ ý.",
        style_tag="review cuốn",
        sample_url=f"{SAMPLE_BASE_URL}/f5/nu-review-cuon.wav",
    ),
    "nam_review_luc": VoicePresetMeta(
        label="Nam review lực",
        description="Bản clone nam có lực hơn, hợp đoạn dẫn nhập, giải thích plot và đẩy nhịp recap.",
        style_tag="dẫn truyện",
        sample_url=f"{SAMPLE_BASE_URL}/f5/nam-review-luc.wav",
    ),
    "nu_ke_chuyen_sau": VoicePresetMeta(
        label="Nữ kể chuyện sâu",
        description="Bản clone nữ mềm và sâu hơn, hợp các đoạn kể biến cố, hồi tưởng và kéo cảm xúc.",
        style_tag="kể chuyện",
        sample_url=f"{SAMPLE_BASE_URL}/f5/nu-ke-chuyen-sau.wav",
    ),
    "nam_cao_trao_gat": VoicePresetMeta(
        label="Nam cao trào gắt",
        description="Bản clone nam nhấn mạnh hơn, hợp các đoạn bẻ lái, combat và cliffhanger cuối câu.",
        style_tag="cao trào",
        sample_url=f"{SAMPLE_BASE_URL}/f5/nam-cao-trao-gat.wav",
    ),
}
