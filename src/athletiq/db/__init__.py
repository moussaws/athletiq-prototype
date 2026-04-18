"""Relational persistence layer (SQLAlchemy 2.0).

The prototype persists AHP pairwise preferences and the squads solved from
them. The default backend is SQLite (so the app runs zero-config); production
targets PostgreSQL via the ``DATABASE_URL`` environment variable:

    DATABASE_URL=postgresql+psycopg://user:pw@host:5432/athletiq

Tables are created on startup via ``Base.metadata.create_all``. Alembic is
listed in ``pyproject.toml`` for the v2 schema-evolution story.
"""

from athletiq.db.models import AhpPreference, Base, SavedSquad
from athletiq.db.session import SessionLocal, engine, get_db, init_db

__all__ = [
    "AhpPreference",
    "Base",
    "SavedSquad",
    "SessionLocal",
    "engine",
    "get_db",
    "init_db",
]
