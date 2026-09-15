from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
        return kwargs
    return {}


settings = get_settings()
engine = create_engine(settings.database_url, **_engine_kwargs(settings.database_url), future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    if engine.dialect.name == "sqlite":
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def init_db() -> None:
    from app.database import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _sqlite_column_names(table: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def _ensure_sqlite_columns() -> None:
    if engine.dialect.name != "sqlite":
        return
    statements: list[str] = []
    run_cols = _sqlite_column_names("runs")
    if run_cols and "llm_mode" not in run_cols:
        statements.append("ALTER TABLE runs ADD COLUMN llm_mode VARCHAR(16) DEFAULT 'live'")
    mutation_cols = _sqlite_column_names("mutations")
    if mutation_cols and "parse_failed" not in mutation_cols:
        statements.append("ALTER TABLE mutations ADD COLUMN parse_failed BOOLEAN DEFAULT 0")
    if mutation_cols and "position" not in mutation_cols:
        statements.append("ALTER TABLE mutations ADD COLUMN position INTEGER DEFAULT 0")
    exp_cols = _sqlite_column_names("experiments")
    if exp_cols:
        additions = {
            "dataset_version": "ALTER TABLE experiments ADD COLUMN dataset_version VARCHAR(64) DEFAULT '1.0'",
            "generator_models_json": "ALTER TABLE experiments ADD COLUMN generator_models_json TEXT DEFAULT '[]'",
            "verifier_models_json": "ALTER TABLE experiments ADD COLUMN verifier_models_json TEXT DEFAULT '[]'",
            "synonym_count": "ALTER TABLE experiments ADD COLUMN synonym_count INTEGER DEFAULT 5",
            "antonym_count": "ALTER TABLE experiments ADD COLUMN antonym_count INTEGER DEFAULT 5",
            "threshold": "ALTER TABLE experiments ADD COLUMN threshold FLOAT DEFAULT 0.5",
            "trials": "ALTER TABLE experiments ADD COLUMN trials INTEGER DEFAULT 1",
            "llm_mode": "ALTER TABLE experiments ADD COLUMN llm_mode VARCHAR(16) DEFAULT 'live'",
            "config_json": "ALTER TABLE experiments ADD COLUMN config_json TEXT DEFAULT '{}'",
            "completed_at": "ALTER TABLE experiments ADD COLUMN completed_at DATETIME",
        }
        for column, statement in additions.items():
            if column not in exp_cols:
                statements.append(statement)
    cond_cols = _sqlite_column_names("experiment_conditions")
    if cond_cols:
        if "generation_id" not in cond_cols:
            statements.append("ALTER TABLE experiment_conditions ADD COLUMN generation_id VARCHAR(36)")
        if "pair_type" not in cond_cols:
            statements.append("ALTER TABLE experiment_conditions ADD COLUMN pair_type VARCHAR(16) DEFAULT 'cross'")
        if "not_sure_rate" not in cond_cols:
            statements.append("ALTER TABLE experiment_conditions ADD COLUMN not_sure_rate FLOAT DEFAULT 0")
    gen_cols = _sqlite_column_names("experiment_generations")
    if gen_cols:
        if "integrity_ok" not in gen_cols:
            statements.append("ALTER TABLE experiment_generations ADD COLUMN integrity_ok BOOLEAN DEFAULT 1")
        if "error_message" not in gen_cols:
            statements.append("ALTER TABLE experiment_generations ADD COLUMN error_message TEXT DEFAULT ''")
        if "mutation_set_hash" not in gen_cols:
            statements.append("ALTER TABLE experiment_generations ADD COLUMN mutation_set_hash VARCHAR(64) DEFAULT ''")
    if not statements:
        return
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
