-- migrations/001_create_tables.sql
-- Sprint 3: Execution History
--
-- Run this ONCE to set up the database.
--
-- Option A — SQL Server Management Studio (SSMS):
--   File > Open > this file, then press F5
--
-- Option B — sqlcmd in PowerShell:
--   sqlcmd -S localhost -E -i migrations\001_create_tables.sql
--
-- Option C — Python helper (from backend folder with venv active):
--   python -c "from database import run_migration; import asyncio; asyncio.run(run_migration())"
-- ---------------------------------------------------------------------------

-- 1. Create database if it doesn't exist
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'ai_cost_router')
BEGIN
    CREATE DATABASE ai_cost_router;
    PRINT 'Database ai_cost_router created.';
END
ELSE
BEGIN
    PRINT 'Database ai_cost_router already exists.';
END
GO

USE ai_cost_router;
GO

-- 2. execution_logs table
--    Every task routed through the system is logged here.
--    tenant_id is included from day one for future multi-tenant support.

IF NOT EXISTS (
    SELECT 1 FROM sys.tables WHERE name = N'execution_logs' AND schema_id = SCHEMA_ID('dbo')
)
BEGIN
    CREATE TABLE dbo.execution_logs (
        id                     UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_logs_id        DEFAULT NEWID(),
        tenant_id              UNIQUEIDENTIFIER NOT NULL CONSTRAINT DF_logs_tenant     DEFAULT 'c3b9b472-5a21-4d32-bb12-9e32f52341a9',
        task_type              NVARCHAR(100)    NOT NULL,
        route                  NVARCHAR(20)     NOT NULL,   -- 'local' | 'small' | 'premium'
        routing_reason         NVARCHAR(MAX)    NULL,
        estimated_cost_usd     DECIMAL(18, 8)   NOT NULL CONSTRAINT DF_logs_cost      DEFAULT 0,
        savings_vs_premium_usd DECIMAL(18, 8)   NOT NULL CONSTRAINT DF_logs_savings   DEFAULT 0,
        estimated_latency_ms   INT              NOT NULL CONSTRAINT DF_logs_latency   DEFAULT 0,
        tokens_used            INT              NOT NULL CONSTRAINT DF_logs_tokens    DEFAULT 0,
        execution_method       NVARCHAR(100)    NULL,
        created_at             DATETIME2        NOT NULL CONSTRAINT DF_logs_created   DEFAULT GETUTCDATE(),

        CONSTRAINT PK_execution_logs PRIMARY KEY CLUSTERED (id)
    );

    -- Indexes for the queries used in /analytics and /history
    CREATE INDEX IX_logs_tenant     ON dbo.execution_logs (tenant_id);
    CREATE INDEX IX_logs_created_at ON dbo.execution_logs (created_at DESC);
    CREATE INDEX IX_logs_route      ON dbo.execution_logs (route);

    PRINT 'Table dbo.execution_logs created with indexes.';
END
ELSE
BEGIN
    PRINT 'Table dbo.execution_logs already exists — skipped.';
END
GO

PRINT 'Migration 001 complete.';
GO
