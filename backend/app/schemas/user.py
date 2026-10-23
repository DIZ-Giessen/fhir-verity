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


class UserDirectoryEntry(BaseModel):
    """Minimal user info for picking whom to share a server with."""

    id: UUID
    username: str | None = None
    full_name: str | None = None
    role: str
    model_config = ConfigDict(from_attributes=True)


class AuthConfigRead(BaseModel):
    """Public auth settings the frontend needs before anyone is signed in."""

    auth_enabled: bool


class LogoutResult(BaseModel):
    """logout_url: Keycloak end-session URL the browser should open next."""

    status: str = "ok"
    logout_url: str | None = None


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
