"""
SQLAlchemy declarative base.

A single shared Base so Alembic's autogenerate can discover every model's
metadata via one import (see app/models/__init__.py and migrations/env.py).
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
