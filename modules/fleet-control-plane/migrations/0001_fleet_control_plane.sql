-- Initial Omni Fleet Control Plane schema contract.
-- PostgreSQL target; execute only from the approved control-plane server path.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS hosts (
    id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    owner TEXT NOT NULL,
    status TEXT NOT NULL,
    provider TEXT NOT NULL,
    os TEXT NOT NULL,
    arch TEXT NOT NULL,
    ssh_target TEXT,
    vpn_ip INET,
    public_ip INET,
    inventory_file TEXT NOT NULL,
    inventory_hash TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS nodes (
    host_id TEXT PRIMARY KEY REFERENCES hosts(id) ON DELETE CASCADE,
    install_mode TEXT NOT NULL CHECK (install_mode IN ('server', 'node')),
    agent_version TEXT,
    health_status TEXT NOT NULL DEFAULT 'unknown',
    last_heartbeat_at TIMESTAMPTZ,
    last_heartbeat JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS programs (
    id BIGSERIAL PRIMARY KEY,
    host_id TEXT NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    install_type TEXT NOT NULL,
    current_version TEXT,
    source TEXT,
    managed_by TEXT NOT NULL,
    update_policy TEXT NOT NULL DEFAULT 'plan-first',
    observed_at TIMESTAMPTZ,
    UNIQUE (host_id, name, install_type)
);

CREATE TABLE IF NOT EXISTS versions (
    id BIGSERIAL PRIMARY KEY,
    program_id BIGINT NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
    current_version TEXT,
    desired_version TEXT,
    policy TEXT NOT NULL DEFAULT 'manual',
    pinned BOOLEAN NOT NULL DEFAULT false,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS update_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    host_id TEXT NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    program_id BIGINT REFERENCES programs(id) ON DELETE SET NULL,
    desired_version TEXT NOT NULL,
    dry_run_output JSONB NOT NULL DEFAULT '{}'::jsonb,
    approval_state TEXT NOT NULL DEFAULT 'pending',
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    execution_state TEXT NOT NULL DEFAULT 'not-started',
    audit_event_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS licenses (
    id BIGSERIAL PRIMARY KEY,
    program_name TEXT NOT NULL,
    scope TEXT NOT NULL,
    owner TEXT NOT NULL,
    status TEXT NOT NULL,
    expires_at DATE,
    seat_count INTEGER,
    secret_ref TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor TEXT NOT NULL,
    host_id TEXT REFERENCES hosts(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    result TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_nodes_health_status ON nodes(health_status);
CREATE INDEX IF NOT EXISTS idx_programs_host_name ON programs(host_id, name);
CREATE INDEX IF NOT EXISTS idx_update_plans_host_state ON update_plans(host_id, approval_state, execution_state);
CREATE INDEX IF NOT EXISTS idx_licenses_program_status ON licenses(program_name, status);
CREATE INDEX IF NOT EXISTS idx_audit_events_host_action ON audit_events(host_id, action, created_at DESC);
