"""
database.py - SQL Server connection and query helpers for AI Cost Router.

Uses pyodbc with Windows Authentication (no credentials needed for local dev).
All blocking pyodbc calls are wrapped in asyncio.to_thread so FastAPI stays
fully non-blocking.

Connection is configured via .env:
  DB_SERVER   — default: localhost
  DB_NAME     — default: ai_cost_router
  DB_DRIVER   — default: ODBC Driver 18 for SQL Server
  DATABASE_URL — full override (optional)

Graceful degradation: every public async function catches exceptions and
prints a warning rather than crashing the API, so the router keeps working
even if the database is unavailable.
"""

import os
import asyncio
import pyodbc


# ── Connection string ─────────────────────────────────────────────────────────

def _build_conn_str() -> str:
    # Full override
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    server   = os.getenv("DB_SERVER",  "localhost")
    database = os.getenv("DB_NAME",    "ai_cost_router")
    driver   = os.getenv("DB_DRIVER",  "ODBC Driver 18 for SQL Server")

    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"Trusted_Connection=yes;"
        f"TrustServerCertificate=yes;"
    )


def _connect() -> pyodbc.Connection:
    return pyodbc.connect(_build_conn_str(), timeout=5)


# ── Migration helper ──────────────────────────────────────────────────────────

def _run_migration_sync() -> None:
    """Run 001_create_tables.sql against a temporary master connection."""
    migration_path = os.path.join(os.path.dirname(__file__), "migrations", "001_create_tables.sql")
    with open(migration_path, "r") as f:
        sql = f.read()

    # Connect to master first (database may not exist yet)
    server = os.getenv("DB_SERVER", "localhost")
    driver = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE=master;"
        f"Trusted_Connection=yes;"
        f"TrustServerCertificate=yes;"
    )
    conn = pyodbc.connect(conn_str, timeout=10, autocommit=True)
    try:
        cursor = conn.cursor()
        # Split on GO statements (T-SQL batch separator)
        batches = [b.strip() for b in sql.split("\nGO") if b.strip()]
        for batch in batches:
            if batch:
                try:
                    cursor.execute(batch)
                except Exception:
                    pass  # PRINT statements etc. may raise benign errors
    finally:
        conn.close()


async def run_migration() -> None:
    """Public entry point — run from CLI or startup."""
    await asyncio.to_thread(_run_migration_sync)
    print("[DB] Migration complete.")


# ── Sync query functions (called via asyncio.to_thread) ───────────────────────

def _log_execution_sync(row: dict) -> None:
    sql = """
        INSERT INTO dbo.execution_logs
            (tenant_id, task_type, route, routing_reason,
             estimated_cost_usd, savings_vs_premium_usd,
             estimated_latency_ms, tokens_used, execution_method)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (
            row["tenant_id"],
            row["task_type"],
            row["route"],
            row["routing_reason"],
            row["estimated_cost_usd"],
            row["savings_vs_premium_usd"],
            row["estimated_latency_ms"],
            row["tokens_used"],
            row["execution_method"],
        ))
        conn.commit()
    finally:
        conn.close()


def _get_history_sync(limit: int) -> list[dict]:
    sql = """
        SELECT TOP (?)
            CAST(id AS NVARCHAR(36))        AS id,
            CAST(tenant_id AS NVARCHAR(36)) AS tenant_id,
            task_type, route, routing_reason,
            CAST(estimated_cost_usd     AS FLOAT) AS estimated_cost_usd,
            CAST(savings_vs_premium_usd AS FLOAT) AS savings_vs_premium_usd,
            estimated_latency_ms, tokens_used, execution_method,
            CONVERT(NVARCHAR(30), created_at, 127)  AS created_at
        FROM dbo.execution_logs
        ORDER BY created_at DESC
    """
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (limit,))
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def _get_analytics_sync() -> dict:
    conn = _connect()
    try:
        cursor = conn.cursor()

        # All-time totals
        cursor.execute("""
            SELECT
                COUNT(*)                                  AS total_tasks,
                COALESCE(SUM(estimated_cost_usd),      0) AS total_cost,
                COALESCE(SUM(savings_vs_premium_usd),  0) AS total_savings
            FROM dbo.execution_logs
        """)
        row = cursor.fetchone()
        total_tasks  = row[0]
        total_cost   = float(row[1])
        total_savings = float(row[2])

        # Daily savings — last 30 days
        cursor.execute("""
            SELECT
                CONVERT(NVARCHAR(10), created_at, 23)        AS day,
                CAST(SUM(savings_vs_premium_usd) AS FLOAT)   AS daily_savings,
                COUNT(*)                                      AS task_count
            FROM dbo.execution_logs
            WHERE created_at >= DATEADD(day, -30, GETUTCDATE())
            GROUP BY CONVERT(NVARCHAR(10), created_at, 23)
            ORDER BY day ASC
        """)
        daily_cols = [d[0] for d in cursor.description]
        daily = [dict(zip(daily_cols, r)) for r in cursor.fetchall()]

        # Breakdown by route
        cursor.execute("""
            SELECT
                route,
                COUNT(*)                                    AS task_count,
                CAST(SUM(savings_vs_premium_usd) AS FLOAT) AS savings
            FROM dbo.execution_logs
            GROUP BY route
        """)
        by_route = {}
        for r in cursor.fetchall():
            by_route[r[0]] = {"count": r[1], "savings": float(r[2])}

        premium_equiv = total_cost + total_savings
        savings_pct   = (total_savings / premium_equiv * 100) if premium_equiv > 0 else 0.0

        return {
            "total_tasks":       total_tasks,
            "total_cost_usd":    round(total_cost, 6),
            "total_savings_usd": round(total_savings, 6),
            "savings_percent":   round(savings_pct, 1),
            "by_route":          by_route,
            "daily_savings":     daily,
        }
    finally:
        conn.close()


# ── Async public API ──────────────────────────────────────────────────────────

DEFAULT_TENANT = "c3b9b472-5a21-4d32-bb12-9e32f52341a9"


async def log_execution(row: dict) -> None:
    """Log one task execution. Never raises — failures are printed, not thrown."""
    row.setdefault("tenant_id", DEFAULT_TENANT)
    try:
        await asyncio.to_thread(_log_execution_sync, row)
    except Exception as exc:
        print(f"[DB] log_execution skipped: {exc}")


async def get_history(limit: int = 50) -> list[dict]:
    """Return the most recent `limit` executions, newest first."""
    try:
        return await asyncio.to_thread(_get_history_sync, limit)
    except Exception as exc:
        print(f"[DB] get_history failed: {exc}")
        return []


async def get_analytics() -> dict:
    """Return aggregate stats and daily savings for the last 30 days."""
    try:
        return await asyncio.to_thread(_get_analytics_sync)
    except Exception as exc:
        print(f"[DB] get_analytics failed: {exc}")
        return {
            "total_tasks": 0, "total_cost_usd": 0.0,
            "total_savings_usd": 0.0, "savings_percent": 0.0,
            "by_route": {}, "daily_savings": [],
        }
