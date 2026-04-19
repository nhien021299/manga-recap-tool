import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from app.core.config import Settings
from app.models.domain import OCRLine, OCRResult, PanelReference, ScriptContext, VisionCaptionRaw
from app.providers.ocr.paddleocr_provider import PaddleOCRProvider
from app.services.caption_service import CaptionService
from app.services.script_pipeline import ScriptPipeline


class FakeTextProvider:
    def repair_json(self, *, invalid_output: str, schema: dict) -> str:
        raise AssertionError(f"repair_json should not be called: {invalid_output} {schema}")


class FakeVisionProvider:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    async def generate_structured(
        self,
        prompt: str,
        *,
        image_paths: list[Path],
        schema: dict | None = None,
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> str:
        assert "panel_index" in prompt
        assert image_paths
        assert schema is not None
        assert system == "Return JSON only."
        assert max_tokens > 0
        return json.dumps(self.payload, ensure_ascii=False)


class FakeOCRProvider:
    def __init__(self, result: OCRResult) -> None:
        self.result = result

    async def extract(self, image_path: Path, panel_id: str) -> OCRResult:
        assert image_path.exists()
        return self.result.model_copy(update={"panel_id": panel_id})


def build_settings(**updates) -> Settings:
    return Settings(_env_file=None).model_copy(update=updates)


def test_caption_prompt_emphasizes_visual_grounding_and_panel_index():
    service = CaptionService(build_settings(), vision_provider=None, text_provider=None)

    prompt = service._build_prompt(
        ScriptContext(mangaName="A", mainCharacter="B", language="vi"),
        [PanelReference(panelId="scene-001.png", orderIndex=0)],
    )

    assert "Describe only what is directly visible in each panel." in prompt
    assert "panel_index" in prompt
    assert "main_event and inset_event" in prompt
    assert "visible_text" in prompt


def test_paddleocr_provider_configures_cpu_without_mkldnn(monkeypatch):
    captured_kwargs: dict[str, object] = {}

    class FakePaddleOCR:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    fake_module = ModuleType("paddleocr")
    fake_module.PaddleOCR = FakePaddleOCR
    monkeypatch.setitem(sys.modules, "paddleocr", fake_module)

    provider = PaddleOCRProvider(min_confidence=0.55, max_text_lines=2, prefer_sfx=True)

    engine = provider._get_engine()

    assert isinstance(engine, FakePaddleOCR)
    assert captured_kwargs["lang"] == "korean"
    assert captured_kwargs["device"] == "cpu"
    assert captured_kwargs["enable_mkldnn"] is False
    assert captured_kwargs["use_doc_orientation_classify"] is False
    assert captured_kwargs["use_doc_unwarping"] is False
    assert captured_kwargs["use_textline_orientation"] is False


@pytest.mark.asyncio
async def test_paddleocr_provider_wraps_onednn_runtime_error(tmp_path: Path):
    image_path = tmp_path / "panel.png"
    image_path.write_bytes(b"img")

    provider = PaddleOCRProvider(min_confidence=0.55, max_text_lines=2, prefer_sfx=True)
    provider._engine = SimpleNamespace(
        predict=lambda _path: (_ for _ in ()).throw(
            NotImplementedError(
                "(Unimplemented) ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]  "
                "(at ..\\paddle\\fluid\\framework\\new_executor\\instruction\\onednn\\onednn_instruction.cc:118)"
            )
        )
    )

    with pytest.raises(RuntimeError, match="pin PaddlePaddle to 3.2.2"):
        await provider.extract(image_path, "panel-1")


def test_merge_panel_prefers_ocr_grounding():
    service = CaptionService(build_settings(), vision_provider=None, text_provider=None)
    panel = PanelReference(panelId="scene-001.png", orderIndex=0)
    vision = VisionCaptionRaw(
        panel_index=1,
        panel_id=panel.panelId,
        main_event="Một tia sáng lớn xé ngang trời mưa.",
        inset_event="Một chiếc giỏ bị lật đổ.",
        visible_objects=["tia sáng", "mái nhà", "giỏ"],
        visible_text=[],
        scene_tone="căng thẳng, đột ngột",
    )
    ocr = OCRResult(
        panel_id=panel.panelId,
        has_text=True,
        full_text="ẦM Chạy mau",
        lines=[
            OCRLine(text="ẦM", confidence=0.98, role="sfx", bbox=[0, 0, 10, 10]),
            OCRLine(text="Chạy mau", confidence=0.96, role="dialogue", bbox=[10, 10, 30, 30]),
        ],
    )

    understanding, diagnostics = service._merge_panel(
        context=ScriptContext(mangaName="A", mainCharacter="B", language="vi"),
        panel=panel,
        vision=vision,
        ocr=ocr,
        caption_source="vision_ocr",
    )

    assert understanding.dialogue == "Chạy mau"
    assert understanding.visible_text == ["ẦM", "Chạy mau"]
    assert "inset_recovered" in diagnostics.correction_tags
    assert "dialogue_grounded" in diagnostics.correction_tags


@pytest.mark.asyncio
async def test_generate_understandings_vision_only_metrics(tmp_path: Path):
    image_path = tmp_path / "scene-001.png"
    image_path.write_bytes(b"fake")
    service = CaptionService(
        build_settings(caption_chunk_size=1),
        vision_provider=FakeVisionProvider(
            {
                "items": [
                    {
                        "panel_index": 1,
                        "main_event": "Một người đàn ông rút kiếm.",
                        "inset_event": "",
                        "visible_objects": ["người đàn ông", "thanh kiếm"],
                        "visible_text": [],
                        "scene_tone": "căng thẳng",
                    }
                ]
            }
        ),
        text_provider=FakeTextProvider(),
        ocr_provider=None,
    )

    result = await service.generate_understandings(
        context=ScriptContext(mangaName="A", mainCharacter="B", language="vi"),
        panels=[PanelReference(panelId="scene-001.png", orderIndex=0)],
        file_paths=[image_path],
        on_log=lambda *_args, **_kwargs: None,
        check_cancel=lambda: None,
    )

    assert result.caption_source == "vision_only"
    assert result.ocr_ms == 0
    assert result.merge_ms >= 0
    assert result.understandings[0].main_event == "Một người đàn ông rút kiếm."


@pytest.mark.asyncio
async def test_generate_understandings_vision_ocr_metrics(tmp_path: Path):
    image_path = tmp_path / "scene-001.png"
    image_path.write_bytes(b"fake")
    ocr_result = OCRResult(
        panel_id="scene-001.png",
        has_text=True,
        full_text="BOOM We move",
        lines=[
            OCRLine(text="BOOM", confidence=0.95, role="sfx", bbox=[0, 0, 10, 10]),
            OCRLine(text="We move", confidence=0.95, role="dialogue", bbox=[10, 10, 30, 30]),
        ],
    )
    service = CaptionService(
        build_settings(caption_chunk_size=1, ocr_enabled=True),
        vision_provider=FakeVisionProvider(
            {
                "items": [
                    {
                        "panel_index": 1,
                        "main_event": "Lightning crashes over the roof.",
                        "inset_event": "",
                        "visible_objects": ["lightning", "roof"],
                        "visible_text": [],
                        "scene_tone": "violent, tense",
                    }
                ]
            }
        ),
        text_provider=FakeTextProvider(),
        ocr_provider=FakeOCRProvider(ocr_result),
    )

    result = await service.generate_understandings(
        context=ScriptContext(mangaName="A", mainCharacter="B", language="en"),
        panels=[PanelReference(panelId="scene-001.png", orderIndex=0)],
        file_paths=[image_path],
        on_log=lambda *_args, **_kwargs: None,
        check_cancel=lambda: None,
    )

    assert result.caption_source == "vision_ocr"
    assert result.ocr_ms >= 0
    assert result.understandings[0].dialogue == "We move"
    assert result.understandings[0].visible_text == ["BOOM", "We move"]


def test_script_pipeline_signature_changes_with_ocr_settings(tmp_path: Path):
    file_path = tmp_path / "scene-001.png"
    file_path.write_bytes(b"fake")
    request = type(
        "Request",
        (),
        {
            "context": ScriptContext(mangaName="A", mainCharacter="B", language="vi"),
            "panels": [PanelReference(panelId="scene-001.png", orderIndex=0)],
        },
    )()
    job = type("Job", (), {"request": request, "file_paths": [file_path]})()
    pipeline = ScriptPipeline(provider_registry=None, caption_service=None, llm_service=None)

    sig_a = pipeline._build_panel_signature(
        job,
        {"visionModel": "qwen2.5vl:7b", "ocrEnabled": False, "ocrProvider": "disabled"},
    )
    sig_b = pipeline._build_panel_signature(
        job,
        {"visionModel": "qwen2.5vl:7b", "ocrEnabled": True, "ocrProvider": "paddleocr"},
    )

    assert sig_a != sig_b
