-- Omni Fleet governance profiles, observations, drift and update profile schema.
-- Raw credentials and tokens must stay outside this schema; use secret_ref only.

CREATE TABLE IF NOT EXISTS "TbDesiredStateProfiles" (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'fleet',
    owner TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    source TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (status IN ('active', 'draft', 'deprecated', 'disabled')),
    CHECK (scope IN ('fleet', 'host', 'group'))
);

CREATE TABLE IF NOT EXISTS "TbDesiredStateRules" (
    id BIGSERIAL PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES "TbDesiredStateProfiles"(id) ON DELETE CASCADE,
    host_id TEXT REFERENCES "TbHosts"(id) ON DELETE CASCADE,
    target_kind TEXT NOT NULL,
    target_name TEXT NOT NULL,
    rule_mode TEXT NOT NULL DEFAULT 'required',
    desired_version TEXT,
    manager TEXT,
    source TEXT,
    selector JSONB NOT NULL DEFAULT '{}'::jsonb,
    assertions JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (target_kind IN ('program', 'package', 'repository', 'policy', 'customization', 'service', 'container')),
    CHECK (rule_mode IN ('required', 'forbidden', 'pinned', 'held', 'manual'))
);

CREATE TABLE IF NOT EXISTS "TbRepositoryProfiles" (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'fleet',
    owner TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "TbRepositorySources" (
    id BIGSERIAL PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES "TbRepositoryProfiles"(id) ON DELETE CASCADE,
    host_id TEXT REFERENCES "TbHosts"(id) ON DELETE CASCADE,
    manager TEXT NOT NULL DEFAULT 'apt',
    name TEXT NOT NULL,
    source_url TEXT,
    suites JSONB NOT NULL DEFAULT '[]'::jsonb,
    components JSONB NOT NULL DEFAULT '[]'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT true,
    keyring_ref TEXT,
    secret_ref TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "TbProgramObservations" (
    id BIGSERIAL PRIMARY KEY,
    host_id TEXT NOT NULL REFERENCES "TbHosts"(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    install_type TEXT NOT NULL,
    manager TEXT NOT NULL,
    current_version TEXT,
    source TEXT,
    raw_ref TEXT,
    confidence TEXT NOT NULL DEFAULT 'observed',
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS "TbDriftFindings" (
    id BIGSERIAL PRIMARY KEY,
    profile_id TEXT REFERENCES "TbDesiredStateProfiles"(id) ON DELETE SET NULL,
    rule_id BIGINT REFERENCES "TbDesiredStateRules"(id) ON DELETE SET NULL,
    host_id TEXT REFERENCES "TbHosts"(id) ON DELETE CASCADE,
    target_kind TEXT NOT NULL,
    target_name TEXT NOT NULL,
    drift_status TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    recommended_action JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    CHECK (drift_status IN ('ok', 'missing', 'version-drift', 'source-drift', 'forbidden-present', 'unknown', 'blocked')),
    CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical'))
);

CREATE TABLE IF NOT EXISTS "TbUpdateProfiles" (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'fleet',
    approval_policy TEXT NOT NULL DEFAULT 'manual',
    rollout_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    allowed_command_keys JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (approval_policy IN ('manual', 'scheduled-manual', 'blocked'))
);

CREATE INDEX IF NOT EXISTS "IdxTbDesiredStateRulesProfileKind"
    ON "TbDesiredStateRules"(profile_id, target_kind, target_name);

CREATE INDEX IF NOT EXISTS "IdxTbRepositorySourcesProfile"
    ON "TbRepositorySources"(profile_id, manager, name);

CREATE INDEX IF NOT EXISTS "IdxTbProgramObservationsHostName"
    ON "TbProgramObservations"(host_id, name, observed_at DESC);

CREATE INDEX IF NOT EXISTS "IdxTbDriftFindingsHostStatus"
    ON "TbDriftFindings"(host_id, drift_status, created_at DESC);

