from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.database import get_db
from app.schemas.user import UserResponse
from app.services.user_service import UserService
from app.api.auth import get_current_admin_user

router = APIRouter()


@router.get("/pending", response_model=List[UserResponse])
async def list_pending_users(
    current_user = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """List pending users (admin only)."""
    user_service = UserService(db)
    users = await user_service.get_pending_users()
    return users


@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: int,
    current_user = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Activate a user (admin only)."""
    user_service = UserService(db)
    user = await user_service.activate_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"message": "用户已激活"}


@router.post("/users/{user_id}/disable")
async def disable_user(
    user_id: int,
    current_user = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Disable a user (admin only)."""
    user_service = UserService(db)
    user = await user_service.disable_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"message": "用户已禁用"}


@router.post("/users/{user_id}/enable")
async def enable_user(
    user_id: int,
    current_user = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Enable a user (admin only)."""
    user_service = UserService(db)
    user = await user_service.enable_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"message": "用户已启用"}


@router.post("/users/{user_id}/set-admin")
async def set_admin(
    user_id: int,
    is_admin: bool = True,
    current_user = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Set user as admin (admin only)."""
    user_service = UserService(db)
    user = await user_service.set_admin(user_id, is_admin)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"message": "已更新用户权限"}


@router.post("/init-admin")
async def init_admin(
    username: str = Body("admin", embed=True),
    password: str = Body("admin123", embed=True),
    display_name: str = Body("管理员", embed=True),
    db: AsyncSession = Depends(get_db)
):
    """Create initial admin user if no users exist."""
    user_service = UserService(db)
    admin = await user_service.create_initial_admin(username, password, display_name)
    if admin:
        return {"message": "管理员账户已创建", "username": username}
    return {"message": "用户已存在，无法创建初始管理员"}
