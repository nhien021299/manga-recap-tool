from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import app.services.gemini_script_service as gemini_module
from app.core.config import Settings
from app.models.domain import OCRLine, OCRResult, ScriptContext, ScriptItem, StoryMemory
from app.services.gemini_script_service import GeminiScriptService, GenerationStats


class FakeOCRProvider:
    def __init__(self, result: OCRResult) -> None:
        self.result = result

    async def extract(self, image_path: Path, panel_id: str) -> OCRResult:
        assert image_path
        return self.result.model_copy(update={"panel_id": panel_id})


class FakeStatusError(Exception):
    def __init__(self, status_code: int, message: str, headers: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.response = SimpleNamespace(status_code=status_code, headers=headers or {})


class FakeClient:
    def __init__(self, events: list[object]) -> None:
        self._events = list(events)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **_kwargs):
        event = self._events.pop(0)
        if isinstance(event, Exception):
            raise event
        return event


def build_settings(**updates) -> Settings:
    base = {
        "gemini_api_key": "test-key",
        "gemini_retry_attempts": 2,
        "gemini_retry_base_delay_ms": 2000,
        "gemini_retry_max_delay_ms": 15000,
        "gemini_script_batch_size": 4,
    }
    base.update(updates)
    return Settings(_env_file=None).model_copy(update=base)


def build_response(text: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18),
    )


def test_script_context_defaults_allow_missing_optional_fields():
    context = ScriptContext()

    assert context.mangaName == ""
    assert context.mainCharacter == ""
    assert context.summary == ""
    assert context.language == "vi"


@pytest.mark.asyncio
async def test_identity_evidence_without_ocr_uses_carryover_and_neutral_fallback():
    service = GeminiScriptService(build_settings())
    evidence = await service._build_identity_evidence(
        context=ScriptContext(mainCharacter="Ly Pham"),
        batch_panels=[],
        batch_paths=[],
        previous_memory=StoryMemory(chunkIndex=0, summary="prev", recentNames=["Elder Mo"]),
        on_log=None,
    )

    assert evidence.confirmed_names == []
    assert evidence.carryover_names == ["Elder Mo", "Ly Pham"]
    assert evidence.use_neutral_fallback is True
    assert evidence.neutral_fallback_reason == "identity OCR experiment disabled"


@pytest.mark.asyncio
async def test_identity_evidence_with_ocr_no_match_does_not_confirm_names(tmp_path: Path):
    image_path = tmp_path / "panel.png"
    image_path.write_bytes(b"img")
    service = GeminiScriptService(
        build_settings(gemini_identity_experiment_enabled=True),
        identity_ocr_provider=FakeOCRProvider(
            OCRResult(
                panel_id="panel-1",
                has_text=True,
                full_text="Unknown fighter",
                lines=[OCRLine(text="Unknown fighter", confidence=0.95, role="dialogue")],
            )
        ),
    )

    evidence = await service._build_identity_evidence(
        context=ScriptContext(mainCharacter="Ly Pham"),
        batch_panels=[SimpleNamespace(panelId="panel-1")],
        batch_paths=[image_path],
        previous_memory=StoryMemory(chunkIndex=0, summary="prev", recentNames=["Elder Mo"]),
        on_log=None,
    )

    assert evidence.confirmed_names == []
    assert evidence.carryover_names == ["Elder Mo", "Ly Pham"]
    assert evidence.use_neutral_fallback is True
    assert evidence.has_text_signal is True


