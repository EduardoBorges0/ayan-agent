import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

APP_ENV = os.getenv("APP_ENV", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()]

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "2"))
OPENAI_MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "1024"))

USER_CONFIG_DIR = Path(os.getenv("APPDATA") or Path.home() / ".config") / "ayan"
AYAN_DB_PATH = USER_CONFIG_DIR / "ayan.db"
AGENT_COMMAND_TIMEOUT_SECONDS = int(os.getenv("AGENT_COMMAND_TIMEOUT_SECONDS", "120"))
MCP_CONFIG_PATH = USER_CONFIG_DIR / "mcp.json"
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
MCP_TIMEOUT_SECONDS = float(os.getenv("MCP_TIMEOUT_SECONDS", "60"))
