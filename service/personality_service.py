import asyncio
import logging

from data.gateway.personality_gateway import PersonalityGateway

logger = logging.getLogger(__name__)

MAX_PERSONALITY_LENGTH = 2000
DEFAULT_PERSONALITY = (
    "Sê simpático, claro e direto. Explica sem rodeios, com exemplos simples quando ajudarem, "
    "e só pergunta o que for mesmo necessário."
)


class PersonalityService:
    @staticmethod
    async def get_personality() -> dict:
        try:
            content = await asyncio.to_thread(PersonalityGateway.read)
        except (OSError, UnicodeDecodeError):
            return {"success": False, "error": "personality_unreadable"}

        if content is None:
            # Primeira execução: cria o ficheiro com o texto padrão para o utilizador o poder editar.
            try:
                await asyncio.to_thread(PersonalityGateway.write, DEFAULT_PERSONALITY)
            except OSError:
                logger.warning("Não foi possível criar o ficheiro da personalidade.", exc_info=True)
            return {"success": True, "data": DEFAULT_PERSONALITY}
        if not content.strip():
            return {"success": True, "data": DEFAULT_PERSONALITY}
        return {"success": True, "data": content.strip()}

    @staticmethod
    async def update_personality(content: str) -> dict:
        content = content.strip()
        if not content:
            return {"success": False, "error": "empty_personality"}
        if len(content) > MAX_PERSONALITY_LENGTH:
            return {"success": False, "error": "personality_too_long"}

        try:
            await asyncio.to_thread(PersonalityGateway.write, content)
        except OSError:
            return {"success": False, "error": "personality_not_saved"}
        return {"success": True, "data": content}
