import os

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_LANGUAGE = os.getenv("TMDB_LANGUAGE", "pt-PT")
TMDB_TIMEOUT_SECONDS = float(os.getenv("TMDB_TIMEOUT_SECONDS", "10"))
