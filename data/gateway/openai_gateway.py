import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager

import openai

from config.connections.openai_connection import OpenAIConnect
from data.model.agent_model import ModelTurn, ToolCall, ToolDefinition, ToolRound
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


def _to_openai_messages(
    messages: Sequence[ChatMessage], instructions: str, tool_rounds: Sequence[ToolRound]
) -> list[dict]:
    openai_messages = [{"role": "system", "content": instructions}]
    openai_messages += [{"role": message.role, "content": message.content} for message in messages]
    for tool_round in tool_rounds:
        openai_messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": call.id, "type": "function", "function": {"name": call.name, "arguments": call.arguments}}
                for call in tool_round.calls
            ],
        })
        openai_messages += [
            {"role": "tool", "tool_call_id": result.call_id, "content": result.output}
            for result in tool_round.results
        ]
    return openai_messages


def _to_openai_tool(tool: ToolDefinition) -> dict:
    return {
        "type": "function",
        "function": {"name": tool.name, "description": tool.description, "parameters": tool.parameters},
    }


class OpenAIGateway:
    @staticmethod
    async def generate_turn(
        messages: Sequence[ChatMessage],
        instructions: str,
        tools: Sequence[ToolDefinition] = (),
        tool_rounds: Sequence[ToolRound] = (),
        allow_tools: bool = True,
    ) -> ModelTurn:
        client = OpenAIConnect.get_client()
        request = {
            "model": OpenAIConnect.get_model(),
            "messages": _to_openai_messages(messages, instructions, tool_rounds),
            "max_completion_tokens": OPENAI_MAX_OUTPUT_TOKENS,
            "store": False,
        }
        if tools:
            request["tools"] = [_to_openai_tool(tool) for tool in tools]
            request["tool_choice"] = "auto" if allow_tools else "none"

        with _translate_openai_errors():
            completion = await client.chat.completions.create(**request)

        message = completion.choices[0].message
        return ModelTurn(
            text=message.content or "",
            tool_calls=[
                ToolCall(id=call.id, name=call.function.name, arguments=call.function.arguments)
                for call in message.tool_calls or []
                if call.type == "function"
            ],
        )

    @staticmethod
    async def list_model_ids() -> list[str]:
        client = OpenAIConnect.get_client()
        with _translate_openai_errors():
            return [model.id async for model in client.models.list()]
