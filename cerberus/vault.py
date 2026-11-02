"""Durable, local-only SQLite memory vault; independent of the desktop GUI."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .settings import data_dir

MAX_TEXT_BYTES = 1024 * 1024
MAX_FILE_BYTES = 50 * 1024 * 1024
CHUNK = 1024 * 1024


class CaptureError(ValueError):
    """A capture was rejected without altering the source."""


class Vault:
    def __init__(self, home: Path | None = None) -> None:
        self.home = Path(home) if home is not None else data_dir()
        self.home.mkdir(parents=True, exist_ok=True)
        self.files_dir = self.home / "files"
        self.files_dir.mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.home / "vault.sqlite3", timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL CHECK(kind IN ('text', 'url', 'file')),
                title TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL,
                original_name TEXT,
                stored_path TEXT,
                checksum TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_items_created ON items(created_at DESC);
        """)
        fts_exists = self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='items_fts'").fetchone() is not None
        try:
            self.db.executescript("""
                CREATE VIRTUAL TABLE IF NOT EXISTS items_fts
                USING fts5(title, content, content='items', content_rowid='id');
                CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
                    INSERT INTO items_fts(rowid,title,content)
                    VALUES(new.id,new.title,new.content);
                END;
                CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON items BEGIN
                    INSERT INTO items_fts(items_fts,rowid,title,content)
                    VALUES('delete',old.id,old.title,old.content);
                END;
                CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE ON items BEGIN
                    INSERT INTO items_fts(items_fts,rowid,title,content)
                    VALUES('delete',old.id,old.title,old.content);
                    INSERT INTO items_fts(rowid,title,content)
                    VALUES(new.id,new.title,new.content);
                END;
            """)
            # Only rebuild newly created indexes; avoid O(n) work on startup.
            if not fts_exists:
                self.db.execute("INSERT INTO items_fts(items_fts) VALUES('rebuild')")
            self.fts = True
        except sqlite3.OperationalError:
            self.fts = False
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "Vault":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    def get(self, item_id: int) -> dict[str, Any] | None:
        return self._row(self.db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone())

    def _insert(self, *, kind: str, title: str, content: str, source: str,
                checksum: str, original_name: str | None = None,
                stored_path: str | None = None) -> dict[str, Any]:
        previous = self.db.execute(
            "SELECT * FROM items WHERE checksum=?", (checksum,)
        ).fetchone()
        if previous is not None:
            return dict(previous)
        created = datetime.now(timezone.utc).isoformat()
        with self.db:
            self.db.execute("""
                INSERT OR IGNORE INTO items
                (kind,title,content,source,original_name,stored_path,checksum,created_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (kind, title, content, source, original_name, stored_path, checksum, created))
        result = self.db.execute(
            "SELECT * FROM items WHERE checksum=?", (checksum,)
        ).fetchone()
        if result is None:
            raise RuntimeError("Vault insert failed")
        return dict(result)

    def add_text(self, text: str, *, title: str | None = None,
                 source: str = "manual") -> dict[str, Any]:
        if not isinstance(text, str) or not text.strip():
            raise CaptureError("Text must not be empty")
        data = text.encode("utf-8")
        if len(data) > MAX_TEXT_BYTES:
            raise CaptureError("Text exceeds the 1 MiB limit")
        checksum = hashlib.sha256(b"text\0" + data).hexdigest()
        return self._insert(kind="text", title=(title or text.strip()[:90]),
                            content=text, source=source, checksum=checksum)

    def add_url(self, url: str, *, title: str | None = None,
                source: str = "manual") -> dict[str, Any]:
        if not isinstance(url, str):
            raise CaptureError("Invalid URL")
        url = url.strip()
        parsed = urlparse(url)
        if parsed.scheme.lower() not in {"https", "http"} or not parsed.hostname:
            raise CaptureError("Only http(s) URLs are supported")
        if len(url.encode("utf-8")) > 8192:
            raise CaptureError("URL is too long")
        digest = hashlib.sha256(("url\0" + url).encode("utf-8")).hexdigest()
        return self._insert(kind="url", title=title or parsed.hostname,
                            content=url, source=source, checksum=digest)

    def capture_text(self, text: str, *, source: str = "drop") -> dict[str, Any]:
        stripped = text.strip()
        parsed = urlparse(stripped)
        if parsed.scheme.lower() in ("http", "https") and parsed.hostname and not any(c.isspace() for c in stripped):
            return self.add_url(stripped, source=source)
        return self.add_text(text, source=source)

    def add_file(self, file_path: Path | str, *, source: str = "drop") -> dict[str, Any]:
        path = Path(file_path).expanduser()
        if path.is_symlink() or not path.is_file():
            raise CaptureError("Drop a regular, non-symlink file")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise CaptureError("Files must be 50 MiB or smaller")
        sha = hashlib.sha256()
        # Stream and bound the read even if the source grows during capture.
        suffix = path.suffix.lower()
        if not re.fullmatch(r"\.[a-z0-9]{1,10}", suffix):
            suffix = ""
        fd, temp_name = tempfile.mkstemp(prefix=".capture-", dir=self.files_dir)
        temp = Path(temp_name)
        size = 0
        try:
            with os.fdopen(fd, "wb") as output, path.open("rb") as original:
                while chunk := original.read(CHUNK):
                    size += len(chunk)
                    if size > MAX_FILE_BYTES:
                        raise CaptureError("File exceeded the 50 MiB limit while reading")
                    sha.update(chunk)
                    output.write(chunk)
            digest = sha.hexdigest()
            checksum = hashlib.sha256(("file\0" + digest).encode()).hexdigest()
            existing = self.db.execute("SELECT * FROM items WHERE checksum=?", (checksum,)).fetchone()
            if existing is not None:
                return dict(existing)
            directory = self.files_dir / digest[:2]
            directory.mkdir(parents=True, exist_ok=True)
            stored = directory / (digest + suffix)
            os.replace(temp, stored)
            return self._insert(kind="file", title=path.name, content="",
                                original_name=path.name, stored_path=str(stored),
                                source=source, checksum=checksum)
        finally:
            temp.unlink(missing_ok=True)

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM items ORDER BY id DESC LIMIT ?", (limit,)
        )]

    def search(self, query: str, *, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        query = query.strip()
        if not query:
            return self.list(limit=limit)
        tokens = re.findall(r"\w+", query, flags=re.UNICODE)
        if self.fts and tokens:
            # FTS syntax is assembled from quoted tokens, not raw user operators.
            expression = " AND ".join('"' + t + '"' for t in tokens[:16])
            try:
                return [dict(r) for r in self.db.execute("""
                    SELECT i.* FROM items i
                    JOIN items_fts f ON f.rowid = i.id
                    WHERE items_fts MATCH ? ORDER BY i.id DESC LIMIT ?
                """, (expression, limit))]
            except sqlite3.OperationalError:
                pass
        pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        return [dict(r) for r in self.db.execute("""
            SELECT * FROM items WHERE title LIKE ? ESCAPE char(92)
            OR content LIKE ? ESCAPE char(92) ORDER BY id DESC LIMIT ?
        """, (pattern, pattern, limit))]

    def delete(self, item_id: int) -> bool:
        item = self.get(item_id)
        if item is None:
            return False
        with self.db:
            self.db.execute("DELETE FROM items WHERE id=?", (item_id,))
        stored = item.get("stored_path")
        if stored:
            candidate = Path(stored)
            # Never remove arbitrary source files or symlinks.
            if not candidate.is_symlink() and candidate.resolve().is_relative_to(self.files_dir.resolve()):
                candidate.unlink(missing_ok=True)
        return True

    def export_json(self, destination: Path | str) -> Path:
        path = Path(destination).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        records = [dict(r) for r in self.db.execute("SELECT * FROM items ORDER BY id")]
        # Exports contain metadata and textual data; file bytes remain in the vault.
        payload = json.dumps({"format": "cerberus-v1", "items": records},
                             ensure_ascii=False, indent=2)
        fd, name = tempfile.mkstemp(prefix=".cerberus-export-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                out.write(payload)
            os.replace(name, path)
        finally:
            Path(name).unlink(missing_ok=True)
        return path
