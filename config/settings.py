"""Application settings loaded from environment variables."""
import os

APP_TITLE = "CardSync AI API"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = (
    "CardSync AI backend: Zoho CRM leads, Brevo email, WhatsApp Cloud API, and Meta webhooks.\n\n"
    "Card OCR runs in the browser — this API receives extracted fields on save/sync.\n\n"
    "**Zoho Features field:** `eventName` → `Event: {name}` and user `notes` → `Notes: {text}` "
    "(both stored in Zoho Lead Description / Features).\n\n"
    "**Swagger UI:** `/docs` · **ReDoc:** `/redoc` · **WhatsApp webhook:** `GET/POST /webhook`"
)

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5000

NETLIFY_FRONTEND_ORIGIN = "https://cardsyncai.netlify.app"

DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    NETLIFY_FRONTEND_ORIGIN,
]

CORS_ORIGIN_REGEX = (
    r"https?://(localhost|127\.0\.0\.1)(:\d+)?|"
    r"https://([a-zA-Z0-9-]+--)?[a-zA-Z0-9-]+\.netlify\.app"
)


def normalize_origin(origin: str) -> str:
    return origin.strip().rstrip("/")


def get_allowed_origins() -> list[str]:
    origins = list(DEFAULT_ALLOWED_ORIGINS)

    frontend_url = os.getenv("FRONTEND_URL")
    if frontend_url:
        origins.append(normalize_origin(frontend_url))

    extra = os.getenv("ALLOWED_ORIGINS")
    if extra:
        origins.extend(normalize_origin(part) for part in extra.split(",") if part.strip())

    return list({normalize_origin(origin) for origin in origins})
