from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    output: str


@dataclass(frozen=True)
class ToolRound:
    calls: list[ToolCall]
    results: list[ToolResult]


@dataclass(frozen=True)
class ModelTurn:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(frozen=True)
class AgentReply:
    reply: str
    events: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ToolContext:
    workspace: Path
    confirm: Callable[[str], bool]
    approved_folders: set[Path] = field(default_factory=set)
    session_tools: tuple[AgentTool, ...] = ()
    approved_tools: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class ToolOutcome:
    output: str
    event: str | None = None


@dataclass(frozen=True)
class AgentTool:
    definition: ToolDefinition
    run: Callable[[str, ToolContext], Awaitable[ToolOutcome]]
