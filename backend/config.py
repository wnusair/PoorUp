import os
from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str | None, default: str) -> list[str]:
    return [entry.strip() for entry in (value or default).split(",") if entry.strip()]


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

    CORS_ORIGINS = _split_csv(
        os.environ.get("CORS_ORIGINS"),
        "http://localhost:3000,http://localhost:5173",
    )

    # Game config
    TURN_AUTO_RESOLVE_SECONDS = 30
    LOG_BUFFER_SIZE = 100


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    DEBUG = False


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)
