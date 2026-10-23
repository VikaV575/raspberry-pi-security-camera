
CREATE TABLE IF NOT EXISTS cameras (
    id TEXT PRIMARY KEY,
    name VARCHAR(100),
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS media (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    camera_id TEXT NOT NULL REFERENCES cameras(id),

    media_type TEXT NOT NULL
        CHECK (media_type IN ('image', 'video')),

    storage_key TEXT NOT NULL UNIQUE,

    size_bytes BIGINT
        CHECK (size_bytes >= 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_media_camera_date
    ON media (camera_id, created_at DESC);
