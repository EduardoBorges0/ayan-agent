from data.gateway.openai_gateway import LLMUnavailableError, OpenAIGateway
from data.model.chat_model import ChatMessage, ChatResponse

SYSTEM_INSTRUCTIONS = "És um assistente útil. Responde em português de Portugal, de forma clara e direta."


class ChatService:
    @staticmethod
    async def reply(messages: list[ChatMessage]) -> dict:
        if messages[-1].role != "user":
            return {"success": False, "error": "last_message_not_from_user"}

        try:
            text = await OpenAIGateway.generate_reply(messages, SYSTEM_INSTRUCTIONS)
        except LLMUnavailableError:
            return {"success": False, "error": "llm_unavailable"}

        if not text.strip():
            return {"success": False, "error": "empty_reply"}

        return {"success": True, "data": ChatResponse(reply=text)}
