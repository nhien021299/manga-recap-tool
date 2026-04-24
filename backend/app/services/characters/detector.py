from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from PIL import Image

from app.core.config import Settings


DETECTOR_VERSION = "hybrid-detector-v4"
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
        self.anime_face_model_path = getattr(settings, "character_anime_face_model_path", "")
        self._anime_detector = None
        self._anime_error = ""
        self._anime_loaded = False
        self._anime_provider = ""  # "onnx" or "anime-face-detector"
        self._object_model = None
        self._object_error = ""
        self._total_face_count = 0
        self._total_head_count = 0
        self._total_heuristic_count = 0
        self._total_object_count = 0

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

        if self._anime_provider == "onnx":
            raw_items = self._run_onnx_anime_detection(detector, rgb)
        else:
            try:
                raw_items = detector(rgb)
            except Exception as exc:  # pragma: no cover
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
            self._total_face_count += 1
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
            self._total_head_count += 1
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
            self._total_heuristic_count += len(deduped[:4])
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

    def warmup_test(self) -> dict[str, object]:
        """Run a quick warmup/test to verify anime face detection is operational.
        Returns diagnostics dict with provider status, device, and any errors.
        """
        result: dict[str, object] = {
            "mode": self.mode,
            "device": self.device,
            "animeProviderLoaded": False,
            "animeProviderError": "",
            "objectProviderLoaded": False,
            "objectProviderError": "",
            "warmupFaceDetected": False,
            "warmupHeadDetected": False,
            "fallbackReason": "",
        }
        if self.mode in {"hybrid", "anime"}:
            detector = self._load_anime_detector()
            if detector is not None:
                result["animeProviderLoaded"] = True
                try:
                    import numpy as _np
                    test_image = _np.full((64, 64, 3), 200, dtype=_np.uint8)
                    test_image[16:48, 20:44] = 60
                    test_items = detector(test_image)
                    if test_items:
                        result["warmupFaceDetected"] = True
                        result["warmupHeadDetected"] = True
                except Exception:
                    pass
            else:
                result["animeProviderError"] = self._anime_error
                result["fallbackReason"] = f"Anime face detector unavailable: {self._anime_error}"

        if self.mode in {"hybrid", "object"}:
            model = self._load_object_model()
            if model is not None:
                result["objectProviderLoaded"] = True
            else:
                result["objectProviderError"] = self._object_error

        if not result["animeProviderLoaded"] and not result["objectProviderLoaded"]:
            result["fallbackReason"] = "No AI detector available, falling back to OpenCV heuristic only."

        return result

    def runtime_diagnostics(self) -> dict[str, object]:
        """Return runtime diagnostics for the detector."""
        return {
            "version": self.version,
            "mode": self.mode,
            "device": self.device,
            "animeProviderLoaded": self._anime_loaded,
            "animeProvider": self._anime_provider,
            "animeProviderError": self._anime_error,
            "animeFaceModelPath": self.anime_face_model_path,
            "objectProviderLoaded": self._object_model is not None,
            "objectProviderError": self._object_error,
            "totalFaceCount": self._total_face_count,
            "totalHeadCount": self._total_head_count,
            "totalHeuristicCount": self._total_heuristic_count,
            "totalObjectCount": self._total_object_count,
        }

    def _load_anime_detector(self):
        if self._anime_detector is not None:
            return self._anime_detector
        # Try ONNX model first (lightweight, no heavy dependencies)
        onnx_path = Path(self.anime_face_model_path) if self.anime_face_model_path else None
        if onnx_path and onnx_path.exists() and onnx_path.suffix == ".onnx":
            try:
                import onnxruntime as ort
                session = ort.InferenceSession(
                    str(onnx_path),
                    providers=["CPUExecutionProvider"],
                )
                self._anime_detector = session
                self._anime_provider = "onnx"
                self._anime_loaded = True
                return self._anime_detector
            except Exception as exc:
                self._anime_error = f"ONNX load failed: {type(exc).__name__}: {exc}"
        # Fallback to anime_face_detector package
        try:
            from anime_face_detector import create_detector  # type: ignore

            self._anime_detector = create_detector("yolov3")
            self._anime_provider = "anime-face-detector"
            self._anime_loaded = True
        except Exception as exc:  # pragma: no cover - optional dependency behavior
            self._anime_error = f"{type(exc).__name__}: {exc}"
            self._anime_detector = None
            self._anime_loaded = False
        return self._anime_detector

    def _run_onnx_anime_detection(self, session, rgb: np.ndarray) -> list[dict]:
        """Run anime face detection using ONNX model from deepghs/anime_face_detection."""
        height, width = rgb.shape[:2]
        target_size = 640
        scale = target_size / max(height, width)
        new_w = int(width * scale)
        new_h = int(height * scale)
        resized = cv2.resize(rgb, (new_w, new_h))

        # Pad to target_size x target_size
        padded = np.full((target_size, target_size, 3), 114, dtype=np.uint8)
        padded[:new_h, :new_w] = resized

        # Preprocess: HWC -> CHW, normalize to [0,1], add batch dim
        blob = padded.astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))
        blob = np.expand_dims(blob, axis=0)

        input_name = session.get_inputs()[0].name
        output_names = [out.name for out in session.get_outputs()]
        try:
            outputs = session.run(output_names, {input_name: blob})
        except Exception as exc:
            self._anime_error = f"ONNX inference failed: {type(exc).__name__}: {exc}"
            return []

        results: list[dict] = []
        # Parse YOLO-style output
        if len(outputs) >= 1:
            predictions = outputs[0]  # shape: (1, N, 5+) or (1, 5+, N)
            if predictions.ndim == 3:
                pred = predictions[0]
                # Check if we need to transpose (some YOLO models output (5+C, N) instead of (N, 5+C))
                if pred.shape[0] < pred.shape[1] and pred.shape[0] <= 10:
                    pred = pred.T
                for detection in pred:
                    if len(detection) < 5:
                        continue
                    # Format: cx, cy, w, h, score (or x1, y1, x2, y2, score)
                    score = float(detection[4])
                    if score < 0.35:
                        continue
                    cx, cy, bw, bh = detection[:4]
                    # Check if coordinates are in center format or corner format
                    if bw > 2.0 and bh > 2.0:  # Likely pixel coordinates
                        if cx < bw and cy < bh:  # Corner format (x1,y1,x2,y2)
                            x1, y1, x2, y2 = cx, cy, bw, bh
                        else:  # Center format
                            x1 = cx - bw / 2
                            y1 = cy - bh / 2
                            x2 = cx + bw / 2
                            y2 = cy + bh / 2
                    else:  # Normalized coordinates
                        x1 = (cx - bw / 2) * target_size
                        y1 = (cy - bh / 2) * target_size
                        x2 = (cx + bw / 2) * target_size
                        y2 = (cy + bh / 2) * target_size
                    # Scale back to original image coordinates
                    x1 = int(x1 / scale)
                    y1 = int(y1 / scale)
                    x2 = int(x2 / scale)
                    y2 = int(y2 / scale)
                    fw = x2 - x1
                    fh = y2 - y1
                    if fw > 5 and fh > 5:
                        results.append({"bbox": (x1, y1, fw, fh), "score": score})
        return results

    def _load_object_model(self):
        if self._object_model is not None:
            return self._object_model
        model_path = Path(self.object_model_name)
        if model_path.suffix == ".pt" and not model_path.exists():
            self._object_error = f"Object model not found locally: {self.object_model_name}"
            self._object_model = None
            return None
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
