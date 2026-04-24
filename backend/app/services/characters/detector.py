from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from PIL import Image

from app.core.config import Settings


DETECTOR_VERSION = "hybrid-detector-v3"
HEURISTIC_DETECTOR_VERSION = "heuristic-multi-crop-v1"

CropKind = Literal["face", "head", "upper_body", "person", "accessory", "heuristic"]


@dataclass(frozen=True)
class DetectedCrop:
    panel_id: str
    order_index: int
    bbox: tuple[int, int, int, int]
    detection_score: float
    kind: CropKind
    detector_source: str
    detector_model: str
    diagnostics: dict[str, float | int | str | bool]


class CharacterCropDetector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.version = DETECTOR_VERSION
        self.mode = settings.character_detector_mode
        self.device = self._resolve_device(settings.character_device)
        self.object_model_name = settings.character_object_model
        self._anime_detector = None
        self._anime_error = ""
        self._object_model = None
        self._object_error = ""

    def detect(self, *, panel_id: str, order_index: int, path: Path) -> list[DetectedCrop]:
        with Image.open(path) as image:
            rgb_image = image.convert("RGB")
            rgb = np.asarray(rgb_image, dtype=np.uint8)

        height, width = rgb.shape[:2]
        if height == 0 or width == 0:
            return []

        candidates: list[DetectedCrop] = []
        if self.mode in {"hybrid", "anime"}:
            candidates.extend(self._detect_anime_faces(panel_id=panel_id, order_index=order_index, rgb=rgb))
        if self.mode in {"hybrid", "object"}:
            candidates.extend(self._detect_objects(panel_id=panel_id, order_index=order_index, rgb=rgb))
        if self.mode in {"hybrid", "heuristic"} or not candidates:
            candidates.extend(self._detect_heuristic(panel_id=panel_id, order_index=order_index, rgb=rgb))

        ranked = sorted(candidates, key=self._rank_key, reverse=True)
        return self._non_max_suppression(ranked)[:8]

    def _detect_anime_faces(self, *, panel_id: str, order_index: int, rgb: np.ndarray) -> list[DetectedCrop]:
        detector = self._load_anime_detector()
        if detector is None:
            return []

        height, width = rgb.shape[:2]
        detections: list[DetectedCrop] = []
        try:
            raw_items = detector(rgb)
        except Exception as exc:  # pragma: no cover - optional dependency behavior
            self._anime_error = f"{type(exc).__name__}: {exc}"
            return []

        for index, item in enumerate(raw_items or [], start=1):
            bbox, score = self._parse_anime_bbox(item)
            if bbox is None:
                continue
            x, y, w, h = self._clamp_bbox(bbox, width=width, height=height)
            if w * h < width * height * 0.002:
                continue
            face_score = max(0.0, min(0.99, float(score)))
            detections.append(
                DetectedCrop(
                    panel_id=panel_id,
                    order_index=order_index,
                    bbox=(x, y, w, h),
                    detection_score=round(face_score, 4),
                    kind="face",
                    detector_source="anime-face-detector",
                    detector_model="anime-face-detector",
                    diagnostics={"provider": "anime-face-detector", "rank": index},
                )
            )
            head_bbox = self._expand_bbox((x, y, w, h), width=width, height=height, pad_x=0.75, pad_top=0.95, pad_bottom=0.65)
            detections.append(
                DetectedCrop(
                    panel_id=panel_id,
                    order_index=order_index,
                    bbox=head_bbox,
                    detection_score=round(min(0.97, face_score * 0.94), 4),
                    kind="head",
                    detector_source="anime-face-detector",
                    detector_model="anime-face-detector",
                    diagnostics={"provider": "anime-face-detector", "derivedFrom": "face", "rank": index},
                )
            )
        return detections

    def _detect_objects(self, *, panel_id: str, order_index: int, rgb: np.ndarray) -> list[DetectedCrop]:
        model = self._load_object_model()
        if model is None:
            return []

        height, width = rgb.shape[:2]
        detections: list[DetectedCrop] = []
        try:
            results = model.predict(rgb, device=self.device, verbose=False)
        except Exception as exc:  # pragma: no cover - optional dependency behavior
            self._object_error = f"{type(exc).__name__}: {exc}"
            return []

        accessory_names = {"backpack", "handbag", "umbrella", "tie", "suitcase", "sports ball", "skateboard"}
        for result in results:
            names = getattr(result, "names", {}) or {}
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for index, box in enumerate(boxes, start=1):
                try:
                    cls_id = int(box.cls[0].item())
                    score = float(box.conf[0].item())
                    x1, y1, x2, y2 = [int(round(value)) for value in box.xyxy[0].tolist()]
                except Exception:
                    continue
                label = str(names.get(cls_id, cls_id)).lower()
                bbox = self._clamp_bbox((x1, y1, x2 - x1, y2 - y1), width=width, height=height)
                if bbox[2] * bbox[3] < width * height * 0.006:
                    continue

                if label == "person":
                    detections.append(
                        DetectedCrop(
                            panel_id=panel_id,
                            order_index=order_index,
                            bbox=bbox,
                            detection_score=round(min(0.96, score), 4),
                            kind="person",
                            detector_source="ultralytics-yolo",
                            detector_model=self.object_model_name,
                            diagnostics={"label": label, "rank": index},
                        )
                    )
                    ux, uy, uw, uh = bbox
                    upper = self._clamp_bbox((ux, uy, uw, max(1, int(uh * 0.62))), width=width, height=height)
                    detections.append(
                        DetectedCrop(
                            panel_id=panel_id,
                            order_index=order_index,
                            bbox=upper,
                            detection_score=round(min(0.94, score * 0.92), 4),
                            kind="upper_body",
                            detector_source="ultralytics-yolo",
                            detector_model=self.object_model_name,
                            diagnostics={"label": label, "derivedFrom": "person", "rank": index},
                        )
                    )
                elif label in accessory_names:
                    detections.append(
                        DetectedCrop(
                            panel_id=panel_id,
                            order_index=order_index,
                            bbox=bbox,
                            detection_score=round(min(0.90, score), 4),
                            kind="accessory",
                            detector_source="ultralytics-yolo",
                            detector_model=self.object_model_name,
                            diagnostics={"label": label, "identityEligible": False, "rank": index},
                        )
                    )
        return detections

    def _detect_heuristic(self, *, panel_id: str, order_index: int, rgb: np.ndarray) -> list[DetectedCrop]:
        height, width = rgb.shape[:2]
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        saturation = hsv[:, :, 1].astype(np.float32) / 255.0
        darkness = 1.0 - (gray.astype(np.float32) / 255.0)
        edges = cv2.Canny(gray, 70, 170).astype(np.float32) / 255.0
        local_contrast = cv2.GaussianBlur(np.abs(cv2.Laplacian(gray, cv2.CV_32F)), (0, 0), 1.2)
        if float(local_contrast.max()) > 1e-6:
            local_contrast = local_contrast / float(local_contrast.max())

        interest_map = darkness * 0.34 + edges * 0.32 + local_contrast * 0.22 + saturation * 0.12
        interest_map = cv2.GaussianBlur(interest_map.astype(np.float32), (0, 0), 3.2)
        threshold = max(
            float(np.quantile(interest_map, 0.83)),
            float(np.mean(interest_map) + (np.std(interest_map) * 0.7)),
            0.24,
        )
        binary = (interest_map >= threshold).astype(np.uint8) * 255
        kernel = np.ones((5, 5), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
        binary = cv2.dilate(binary, kernel, iterations=1)

        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        raw_candidates: list[DetectedCrop] = []
        min_area = width * height * 0.015
        max_area = width * height * 0.82
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            if area < min_area or area > max_area:
                continue
            aspect_ratio = w / max(1.0, float(h))
            if aspect_ratio < 0.22 or aspect_ratio > 1.8:
                continue
            expanded = self._expand_bbox((x, y, w, h), width=width, height=height, pad_x=0.22, pad_top=0.18, pad_bottom=0.12)
            ex, ey, ew, eh = expanded
            region_interest = float(np.mean(interest_map[ey : ey + eh, ex : ex + ew]))
            region_edges = float(np.mean(edges[ey : ey + eh, ex : ex + ew]))
            region_darkness = float(np.mean(darkness[ey : ey + eh, ex : ex + ew]))
            center_bonus = self._center_bonus(expanded, width=width, height=height)
            score = min(0.86, (region_interest * 0.42) + (region_edges * 0.18) + (region_darkness * 0.20) + center_bonus)
            raw_candidates.append(
                DetectedCrop(
                    panel_id=panel_id,
                    order_index=order_index,
                    bbox=expanded,
                    detection_score=round(score, 4),
                    kind="heuristic",
                    detector_source="opencv-heuristic",
                    detector_model=HEURISTIC_DETECTOR_VERSION,
                    diagnostics={
                        "region_interest": round(region_interest, 4),
                        "region_edges": round(region_edges, 4),
                        "region_darkness": round(region_darkness, 4),
                        "area_ratio": round(area / float(width * height), 4),
                        "aspect_ratio": round(aspect_ratio, 4),
                    },
                )
            )

        deduped = self._non_max_suppression(sorted(raw_candidates, key=lambda item: item.detection_score, reverse=True))
        if deduped:
            return deduped[:4]
        return self._fallback_candidates(
            panel_id=panel_id,
            order_index=order_index,
            width=width,
            height=height,
            interest_map=interest_map,
            edges=edges,
            darkness=darkness,
        )[:4]

    def _fallback_candidates(
        self,
        *,
        panel_id: str,
        order_index: int,
        width: int,
        height: int,
        interest_map: np.ndarray,
        edges: np.ndarray,
        darkness: np.ndarray,
    ) -> list[DetectedCrop]:
        max_interest = float(interest_map.max())
        if max_interest < 0.22:
            return []
        fallback_candidates: list[DetectedCrop] = []
        flat_indices = np.argpartition(interest_map.flatten(), -3)[-3:]
        for flat_index in flat_indices:
            py, px = divmod(int(flat_index), width)
            crop_w = max(int(width * 0.46), 72)
            crop_h = max(int(height * 0.62), 96)
            x = max(0, min(width - crop_w, px - (crop_w // 2)))
            y = max(0, min(height - crop_h, py - int(crop_h * 0.35)))
            bbox = (x, y, crop_w, crop_h)
            region_interest = float(np.mean(interest_map[y : y + crop_h, x : x + crop_w]))
            region_edges = float(np.mean(edges[y : y + crop_h, x : x + crop_w]))
            region_darkness = float(np.mean(darkness[y : y + crop_h, x : x + crop_w]))
            score = min(0.80, (region_interest * 0.44) + (region_edges * 0.18) + (region_darkness * 0.16) + 0.08)
            fallback_candidates.append(
                DetectedCrop(
                    panel_id=panel_id,
                    order_index=order_index,
                    bbox=bbox,
                    detection_score=round(score, 4),
                    kind="heuristic",
                    detector_source="opencv-heuristic",
                    detector_model=HEURISTIC_DETECTOR_VERSION,
                    diagnostics={
                        "fallback": True,
                        "region_interest": round(region_interest, 4),
                        "region_edges": round(region_edges, 4),
                        "region_darkness": round(region_darkness, 4),
                    },
                )
            )
        return sorted(fallback_candidates, key=lambda item: item.detection_score, reverse=True)

    def _load_anime_detector(self):
        if self._anime_detector is not None:
            return self._anime_detector
        try:
            from anime_face_detector import create_detector  # type: ignore

            self._anime_detector = create_detector("yolov3")
        except Exception as exc:  # pragma: no cover - optional dependency behavior
            self._anime_error = f"{type(exc).__name__}: {exc}"
            self._anime_detector = None
        return self._anime_detector

    def _load_object_model(self):
        if self._object_model is not None:
            return self._object_model
        try:
            from ultralytics import YOLO  # type: ignore

            self._object_model = YOLO(self.object_model_name)
        except Exception as exc:  # pragma: no cover - optional dependency behavior
            self._object_error = f"{type(exc).__name__}: {exc}"
            self._object_model = None
        return self._object_model

    def _parse_anime_bbox(self, item) -> tuple[tuple[int, int, int, int] | None, float]:
        if isinstance(item, dict):
            bbox = item.get("bbox") or item.get("box")
            score = float(item.get("score") or item.get("confidence") or 0.95)
        else:
            bbox = getattr(item, "bbox", None) or getattr(item, "box", None)
            score = float(getattr(item, "score", 0.95))
        if bbox is None or len(bbox) < 4:
            return None, score
        values = [int(round(float(value))) for value in bbox[:4]]
        x1, y1, third, fourth = values
        if third > x1 and fourth > y1:
            return (x1, y1, third - x1, fourth - y1), score
        return (x1, y1, max(1, third), max(1, fourth)), score

    def _rank_key(self, candidate: DetectedCrop) -> tuple[float, float]:
        kind_priority = {
            "face": 0.28,
            "head": 0.24,
            "upper_body": 0.12,
            "person": 0.08,
            "heuristic": 0.02,
            "accessory": -0.18,
        }
        return candidate.detection_score + kind_priority.get(candidate.kind, 0.0), candidate.detection_score

    def _expand_bbox(
        self,
        bbox: tuple[int, int, int, int],
        *,
        width: int,
        height: int,
        pad_x: float,
        pad_top: float,
        pad_bottom: float,
    ) -> tuple[int, int, int, int]:
        x, y, w, h = bbox
        nx = max(0, x - int(w * pad_x))
        ny = max(0, y - int(h * pad_top))
        nr = min(width, x + w + int(w * pad_x))
        nb = min(height, y + h + int(h * pad_bottom))
        return (nx, ny, max(1, nr - nx), max(1, nb - ny))

    def _clamp_bbox(self, bbox: tuple[int, int, int, int], *, width: int, height: int) -> tuple[int, int, int, int]:
        x, y, w, h = bbox
        nx = max(0, min(width - 1, x))
        ny = max(0, min(height - 1, y))
        nr = max(nx + 1, min(width, x + max(1, w)))
        nb = max(ny + 1, min(height, y + max(1, h)))
        return (nx, ny, nr - nx, nb - ny)

    def _center_bonus(self, bbox: tuple[int, int, int, int], *, width: int, height: int) -> float:
        x, y, w, h = bbox
        cx = (x + (w / 2)) / max(1.0, float(width))
        cy = (y + (h / 2)) / max(1.0, float(height))
        distance = abs(cx - 0.5) + abs(cy - 0.52)
        return max(0.04, 0.22 - (distance * 0.18))

    def _non_max_suppression(self, candidates: list[DetectedCrop]) -> list[DetectedCrop]:
        kept: list[DetectedCrop] = []
        for candidate in candidates:
            threshold = 0.54 if candidate.kind in {"face", "head"} else 0.48
            if any(self._iou(candidate.bbox, existing.bbox) >= threshold for existing in kept):
                continue
            kept.append(candidate)
        return kept

    def _iou(self, left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> float:
        lx, ly, lw, lh = left
        rx, ry, rw, rh = right
        li_x = max(lx, rx)
        li_y = max(ly, ry)
        ri_x = min(lx + lw, rx + rw)
        ri_y = min(ly + lh, ry + rh)
        if ri_x <= li_x or ri_y <= li_y:
            return 0.0
        intersection = float((ri_x - li_x) * (ri_y - li_y))
        union = float((lw * lh) + (rw * rh)) - intersection
        return 0.0 if union <= 1e-6 else intersection / union

    def _resolve_device(self, requested: str) -> str:
        if requested == "cpu":
            return "cpu"
        if requested == "gpu":
            return "0"
        try:
            import torch

            return "0" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"
