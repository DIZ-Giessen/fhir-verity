"""Model for User"""

import enum
import uuid

from sqlalchemy import Boolean, Column, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    """
    Enum for user roles in the application.

    - viewer: Can view resources but cannot make changes.
    - editor: Can view and edit resources, but has limited administrative privileges.
    - admin: Has full administrative access to all resources and settings.

    Assign roles to users based on their responsibilities and required access level.
    """

    viewer = "viewer"
    editor = "editor"
    admin = "admin"


class User(Base, TimestampMixin):
    """Local mirror of a Keycloak user, provisioned just-in-time on first login."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keycloak_sub = Column(String, nullable=False, unique=True, index=True)
    username = Column(String, nullable=True)
    email = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    email_notifications_enabled = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Stored as plain string (not a PG enum) to keep migrations trivial.
    role = Column(String, nullable=False, default=UserRole.viewer.value)
