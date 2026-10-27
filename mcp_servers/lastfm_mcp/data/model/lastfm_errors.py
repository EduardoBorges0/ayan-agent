class LastFmApiError(Exception):
    """O Last.fm respondeu, mas com um erro da API (ex.: chave inválida, limite de pedidos)."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class LastFmUnavailableError(Exception):
    """Não foi possível obter uma resposta utilizável do Last.fm (rede, timeout, 5xx)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason
