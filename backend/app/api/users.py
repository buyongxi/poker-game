from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.database import get_db
from app.schemas.user import UserResponse
from app.services.user_service import UserService
from app.api.auth import get_current_active_user

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user = Depends(get_current_active_user)
):
    """Get current user info."""
    return current_user


@router.get("/", response_model=List[UserResponse])
async def list_users(
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List all users."""
    user_service = UserService(db)
    users = await user_service.get_all_users()
    return users
