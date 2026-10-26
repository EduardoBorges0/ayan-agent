from openai import AsyncOpenAI

from load_env import OPENAI_API_KEY, OPENAI_MAX_RETRIES, OPENAI_MODEL, OPENAI_TIMEOUT_SECONDS


class OpenAIConnect:
    _client: AsyncOpenAI | None = None

    @staticmethod
    def get_client() -> AsyncOpenAI:
        if OpenAIConnect._client is None:
            if not OPENAI_API_KEY or not OPENAI_MODEL:
                raise RuntimeError("OPENAI_API_KEY e OPENAI_MODEL têm de estar configuradas.")
            OpenAIConnect._client = AsyncOpenAI(
                api_key=OPENAI_API_KEY,
                timeout=OPENAI_TIMEOUT_SECONDS,
                max_retries=OPENAI_MAX_RETRIES,
            )
        return OpenAIConnect._client
