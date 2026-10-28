from pydantic import BaseModel

from data.model.agent_model import AgentTool, ToolContext, ToolDefinition, ToolOutcome
from service.personality_service import MAX_PERSONALITY_LENGTH, PersonalityService

UPDATE_PERSONALITY_TOOL_NAME = "update_personality"

_PERSONALITY_ERRORS = {
    "empty_personality": "a personalidade está vazia",
    "personality_too_long": f"a personalidade tem mais de {MAX_PERSONALITY_LENGTH} caracteres; resume-a",
    "personality_not_saved": "não foi possível gravar o ficheiro da personalidade",
}


class _UpdatePersonalityArgs(BaseModel):
    content: str


async def _update_personality(arguments: str, _context: ToolContext) -> ToolOutcome:
    result = await PersonalityService.update_personality(_UpdatePersonalityArgs.model_validate_json(arguments).content)
    if not result["success"]:
        return ToolOutcome(f"Erro: {_PERSONALITY_ERRORS[result['error']]}.")
    return ToolOutcome(
        "Personalidade atualizada. Passa a usá-la já nesta resposta.",
        "Atualizei a minha personalidade (vê-a com /personalidade).",
    )


PERSONALITY_TOOLS = [
    AgentTool(
        ToolDefinition(
            name=UPDATE_PERSONALITY_TOOL_NAME,
            description=(
                "Substitui a personalidade do Ayan (tom, humor, estilo e forma de explicar) pelo texto completo "
                "enviado. Só para quando o utilizador pede para mudares a forma como falas ou te comportas."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": (
                            "Texto COMPLETO da nova personalidade, em Markdown e em segunda pessoa. "
                            "Inclui o que já existia e o utilizador não pediu para mudar."
                        ),
                    },
                },
                "required": ["content"],
                "additionalProperties": False,
            },
        ),
        _update_personality,
    ),
]
