from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App settings
    APP_NAME: str = "Poker Game"
    DEBUG: bool = True
    SECRET_KEY: str = "your-secret-key-change-in-production"
    DATABASE_URL: str = "sqlite+aiosqlite:///./poker.db"

    # JWT settings
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # Game limits
    MAX_USERS: int = 20
    MAX_ROOMS: int = 10
    SESSION_TIMEOUT: int = 30 * 60  # 30 minutes
    LOGIN_LOCKOUT_TIME: int = 15 * 60  # 15 minutes
    MAX_LOGIN_ATTEMPTS: int = 5
    ACTION_TIMEOUT: int = 30  # 30 seconds
    RECONNECT_TIMEOUT: int = 5 * 60  # 5 minutes

    # CORS
    CORS_ORIGINS: list = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Initial admin account
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    ADMIN_DISPLAY_NAME: str = "管理员"

    class Config:
        env_file = ".env"


settings = Settings()
