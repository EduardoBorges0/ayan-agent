from fastapi import APIRouter, HTTPException

from data.model.chat_model import ChatRequest, ChatResponse
from service.chat_service import ChatService

router = APIRouter()

_ERRORS = {
    "last_message_not_from_user": (422, "A última mensagem tem de ser do utilizador."),
    "llm_unavailable": (502, "O serviço de IA está indisponível. Tente novamente mais tarde."),
    "empty_reply": (502, "O serviço de IA não devolveu resposta."),
}


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    result = await ChatService.reply(body.messages)
    if not result["success"]:
        status_code, detail = _ERRORS[result["error"]]
        raise HTTPException(status_code=status_code, detail=detail)
    return result["data"]
