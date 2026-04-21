from __future__ import annotations

import argparse
import asyncio
import csv
import json
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.models.domain import PanelReference, ScriptContext
from app.services.caption_service import CaptionPanelArtifacts, CaptionService
from app.services.llm_service import LLMService
from app.services.provider_registry import ProviderRegistry

GENERIC_MARKERS = (
    "something",
    "someone",
    "a person",
    "thing happens",
    "có chuyện gì đó",
    "một người",
    "có điều gì đó",
)
ACTION_MARKERS = (
    "run",
    "strike",
    "fall",
    "grab",
    "opens",
    "lightning",
    "attack",
    "đánh",
    "giáng",
    "lao",
    "rơi",
    "rút",
    "chém",
    "đổ",
)
DARK_MARKERS = ("dark", "shadow", "gloom", "night", "tối", "u ám", "bóng", "đen")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run caption/script benchmark directly via backend services.")
    parser.add_argument("--images", required=True, help="Folder containing cropped panel images.")
    parser.add_argument("--models", nargs="+", required=True, help="Vision models to benchmark.")
    parser.add_argument("--modes", nargs="+", default=["vision_only", "vision_ocr"], help="Benchmark modes.")
    parser.add_argument("--workloads", nargs="+", type=int, default=[10, 30, 52], help="Panel counts to test.")
    parser.add_argument("--output", required=True, help="Output directory for benchmark artifacts.")
    parser.add_argument("--language", default="vi", choices=["vi", "en"], help="Output language for caption/script stages.")
    return parser.parse_args()


def get_image_paths(folder: Path, workload: int) -> list[Path]:
    image_paths = sorted([path for path in folder.iterdir() if path.is_file()])
    return image_paths[:workload]


def build_context(folder: Path, language: str) -> ScriptContext:
    manga_name = folder.parent.name
    main_character = "Nhân vật chính" if language == "vi" else "Main character"
    return ScriptContext(mangaName=manga_name, mainCharacter=main_character, language=language)


def build_panel_refs(image_paths: list[Path]) -> list[PanelReference]:
    return [PanelReference(panelId=path.name, orderIndex=index) for index, path in enumerate(image_paths)]


def make_services(settings: Settings) -> tuple[ProviderRegistry, CaptionService, LLMService]:
    registry = ProviderRegistry(settings)
    text_provider = registry.get_text_provider()
    vision_provider = registry.get_vision_provider()
    caption_service = CaptionService(settings, vision_provider, text_provider, ocr_provider=registry.get_ocr_provider())
    llm_service = LLMService(settings, text_provider)
    return registry, caption_service, llm_service


def clean_text(value: str) -> str:
    return " ".join(value.split()).strip()


def contains_marker(value: str, markers: tuple[str, ...]) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in markers)


def clamp_score(value: float) -> float:
    return max(1.0, min(5.0, round(value, 2)))


def score_panel(
    artifact: CaptionPanelArtifacts,
    ai_view: str,
    voiceover_text: str,
    mode: str,
) -> tuple[dict[str, float], list[str], str]:
    summary = clean_text(artifact.understanding.summary)
    action = clean_text(artifact.understanding.action)
    dialogue = clean_text(artifact.understanding.dialogue)
    visible_text = artifact.understanding.visible_text
    sfx = artifact.understanding.sfx

    specificity = 2.0 + min(len(summary.split()), 18) / 6.0 + min(len(artifact.understanding.visible_objects), 5) * 0.2
    if contains_marker(summary, GENERIC_MARKERS):
        specificity -= 0.9

    action_clarity = 2.0 + (1.2 if contains_marker(action or summary, ACTION_MARKERS) else 0.0)
    if artifact.understanding.inset_event:
        action_clarity += 0.5

    text_sfx_grounding = 1.5
    if dialogue:
        text_sfx_grounding += 1.5
    if sfx:
        text_sfx_grounding += 1.0
    if visible_text:
        text_sfx_grounding += 0.5
    if mode == "vision_ocr" and artifact.ocr.has_text:
        text_sfx_grounding += 0.5

    structure_awareness = 3.0 if artifact.understanding.inset_event else 2.0
    if artifact.understanding.inset_event and "inset_recovered" in artifact.diagnostics.correction_tags:
        structure_awareness += 1.0

    script_usefulness = 2.0 + min(len(ai_view.split()), 20) / 10.0 + min(len(voiceover_text.split()), 25) / 12.0
    if contains_marker(voiceover_text, GENERIC_MARKERS):
        script_usefulness -= 0.7

    error_tags: list[str] = []
    if contains_marker(" ".join([summary, action]), GENERIC_MARKERS):
        error_tags.append("generic_caption")
    if artifact.ocr.has_text and not dialogue and not sfx:
        error_tags.extend(["miss_dialogue", "miss_sfx"])
    if artifact.understanding.inset_event and "inset_recovered" not in artifact.diagnostics.correction_tags:
        error_tags.append("miss_inset")
    if "hallucination_dampened" in artifact.diagnostics.correction_tags:
        error_tags.append("hallucination_entity")
    if not contains_marker(action or summary, ACTION_MARKERS):
        error_tags.append("wrong_action")

    review_bucket = "action-heavy"
    if artifact.ocr.has_text or dialogue or sfx:
        review_bucket = "text-sfx-heavy"
    elif contains_marker(" ".join([artifact.understanding.scene_tone, summary]), DARK_MARKERS):
        review_bucket = "dark-ambiguous"

    metrics = {
        "visual_fidelity": clamp_score(specificity),
        "action_clarity": clamp_score(action_clarity),
        "text_sfx_grounding": clamp_score(text_sfx_grounding),
        "structure_awareness": clamp_score(structure_awareness),
        "script_usefulness": clamp_score(script_usefulness),
    }
    return metrics, sorted(set(error_tags)), review_bucket


