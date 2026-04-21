from __future__ import annotations

import argparse
import asyncio
import json
import statistics
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.models.api import ScriptJobOptions
from app.models.domain import PanelReference, ScriptContext
from app.services.gemini_script_service import GeminiScriptService

DEFAULT_BATCH_SIZES = [2, 4, 6, 8]
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark Gemini script latency across multiple batch sizes.")
    parser.add_argument(
        "--chapter-dir",
        dest="chapter_dirs",
        action="append",
        required=True,
        help="Chapter directory containing panel images. Provide this flag multiple times for multiple chapters.",
    )
    parser.add_argument(
        "--output",
        default="benchmark_out/m2_gemini_latency",
        help="Directory where benchmark results will be written.",
    )
    parser.add_argument(
        "--batch-sizes",
        default="2,4,6,8",
        help="Comma-separated batch sizes to benchmark.",
    )
    parser.add_argument("--manga-name", default="", help="Optional manga title context.")
    parser.add_argument("--main-character", default="", help="Optional main character hint.")
    parser.add_argument("--summary", default="", help="Optional story summary context.")
    parser.add_argument("--language", default="vi", choices=["vi", "en"], help="Output language for generation.")
    return parser.parse_args()


def load_panels(chapter_dir: Path) -> tuple[list[PanelReference], list[Path]]:
    file_paths = sorted(
        [path for path in chapter_dir.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS]
    )
    panels = [PanelReference(panelId=f"{chapter_dir.name}-p{index + 1}", orderIndex=index) for index, _ in enumerate(file_paths)]
    return panels, file_paths


def classify_failure(error_message: str) -> str:
    lowered = error_message.lower()
    if "parse error" in lowered or "expected " in lowered:
        return "parse_or_schema_failure"
    if "api error" in lowered or "network error" in lowered or "timeout" in lowered:
        return "provider_failure"
    return "unknown_failure"


async def run_single_benchmark(
    *,
    chapter_dir: Path,
    batch_size: int,
    context: ScriptContext,
) -> dict[str, Any]:
    settings = get_settings().model_copy(update={"gemini_script_batch_size": batch_size})
    service = GeminiScriptService(settings)
    panels, file_paths = load_panels(chapter_dir)
    logs: list[dict[str, str | None]] = []

    def on_log(log_type: str, message: str, details: str | None = None) -> None:
        logs.append({"type": log_type, "message": message, "details": details})

    if not file_paths:
        return {
            "chapterDir": str(chapter_dir),
            "batchSize": batch_size,
            "panelCount": 0,
            "providerFailure": True,
            "failureType": "missing_images",
            "error": "No supported images found.",
            "logs": logs,
        }

    try:
        result = await service.generate_script(
            context=context,
            panels=panels,
            file_paths=file_paths,
            options=ScriptJobOptions(returnRawOutputs=True),
            on_log=on_log,
        )
        metrics = result.metrics.model_dump()
        return {
            "chapterDir": str(chapter_dir),
            "batchSize": batch_size,
            "panelCount": len(panels),
            "providerFailure": False,
            "failureType": None,
            "error": None,
            "totalMs": metrics["totalMs"],
            "avgPanelMs": metrics["avgPanelMs"],
            "totalTokens": metrics["totalTokens"],
            "promptTokens": metrics["totalPromptTokens"],
            "completionTokens": metrics["totalCandidatesTokens"],
            "retryCount": metrics["retryCount"],
            "429Count": metrics["rateLimitedCount"],
            "throttleWaitMs": metrics["throttleWaitMs"],
            "rawOutputs": result.rawOutputs.model_dump() if result.rawOutputs else None,
            "generatedItems": [item.model_dump() for item in result.generatedItems],
            "storyMemories": [item.model_dump() for item in result.storyMemories],
            "logs": logs,
        }
    except Exception as exc:
        error_message = str(exc)
        return {
            "chapterDir": str(chapter_dir),
            "batchSize": batch_size,
            "panelCount": len(panels),
            "providerFailure": True,
            "failureType": classify_failure(error_message),
            "error": error_message,
            "logs": logs,
        }


def choose_recommended_batch_size(runs: list[dict[str, Any]]) -> int | None:
    successful_runs = [run for run in runs if not run["providerFailure"]]
    if not successful_runs:
        return None

    medians: dict[int, float] = {}
    for batch_size in sorted({run["batchSize"] for run in successful_runs}):
        samples = [run["totalMs"] for run in successful_runs if run["batchSize"] == batch_size]
        if samples:
            medians[batch_size] = statistics.median(samples)

    if not medians:
        return None

    ordered = sorted(medians.items(), key=lambda item: item[1])
    best_batch, best_median = ordered[0]
    for batch_size, median_value in ordered[1:]:
        if best_median == 0:
            continue
        if ((median_value - best_median) / best_median) <= 0.05 and batch_size > best_batch:
            best_batch = batch_size
    return best_batch


async def main() -> None:
    args = parse_args()
    batch_sizes = [int(item.strip()) for item in args.batch_sizes.split(",") if item.strip()]
    chapter_dirs = [Path(item).resolve() for item in args.chapter_dirs]
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    context = ScriptContext(
        mangaName=args.manga_name,
        mainCharacter=args.main_character,
        summary=args.summary,
        language=args.language,
    )

    runs: list[dict[str, Any]] = []
    for chapter_dir in chapter_dirs:
        for batch_size in batch_sizes:
            print(f"Running benchmark | chapter={chapter_dir} batch_size={batch_size}")
            run = await run_single_benchmark(chapter_dir=chapter_dir, batch_size=batch_size, context=context)
            runs.append(run)

    recommended_batch_size = choose_recommended_batch_size(runs)
    summary = {
        "chapterDirs": [str(path) for path in chapter_dirs],
        "batchSizes": batch_sizes,
        "recommendedBatchSize": recommended_batch_size,
        "totalRuns": len(runs),
        "successfulRuns": sum(1 for run in runs if not run["providerFailure"]),
        "failedRuns": sum(1 for run in runs if run["providerFailure"]),
    }

    (output_dir / "result.json").write_text(json.dumps({"runs": runs}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
