from __future__ import annotations

import hashlib
import json
from time import perf_counter

from app.models.api import ScriptJobResult
from app.models.domain import Metrics, RawOutputs
from app.models.jobs import JobRecord


class ScriptPipeline:
    def __init__(self, provider_registry, caption_service, llm_service) -> None:
        self.provider_registry = provider_registry
        self.caption_service = caption_service
        self.llm_service = llm_service
        self.understanding_cache: dict[str, tuple[list, str, str]] = {}

    async def run_job(self, job: JobRecord) -> ScriptJobResult:
        job.add_log("request", "Starting backend script pipeline")
        started_at = perf_counter()

        def check_cancel() -> None:
            if job.cancel_requested:
                raise RuntimeError("Job cancelled by user.")

        provider_profile = self.provider_registry.get_provider_info()
        panel_signature = self._build_panel_signature(job, provider_profile)
        understandings = None
        understanding_raw_output = ""
        caption_run = None

        if job.request.options.reuseCache and panel_signature in self.understanding_cache:
            understandings, understanding_raw_output, cached_caption_source = self.understanding_cache[panel_signature]
            job.add_log("result", f"Reusing structured scene cache for {len(understandings)} panels")
            caption_ms = 0
            ocr_ms = 0
            merge_ms = 0
            avg_panel_ms = 0.0
            caption_source = cached_caption_source
        else:
            caption_run = await self.caption_service.generate_understandings(
                context=job.request.context,
                panels=job.request.panels,
                file_paths=job.file_paths,
                on_log=job.add_log,
                check_cancel=check_cancel,
            )
            understandings = caption_run.understandings
            understanding_raw_output = caption_run.raw_output
            caption_ms = caption_run.caption_ms
            ocr_ms = caption_run.ocr_ms
            merge_ms = caption_run.merge_ms
            avg_panel_ms = caption_run.avg_panel_ms
            caption_source = caption_run.caption_source
            self.understanding_cache[panel_signature] = (understandings, understanding_raw_output, caption_source)

        if caption_run is None:
            job.add_log(
                "result",
                "Structured caption cache reused",
                json.dumps(
                    {
                        "captionSource": caption_source,
                        "ocrMs": ocr_ms,
                        "mergeMs": merge_ms,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        else:
            job.add_log(
                "result",
                "Caption stage metrics",
                json.dumps(
                    {
                        "captionSource": caption_source,
                        "ocrMs": ocr_ms,
                        "mergeMs": merge_ms,
                        "avgPanelMs": avg_panel_ms,
                        "ocrHasText": any(item.diagnostics.ocr_has_text for item in caption_run.panel_artifacts),
                        "ocrLineCount": sum(item.diagnostics.ocr_line_count for item in caption_run.panel_artifacts),
                        "mergeCorrectionTags": sorted(
                            {
                                tag
                                for item in caption_run.panel_artifacts
                                for tag in item.diagnostics.correction_tags
                            }
                        ),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

        generated_items, story_memories, script_raw_output, script_ms = await self.llm_service.generate_script(
            context=job.request.context,
            understandings=understandings,
            on_log=job.add_log,
            check_cancel=check_cancel,
        )

        total_ms = int((perf_counter() - started_at) * 1000)
        raw_outputs = None
        if job.request.options.returnRawOutputs:
            raw_outputs = RawOutputs(understanding=understanding_raw_output, script=script_raw_output)
        return ScriptJobResult(
            understandings=understandings,
            generatedItems=generated_items,
            storyMemories=story_memories,
            panelSignature=panel_signature,
            rawOutputs=raw_outputs,
            metrics=Metrics(
                panelCount=len(job.request.panels),
                totalMs=total_ms,
                captionMs=caption_ms,
                ocrMs=ocr_ms,
                mergeMs=merge_ms,
                scriptMs=script_ms,
                avgPanelMs=avg_panel_ms,
                captionSource=caption_source,
            ),
        )

    def _build_panel_signature(self, job: JobRecord, provider_profile: dict[str, object]) -> str:
        payload = {
            "context": job.request.context.model_dump(),
            "panels": [panel.model_dump() for panel in job.request.panels],
            "providers": provider_profile,
            "files": [{"name": path.name, "size": path.stat().st_size} for path in job.file_paths],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
