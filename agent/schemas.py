from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    tool: str
    status: Literal["ok", "error", "denied"]
    data: Any = None
    error: str | None = None
    duration_ms: float = 0
    request_id: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    confirmation_token: str | None = None


class ChatResponse(BaseModel):
    request_id: str
    answer: str
    evidence: list[ToolResult]
    confirmation_token: str | None = None
    proposed_action: dict | None = None
