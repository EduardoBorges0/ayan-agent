from dataclasses import dataclass, field


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
    memory_events: list[str] = field(default_factory=list)