@pytest.mark.asyncio
async def test_identity_evidence_with_ocr_match_confirms_candidate_name(tmp_path: Path):
    image_path = tmp_path / "panel.png"
    image_path.write_bytes(b"img")
    service = GeminiScriptService(
        build_settings(gemini_identity_experiment_enabled=True),
        identity_ocr_provider=FakeOCRProvider(
            OCRResult(
                panel_id="panel-1",
                has_text=True,
                full_text="Ly Pham, retreat now",
                lines=[OCRLine(text="Ly Pham", confidence=0.99, role="dialogue")],
            )
        ),
    )

    evidence = await service._build_identity_evidence(
        context=ScriptContext(mainCharacter="Ly Pham"),
        batch_panels=[SimpleNamespace(panelId="panel-1")],
        batch_paths=[image_path],
        previous_memory=StoryMemory(chunkIndex=0, summary="prev", recentNames=["Elder Mo"]),
        on_log=None,
    )
    prompt = service._build_unified_prompt(
        context=ScriptContext(summary="A tense chase is already underway."),
        panel_count=2,
        start_index=1,
        previous_memory=StoryMemory(
            chunkIndex=0,
            summary="The opponent suddenly closed the distance.",
            recentNames=["Ly Pham", "Elder Mo", "Third Name"],
        ),
        identity_evidence=evidence,
    )

    assert evidence.confirmed_names == ["Ly Pham"]
    assert evidence.carryover_names == ["Elder Mo"]
    assert evidence.use_neutral_fallback is False
    assert "Confirmed from visible text/dialogue in this batch:" in prompt
    assert "Ly Pham" in prompt
    assert "Carryover names from previous chunk:" in prompt
    assert "Elder Mo" in prompt
    assert "Naming rules:" in prompt
    assert "Truth rules:" in prompt


def test_build_unified_prompt_contains_update_2_1_style_blocks():
    service = GeminiScriptService(build_settings())
    prompt = service._build_unified_prompt(
        context=ScriptContext(
            summary="A bloody chase becomes a desperate fight in a dark corridor.",
            mainCharacter="Ly Pham",
        ),
        panel_count=3,
        start_index=4,
        previous_memory=StoryMemory(
            chunkIndex=0,
            summary="The wounded group hears something moving behind them.",
            recentNames=["Ly Pham"],
        ),
        identity_evidence=gemini_module.IdentityEvidence(
            candidate_pool=["Ly Pham"],
            confirmed_names=["Ly Pham"],
            carryover_names=[],
            has_text_signal=True,
            use_neutral_fallback=False,
            neutral_fallback_reason="",
        ),
    )

    assert "Current mode:" in prompt
    assert "Truth rules:" in prompt
    assert "Output rules:" in prompt
    assert "Lexical rules:" in prompt
    assert "Batch flow rules:" in prompt
    assert "Return raw JSON only with this schema:" in prompt
    assert "Prefer 1 to 2 short sentences per panel." in prompt
    assert "Do not mechanically describe each image in isolation." in prompt
    assert "Make adjacent panels flow like one seamless recap." in prompt
    assert "Every voiceover_text should flow logically into the next one as part of a continuous chapter recap." in prompt


def test_build_unified_prompt_keeps_json_only_guardrails():
    service = GeminiScriptService(build_settings())
    prompt = service._build_unified_prompt(
        context=ScriptContext(summary="A quiet room hides a clue."),
        panel_count=2,
        start_index=1,
        previous_memory=None,
        identity_evidence=gemini_module.IdentityEvidence(
            candidate_pool=[],
            confirmed_names=[],
            carryover_names=[],
            has_text_signal=False,
            use_neutral_fallback=True,
            neutral_fallback_reason="no candidate names available",
        ),
    )

    assert "Return raw JSON only with this schema:" in prompt
    assert '"panel_index": 1' in prompt
    assert '"voiceover_text": "..."' in prompt
    assert "Return exactly 2 items for 2 images." in prompt
    assert "panel_index starts at 1 and increases by 1." in prompt


def test_infer_narration_mode_returns_horror():
    service = GeminiScriptService(build_settings())

    mode = service._infer_narration_mode(
        ScriptContext(summary="Mau chay lenh lang va con quy lao ra tu bong toi."),
        None,
    )

    assert mode == "horror"


def test_infer_narration_mode_returns_combat():
    service = GeminiScriptService(build_settings())

    mode = service._infer_narration_mode(
        ScriptContext(summary="Cuoc giao chien no ra khi thanh kiem va don tan cong dap vao nhau."),
        None,
    )

    assert mode == "combat"


