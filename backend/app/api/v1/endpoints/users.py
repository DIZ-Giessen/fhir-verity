"""User administration: list users and manage roles (admin only)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.user import User, UserRole
from app.schemas.user import UserRead, UserRoleUpdate
from app.core.security import get_current_user
from app.schemas.user import UserPreferencesUpdate

router = APIRouter()


@router.get("/users", response_model=list[UserRead])
async def list_users(
    _: User = Depends(require_role(UserRole.admin.value)),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 200,
):
    """
    Returns a list of users in the system, ordered by creation date.

    Accessible only to admin users. Supports pagination via `skip` and `limit` parameters.
    """
    rows = (
        (
            await db.execute(
                select(User).order_by(User.created_at).offset(skip).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


@router.patch("/users/{user_id}/role", response_model=UserRead)
async def update_user_role(
    user_id: uuid.UUID,
    payload: UserRoleUpdate,
    current: User = Depends(require_role(UserRole.admin.value)),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a user's role.

    Only admins can update user roles. Cannot demote yourself from admin, or
    remove the last remaining admin role in the system.
    """
    target = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    new_role = payload.role.value

    if target.id == current.id and new_role != UserRole.admin.value:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "You cannot change your own admin role"
        )

    if target.role == UserRole.admin.value and new_role != UserRole.admin.value:
        admin_count = (
            await db.execute(
                select(func.count(User.id)).where(User.role == UserRole.admin.value)
            )
        ).scalar_one()
        if admin_count <= 1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Cannot demote the last remaining admin"
            )

    target.role = new_role
    await db.commit()
    await db.refresh(target)
    return target


@router.patch("/users/me/preferences", response_model=UserRead)
async def update_my_preferences(
    payload: UserPreferencesUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update the current user's preferences.

    Allows the currently authenticated user to update their personal preferences,
    such as whether they wish to receive email notifications.
    """
    user.email_notifications_enabled = payload.email_notifications_enabled
    await db.commit()
    await db.refresh(user)
    return user
