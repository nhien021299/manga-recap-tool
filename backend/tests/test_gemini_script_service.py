from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.services.gemini_script_service as gemini_module
from app.core.config import Settings
from app.models.domain import ScriptContext, ScriptItem, StoryMemory
from app.services.gemini_script_service import GeminiScriptService, GenerationStats


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
async def test_identity_evidence_uses_carryover_and_neutral_fallback():
    service = GeminiScriptService(build_settings())
    evidence = service._build_identity_evidence(
        context=ScriptContext(mainCharacter="Ly Pham"),
        previous_memory=StoryMemory(chunkIndex=0, summary="prev", recentNames=["Elder Mo"]),
    )

    assert evidence.confirmed_names == []
    assert evidence.carryover_names == ["Elder Mo", "Ly Pham"]
    assert evidence.locked_names == []
    assert evidence.use_neutral_fallback is True
    assert evidence.neutral_fallback_reason == "using carryover hints only"


def test_identity_evidence_prompt_uses_carryover_only():
    service = GeminiScriptService(build_settings())
    evidence = service._build_identity_evidence(
        context=ScriptContext(mainCharacter="Ly Pham"),
        previous_memory=StoryMemory(chunkIndex=0, summary="prev", recentNames=["Elder Mo"]),
    )
    prompt = service._build_unified_prompt(
        context=ScriptContext(summary="A tense chase is already underway."),
        batch_panels=[],
        panel_count=2,
        start_index=1,
        previous_memory=StoryMemory(
            chunkIndex=0,
            summary="The opponent suddenly closed the distance.",
            recentNames=["Ly Pham", "Elder Mo", "Third Name"],
        ),
        identity_evidence=evidence,
    )

    assert evidence.confirmed_names == []
    assert evidence.carryover_names == ["Elder Mo", "Ly Pham"]
    assert evidence.locked_names == []
    assert evidence.use_neutral_fallback is True
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
        batch_panels=[],
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
            locked_names=["Ly Pham"],
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
    assert "Default to the shortest phrasing that still sounds cinematic and clear." in prompt
    assert "Do not mechanically describe each image in isolation." in prompt
    assert "Make adjacent panels flow like one seamless recap." in prompt
    assert "Every voiceover_text should flow logically into the next one as part of a continuous chapter recap." in prompt
    assert "label people by visible age, outfit, role, weapon, job, or standout physical traits" in prompt
    assert "Avoid overusing flat labels like \"nam nhan\"" in prompt
    assert "Add a very light touch of modern Vietnamese Gen Z phrasing" in prompt
    assert "keep the same descriptor unless the images clearly reveal better identity detail" in prompt
    assert "Do not switch an unnamed character from one guessed role or job to another across nearby panels" in prompt
    assert "Do not infer a profession such as herb picker, worker, guard, or servant unless the current images make that role genuinely clear." in prompt


def test_build_unified_prompt_keeps_json_only_guardrails():
    service = GeminiScriptService(build_settings())
    prompt = service._build_unified_prompt(
        context=ScriptContext(summary="A quiet room hides a clue."),
        batch_panels=[],
        panel_count=2,
        start_index=1,
        previous_memory=None,
        identity_evidence=gemini_module.IdentityEvidence(
            candidate_pool=[],
            confirmed_names=[],
            carryover_names=[],
            locked_names=[],
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


def test_build_unified_prompt_injects_character_mapping_rules():
    service = GeminiScriptService(build_settings())
    prompt = service._build_unified_prompt(
        context=ScriptContext(
            summary="A chase through ruined alleys.",
            characterContext={
                "chapterId": "chapter_x",
                "characters": [
                    {
                        "clusterId": "char_001",
                        "canonicalName": "Ly Pham",
                        "displayLabel": "ga ao den",
                        "lockName": True,
                    }
                ],
                "panelCharacterRefs": {"panel-1": ["char_001"]},
                "unknownPanelIds": [],
            },
        ),
        batch_panels=[SimpleNamespace(panelId="panel-1", orderIndex=0)],
        panel_count=1,
        start_index=1,
        previous_memory=None,
        identity_evidence=gemini_module.IdentityEvidence(
            candidate_pool=["Ly Pham"],
            confirmed_names=[],
            carryover_names=["Ly Pham"],
            locked_names=["Ly Pham"],
            has_text_signal=False,
            use_neutral_fallback=False,
            neutral_fallback_reason="locked character mapping available",
        ),
    )

    assert "Character consistency rules:" in prompt
    assert "always use that canonical name" in prompt
    assert "Panel 1: Ly Pham (locked)" in prompt


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
    assert len(memory.summary.split()) <= 70
    assert memory.summary


def test_summarize_batch_uses_first_and_last_sentence_from_recent_items():
    service = GeminiScriptService(build_settings())
    items = [
        ScriptItem(
            panel_index=1,
            voiceover_text="Ly Pham khung lai trong gang tac, nhung ga ao den da ep sat den muc khong con duong lui.",
        ),
        ScriptItem(
            panel_index=2,
            voiceover_text="Elder Mo loang choang o phia sau, con luoi kiem cua doi thu thi lia ngang nhu muon cat dut moi co hoi song sot.",
        ),
        ScriptItem(
            panel_index=3,
            voiceover_text=(
                "Den luc nhom tuong da thoat, bong nguoi bi thuong lai nhin thay mot cai bong khac dang bo theo tu cuoi hanh lang."
            ),
        ),
    ]

    summary = service._summarize_batch(items)

    assert "Ly Pham khung lai trong gang tac" in summary
    assert "bong khac dang bo theo tu cuoi hanh lang" in summary
    assert "Elder Mo loang choang" not in summary


def test_extract_recent_names_drops_stale_names_when_current_chunk_has_no_match():
    service = GeminiScriptService(build_settings())
    previous_memory = StoryMemory(chunkIndex=0, summary="prev", recentNames=["Ly Pham", "Elder Mo"])
    items = [
        ScriptItem(
            panel_index=4,
            voiceover_text="Ga ao den van ap dao, con bong nguoi bi thuong chi con biet loang choang bam theo.",
        )
    ]

    recent_names = service._extract_recent_names(
        ScriptContext(mainCharacter="Ly Pham", summary="Ly Pham bi truy sat trong hanh lang ngap mau."),
        items,
        previous_memory,
    )

    assert recent_names == []


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