def test_infer_narration_mode_falls_back_to_mystery():
    service = GeminiScriptService(build_settings())

    mode = service._infer_narration_mode(
        ScriptContext(summary="A stranger stands in the doorway and nobody understands why."),
        None,
    )

    assert mode == "mystery"


def test_build_story_memory_returns_tiny_summary_and_recent_names():
    service = GeminiScriptService(build_settings())
    context = ScriptContext(mainCharacter="Ly Pham", summary="Ly Pham is cornered by an enemy.")
    items = [
        ScriptItem(
            panel_index=1,
            voiceover_text=(
                "Ly Pham giat minh khi doi thu bat ngo ap sat, va khong khi trong canh nay lap tuc bi day len dinh diem. "
                "Ngay ca luc rut lui, Ly Pham van bi khoa chat trong the bi dong."
            ),
        )
    ]

    memory = service._build_story_memory(0, context, items, None)

    assert memory.chunkIndex == 0
    assert memory.recentNames == ["Ly Pham"]
    assert len(memory.summary.split()) <= 50
    assert memory.summary


@pytest.mark.asyncio
async def test_call_gemini_retries_with_retry_after_and_updates_stats(monkeypatch):
    sleep_calls: list[float] = []

    async def fake_sleep(duration: float) -> None:
        sleep_calls.append(duration)

    monkeypatch.setattr(gemini_module.asyncio, "sleep", fake_sleep)

    service = GeminiScriptService(build_settings())
    service._create_openai_client = lambda *, api_key: FakeClient(
        [
            FakeStatusError(429, "quota", {"retry-after": "3"}),
            build_response('[{"panel_index": 1, "voiceover_text": "ok"}]'),
        ]
    )

    stats = GenerationStats()
    text, usage = await service._call_gemini(
        api_key="test-key",
        prompt="prompt",
        inline_data=None,
        on_log=None,
        stats=stats,
    )

    assert text.startswith("[")
    assert usage["total_tokens"] == 18
    assert stats.retry_count == 1
    assert stats.rate_limited_count == 1
    assert sleep_calls == [3.0]


@pytest.mark.asyncio
async def test_call_gemini_retries_on_503_with_exponential_backoff(monkeypatch):
    sleep_calls: list[float] = []

    async def fake_sleep(duration: float) -> None:
        sleep_calls.append(duration)

    monkeypatch.setattr(gemini_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(gemini_module.random, "random", lambda: 0.0)

    service = GeminiScriptService(build_settings())
    service._create_openai_client = lambda *, api_key: FakeClient(
        [
            FakeStatusError(503, "unavailable"),
            build_response('[{"panel_index": 1, "voiceover_text": "ok"}]'),
        ]
    )

    stats = GenerationStats()
    await service._call_gemini(
        api_key="test-key",
        prompt="prompt",
        inline_data=None,
        on_log=None,
        stats=stats,
    )

    assert stats.retry_count == 1
    assert sleep_calls == [2.0]


@pytest.mark.asyncio
async def test_call_gemini_raises_after_exhausting_retries(monkeypatch):
    sleep_calls: list[float] = []

    async def fake_sleep(duration: float) -> None:
        sleep_calls.append(duration)

    monkeypatch.setattr(gemini_module.asyncio, "sleep", fake_sleep)

    service = GeminiScriptService(build_settings())
    service._create_openai_client = lambda *, api_key: FakeClient([FakeStatusError(503, "down"), FakeStatusError(503, "down")])

    stats = GenerationStats()
    with pytest.raises(RuntimeError, match="OpenAI API Error \\(503\\)"):
        await service._call_gemini(
            api_key="test-key",
            prompt="prompt",
            inline_data=None,
            on_log=None,
            stats=stats,
        )

    assert stats.retry_count == 1
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == pytest.approx(2.08, abs=0.5)
