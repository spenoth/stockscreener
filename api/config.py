import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_NAME = os.environ.get("DB_NAME", "mydb")
DB_USER = os.environ.get("DB_USER", "myuser")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "mypassword")

API_PORT = int(os.environ.get("API_PORT", "8000"))

# ---------------------------------------------------------------------------
# CORS configuration
# ---------------------------------------------------------------------------
# Comma-separated list of exact origins allowed to call the API, e.g.
#   CORS_ALLOWED_ORIGINS="http://localhost:4200,http://192.168.1.50"
# Use "*" to allow any origin (only valid when credentials are NOT allowed).
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:4200,http://127.0.0.1:4200",
    ).split(",")
    if o.strip()
]

# Optional regex for matching origins dynamically (useful on a LAN where
# clients hit the server by IP/hostname). Example that allows any host on
# your local network on any port:
#   CORS_ALLOWED_ORIGIN_REGEX=r"^http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)(:\d+)?$"
CORS_ALLOWED_ORIGIN_REGEX = os.environ.get("CORS_ALLOWED_ORIGIN_REGEX", "") or None

# Whether to allow credentials (cookies/Authorization). Must be False if you
# want to use "*" in CORS_ALLOWED_ORIGINS.
CORS_ALLOW_CREDENTIALS = os.environ.get("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"
