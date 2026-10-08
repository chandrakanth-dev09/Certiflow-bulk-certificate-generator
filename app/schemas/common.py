from typing import Any

from pydantic import BaseModel, ConfigDict


class ApiError(BaseModel):
    code: str
    message: str
    details: list[Any] = []


class ApiResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    success: bool
    data: Any | None = None
    meta: dict[str, Any] | None = None
    error: ApiError | None = None
