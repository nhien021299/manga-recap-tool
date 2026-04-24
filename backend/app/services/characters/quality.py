from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


QUALITY_VERSION = "crop-quality-v1"


@dataclass(frozen=True)
class CharacterCropQuality:
    score: float
    bucket: str
    diagnostics: dict[str, float | int]


class CharacterCropQualityScorer:
    def __init__(self) -> None:
        self.version = QUALITY_VERSION

    def score(
        self,
        *,
        panel_rgb: np.ndarray,
        bbox: tuple[int, int, int, int],
        detection_score: float,
    ) -> CharacterCropQuality:
        x, y, w, h = bbox
        crop = panel_rgb[y : y + h, x : x + w]
        panel_height, panel_width = panel_rgb.shape[:2]
        crop_gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        crop_hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)

        blur_variance = float(cv2.Laplacian(crop_gray, cv2.CV_32F).var())
        contrast = float(crop_gray.std())
        area_ratio = float((w * h) / max(1.0, float(panel_width * panel_height)))
        saturation = float(crop_hsv[:, :, 1].mean() / 255.0)
        darkness = float(np.mean(1.0 - (crop_gray.astype(np.float32) / 255.0)))
        edge_density = float(np.mean(cv2.Canny(crop_gray, 70, 170) > 0))

        border_touch_px = int(x <= 2) + int(y <= 2) + int((x + w) >= panel_width - 2) + int((y + h) >= panel_height - 2)
        border_penalty = min(0.25, border_touch_px * 0.07)

        normalized_blur = min(1.0, blur_variance / 600.0)
        normalized_contrast = min(1.0, contrast / 68.0)
        normalized_area = min(1.0, area_ratio / 0.18)
        occupancy = min(1.0, (darkness * 0.55) + (edge_density * 1.45) + (saturation * 0.25))

        score = (
            min(1.0, detection_score) * 0.18
            + normalized_blur * 0.20
            + normalized_contrast * 0.17
            + normalized_area * 0.23
            + occupancy * 0.22
        ) - border_penalty
        score = max(0.0, min(0.99, score))

        if score >= 0.66 and area_ratio >= 0.035 and border_touch_px <= 2:
            bucket = "good"
        elif score >= 0.44 and area_ratio >= 0.018:
            bucket = "medium"
        else:
            bucket = "poor"

        return CharacterCropQuality(
            score=round(score, 4),
            bucket=bucket,
            diagnostics={
                "blurVariance": round(blur_variance, 4),
                "contrast": round(contrast, 4),
                "areaRatio": round(area_ratio, 4),
                "saturation": round(saturation, 4),
                "darkness": round(darkness, 4),
                "edgeDensity": round(edge_density, 4),
                "borderTouchPx": border_touch_px,
                "borderPenalty": round(border_penalty, 4),
                "occupancy": round(occupancy, 4),
            },
        )
