"""SQLAlchemy declarative base for the app database."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""


__all__ = ["Base"]
