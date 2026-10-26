from pydantic import BaseModel

from data.model.agent_model import AgentTool, ToolContext, ToolDefinition, ToolOutcome
from service.memory_service import MAX_MEMORY_LENGTH, MemoryService

_MEMORY_ERRORS = {
    "empty_memory": "a memória está vazia",
    "memory_too_long": f"a memória tem mais de {MAX_MEMORY_LENGTH} caracteres",
    "memory_looks_like_secret": "parece conter uma chave ou segredo e não foi guardada",
    "memory_already_exists": "essa memória já existe",
    "memory_limit_reached": "a memória está cheia; esquece memórias desatualizadas antes de guardar novas",
    "memory_not_found": "não existe nenhuma memória com esse número",
}


class _SaveMemoryArgs(BaseModel):
    content: str


class _ForgetMemoryArgs(BaseModel):
    memory_id: int


async def _save_memory(arguments: str, _context: ToolContext) -> ToolOutcome:
    result = await MemoryService.remember(_SaveMemoryArgs.model_validate_json(arguments).content)
    if not result["success"]:
        return ToolOutcome(f"Erro: {_MEMORY_ERRORS[result['error']]}.")
    memory = result["data"]
    return ToolOutcome(f"Memória guardada com o número {memory.id}.", f"Guardei na memória: {memory.content}")


async def _forget_memory(arguments: str, _context: ToolContext) -> ToolOutcome:
    result = await MemoryService.forget(_ForgetMemoryArgs.model_validate_json(arguments).memory_id)
    if not result["success"]:
        return ToolOutcome(f"Erro: {_MEMORY_ERRORS[result['error']]}.")
    return ToolOutcome("Memória apagada.", f"Esqueci: {result['data'].content}")


MEMORY_TOOLS = [
    AgentTool(
        ToolDefinition(
            name="save_memory",
            description="Guarda um facto duradouro sobre o utilizador na memória persistente.",
            parameters={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Facto curto e autónomo sobre o utilizador."},
                },
                "required": ["content"],
                "additionalProperties": False,
            },
        ),
        _save_memory,
    ),
    AgentTool(
        ToolDefinition(
            name="forget_memory",
            description="Apaga uma memória pelo seu número.",
            parameters={
                "type": "object",
                "properties": {
                    "memory_id": {"type": "integer", "description": "Número da memória, tal como aparece na lista."},
                },
                "required": ["memory_id"],
                "additionalProperties": False,
            },
        ),
        _forget_memory,
    ),
]
