from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

MAX_HISTORY_MESSAGES = 50


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_HISTORY_MESSAGES)


class ChatResponse(BaseModel):
    reply: str


@dataclass(frozen=True)
class CompactedConversation:
    summary: str | None
    messages: list[ChatMessage]
