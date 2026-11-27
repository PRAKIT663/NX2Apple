"""Persistent one-time activation for a trusted server-side caller."""

import hashlib
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path


class ActivationStore:
    def __init__(self, database: Path):
        self.database = database
        with closing(sqlite3.connect(database)) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS licenses (
                    id TEXT PRIMARY KEY,
                    game TEXT NOT NULL,
                    code_hash TEXT NOT NULL UNIQUE,
                    expires_at INTEGER NOT NULL,
                    installation_hash TEXT,
                    revoked INTEGER NOT NULL DEFAULT 0
                )
            """)
            db.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS active_installation
                ON licenses (game, installation_hash) WHERE revoked = 0
            """)

    def issue(self, game: str, lifetime_seconds: int = 86400) -> tuple[str, str]:
        if not game or not 0 < lifetime_seconds <= 7 * 86400:
            raise ValueError("A game and a lifetime of up to seven days are required")
        license_id, code = secrets.token_hex(16), secrets.token_urlsafe(18)
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute(
                "INSERT INTO licenses (id, game, code_hash, expires_at) VALUES (?, ?, ?, ?)",
                (license_id, game, self._digest(code), int(time.time()) + lifetime_seconds),
            )
        return license_id, code

    def redeem(self, game: str, code: str, installation_token: str) -> bool:
        # The app generates a random token and stores it in non-migrating Keychain storage
        # before requesting activation. A retry of an already committed request can succeed.
        if not code or len(installation_token) < 43:
            return False
        token_hash = self._digest(installation_token)
        with closing(sqlite3.connect(self.database)) as db, db:
            result = db.execute("""
                UPDATE licenses SET installation_hash = ?
                WHERE game = ? AND code_hash = ? AND revoked = 0
                  AND (installation_hash = ? OR (installation_hash IS NULL AND expires_at > ?))
                  AND NOT EXISTS (
                      SELECT 1 FROM licenses AS other
                      WHERE other.game = licenses.game
                        AND other.installation_hash = ? AND other.id != licenses.id AND other.revoked = 0
                  )
            """, (token_hash, game, self._digest(code), token_hash, int(time.time()), token_hash))
            return result.rowcount == 1

    def allows(self, game: str, installation_token: str) -> bool:
        with closing(sqlite3.connect(self.database)) as db:
            return db.execute(
                "SELECT 1 FROM licenses WHERE game = ? AND installation_hash = ? AND revoked = 0",
                (game, self._digest(installation_token)),
            ).fetchone() is not None

    def revoke(self, game: str, license_id: str) -> bool:
        with closing(sqlite3.connect(self.database)) as db, db:
            result = db.execute(
                "UPDATE licenses SET revoked = 1 WHERE game = ? AND id = ? AND revoked = 0",
                (game, license_id),
            )
            return result.rowcount == 1

    @staticmethod
    def _digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
