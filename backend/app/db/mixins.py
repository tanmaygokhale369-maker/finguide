"""
Shared model mixins.
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

# Postgres's now() returns the *transaction's* start time — identical for
# every row inserted within the same transaction (routine with our
# savepoint-based test sessions, and possible in production with batched
# inserts). clock_timestamp() returns the true wall-clock time at each
# statement, which is what "created_at" is supposed to mean, and is
# required for any code that orders rows by created_at to determine
# actual sequence (e.g. metrics history, "most recent value" reasoning).
_NOW = func.clock_timestamp()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=_NOW,
        onupdate=_NOW,
        nullable=False,
    )
