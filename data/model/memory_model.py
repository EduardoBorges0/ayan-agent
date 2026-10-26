from dataclasses import dataclass


@dataclass(frozen=True)
class Memory:
    id: int
    content: str
    created_at: str
