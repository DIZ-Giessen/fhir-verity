"""Pydantic schema for the current authenticated user."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.user import UserRole


class UserRead(BaseModel):
    """User Model"""

    id: UUID
    keycloak_sub: str
    username: str | None = None
    email: str | None = None
    full_name: str | None = None
    role: str
    email_notifications_enabled: bool
    model_config = ConfigDict(from_attributes=True)


class AuthConfigRead(BaseModel):
    """Public auth settings the frontend needs before anyone is signed in."""

    auth_enabled: bool


class UserRoleUpdate(BaseModel):
    """
    Schema for updating the user's role.

    Fields:
        role (UserRole): The new role to assign to the user.
    """

    role: UserRole


class UserPreferencesUpdate(BaseModel):
    """
    Schema for updating a user's preferences.

    Fields:
        email_notifications_enabled (bool): Whether the user wants to receive email notifications.
    """

    email_notifications_enabled: bool
