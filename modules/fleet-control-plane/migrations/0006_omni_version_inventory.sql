-- Omni Srv Admin per-computer version inventory.
-- Tracks installed omni-srv-admin state on each computer and the GitHub release
-- version it is expected to match. Values are observations, not secrets.

CREATE TABLE IF NOT EXISTS "TbVersion" (
    id BIGSERIAL PRIMARY KEY,
    host_id TEXT NOT NULL REFERENCES "TbHosts"(id) ON DELETE CASCADE,
    component TEXT NOT NULL DEFAULT 'omni-srv-admin',
    installed_version TEXT,
    git_branch TEXT,
    git_commit TEXT,
    git_dirty BOOLEAN NOT NULL DEFAULT false,
    github_version TEXT,
    github_commit TEXT,
    source TEXT NOT NULL DEFAULT 'omni-fleet-agent',
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT "UqTbVersionHostComponent" UNIQUE (host_id, component),
    CONSTRAINT "CkTbVersionComponent" CHECK (component <> ''),
    CONSTRAINT "CkTbVersionSource" CHECK (source <> '')
);

CREATE INDEX IF NOT EXISTS "IdxTbVersionGithubVersion"
    ON "TbVersion"(github_version, component);

CREATE INDEX IF NOT EXISTS "IdxTbVersionObservedAt"
    ON "TbVersion"(observed_at DESC);

INSERT INTO "TbVersion" (host_id, component, source, metadata)
SELECT "TbHosts".id, 'omni-srv-admin', 'migration',
       '{"github_repo":"giovannimnz/omni-srv-admin","expected_transport":"vpn","db_endpoint":"10.11.1.11:6432"}'::jsonb
FROM "TbHosts"
ON CONFLICT (host_id, component) DO UPDATE SET
    metadata = "TbVersion".metadata || EXCLUDED.metadata,
    observed_at = now();
