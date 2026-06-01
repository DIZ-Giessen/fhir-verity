import enum
import uuid

from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin


class UserRole(str, enum.Enum):
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
    # Stored as plain string (not a PG enum) to keep migrations trivial.
    role = Column(String, nullable=False, default=UserRole.viewer.value)
