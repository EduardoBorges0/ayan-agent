import logging
from collections.abc import Iterator
from contextlib import contextmanager

import openai

from config.connections.openai_connection import OpenAIConnect
from data.model.chat_model import ChatMessage
from load_env import OPENAI_MAX_OUTPUT_TOKENS

logger = logging.getLogger(__name__)


class LLMUnavailableError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class LLMAuthenticationError(Exception):
    pass


def _describe(exc: openai.OpenAIError) -> str:
    if isinstance(exc, openai.APIStatusError):
        body_message = exc.body.get("message") if isinstance(exc.body, dict) else None
        return f"HTTP {exc.status_code}: {body_message or exc.message}"
    return f"{type(exc).__name__}: {exc}"


@contextmanager
def _translate_openai_errors() -> Iterator[None]:
    try:
        yield
    except openai.AuthenticationError as exc:
        logger.warning("Chave OpenAI rejeitada.")
        raise LLMAuthenticationError from exc
    except openai.OpenAIError as exc:
        reason = _describe(exc)
        logger.warning("Falha ao contactar a OpenAI: %s", reason)
        raise LLMUnavailableError(reason) from exc


class OpenAIGateway:
    @staticmethod
    async def generate_reply(messages: list[ChatMessage], instructions: str) -> str:
        client = OpenAIConnect.get_client()
        with _translate_openai_errors():
            response = await client.responses.create(
                model=OpenAIConnect.get_model(),
                instructions=instructions,
                input=[{"role": message.role, "content": message.content} for message in messages],
                max_output_tokens=OPENAI_MAX_OUTPUT_TOKENS,
                store=False,
            )
        return response.output_text

    @staticmethod
    async def list_model_ids() -> list[str]:
        client = OpenAIConnect.get_client()
        with _translate_openai_errors():
            return [model.id async for model in client.models.list()]
