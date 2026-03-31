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
    # 玩家单次思考/操作上限（秒），可通过环境变量 ACTION_TIMEOUT 或 run.py --action-timeout 配置
    ACTION_TIMEOUT: int = 30
    RECONNECT_TIMEOUT: int = 5 * 60  # 5 minutes - 断线重连超时
    AUTO_START_DELAY: int = 3  # 自动开始下一手前的延迟（秒）
    DEALING_DELAY: int = 5  # 每轮发牌后的等待时间（秒），让玩家看清牌面后再开始行动计时
    HAND_END_DELAY: int = 10  # 每局结束后的等待时间（秒），让玩家看清输赢结果后再开始下一局
    MAX_CHAT_LENGTH: int = 500  # 聊天消息最大长度

    # CORS
    CORS_ORIGINS: list = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Initial admin account
    ADMIN_USERNAME: Optional[str] = None
    ADMIN_PASSWORD: Optional[str] = None
    ADMIN_DISPLAY_NAME: Optional[str] = None

    class Config:
        env_file = ".env"


settings = Settings()
