-- Fleet node agent executor, telemetry and resource policy extension.
-- Safe to run repeatedly through PgBouncer on DbOmniFleet.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE "TbUpdatePlans"
    ADD COLUMN IF NOT EXISTS requested_by TEXT,
    ADD COLUMN IF NOT EXISTS requested_from_host TEXT REFERENCES "TbHosts"(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS executor_host_id TEXT REFERENCES "TbHosts"(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS target_command TEXT,
    ADD COLUMN IF NOT EXISTS command_args JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS execution_profile TEXT NOT NULL DEFAULT 'interactive',
    ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 100,
    ADD COLUMN IF NOT EXISTS lease_owner TEXT,
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS max_attempts INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS execution_output JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS rollback_ref TEXT,
    ADD COLUMN IF NOT EXISTS idempotency_key TEXT;

UPDATE "TbUpdatePlans"
SET requested_by = COALESCE(requested_by, approved_by, 'operator'),
    command_args = COALESCE(command_args, '[]'::jsonb),
    execution_profile = COALESCE(execution_profile, 'interactive'),
    execution_output = COALESCE(execution_output, '{}'::jsonb),
    priority = COALESCE(priority, 100),
    attempt_count = COALESCE(attempt_count, 0),
    max_attempts = COALESCE(max_attempts, 1)
WHERE requested_by IS NULL
   OR command_args IS NULL
   OR execution_profile IS NULL
   OR execution_output IS NULL
   OR priority IS NULL
   OR attempt_count IS NULL
   OR max_attempts IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'CkTbUpdatePlansApprovalState'
    ) THEN
        ALTER TABLE "TbUpdatePlans"
            ADD CONSTRAINT "CkTbUpdatePlansApprovalState"
            CHECK (approval_state IN ('pending', 'approved', 'rejected', 'cancelled'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'CkTbUpdatePlansExecutionState'
    ) THEN
        ALTER TABLE "TbUpdatePlans"
            ADD CONSTRAINT "CkTbUpdatePlansExecutionState"
            CHECK (execution_state IN ('not-started', 'queued', 'claimed', 'running', 'retry', 'succeeded', 'failed', 'cancelled', 'blocked'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'CkTbUpdatePlansApprovedMetadata'
    ) THEN
        ALTER TABLE "TbUpdatePlans"
            ADD CONSTRAINT "CkTbUpdatePlansApprovedMetadata"
            CHECK (
                approval_state <> 'approved'
                OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)
            );
    END IF;
END $$;

DROP INDEX IF EXISTS "UqTbUpdatePlansIdempotencyKey";
CREATE UNIQUE INDEX "UqTbUpdatePlansIdempotencyKey"
    ON "TbUpdatePlans"(idempotency_key);

CREATE INDEX IF NOT EXISTS "IdxTbUpdatePlansAgentQueue"
    ON "TbUpdatePlans"(host_id, approval_state, execution_state, priority, created_at)
    WHERE approval_state = 'approved'
      AND execution_state IN ('queued', 'retry');

CREATE INDEX IF NOT EXISTS "IdxTbUpdatePlansLease"
    ON "TbUpdatePlans"(lease_owner, lease_expires_at)
    WHERE lease_owner IS NOT NULL;

CREATE TABLE IF NOT EXISTS "TbFleetCommands" (
    command_key TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    local_invocation TEXT NOT NULL,
    default_profile TEXT NOT NULL DEFAULT 'interactive',
    requires_approval BOOLEAN NOT NULL DEFAULT true,
    enabled BOOLEAN NOT NULL DEFAULT true,
    timeout_seconds INTEGER NOT NULL DEFAULT 900,
    allowed_host_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (jsonb_typeof(allowed_host_ids) = 'array'),
    CHECK (timeout_seconds BETWEEN 1 AND 86400)
);

CREATE TABLE IF NOT EXISTS "TbNodeTelemetry" (
    id BIGSERIAL PRIMARY KEY,
    host_id TEXT NOT NULL REFERENCES "TbHosts"(id) ON DELETE CASCADE,
    observer_host_id TEXT REFERENCES "TbHosts"(id) ON DELETE SET NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    agent_id TEXT,
    health_status TEXT NOT NULL,
    cpu_count INTEGER,
    load_1m NUMERIC,
    load_5m NUMERIC,
    load_15m NUMERIC,
    memory_total_bytes BIGINT,
    memory_available_bytes BIGINT,
    memory_used_percent NUMERIC,
    swap_used_percent NUMERIC,
    disk_root_total_bytes BIGINT,
    disk_root_used_bytes BIGINT,
    disk_root_used_percent NUMERIC,
    disk_read_bytes BIGINT,
    disk_write_bytes BIGINT,
    service_health JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (health_status IN ('healthy', 'degraded', 'critical', 'offline', 'unknown'))
);

CREATE INDEX IF NOT EXISTS "IdxTbNodeTelemetryHostObserved"
    ON "TbNodeTelemetry"(host_id, observed_at DESC);

CREATE INDEX IF NOT EXISTS "IdxTbNodeTelemetryHealth"
    ON "TbNodeTelemetry"(health_status, observed_at DESC);

CREATE TABLE IF NOT EXISTS "TbNodeResourcePolicies" (
    host_id TEXT PRIMARY KEY REFERENCES "TbHosts"(id) ON DELETE CASCADE,
    max_parallel_jobs INTEGER NOT NULL DEFAULT 1,
    max_load_per_cpu NUMERIC NOT NULL DEFAULT 2.0,
    max_memory_used_percent NUMERIC NOT NULL DEFAULT 85,
    max_disk_root_used_percent NUMERIC NOT NULL DEFAULT 88,
    max_disk_write_bytes_per_cycle BIGINT,
    allowed_profiles JSONB NOT NULL DEFAULT '["interactive"]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (max_parallel_jobs >= 1),
    CHECK (jsonb_typeof(allowed_profiles) = 'array')
);

CREATE UNIQUE INDEX IF NOT EXISTS "UqTbConfigItemsScopeHostKeyNullSafe"
    ON "TbConfigItems" (
        COALESCE(scope_id, '__global__'),
        COALESCE(host_id, '__global__'),
        key
    );

CREATE UNIQUE INDEX IF NOT EXISTS "UqTbSlashCommandBindingsNullSafe"
    ON "TbSlashCommandBindings" (
        command_id,
        COALESCE(scope_id, '__global__'),
        COALESCE(host_id, '__global__')
    );

INSERT INTO "TbFleetCommands" (
    command_key, description, local_invocation, default_profile,
    requires_approval, enabled, timeout_seconds, allowed_host_ids, metadata
)
VALUES
    (
        'omni.noop',
        'Safe no-op used for fleet agent validation.',
        'python3 -c "print(''omni.noop ok'')"',
        'interactive',
        true,
        true,
        60,
        '["atius-srv-1","atius-srv-2","atius-srv-3"]'::jsonb,
        '{"kind":"validation"}'::jsonb
    ),
    (
        'omni.fleet.heartbeat',
        'Internal heartbeat and telemetry collection.',
        'internal:heartbeat',
        'interactive',
        false,
        true,
        60,
        '["atius-srv-1","atius-srv-2","atius-srv-3"]'::jsonb,
        '{"kind":"internal"}'::jsonb
    ),
    (
        'omni.resource.snapshot',
        'Collect SRV-1 resource-governor snapshot.',
        'python3 {repo}/modules/srv1-ops/scripts/resource-governor-snapshot.py',
        'interactive',
        true,
        true,
        300,
        '["atius-srv-1"]'::jsonb,
        '{"kind":"resource-governor","scope":"srv1-ops"}'::jsonb
    ),
    (
        'ubuntu-dark-theme.apply',
        'Reserved command key for the Ubuntu 24.04 dark theme module once its harness is finalized.',
        'bash {repo}/dark-theme-ubuntu/repair.sh',
        'interactive',
        true,
        false,
        1800,
        '["atius-srv-1","atius-srv-2","atius-srv-3"]'::jsonb,
        '{"kind":"desktop-theme","status":"disabled-until-cli-anything-harness"}'::jsonb
    )
ON CONFLICT (command_key) DO UPDATE SET
    description = EXCLUDED.description,
    local_invocation = EXCLUDED.local_invocation,
    default_profile = EXCLUDED.default_profile,
    requires_approval = EXCLUDED.requires_approval,
    enabled = EXCLUDED.enabled,
    timeout_seconds = EXCLUDED.timeout_seconds,
    allowed_host_ids = EXCLUDED.allowed_host_ids,
    metadata = EXCLUDED.metadata,
    updated_at = now();

INSERT INTO "TbNodeResourcePolicies" (
    host_id, max_parallel_jobs, max_load_per_cpu, max_memory_used_percent,
    max_disk_root_used_percent, allowed_profiles, metadata
)
SELECT id, 1, 2.0, 85, 88, '["interactive"]'::jsonb, '{"source":"m004-default"}'::jsonb
FROM "TbHosts"
WHERE id IN ('atius-srv-1', 'atius-srv-2', 'atius-srv-3')
ON CONFLICT (host_id) DO UPDATE SET
    max_parallel_jobs = EXCLUDED.max_parallel_jobs,
    max_load_per_cpu = EXCLUDED.max_load_per_cpu,
    max_memory_used_percent = EXCLUDED.max_memory_used_percent,
    max_disk_root_used_percent = EXCLUDED.max_disk_root_used_percent,
    allowed_profiles = EXCLUDED.allowed_profiles,
    metadata = EXCLUDED.metadata,
    updated_at = now();
