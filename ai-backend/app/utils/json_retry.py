from __future__ import annotations

from typing import Awaitable, Callable, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


async def parse_with_single_repair(
    raw_call: Callable[[], Awaitable[str]],
    repair_call: Callable[[str], Awaitable[str]],
    response_model: type[T],
) -> tuple[T, str]:
    raw_output = await raw_call()
    try:
        return response_model.model_validate_json(raw_output), raw_output
    except ValidationError:
        repaired_output = await repair_call(raw_output)
        return response_model.model_validate_json(repaired_output), repaired_output
