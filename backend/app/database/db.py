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
    if run_cols and "status" not in run_cols:
        statements.append("ALTER TABLE runs ADD COLUMN status VARCHAR(32) DEFAULT 'completed'")
    if run_cols and "analysis_error" not in run_cols:
        statements.append("ALTER TABLE runs ADD COLUMN analysis_error TEXT DEFAULT ''")
    if run_cols and "web_evidence_status" not in run_cols:
        statements.append("ALTER TABLE runs ADD COLUMN web_evidence_status VARCHAR(32) DEFAULT 'pending'")
    if run_cols and "web_evidence_error" not in run_cols:
        statements.append("ALTER TABLE runs ADD COLUMN web_evidence_error TEXT DEFAULT ''")
    if run_cols and "web_evidence_json" not in run_cols:
        statements.append("ALTER TABLE runs ADD COLUMN web_evidence_json TEXT DEFAULT ''")
    if run_cols and "ai_verdicts_json" not in run_cols:
        statements.append("ALTER TABLE runs ADD COLUMN ai_verdicts_json TEXT DEFAULT ''")
    if run_cols and "answer_ms" not in run_cols:
        statements.append("ALTER TABLE runs ADD COLUMN answer_ms FLOAT")
    if run_cols and "mutation_ms" not in run_cols:
        statements.append("ALTER TABLE runs ADD COLUMN mutation_ms FLOAT")
    if run_cols and "verify_ms" not in run_cols:
        statements.append("ALTER TABLE runs ADD COLUMN verify_ms FLOAT")
    if run_cols and "total_ms" not in run_cols:
        statements.append("ALTER TABLE runs ADD COLUMN total_ms FLOAT")
    if run_cols and "mutation_generator_model" not in run_cols:
        statements.append("ALTER TABLE runs ADD COLUMN mutation_generator_model VARCHAR(128)")
    if run_cols and "mutation_verifier_model" not in run_cols:
        statements.append("ALTER TABLE runs ADD COLUMN mutation_verifier_model VARCHAR(128)")
    if run_cols and "combined_risk_score" not in run_cols:
        statements.append("ALTER TABLE runs ADD COLUMN combined_risk_score FLOAT")
    if run_cols and "overall_verdict" not in run_cols:
        statements.append("ALTER TABLE runs ADD COLUMN overall_verdict VARCHAR(64)")
    mutation_cols = _sqlite_column_names("mutations")
    if mutation_cols and "parse_failed" not in mutation_cols:
        statements.append("ALTER TABLE mutations ADD COLUMN parse_failed BOOLEAN DEFAULT 0")
    if mutation_cols and "verified" not in mutation_cols:
        statements.append("ALTER TABLE mutations ADD COLUMN verified BOOLEAN DEFAULT 1")
    if mutation_cols and "position" not in mutation_cols:
        statements.append("ALTER TABLE mutations ADD COLUMN position INTEGER DEFAULT 0")
    if mutation_cols and "verdicts_json" not in mutation_cols:
        statements.append("ALTER TABLE mutations ADD COLUMN verdicts_json TEXT DEFAULT ''")
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
    eval_run_cols = _sqlite_column_names("evaluation_runs")
    if eval_run_cols and "summary_metrics_json" not in eval_run_cols:
        statements.append("ALTER TABLE evaluation_runs ADD COLUMN summary_metrics_json TEXT DEFAULT '{}'")

    eval_result_cols = _sqlite_column_names("evaluation_results")
    if eval_result_cols:
        result_additions = {
            "metaqa_score": "ALTER TABLE evaluation_results ADD COLUMN metaqa_score FLOAT",
            "metaqa_prediction": "ALTER TABLE evaluation_results ADD COLUMN metaqa_prediction VARCHAR(32)",
            "metaqa_outcome": "ALTER TABLE evaluation_results ADD COLUMN metaqa_outcome VARCHAR(32)",
            "web_evidence_score": "ALTER TABLE evaluation_results ADD COLUMN web_evidence_score FLOAT",
            "web_evidence_verdict": "ALTER TABLE evaluation_results ADD COLUMN web_evidence_verdict VARCHAR(32)",
            "web_evidence_prediction": "ALTER TABLE evaluation_results ADD COLUMN web_evidence_prediction VARCHAR(32)",
            "web_evidence_status": "ALTER TABLE evaluation_results ADD COLUMN web_evidence_status VARCHAR(32) DEFAULT 'not_run'",
            "web_evidence_outcome": "ALTER TABLE evaluation_results ADD COLUMN web_evidence_outcome VARCHAR(32)",
            "multi_model_consensus": "ALTER TABLE evaluation_results ADD COLUMN multi_model_consensus VARCHAR(32)",
            "multi_model_prediction": "ALTER TABLE evaluation_results ADD COLUMN multi_model_prediction VARCHAR(32)",
            "multi_model_status": "ALTER TABLE evaluation_results ADD COLUMN multi_model_status VARCHAR(32) DEFAULT 'not_run'",
            "multi_model_agreement": "ALTER TABLE evaluation_results ADD COLUMN multi_model_agreement FLOAT",
            "multi_model_outcome": "ALTER TABLE evaluation_results ADD COLUMN multi_model_outcome VARCHAR(32)",
            "combined_risk_score": "ALTER TABLE evaluation_results ADD COLUMN combined_risk_score FLOAT",
            "combined_verdict": "ALTER TABLE evaluation_results ADD COLUMN combined_verdict VARCHAR(64)",
            "combined_prediction": "ALTER TABLE evaluation_results ADD COLUMN combined_prediction VARCHAR(32)",
            "combined_outcome": "ALTER TABLE evaluation_results ADD COLUMN combined_outcome VARCHAR(32)",
            "component_details_json": "ALTER TABLE evaluation_results ADD COLUMN component_details_json TEXT DEFAULT '{}'",
            "latency_ms": "ALTER TABLE evaluation_results ADD COLUMN latency_ms FLOAT",
            "error": "ALTER TABLE evaluation_results ADD COLUMN error TEXT",
            "judge_label": "ALTER TABLE evaluation_results ADD COLUMN judge_label VARCHAR(32)",
            "judge_reasoning": "ALTER TABLE evaluation_results ADD COLUMN judge_reasoning TEXT",
            "judge_confidence": "ALTER TABLE evaluation_results ADD COLUMN judge_confidence FLOAT",
            "judge_status": "ALTER TABLE evaluation_results ADD COLUMN judge_status VARCHAR(32) DEFAULT 'not_run'",
            "reviewer1_label": "ALTER TABLE evaluation_results ADD COLUMN reviewer1_label VARCHAR(32)",
            "reviewer2_label": "ALTER TABLE evaluation_results ADD COLUMN reviewer2_label VARCHAR(32)",
            "adjudicated_label": "ALTER TABLE evaluation_results ADD COLUMN adjudicated_label VARCHAR(32)",
            "validation_status": "ALTER TABLE evaluation_results ADD COLUMN validation_status VARCHAR(32) DEFAULT 'legacy_inferred'",
        }
        for col, stmt in result_additions.items():
            if col not in eval_result_cols:
                statements.append(stmt)

    eval_metric_cols = _sqlite_column_names("evaluation_metrics")
    if eval_metric_cols:
        metric_additions = {
            "component": "ALTER TABLE evaluation_metrics ADD COLUMN component VARCHAR(32) DEFAULT 'metaqa'",
            "coverage": "ALTER TABLE evaluation_metrics ADD COLUMN coverage FLOAT DEFAULT 1.0",
            "abstained_examples": "ALTER TABLE evaluation_metrics ADD COLUMN abstained_examples INTEGER DEFAULT 0",
        }
        for col, stmt in metric_additions.items():
            if col not in eval_metric_cols:
                statements.append(stmt)

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
