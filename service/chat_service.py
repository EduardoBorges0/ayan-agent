import re

from data.gateway.openai_gateway import LLMAuthenticationError, LLMUnavailableError, OpenAIGateway
from data.model.chat_model import ChatMessage, ChatResponse

SYSTEM_INSTRUCTIONS = "És um assistente útil. Responde em português de Portugal, de forma clara e direta."

_CHAT_MODEL_FAMILY = re.compile(r"^(gpt-|o\d)")
_DATED_SNAPSHOT = re.compile(r"-\d{4}-\d{2}-\d{2}$")
_NON_CHAT_MARKERS = (
    "audio", "realtime", "tts", "transcribe", "image", "search", "instruct", "embedding", "moderation",
)


def _is_chat_model(model_id: str) -> bool:
    return (
        bool(_CHAT_MODEL_FAMILY.match(model_id))
        and not _DATED_SNAPSHOT.search(model_id)
        and not any(marker in model_id for marker in _NON_CHAT_MARKERS)
    )


class ChatService:
    @staticmethod
    async def reply(messages: list[ChatMessage]) -> dict:
        if messages[-1].role != "user":
            return {"success": False, "error": "last_message_not_from_user"}

        try:
            turn = await OpenAIGateway.generate_turn(messages, SYSTEM_INSTRUCTIONS)
        except LLMAuthenticationError:
            return {"success": False, "error": "llm_auth_failed"}
        except LLMUnavailableError as exc:
            return {"success": False, "error": "llm_unavailable", "detail": exc.reason}

        if not turn.text.strip():
            return {"success": False, "error": "empty_reply"}

        return {"success": True, "data": ChatResponse(reply=turn.text)}

    @staticmethod
    async def available_models() -> dict:
        try:
            model_ids = await OpenAIGateway.list_model_ids()
        except LLMAuthenticationError:
            return {"success": False, "error": "llm_auth_failed"}
        except LLMUnavailableError as exc:
            return {"success": False, "error": "llm_unavailable", "detail": exc.reason}

        return {"success": True, "data": sorted(m for m in model_ids if _is_chat_model(m))}
