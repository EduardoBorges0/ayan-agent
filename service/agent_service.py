from pydantic import BaseModel, ValidationError

from data.gateway.openai_gateway import LLMAuthenticationError, LLMUnavailableError, OpenAIGateway
from data.model.agent_model import AgentReply, ToolCall, ToolDefinition, ToolResult, ToolRound
from data.model.chat_model import ChatMessage
from data.model.memory_model import Memory
from service.memory_service import MAX_MEMORY_LENGTH, MemoryService

MAX_TOOL_ROUNDS = 3

AGENT_INSTRUCTIONS = f"""És o Ayan, um assistente pessoal que corre no computador do utilizador. \
Responde em português de Portugal, de forma clara e direta.

Tens uma memória persistente sobre o utilizador, que se mantém entre conversas.
- Usa save_memory quando aprenderes algo duradouro e útil para conversas futuras: preferências, \
forma de trabalhar, contexto profissional, factos que o utilizador partilhe sobre si.
- Não guardes informação passageira, nem segredos, palavras-passe, chaves API ou dados de terceiros.
- Cada memória é uma frase curta e autónoma, na terceira pessoa, com no máximo {MAX_MEMORY_LENGTH} \
caracteres (ex.: "Prefere respostas curtas.").
- Usa forget_memory quando o utilizador pedir para esqueceres algo ou quando uma memória ficar \
desatualizada. Para corrigir uma memória, esquece a antiga e guarda a nova."""

SAVE_MEMORY_TOOL = ToolDefinition(
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
)

FORGET_MEMORY_TOOL = ToolDefinition(
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
)

TOOLS = [SAVE_MEMORY_TOOL, FORGET_MEMORY_TOOL]

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


def _build_instructions(memories: list[Memory]) -> str:
    if not memories:
        return f"{AGENT_INSTRUCTIONS}\n\nMemórias atuais: ainda não há nenhuma."
    listed = "\n".join(f"[{memory.id}] {memory.content}" for memory in memories)
    return f"{AGENT_INSTRUCTIONS}\n\nMemórias atuais:\n{listed}"


async def _run_tool(call: ToolCall) -> tuple[ToolResult, str | None]:
    try:
        if call.name == SAVE_MEMORY_TOOL.name:
            result = await MemoryService.remember(_SaveMemoryArgs.model_validate_json(call.arguments).content)
            if result["success"]:
                memory = result["data"]
                return ToolResult(call.id, f"Memória guardada com o número {memory.id}."), \
                    f"Guardei na memória: {memory.content}"
        elif call.name == FORGET_MEMORY_TOOL.name:
            result = await MemoryService.forget(_ForgetMemoryArgs.model_validate_json(call.arguments).memory_id)
            if result["success"]:
                return ToolResult(call.id, "Memória apagada."), f"Esqueci: {result['data'].content}"
        else:
            return ToolResult(call.id, "Erro: ferramenta desconhecida."), None
    except ValidationError:
        return ToolResult(call.id, "Erro: argumentos inválidos."), None

    return ToolResult(call.id, f"Erro: {_MEMORY_ERRORS[result['error']]}."), None


class AgentService:
    @staticmethod
    async def reply(messages: list[ChatMessage]) -> dict:
        if messages[-1].role != "user":
            return {"success": False, "error": "last_message_not_from_user"}

        memories = (await MemoryService.list_memories())["data"]
        instructions = _build_instructions(memories)
        tool_rounds: list[ToolRound] = []
        memory_events: list[str] = []

        for round_number in range(MAX_TOOL_ROUNDS + 1):
            try:
                turn = await OpenAIGateway.generate_turn(
                    messages, instructions, TOOLS, tool_rounds, allow_tools=round_number < MAX_TOOL_ROUNDS
                )
            except LLMAuthenticationError:
                return {"success": False, "error": "llm_auth_failed"}
            except LLMUnavailableError as exc:
                return {"success": False, "error": "llm_unavailable", "detail": exc.reason}

            if not turn.tool_calls:
                if not turn.text.strip():
                    return {"success": False, "error": "empty_reply"}
                return {"success": True, "data": AgentReply(reply=turn.text, memory_events=memory_events)}

            results = []
            for call in turn.tool_calls:
                result, event = await _run_tool(call)
                results.append(result)
                if event:
                    memory_events.append(event)
            tool_rounds.append(ToolRound(calls=turn.tool_calls, results=results))

        return {"success": False, "error": "empty_reply"}