def compute_run_score(panel_metrics: list[dict[str, Any]]) -> float:
    if not panel_metrics:
        return 0.0
    total = 0.0
    penalties = 0.0
    for row in panel_metrics:
        total += (
            row["visual_fidelity"] * 0.30
            + row["action_clarity"] * 0.20
            + row["text_sfx_grounding"] * 0.20
            + row["structure_awareness"] * 0.15
            + row["script_usefulness"] * 0.15
        )
        for tag in row["error_tags"]:
            if tag == "hallucination_entity":
                penalties += 0.40
            elif tag == "hallucination_story":
                penalties += 0.30
            elif tag == "wrong_action":
                penalties += 0.20
            elif tag == "generic_caption":
                penalties += 0.10
            elif tag == "miss_inset":
                penalties += 0.10
    return round(max(0.0, total / len(panel_metrics) - penalties), 3)


def select_manual_samples(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    for row in rows:
        key = (row["model"], row["mode"], row["workload"])
        grouped.setdefault(key, []).append(row)

    samples: list[dict[str, Any]] = []
    for key_rows in grouped.values():
        for bucket in ("action-heavy", "text-sfx-heavy", "dark-ambiguous"):
            bucket_rows = [row for row in key_rows if row["review_bucket"] == bucket]
            samples.extend(bucket_rows[:4])
    unique: dict[tuple[str, str, int, str], dict[str, Any]] = {}
    for row in samples:
        unique[(row["model"], row["mode"], row["workload"], row["panel_id"])] = row
    return list(unique.values())


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def build_summary_markdown(summary_rows: list[dict[str, Any]], output_dir: Path) -> str:
    lines = [
        "# OCR + Vision Benchmark Summary",
        "",
        f"Output directory: `{output_dir}`",
        "",
        "| Model | Mode | Workload | Status | Run Score | Total Ms | Caption Ms | OCR Ms | Merge Ms | Script Ms | Avg Panel Ms | OCR Provider |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in summary_rows:
        lines.append(
            "| {model} | {mode} | {workload} | {status} | {run_score} | {totalMs} | {captionMs} | {ocrMs} | {mergeMs} | {scriptMs} | {avgPanelMs} | {ocrProvider} |".format(
                **row
            )
        )
    return "\n".join(lines) + "\n"


async def run_benchmark(args: argparse.Namespace) -> None:
    image_dir = Path(args.images).resolve()
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    base_settings = Settings()
    context = build_context(image_dir, args.language)

    caption_rows: list[dict[str, Any]] = []
    ocr_rows: list[dict[str, Any]] = []
    merged_rows: list[dict[str, Any]] = []
    auto_score_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for model in args.models:
        for mode in args.modes:
            for workload in args.workloads:
                image_paths = get_image_paths(image_dir, workload)
                if len(image_paths) < workload:
                    raise RuntimeError(f"Requested {workload} panels but found only {len(image_paths)} in {image_dir}")

                panels = build_panel_refs(image_paths)
                settings = base_settings.model_copy(
                    update={
                        "vision_model": model,
                        "ocr_enabled": mode == "vision_ocr",
                        "ocr_debug_save_json": False,
                    }
                )
                _registry, caption_service, llm_service = make_services(settings)

                def on_log(_log_type: str, _message: str, _details: str | None = None) -> None:
                    return None

                run_id = f"{model.replace(':', '_')}-{mode}-{workload}"
                run_key = {
                    "run_id": run_id,
                    "model": model,
                    "mode": mode,
                    "workload": workload,
                    "ocrProvider": "paddleocr" if mode == "vision_ocr" else "disabled",
                }
                try:
                    caption_result = await caption_service.generate_understandings(
                        context=context,
                        panels=panels,
                        file_paths=image_paths,
                        on_log=on_log,
                        check_cancel=lambda: None,
                    )
                    generated_items, story_memories, script_raw_output, script_ms = await llm_service.generate_script(
                        context=context,
                        understandings=caption_result.understandings,
                        on_log=on_log,
                        check_cancel=lambda: None,
                    )
                    caption_rows.append(
                        {
                            **run_key,
                            "raw_caption": caption_result.raw_output,
                            "raw_script": script_raw_output,
                            "story_memories": [memory.model_dump() for memory in story_memories],
                        }
                    )
                    generated_by_panel = {item.panel_index - 1: item for item in generated_items}
                    panel_metric_rows: list[dict[str, Any]] = []
                    for artifact in caption_result.panel_artifacts:
                        script_item = generated_by_panel[artifact.panel.orderIndex]
                        score_metrics, error_tags, review_bucket = score_panel(
                            artifact,
                            ai_view=script_item.ai_view,
                            voiceover_text=script_item.voiceover_text,
                            mode=mode,
                        )
                        auto_row = {
                            **run_key,
                            "panel_id": artifact.panel.panelId,
                            "review_bucket": review_bucket,
                            "error_tags": error_tags,
                            **score_metrics,
                        }
                        auto_score_rows.append(auto_row)
                        panel_metric_rows.append(auto_row)
                        ocr_rows.append(
                            {
                                **run_key,
                                "panel_id": artifact.panel.panelId,
                                "ocr": artifact.ocr.model_dump(),
                                "mergeDiagnostics": artifact.diagnostics.model_dump(),
                            }
                        )
                        merged_rows.append(
                            {
                                **run_key,
                                "panel_id": artifact.panel.panelId,
                                "understanding": artifact.understanding.model_dump(),
                                "scriptItem": script_item.model_dump(),
                                "mergeDiagnostics": artifact.diagnostics.model_dump(),
                            }
                        )

                    total_ms = caption_result.caption_ms + script_ms
                    summary_rows.append(
                        {
                            **run_key,
                            "status": "completed",
                            "run_score": compute_run_score(panel_metric_rows),
                            "panelCount": workload,
                            "totalMs": total_ms,
                            "captionMs": caption_result.caption_ms,
                            "ocrMs": caption_result.ocr_ms,
                            "mergeMs": caption_result.merge_ms,
                            "scriptMs": script_ms,
                            "avgPanelMs": caption_result.avg_panel_ms,
                        }
                    )
                except Exception as exc:
                    summary_rows.append(
                        {
                            **run_key,
                            "status": "failed",
                            "run_score": 0.0,
                            "panelCount": workload,
                            "totalMs": 0,
                            "captionMs": 0,
                            "ocrMs": 0,
                            "mergeMs": 0,
                            "scriptMs": 0,
                            "avgPanelMs": 0,
                            "error": str(exc),
                        }
                    )

    manual_rows = select_manual_samples(auto_score_rows)

    write_jsonl(output_dir / "captions_raw.jsonl", caption_rows)
    write_jsonl(output_dir / "ocr_raw.jsonl", ocr_rows)
    write_jsonl(output_dir / "merged_understandings.jsonl", merged_rows)
    write_csv(
        output_dir / "auto_scores.csv",
        auto_score_rows,
        [
            "model",
            "mode",
            "workload",
            "ocrProvider",
            "panel_id",
            "review_bucket",
            "visual_fidelity",
            "action_clarity",
            "text_sfx_grounding",
            "structure_awareness",
            "script_usefulness",
            "error_tags",
        ],
    )
    write_csv(
        output_dir / "manual_review.csv",
        manual_rows,
        [
            "model",
            "mode",
            "workload",
            "ocrProvider",
            "panel_id",
            "review_bucket",
            "manual_specificity",
            "action_clarity_manual",
            "manual_emotion",
            "manual_dialogue",
            "notes",
        ],
    )
    (output_dir / "summary.json").write_text(
        json.dumps(summary_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "SUMMARY.md").write_text(
        build_summary_markdown(summary_rows, output_dir),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    asyncio.run(run_benchmark(args))


if __name__ == "__main__":
    main()
