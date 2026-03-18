from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import get_settings
from pathlib import Path
import os
import sqlite3
import json
from datetime import datetime


_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _normalize_sqlite_url(url: str) -> str:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url

    db_path = url[len(prefix):]
    if db_path == ":memory:":
        return url

    # Keep absolute sqlite URLs unchanged.
    is_windows_drive = len(db_path) > 1 and db_path[1] == ":"
    if db_path.startswith("/") or db_path.startswith("\\") or is_windows_drive:
        return url

    absolute = (_BACKEND_ROOT / db_path.lstrip("./\\")).resolve()
    return f"sqlite:///{absolute.as_posix()}"


def _is_production_runtime() -> bool:
    env = str(os.getenv("ENVIRONMENT") or "").strip().lower()
    if env == "production":
        return True
    # Common cloud markers.
    return any(
        bool(os.getenv(key))
        for key in (
            "RENDER",
            "RENDER_SERVICE_ID",
            "RAILWAY_ENVIRONMENT",
            "VERCEL",
            "HEROKU_APP_NAME",
        )
    )


def _is_sqlite_url(url: str) -> bool:
    return str(url or "").lower().startswith("sqlite:///")


def _sqlite_file_from_url(url: str) -> Path | None:
    if not _is_sqlite_url(url):
        return None
    prefix = "sqlite:///"
    raw = str(url)[len(prefix):]
    if raw == ":memory:":
        return None
    if len(raw) > 1 and raw[1] == ":":
        return Path(raw)
    if raw.startswith("/") or raw.startswith("\\"):
        return Path(raw)
    return (_BACKEND_ROOT / raw).resolve()


def _resolve_database_url(settings) -> str:
    """Resolve primary DB URL from settings and common cloud aliases."""
    primary = str(getattr(settings, "DATABASE_URL", "") or "").strip()
    if primary:
        return primary

    # Defensive fallbacks for cloud providers / managed DB integrations.
    for key in (
        "POSTGRES_URL",
        "POSTGRESQL_URL",
        "POSTGRES_INTERNAL_URL",
        "RENDER_DATABASE_URL",
        "RENDER_POSTGRES_INTERNAL_URL",
    ):
        value = str(os.getenv(key) or "").strip()
        if value:
            return value
    return ""

settings = get_settings()

# Use the configured DATABASE_URL in production.
# Fall back to local SQLite only when DATABASE_URL is empty or still a placeholder.
db_url = _resolve_database_url(settings)
placeholder_tokens = (
    "YOUR_PRODUCTION_DB_HOST",
    "user:password@",
)
if not db_url or any(token in db_url for token in placeholder_tokens):
    db_url = "sqlite:///./algotrade.db"

db_url = _normalize_sqlite_url(db_url)

if _is_production_runtime() and _is_sqlite_url(db_url):
    raise RuntimeError(
        "Production requires a persistent DATABASE_URL (PostgreSQL). "
        "Refusing to start with SQLite because redeploys can lose data."
    )

