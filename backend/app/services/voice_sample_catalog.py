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
        label="Nữ hook mở đầu",
        description="Giọng nữ miền Bắc sắc, nhịp nhanh — chuyên câu hook mở đầu, tạo tò mò dẫn dắt người nghe.",
        style_tag="hook mở đầu",
        sample_url=f"{SAMPLE_BASE_URL}/vieneu/nu-hook-mo-dau.wav",
    ),
    "Phạm Tuyên (Nam - Miền Bắc)": VoicePresetMeta(
        label="Nam dẫn plot",
        description="Giọng nam miền Bắc chắc, rõ — chuyên tóm tắt cốt truyện mạch lạc, giữ nhịp và đẩy tình tiết liên tục.",
        style_tag="dẫn plot",
        sample_url=f"{SAMPLE_BASE_URL}/vieneu/nam-dan-plot.wav",
    ),
    "Thục Đoan (Nữ - Miền Nam)": VoicePresetMeta(
        label="Nữ kể cảm xúc",
        description="Giọng nữ miền Nam mềm mại — chuyên các đoạn bi kịch, hồi tưởng và kéo cảm xúc người nghe.",
        style_tag="kể cảm xúc",
        sample_url=f"{SAMPLE_BASE_URL}/vieneu/nu-ke-cam-xuc.wav",
    ),
    "Xuân Vĩnh (Nam - Miền Nam)": VoicePresetMeta(
        label="Nam cao trào",
        description="Giọng nam miền Nam nhấn gắt — chuyên các đoạn twist, combat và chốt cliffhanger cuối tập.",
        style_tag="cao trào",
        sample_url=f"{SAMPLE_BASE_URL}/vieneu/nam-cao-trao.wav",
    ),
}


F5_PRESET_CATALOG: dict[str, VoicePresetMeta] = {
    "nu_review_cuon": VoicePresetMeta(
        label="Nữ review cuốn",
        description="Bản clone nữ sáng, nhịp nhanh — hợp video review truyện giữ độ cuốn và rõ ý.",
        style_tag="review cuốn",
        sample_url=f"{SAMPLE_BASE_URL}/f5/nu-review-cuon.wav",
    ),
    "nam_review_luc": VoicePresetMeta(
        label="Nam review lực",
        description="Bản clone nam có lực — hợp đoạn tóm recap chắc gọn, nhấn mạnh các nút thắt và mâu thuẫn.",
        style_tag="review lực",
        sample_url=f"{SAMPLE_BASE_URL}/f5/nam-review-luc.wav",
    ),
    "nu_ke_chuyen_sau": VoicePresetMeta(
        label="Nữ kể chuyện sâu",
        description="Bản clone nữ mềm và sâu — chuyên narrate các đoạn bi kịch, flashback, hy sinh đầy cảm xúc.",
        style_tag="kể chuyện sâu",
        sample_url=f"{SAMPLE_BASE_URL}/f5/nu-ke-chuyen-sau.wav",
    ),
    "nam_cao_trao_gat": VoicePresetMeta(
        label="Nam cao trào gắt",
        description="Bản clone nam nhấn mạnh gắt — chuyên các đoạn bẻ lái combat cực căng và cliffhanger cuối câu.",
        style_tag="cao trào gắt",
        sample_url=f"{SAMPLE_BASE_URL}/f5/nam-cao-trao-gat.wav",
    ),
}

