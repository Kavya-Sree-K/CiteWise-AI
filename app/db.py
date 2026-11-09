import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DB_URL = os.getenv("DATABASE_URL", "sqlite:///./knowledge.db")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})

@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False)

class Base(DeclarativeBase):
    pass


def upgrade_schema(bind=None):
    """Bring an EXISTING database up to date without losing data (no re-ingest needed):
    creates missing tables and adds missing columns. Safe to run on every start."""
    from sqlalchemy import inspect, text
    import app.models  # noqa: F401  (registers all tables)
    bind = bind or engine
    Base.metadata.create_all(bind)
    inspector = inspect(bind)
    with bind.begin() as conn:
        for table in Base.metadata.sorted_tables:
            have = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                ddl = f'ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(bind.dialect)}'
                default = getattr(getattr(col, "default", None), "arg", None)
                if isinstance(default, (int, float, str)) and not callable(default):
                    ddl += f" DEFAULT {default!r}"
                conn.execute(text(ddl))