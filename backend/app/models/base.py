from datetime import datetime
from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """Abstract base for all models."""
    pass

class TimestampMixin:
    """ Mixin for timestamp columns."""
    created_at = Column(DateTime(timezone=True), default=datetime.now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now, nullable=False)