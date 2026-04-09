import os
from urllib.parse import urlsplit
from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str | None, default: str) -> list[str]:
    return [entry.strip() for entry in (value or default).split(",") if entry.strip()]


def _env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _format_origin_host(hostname: str) -> str:
    return f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname


def _expand_origin(origin: str) -> list[str]:
    parsed = urlsplit(origin)

    if not parsed.scheme or not parsed.hostname or parsed.port is not None:
        return [origin]

    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        return [origin]

    host = _format_origin_host(parsed.hostname)
    variants = [origin]
    variants.extend(
        f"{parsed.scheme}://{host}:{port}"
        for port in (3000, 4173, 5173)
    )
    return variants


def _expand_origin_list(origins: list[str]) -> list[str]:
    expanded: list[str] = []

    for origin in origins:
        for candidate in _expand_origin(origin):
            if candidate not in expanded:
                expanded.append(candidate)

    return expanded


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    DATABASE_URL = os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/poorup"
    )
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    SESSION_TYPE = "redis"
    SESSION_PERMANENT = True
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = "poorup_session:"
    PERMANENT_SESSION_LIFETIME = 86400  # 1 day

    CORS_ORIGINS = _expand_origin_list(
        _split_csv(
            os.environ.get("CORS_ORIGINS"),
            "http://localhost:3000,http://localhost:5173",
        )
    )

    # Game config
    TURN_AUTO_RESOLVE_SECONDS = 30
    LOG_BUFFER_SIZE = 100


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False
    ENABLE_HOST_DEBUG_TOOLS = _env_flag("ENABLE_HOST_DEBUG_TOOLS", True)


class ProductionConfig(Config):
    DEBUG = False
    ENABLE_HOST_DEBUG_TOOLS = _env_flag("ENABLE_HOST_DEBUG_TOOLS", False)


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)
