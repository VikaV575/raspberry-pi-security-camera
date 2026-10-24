-- Safe to re-run against the PostgreSQL database created earlier.
-- Files remain in uploads/ until the object-storage integration is added.

CREATE TABLE IF NOT EXISTS cameras (
    id TEXT PRIMARY KEY,
    name VARCHAR(100),
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE cameras ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS media (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    camera_id TEXT NOT NULL REFERENCES cameras(id),
    media_type TEXT NOT NULL CHECK (media_type IN ('image', 'video')),
    storage_key TEXT NOT NULL UNIQUE,
    size_bytes BIGINT CHECK (size_bytes >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- The dashboard already uses UUID strings for its media IDs. Preserve those
-- public IDs without changing the existing numeric database primary key.
ALTER TABLE media ADD COLUMN IF NOT EXISTS public_id TEXT;
ALTER TABLE media ADD COLUMN IF NOT EXISTS content_type TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_media_public_id ON media (public_id);
CREATE INDEX IF NOT EXISTS idx_media_camera_date
    ON media (camera_id, created_at DESC);

-- Retain flexible agent-specific command fields inside JSONB while indexing
-- their normalised lifecycle fields.
CREATE TABLE IF NOT EXISTS commands (
    id TEXT PRIMARY KEY,
    camera_id TEXT NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    command_type TEXT NOT NULL,
    status TEXT NOT NULL,
    record JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_commands_camera_date
    ON commands (camera_id, created_at DESC);

-- Prevent a deleted camera from being resurrected by the legacy JSON importer.
CREATE TABLE IF NOT EXISTS legacy_imports (
    source TEXT PRIMARY KEY,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
