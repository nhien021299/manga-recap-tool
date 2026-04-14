from __future__ import annotations

import json

import httpx


class OllamaTextProvider:
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate_text(
        self,
        prompt: str,
        *,
        schema: dict | None = None,
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> str:
        payload: dict = {
            "model": self.model,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": max_tokens,
            },
            "messages": [],
        }
        if system:
            payload["messages"].append({"role": "system", "content": system})
        payload["messages"].append({"role": "user", "content": prompt})
        if schema:
            payload["format"] = schema

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            return (data.get("message", {}) or {}).get("content", "").strip()

    async def repair_json(self, *, invalid_output: str, schema: dict) -> str:
        prompt = (
            "Rewrite the following output so it becomes valid JSON matching this schema exactly.\n"
            f"Schema:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
            f"Invalid output:\n{invalid_output}\n"
        )
        return await self.generate_text(prompt, schema=schema, max_tokens=1024)
