from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from app.services.characters.directml_runtime import create_onnx_session, session_diagnostics

EMBEDDER_VERSION = "crop-embedding-v3"


@dataclass(frozen=True)
class CharacterCropEmbedding:
    cache_key: str
    vector: np.ndarray
    diagnostics: dict[str, object]


class CharacterCropEmbedder:
    def __init__(
        self,
        cache_root: Path,
        *,
        embedder: str = "handcrafted",
        dino_model_path: str = "",
        arcface_model_path: str = "",
        embed_device: str = "auto",
    ) -> None:
        self.cache_root = cache_root
        self.version = EMBEDDER_VERSION
        self._embedder_mode = str(embedder or "handcrafted").strip().lower()
        self._dino_model_path = dino_model_path
        self._arcface_model_path = arcface_model_path
        self._embed_device = embed_device
        self._dino_model = None
        self._dino_transform = None
        self._dino_error = ""
        self._dino_loaded = False
        self._arcface_session = None
        self._arcface_error = ""
        self._arcface_runtime: dict[str, object] = {}
        self._dino_model_hash = self._compute_model_hash(dino_model_path) if dino_model_path else ""
        self._arcface_model_hash = self._compute_model_hash(arcface_model_path) if arcface_model_path else ""
        self._resolved_device = self._resolve_device(embed_device)
        self._embedder_provider = self._resolve_provider()

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
        digest.update(self._embedder_provider.encode("utf-8"))
        digest.update(self._dino_model_hash.encode("utf-8"))
        digest.update(self._arcface_model_hash.encode("utf-8"))
        digest.update(self._resolved_device.encode("utf-8"))
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

        arcface_vector = self._compute_arcface_embedding(crop_image)
        if arcface_vector is not None:
            combined = np.concatenate(
                [
                    arcface_vector * 4.0,
                    normalized_vector * 0.20,
                ]
            )
            final_vector = self._normalize(combined.astype(np.float32))
            diagnostics = {
                "version": self.version,
                "provider": self._embedder_provider,
                "dimension": int(final_vector.shape[0]),
                "cropKind": crop_kind,
                "weights": weights,
                "arcfaceDimension": int(arcface_vector.shape[0]),
                "handcraftedDimension": int(normalized_vector.shape[0]),
                "arcfaceModelPath": self._arcface_model_path,
                "arcfaceModelHash": self._arcface_model_hash[:12],
                "device": self._resolved_device,
                "runtime": self._arcface_runtime,
            }
            return final_vector, diagnostics

        # Legacy fallback: DINOv2 is only allowed when explicitly configured and not CPU-bound.
        dino_vector = self._compute_dino_embedding(crop_image)
        if dino_vector is not None:
            combined = np.concatenate([
                dino_vector * 4.5,
                normalized_vector * 0.15,
            ])
            final_vector = self._normalize(combined.astype(np.float32))
            diagnostics = {
                "version": self.version,
                "provider": self._embedder_provider,
                "dimension": int(final_vector.shape[0]),
                "cropKind": crop_kind,
                "weights": weights,
                "dinoDimension": int(dino_vector.shape[0]),
                "handcraftedDimension": int(normalized_vector.shape[0]),
                "dinoModelPath": self._dino_model_path,
                "dinoModelHash": self._dino_model_hash[:12],
                "device": self._resolved_device,
            }
            return final_vector, diagnostics

        diagnostics = {
            "version": self.version,
            "provider": self._embedder_provider,
            "dimension": int(normalized_vector.shape[0]),
            "cropKind": crop_kind,
            "weights": weights,
            "arcfaceFallbackReason": self._arcface_error or "ArcFace ONNX model not configured or not found locally.",
            "dinoFallbackReason": self._dino_error or "DINOv2 disabled or not configured.",
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

    # --- Phase 4: DINOv2 learned embedding ---

    def _compute_arcface_embedding(self, crop_image: Image.Image) -> np.ndarray | None:
        if self._embedder_provider != "arcface-onnx":
            return None
        session = self._load_arcface_session()
        if session is None:
            return None
        batch = self._preprocess_arcface_batch([crop_image])
        try:
            input_name = session.get_inputs()[0].name
            outputs = session.run(None, {input_name: batch})
            embedding = np.asarray(outputs[0])[0].astype(np.float32).reshape(-1)
            return self._normalize(embedding)
        except Exception as exc:
            self._arcface_error = f"{type(exc).__name__}: {exc}"
            return None

    def _load_arcface_session(self):
        if self._arcface_session is not None:
            return self._arcface_session
        if not self._arcface_model_path:
            self._arcface_error = "ArcFace ONNX model path not configured."
            return None
        model_path = Path(self._arcface_model_path)
        if not model_path.exists() or model_path.suffix.lower() != ".onnx":
            self._arcface_error = f"ArcFace ONNX model not found locally: {self._arcface_model_path}"
            return None
        try:
            self._arcface_session = create_onnx_session(model_path, device=self._embed_device)
            self._arcface_runtime = session_diagnostics(self._arcface_session)
        except Exception as exc:
            self._arcface_error = f"{type(exc).__name__}: {exc}"
            self._arcface_session = None
        return self._arcface_session

    def _preprocess_arcface_batch(self, images: list[Image.Image]) -> np.ndarray:
        batch: list[np.ndarray] = []
        for image in images:
            arr = np.asarray(image.convert("RGB").resize((112, 112), Image.BICUBIC), dtype=np.float32)
            arr = (arr / 255.0 - 0.5) / 0.5
            batch.append(arr.transpose(2, 0, 1))
        return np.stack(batch, axis=0).astype(np.float32)

    def _compute_dino_embedding(self, crop_image: Image.Image) -> np.ndarray | None:
        """Compute a DINOv2 embedding for a single crop image. Returns None if DINOv2 is not available."""
        if self._embedder_provider != "hybrid-dinov2":
            return None
        if self._resolved_device == "cpu":
            self._dino_error = "DINOv2 disabled on CPU to avoid character prepass stalls; use ArcFace ONNX DirectML or handcrafted embedding."
            return None
        model, transform = self._load_dino_model()
        if model is None or transform is None:
            return None
        try:
            import torch
            rgb = crop_image.convert("RGB")
            tensor = transform(rgb).unsqueeze(0)
            with torch.no_grad():
                outputs = model(pixel_values=tensor)
            # DINOv2 cls_token is at position 0 of last_hidden_state
            cls_embedding = outputs.last_hidden_state[:, 0, :]
            embedding = cls_embedding[0].numpy().astype(np.float32)
            return self._normalize(embedding)
        except Exception as exc:
            self._dino_error = f"{type(exc).__name__}: {exc}"
            return None

    def embed_batch(
        self,
        *,
        chapter_id: str,
        items: list[dict],
    ) -> list[CharacterCropEmbedding]:
        """Batch embed multiple crops. Each item should have: crop_id, crop_kind, crop_image, cache_hint."""
        if not items:
            return []

        results: list[CharacterCropEmbedding | None] = [None] * len(items)
        uncached: list[tuple[int, dict, str, Path, Path]] = []
        cache_dir = self.cache_root / hashlib.sha1(chapter_id.encode("utf-8")).hexdigest()[:12] / "embeddings"
        for index, item in enumerate(items):
            cache_key = self._build_cache_key(
                chapter_id=chapter_id,
                crop_id=item["crop_id"],
                crop_kind=item["crop_kind"],
                cache_hint=item["cache_hint"],
                crop_image=item["crop_image"],
            )
            vector_path = cache_dir / f"{cache_key}.npy"
            meta_path = cache_dir / f"{cache_key}.json"
            if vector_path.exists() and meta_path.exists():
                vector = np.load(vector_path)
                diagnostics = json.loads(meta_path.read_text(encoding="utf-8"))
                results[index] = CharacterCropEmbedding(cache_key=cache_key, vector=vector, diagnostics=diagnostics)
            else:
                uncached.append((index, item, cache_key, vector_path, meta_path))

        batched_vectors = self._compute_arcface_embeddings([entry[1]["crop_image"] for entry in uncached])
        cache_dir.mkdir(parents=True, exist_ok=True)
        for offset, (index, item, cache_key, vector_path, meta_path) in enumerate(uncached):
            if batched_vectors is not None:
                handcrafted_vector, handcrafted_diagnostics = self._build_handcrafted_embedding(
                    item["crop_image"],
                    crop_kind=item["crop_kind"],
                )
                combined = np.concatenate([batched_vectors[offset] * 4.0, handcrafted_vector * 0.20])
                vector = self._normalize(combined.astype(np.float32))
                diagnostics = {
                    "version": self.version,
                    "provider": self._embedder_provider,
                    "dimension": int(vector.shape[0]),
                    "cropKind": item["crop_kind"],
                    "arcfaceDimension": int(batched_vectors[offset].shape[0]),
                    "handcraftedDimension": int(handcrafted_vector.shape[0]),
                    "arcfaceModelPath": self._arcface_model_path,
                    "arcfaceModelHash": self._arcface_model_hash[:12],
                    "device": self._resolved_device,
                    "runtime": self._arcface_runtime,
                    "handcraftedWeights": handcrafted_diagnostics["weights"],
                }
            else:
                vector, diagnostics = self._build_embedding(item["crop_image"], crop_kind=item["crop_kind"])
            np.save(vector_path, vector)
            meta_path.write_text(json.dumps(diagnostics), encoding="utf-8")
            results[index] = CharacterCropEmbedding(cache_key=cache_key, vector=vector, diagnostics=diagnostics)

        return [result for result in results if result is not None]

    def _compute_arcface_embeddings(self, images: list[Image.Image]) -> list[np.ndarray] | None:
        if not images or self._embedder_provider != "arcface-onnx":
            return None
        session = self._load_arcface_session()
        if session is None:
            return None
        try:
            input_name = session.get_inputs()[0].name
            outputs = session.run(None, {input_name: self._preprocess_arcface_batch(images)})
            embeddings = np.asarray(outputs[0]).astype(np.float32)
            return [self._normalize(row.reshape(-1)) for row in embeddings]
        except Exception as exc:
            self._arcface_error = f"{type(exc).__name__}: {exc}"
            return None

    def _load_dino_model(self):
        """Load DINOv2 model from local HuggingFace directory. Never downloads at runtime."""
        if self._dino_model is not None:
            return self._dino_model, self._dino_transform
        if not self._dino_model_path:
            self._dino_error = "DINOv2 model path not configured."
            return None, None
        model_path = Path(self._dino_model_path)
        if not model_path.exists() or not (model_path / "config.json").exists():
            self._dino_error = f"DINOv2 model not found locally: {self._dino_model_path}"
            return None, None
        try:
            import torch
            from transformers import AutoModel

            self._dino_model = AutoModel.from_pretrained(
                str(model_path),
                local_files_only=True,
            )
            self._dino_model.eval()

            # Manual transform equivalent to torchvision:
            # Resize(518) → CenterCrop(518) → ToTensor → Normalize
            # This avoids the heavy torchvision dependency.
            _mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)
            _std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)

            def _dino_preprocess(pil_image: Image.Image) -> "torch.Tensor":
                img = pil_image.resize((518, 518), Image.BICUBIC)
                arr = np.asarray(img, dtype=np.float32) / 255.0  # HWC, [0,1]
                arr = arr.transpose(2, 0, 1)  # CHW
                arr = (arr - _mean) / _std
                return torch.from_numpy(arr)

            self._dino_transform = _dino_preprocess
            self._dino_loaded = True
        except Exception as exc:
            self._dino_error = f"{type(exc).__name__}: {exc}"
            self._dino_model = None
            self._dino_transform = None
            self._dino_loaded = False
        return self._dino_model, self._dino_transform

    def runtime_diagnostics(self) -> dict[str, object]:
        """Return runtime diagnostics for the embedder."""
        return {
            "version": self.version,
            "provider": self._embedder_provider,
            "mode": self._embedder_mode,
            "arcfaceModelPath": self._arcface_model_path,
            "arcfaceModelHash": self._arcface_model_hash[:12] if self._arcface_model_hash else "",
            "arcfaceError": self._arcface_error,
            "arcfaceRuntime": self._arcface_runtime,
            "dinoModelPath": self._dino_model_path,
            "dinoModelHash": self._dino_model_hash[:12] if self._dino_model_hash else "",
            "dinoLoaded": self._dino_loaded,
            "dinoError": self._dino_error,
            "device": self._resolved_device,
        }

    def _compute_model_hash(self, model_path: str) -> str:
        """Compute a hash of the model file for cache invalidation."""
        path = Path(model_path)
        if not path.exists():
            return ""
        try:
            digest = hashlib.sha1()
            digest.update(str(path.stat().st_size).encode("utf-8"))
            digest.update(str(path.stat().st_mtime_ns).encode("utf-8"))
            digest.update(path.name.encode("utf-8"))
            return digest.hexdigest()
        except Exception:
            return ""

    def _resolve_device(self, requested: str) -> str:
        normalized = str(requested or "auto").strip().lower()
        if normalized == "cpu":
            return "cpu"
        if normalized in {"gpu", "cuda"}:
            try:
                import torch
                return "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                return "cpu"
        if normalized in {"directml", "dml"}:
            return "directml"
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def _resolve_provider(self) -> str:
        if self._embedder_mode in {"arcface", "arcface-directml"}:
            return "arcface-onnx" if self._arcface_model_path and Path(self._arcface_model_path).exists() else "handcrafted"
        if self._embedder_mode in {"dinov2", "hybrid-dinov2"}:
            return "hybrid-dinov2" if self._dino_model_path and Path(self._dino_model_path).exists() else "handcrafted"
        return "handcrafted"

    def _build_handcrafted_embedding(self, crop_image: Image.Image, *, crop_kind: str) -> tuple[np.ndarray, dict[str, object]]:
        current_provider = self._embedder_provider
        self._embedder_provider = "handcrafted"
        try:
            return self._build_embedding(crop_image, crop_kind=crop_kind)
        finally:
            self._embedder_provider = current_provider