# Accept Heroku/Render style postgres:// URLs.
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Configure SQLite connection with proper pooling settings
engine = create_engine(
    db_url, 
    connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
    pool_size=20,  # Increase from default 5
    max_overflow=40,  # Increase from default 10
    pool_pre_ping=True,  # Enable connection health checks
    pool_recycle=3600  # Recycle connections after 1 hour
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def bootstrap_sqlite_trade_data_if_needed() -> dict:
    """One-time bootstrap of trade tables from local SQLite into current primary DB.

    Runs only when:
    1) current DB is not SQLite, and
    2) target tables are empty, and
    3) source SQLite file exists.
    """
    if _is_sqlite_url(db_url):
        return {"status": "skipped", "reason": "target_db_is_sqlite"}

    source_path = Path(os.getenv("SQLITE_BOOTSTRAP_PATH", str((_BACKEND_ROOT / "local.db").resolve())))
    if not source_path.exists():
        return {"status": "skipped", "reason": "sqlite_source_missing", "source": str(source_path)}

    from app.models.trading import ActiveTrade, TradeReport, PaperTrade  # local import to avoid cycles

    target = SessionLocal()
    source_conn = None
    try:
        # If target already has rows, avoid duplicate migration on restart.
        existing_active = target.query(ActiveTrade).count()
        existing_reports = target.query(TradeReport).count()
        existing_paper = target.query(PaperTrade).count()
        if (existing_active + existing_reports + existing_paper) > 0:
            return {
                "status": "skipped",
                "reason": "target_not_empty",
                "active": existing_active,
                "reports": existing_reports,
                "paper": existing_paper,
            }

        source_conn = sqlite3.connect(str(source_path))
        source_conn.row_factory = sqlite3.Row
        cur = source_conn.cursor()

        migrated = {"active_trades": 0, "trade_reports": 0, "paper_trades": 0}

        def _coerce_dt(value):
            if value is None or isinstance(value, datetime):
                return value
            if isinstance(value, str):
                s = value.strip()
                if not s:
                    return None
                try:
                    return datetime.fromisoformat(s)
                except Exception:
                    return None
            return None

        def _coerce_json(value):
            if value is None:
                return None
            if isinstance(value, (dict, list)):
                return value
            if isinstance(value, str):
                s = value.strip()
                if not s:
                    return None
                try:
                    return json.loads(s)
                except Exception:
                    return None
            return None

        def has_table(name: str) -> bool:
            row = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (name,),
            ).fetchone()
            return row is not None

        if has_table("active_trades"):
            rows = cur.execute("SELECT * FROM active_trades").fetchall()
            for r in rows:
                target.add(
                    ActiveTrade(
                        id=r["id"],
                        trade_uid=r["trade_uid"],
                        symbol=r["symbol"],
                        side=r["side"],
                        status=r["status"],
                        trade_mode=r["trade_mode"],
                        entry_time=_coerce_dt(r["entry_time"]),
                        payload=_coerce_json(r["payload"]) or {},
                        created_at=_coerce_dt(r["created_at"]),
                        updated_at=_coerce_dt(r["updated_at"]),
                    )
                )
            migrated["active_trades"] = len(rows)

        if has_table("trade_reports"):
            rows = cur.execute("SELECT * FROM trade_reports").fetchall()
            for r in rows:
                target.add(
                    TradeReport(
                        id=r["id"],
                        symbol=r["symbol"],
                        side=r["side"],
                        quantity=r["quantity"],
                        entry_price=r["entry_price"],
                        exit_price=r["exit_price"],
                        pnl=r["pnl"],
                        pnl_percentage=r["pnl_percentage"],
                        strategy=r["strategy"],
                        status=r["status"],
                        entry_time=_coerce_dt(r["entry_time"]),
                        exit_time=_coerce_dt(r["exit_time"]),
                        trading_date=r["trading_date"],
                        meta=_coerce_json(r["meta"]),
                    )
                )
            migrated["trade_reports"] = len(rows)

        if has_table("paper_trades"):
            rows = cur.execute("SELECT * FROM paper_trades").fetchall()
            for r in rows:
                target.add(
                    PaperTrade(
                        id=r["id"],
                        user_id=r["user_id"],
                        symbol=r["symbol"],
                        index_name=r["index_name"],
                        side=r["side"],
                        signal_type=r["signal_type"],
                        quantity=r["quantity"],
                        entry_price=r["entry_price"],
                        current_price=r["current_price"],
                        stop_loss=r["stop_loss"],
                        target=r["target"],
                        status=r["status"],
                        exit_price=r["exit_price"],
                        pnl=r["pnl"],
                        pnl_percentage=r["pnl_percentage"],
                        strategy=r["strategy"],
                        signal_data=_coerce_json(r["signal_data"]),
                        entry_time=_coerce_dt(r["entry_time"]),
                        exit_time=_coerce_dt(r["exit_time"]),
                        trading_date=r["trading_date"],
                        updated_at=_coerce_dt(r["updated_at"]),
                    )
                )
            migrated["paper_trades"] = len(rows)

        target.commit()
        return {"status": "migrated", "source": str(source_path), **migrated}
    except Exception as exc:
        target.rollback()
        return {"status": "error", "error": str(exc), "source": str(source_path)}
    finally:
        if source_conn is not None:
            source_conn.close()
        target.close()

def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
