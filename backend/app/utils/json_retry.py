from __future__ import annotations

from typing import Awaitable, Callable, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class RawProviderError(RuntimeError):
    pass


class JsonRepairFailedError(RuntimeError):
    def __init__(self, raw_output: str, cause: Exception) -> None:
        super().__init__("JSON repair failed.")
        self.raw_output = raw_output
        self.cause = cause


class RepairedJsonValidationFailedError(RuntimeError):
    def __init__(self, raw_output: str, repaired_output: str, validation_error: ValidationError) -> None:
        super().__init__("Repaired JSON validation failed.")
        self.raw_output = raw_output
        self.repaired_output = repaired_output
        self.validation_error = validation_error


async def parse_with_single_repair(
    raw_call: Callable[[], Awaitable[str]],
    repair_call: Callable[[str], Awaitable[str]],
    response_model: type[T],
) -> tuple[T, str]:
    try:
        raw_output = await raw_call()
    except Exception as exc:
        raise RawProviderError(str(exc)) from exc

    try:
        return response_model.model_validate_json(raw_output), raw_output
    except ValidationError as exc:
        try:
            repaired_output = await repair_call(raw_output)
        except Exception as repair_exc:
            raise JsonRepairFailedError(raw_output, repair_exc) from repair_exc
        try:
            return response_model.model_validate_json(repaired_output), repaired_output
        except ValidationError as repaired_exc:
            raise RepairedJsonValidationFailedError(raw_output, repaired_output, repaired_exc) from repaired_exc
