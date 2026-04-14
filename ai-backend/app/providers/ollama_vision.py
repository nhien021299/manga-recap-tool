from __future__ import annotations

from pathlib import Path

import httpx

from app.utils.image_io import image_to_base64


class OllamaVisionProvider:
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

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
                "images": [image_to_base64(path) for path in image_paths],
            }
        )
        if schema:
            payload["format"] = schema

        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            return (data.get("message", {}) or {}).get("content", "").strip()
