"""Pydantic schema for the current authenticated user."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    """User Model"""

    id: UUID
    keycloak_sub: str
    username: str | None = None
    email: str | None = None
    full_name: str | None = None
    role: str

    model_config = ConfigDict(from_attributes=True)
