from openai import AsyncOpenAI

from load_env import OPENAI_API_KEY, OPENAI_MAX_RETRIES, OPENAI_MODEL, OPENAI_TIMEOUT_SECONDS


class OpenAIConnect:
    _client: AsyncOpenAI | None = None
    _api_key: str | None = OPENAI_API_KEY
    _model: str | None = OPENAI_MODEL

    @classmethod
    def configure(cls, api_key: str, model: str) -> None:
        cls._api_key = api_key
        cls._model = model
        cls._client = None

    @classmethod
    def get_client(cls) -> AsyncOpenAI:
        if cls._client is None:
            if not cls._api_key or not cls._model:
                raise RuntimeError("A chave e o modelo da OpenAI têm de estar configurados.")
            cls._client = AsyncOpenAI(
                api_key=cls._api_key,
                timeout=OPENAI_TIMEOUT_SECONDS,
                max_retries=OPENAI_MAX_RETRIES,
            )
        return cls._client

    @classmethod
    def get_model(cls) -> str:
        return cls._model
