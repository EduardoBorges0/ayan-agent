import os

LASTFM_API_KEY = (os.getenv("LASTFM_API_KEY") or "").strip()

LASTFM_BASE_URL = "https://ws.audioscrobbler.com/2.0/"
LASTFM_TIMEOUT_SECONDS = float(os.getenv("LASTFM_TIMEOUT_SECONDS", "10"))
LASTFM_MAX_ATTEMPTS = 3
LASTFM_RETRY_BACKOFF_SECONDS = 0.5
LASTFM_USER_AGENT = "ayan-lastfm-mcp/1.0"
