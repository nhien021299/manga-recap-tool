from __future__ import annotations

import httpx


class LlamaCppTextProvider:
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
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system or "Return JSON when the user asks for it."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"} if schema else {"type": "text"},
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.base_url}/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

    async def repair_json(self, *, invalid_output: str, schema: dict) -> str:
        prompt = (
            "Return valid JSON only. Fix the following output to match the requested schema.\n"
            f"Output:\n{invalid_output}"
        )
        return await self.generate_text(prompt, schema=schema, max_tokens=1024)
