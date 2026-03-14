from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.user import User, UserStatus
from app.schemas.user import UserCreate
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Tuple


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

    def get_password_hash(self, password: str) -> str:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    async def create_user(self, user_data: UserCreate) -> User:
        """Create a new user with pending status."""
        hashed_password = self.get_password_hash(user_data.password)
        user = User(
            username=user_data.username,
            password_hash=hashed_password,
            display_name=user_data.display_name,
            status=UserStatus.PENDING
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate(self, username: str, password: str) -> Tuple[Optional[User], str]:
        """
        Authenticate a user.
        Returns (user, error_message).
        """
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None, "用户名或密码错误"

        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60)
            return None, f"账户已锁定，请{remaining}分钟后再试"

        # Check if user is active
        if user.status == UserStatus.DISABLED:
            return None, "账户已被禁用"

        if user.status == UserStatus.PENDING:
            return None, "账户待审核，请等待管理员激活"

        # Verify password
        if not self.verify_password(password, user.password_hash):
            # Increment failed attempts
            user.failed_login_attempts += 1

            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=15)
                await self.db.commit()
                return None, "登录失败次数过多，账户已锁定15分钟"

            await self.db.commit()
            return None, "用户名或密码错误"

        # Reset failed attempts on successful login
        user.failed_login_attempts = 0
        user.locked_until = None
        await self.db.commit()

        return user, ""

    async def check_username_exists(self, username: str) -> bool:
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none() is not None
