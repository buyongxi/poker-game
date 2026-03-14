from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User, UserStatus, UserRole
from app.schemas.user import UserCreate
from typing import List, Optional
from app.config import settings


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_all_users(self) -> List[User]:
        result = await self.db.execute(select(User))
        return result.scalars().all()

    async def get_pending_users(self) -> List[User]:
        result = await self.db.execute(
            select(User).where(User.status == UserStatus.PENDING)
        )
        return result.scalars().all()

    async def activate_user(self, user_id: int) -> Optional[User]:
        user = await self.get_user_by_id(user_id)
        if user:
            user.status = UserStatus.ACTIVE
            await self.db.commit()
            await self.db.refresh(user)
        return user

    async def disable_user(self, user_id: int) -> Optional[User]:
        user = await self.get_user_by_id(user_id)
        if user:
            user.status = UserStatus.DISABLED
            await self.db.commit()
            await self.db.refresh(user)
        return user

    async def enable_user(self, user_id: int) -> Optional[User]:
        user = await self.get_user_by_id(user_id)
        if user:
            user.status = UserStatus.ACTIVE
            await self.db.commit()
            await self.db.refresh(user)
        return user

    async def set_admin(self, user_id: int, is_admin: bool) -> Optional[User]:
        user = await self.get_user_by_id(user_id)
        if user:
            user.role = UserRole.ADMIN if is_admin else UserRole.USER
            await self.db.commit()
            await self.db.refresh(user)
        return user

    async def can_register(self) -> bool:
        """Check if new user registration is allowed."""
        result = await self.db.execute(select(User))
        users = result.scalars().all()
        return len(users) < settings.MAX_USERS

    async def create_initial_admin(
        self,
        username: str = "admin",
        password: str = "admin123",
        display_name: str = "管理员"
    ) -> Optional[User]:
        """Create initial admin user if no users exist."""
        result = await self.db.execute(select(User))
        if result.scalars().first():
            return None

        import bcrypt

        admin = User(
            username=username,
            password_hash=bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
            display_name=display_name,
            status=UserStatus.ACTIVE,
            role=UserRole.ADMIN
        )
        self.db.add(admin)
        await self.db.commit()
        await self.db.refresh(admin)
        return admin
