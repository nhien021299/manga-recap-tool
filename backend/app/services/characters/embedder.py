from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


EMBEDDER_VERSION = "crop-embedding-v1"


@dataclass(frozen=True)
class CharacterCropEmbedding:
    cache_key: str
    vector: np.ndarray
    diagnostics: dict[str, object]


class CharacterCropEmbedder:
    def __init__(self, cache_root: Path) -> None:
        self.cache_root = cache_root
        self.version = EMBEDDER_VERSION

    def embed(
        self,
        *,
        chapter_id: str,
        crop_id: str,
        crop_kind: str,
        crop_image: Image.Image,
        cache_hint: str,
    ) -> CharacterCropEmbedding:
        cache_key = self._build_cache_key(
            chapter_id=chapter_id,
            crop_id=crop_id,
            crop_kind=crop_kind,
            cache_hint=cache_hint,
            crop_image=crop_image,
        )
        cache_dir = self.cache_root / hashlib.sha1(chapter_id.encode("utf-8")).hexdigest()[:12] / "embeddings"
        vector_path = cache_dir / f"{cache_key}.npy"
        meta_path = cache_dir / f"{cache_key}.json"
        if vector_path.exists() and meta_path.exists():
            vector = np.load(vector_path)
            diagnostics = json.loads(meta_path.read_text(encoding="utf-8"))
            return CharacterCropEmbedding(cache_key=cache_key, vector=vector, diagnostics=diagnostics)

        vector, diagnostics = self._build_embedding(crop_image, crop_kind=crop_kind)
        cache_dir.mkdir(parents=True, exist_ok=True)
        np.save(vector_path, vector)
        meta_path.write_text(json.dumps(diagnostics), encoding="utf-8")
        return CharacterCropEmbedding(cache_key=cache_key, vector=vector, diagnostics=diagnostics)

    def _build_cache_key(self, *, chapter_id: str, crop_id: str, crop_kind: str, cache_hint: str, crop_image: Image.Image) -> str:
        buffer = BytesIO()
        crop_image.save(buffer, format="PNG")
        digest = hashlib.sha1()
        digest.update(self.version.encode("utf-8"))
        digest.update(chapter_id.encode("utf-8"))
        digest.update(crop_id.encode("utf-8"))
        digest.update(crop_kind.encode("utf-8"))
        digest.update(cache_hint.encode("utf-8"))
        digest.update(buffer.getvalue())
        return digest.hexdigest()

    def _build_embedding(self, crop_image: Image.Image, *, crop_kind: str) -> tuple[np.ndarray, dict[str, object]]:
        rgb = np.asarray(crop_image.convert("RGB").resize((96, 128)), dtype=np.uint8)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)

        global_hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 4, 4], [0, 180, 0, 256, 0, 256]).flatten()
        global_hist = global_hist / max(1.0, float(global_hist.sum()))

        region_features: list[np.ndarray] = []
        for region in self._regions(gray):
            hist, _ = np.histogram(region, bins=16, range=(0, 255), density=True)
            region_features.append(hist.astype(np.float32))

        small = cv2.resize(gray, (32, 32)).astype(np.float32) / 255.0
        dct = cv2.dct(small)
        dct_features = dct[:6, :6].flatten()

        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        magnitude, angle = cv2.cartToPolar(gx, gy, angleInDegrees=True)
        orientation_histograms: list[np.ndarray] = []
        for region in self._regions(angle, secondary=magnitude):
            if isinstance(region, tuple):
                angle_region, magnitude_region = region
                hist, _ = np.histogram(angle_region, bins=8, range=(0, 360), weights=magnitude_region)
                orientation_histograms.append(hist.astype(np.float32))

        silhouette = (gray < np.percentile(gray, 46)).astype(np.float32)
        row_profile = silhouette.mean(axis=1)
        col_profile = silhouette.mean(axis=0)
        profile_features = np.concatenate(
            [
                self._bin_profile(row_profile, bins=8),
                self._bin_profile(col_profile, bins=8),
            ]
        )
        hu_moments = self._hu_moments(silhouette)
        geometry = np.asarray(
            [
                float(silhouette.mean()),
                float(np.max(np.sum(silhouette, axis=0)) / max(1.0, silhouette.shape[0])),
                float(np.max(np.sum(silhouette, axis=1)) / max(1.0, silhouette.shape[1])),
            ],
            dtype=np.float32,
        )
        silhouette_signature = cv2.resize(silhouette, (12, 16), interpolation=cv2.INTER_AREA).flatten()

        phash_features = self._perceptual_hash_features(gray)
        kind_features = self._kind_features(crop_kind)
        weights = self._kind_weights(crop_kind)

        feature_vector = np.concatenate(
            [
                self._normalize(global_hist.astype(np.float32)) * weights["color"],
                *(self._normalize(feature.astype(np.float32)) * weights["regions"] for feature in region_features),
                self._normalize(dct_features.astype(np.float32)) * weights["dct"],
                *(self._normalize(feature.astype(np.float32)) * weights["edges"] for feature in orientation_histograms),
                self._normalize(profile_features.astype(np.float32)) * weights["profile"],
                self._normalize(hu_moments.astype(np.float32)) * weights["moments"],
                self._normalize(geometry.astype(np.float32)) * weights["geometry"],
                self._normalize(silhouette_signature.astype(np.float32)) * weights["silhouette"],
                self._normalize(phash_features.astype(np.float32)) * weights["phash"],
                kind_features,
            ]
        )
        normalized_vector = self._normalize(feature_vector.astype(np.float32))
        diagnostics = {
            "version": self.version,
            "dimension": int(normalized_vector.shape[0]),
            "cropKind": crop_kind,
            "weights": weights,
        }
        return normalized_vector, diagnostics

    def _kind_features(self, crop_kind: str) -> np.ndarray:
        ordered = ["face", "head", "heuristic", "upper_body", "person", "accessory"]
        values = np.zeros((len(ordered),), dtype=np.float32)
        if crop_kind in ordered:
            values[ordered.index(crop_kind)] = 1.0
        return values * 0.18

    def _kind_weights(self, crop_kind: str) -> dict[str, float]:
        if crop_kind in {"face", "head"}:
            return {
                "color": 0.42,
                "regions": 0.42,
                "dct": 0.45,
                "edges": 0.65,
                "profile": 2.2,
                "moments": 2.7,
                "geometry": 2.4,
                "silhouette": 2.9,
                "phash": 0.28,
            }
        if crop_kind in {"person", "upper_body"}:
            return {
                "color": 0.8,
                "regions": 0.6,
                "dct": 0.28,
                "edges": 0.48,
                "profile": 1.25,
                "moments": 1.25,
                "geometry": 1.3,
                "silhouette": 1.55,
                "phash": 0.22,
            }
        if crop_kind == "accessory":
            return {
                "color": 0.55,
                "regions": 0.25,
                "dct": 0.18,
                "edges": 0.22,
                "profile": 0.45,
                "moments": 0.45,
                "geometry": 0.45,
                "silhouette": 0.55,
                "phash": 0.18,
            }
        return {
            "color": 0.55,
            "regions": 0.45,
            "dct": 0.35,
            "edges": 0.55,
            "profile": 1.85,
            "moments": 2.4,
            "geometry": 2.1,
            "silhouette": 2.6,
            "phash": 0.35,
        }

    def _regions(self, array: np.ndarray, secondary: np.ndarray | None = None):
        height, width = array.shape[:2]
        half_h = height // 2
        half_w = width // 2
        slices = [
            (slice(0, half_h), slice(0, half_w)),
            (slice(0, half_h), slice(half_w, width)),
            (slice(half_h, height), slice(0, half_w)),
            (slice(half_h, height), slice(half_w, width)),
        ]
        if secondary is None:
            return [array[ys, xs] for ys, xs in slices]
        return [(array[ys, xs], secondary[ys, xs]) for ys, xs in slices]

    def _bin_profile(self, values: np.ndarray, *, bins: int) -> np.ndarray:
        chunks = np.array_split(values, bins)
        return np.asarray([float(chunk.mean()) if chunk.size else 0.0 for chunk in chunks], dtype=np.float32)

    def _perceptual_hash_features(self, gray: np.ndarray) -> np.ndarray:
        resized = cv2.resize(gray, (32, 32)).astype(np.float32)
        dct = cv2.dct(resized)
        low_freq = dct[:8, :8]
        threshold = float(np.median(low_freq[1:, 1:]))
        bits = (low_freq.flatten() > threshold).astype(np.float32)
        return (bits * 2.0) - 1.0

    def _hu_moments(self, silhouette: np.ndarray) -> np.ndarray:
        moments = cv2.moments((silhouette * 255).astype(np.uint8))
        hu = cv2.HuMoments(moments).flatten()
        normalized: list[float] = []
        for value in hu[:4]:
            if abs(float(value)) < 1e-12:
                normalized.append(0.0)
            else:
                normalized.append(float(np.sign(value) * np.log10(abs(value))))
        return np.asarray(normalized, dtype=np.float32)

    def _normalize(self, vector: np.ndarray) -> np.ndarray:
        norm = float(np.linalg.norm(vector))
        if norm <= 1e-6:
            return vector
        return vector / norm
