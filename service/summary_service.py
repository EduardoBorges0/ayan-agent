from data.gateway.openai_gateway import LLMAuthenticationError, LLMUnavailableError, OpenAIGateway
from data.model.chat_model import ChatMessage


class SummaryService:
    @staticmethod
    async def summarize(instructions: str, text: str, max_length: int) -> dict:
        # O limite de tamanho do ChatMessage protege o input do utilizador, não o texto interno a resumir.
        message = ChatMessage.model_construct(role="user", content=text)
        try:
            turn = await OpenAIGateway.generate_turn([message], instructions)
        except LLMAuthenticationError:
            return {"success": False, "error": "llm_auth_failed"}
        except LLMUnavailableError as exc:
            return {"success": False, "error": "llm_unavailable", "detail": exc.reason}

        summary = turn.text.strip()
        if not summary:
            return {"success": False, "error": "empty_summary"}
        if len(summary) > max_length:
            return {"success": False, "error": "summary_too_long"}
        return {"success": True, "data": summary}
