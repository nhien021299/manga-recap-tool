from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx

from app.utils.image_io import image_to_base64

logger = logging.getLogger(__name__)


class OllamaVisionProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
        timeout_retries: int = 2,
        retry_delay_seconds: float = 5.0,
        max_width: int | None = None,
        max_height: int | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.timeout_retries = timeout_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.max_width = max_width
        self.max_height = max_height

    async def generate_structured(
        self,
        prompt: str,
        *,
        image_paths: list[Path],
        schema: dict | None = None,
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> str:
        payload: dict = {
            "model": self.model,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": max_tokens,
            },
            "messages": [],
        }
        if system:
            payload["messages"].append({"role": "system", "content": system})
        payload["messages"].append(
            {
                "role": "user",
                "content": prompt,
                "images": [
                    image_to_base64(path, max_width=self.max_width, max_height=self.max_height) for path in image_paths
                ],
            }
        )
        if schema:
            payload["format"] = schema

        endpoint = f"{self.base_url}/api/chat"
        max_attempts = max(1, self.timeout_retries + 1)
        attempt = 0
        last_exception: Exception | None = None

        while attempt < max_attempts:
            attempt += 1
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                try:
                    response = await client.post(endpoint, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    return (data.get("message", {}) or {}).get("content", "").strip()
                except httpx.ReadTimeout as exc:
                    last_exception = exc
                    if attempt < max_attempts:
                        logger.warning(
                            "ollama vision timeout, retrying | model=%s attempt=%s/%s delay=%ss images=%s",
                            self.model,
                            attempt,
                            max_attempts,
                            self.retry_delay_seconds,
                            len(image_paths),
                        )
                        await asyncio.sleep(self.retry_delay_seconds)
                        continue
                    break
                except Exception as exc:
                    raise RuntimeError(
                        f"provider=ollama_vision model={self.model} endpoint={endpoint} "
                        f"max_width={self.max_width} max_height={self.max_height} "
                        f"image_count={len(image_paths)} timeout_seconds={self.timeout_seconds} "
                        f"timeout_retries={self.timeout_retries} retry_delay_seconds={self.retry_delay_seconds} "
                        f"attempt={attempt}/{max_attempts} exception_type={type(exc).__name__} error={exc}"
                    ) from exc

        raise RuntimeError(
            f"provider=ollama_vision model={self.model} endpoint={endpoint} "
            f"max_width={self.max_width} max_height={self.max_height} "
            f"image_count={len(image_paths)} timeout_seconds={self.timeout_seconds} "
            f"timeout_retries={self.timeout_retries} retry_delay_seconds={self.retry_delay_seconds} "
            f"attempt={max_attempts}/{max_attempts} exception_type={type(last_exception).__name__ if last_exception else 'ReadTimeout'} "
            f"error={last_exception or ''}"
        ) from last_exception
