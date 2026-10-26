from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from data.model.agent_model import AgentTool


class McpServerConfig(BaseModel):
    name: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,30}$")
    command: str = Field(min_length=1)
    args: list[str] = []
    env: dict[str, str] = {}
    cwd: str | None = None
    trusted: bool = False


@dataclass(frozen=True)
class McpToolInfo:
    server: str
    name: str
    description: str
    input_schema: dict


@dataclass(frozen=True)
class McpCallResult:
    text: str
    is_error: bool


@dataclass(frozen=True)
class McpConnection:
    tools: list[AgentTool] = field(default_factory=list)
    servers: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
