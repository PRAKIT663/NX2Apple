-- Persistent storage for one-time activation codes. Store only hashes of secrets.
CREATE TABLE IF NOT EXISTS licenses (
    id TEXT PRIMARY KEY,
    game TEXT NOT NULL,
    code_hash TEXT NOT NULL UNIQUE,
    expires_at INTEGER NOT NULL,
    installation_hash TEXT,
    revoked INTEGER NOT NULL DEFAULT 0 CHECK (revoked IN (0, 1))
);

CREATE UNIQUE INDEX IF NOT EXISTS active_installation
ON licenses (game, installation_hash) WHERE revoked = 0;
