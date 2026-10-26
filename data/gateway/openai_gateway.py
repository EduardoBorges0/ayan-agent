import logging

import openai

from config.connections.openai_connection import OpenAIConnect
from data.model.chat_model import ChatMessage
from load_env import OPENAI_MAX_OUTPUT_TOKENS, OPENAI_MODEL

logger = logging.getLogger(__name__)


class LLMUnavailableError(Exception):
    pass


class OpenAIGateway:
    @staticmethod
    async def generate_reply(messages: list[ChatMessage], instructions: str) -> str:
        client = OpenAIConnect.get_client()
        try:
            response = await client.responses.create(
                model=OPENAI_MODEL,
                instructions=instructions,
                input=[{"role": message.role, "content": message.content} for message in messages],
                max_output_tokens=OPENAI_MAX_OUTPUT_TOKENS,
                store=False,
            )
        except openai.OpenAIError as exc:
            logger.warning("Falha ao contactar a OpenAI: %s", type(exc).__name__)
            raise LLMUnavailableError from exc
        return response.output_text
