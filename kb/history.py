"""Saved chats in a small SQLite file. Every query is scoped to the signed-in username."""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager

DB_PATH = "chat_history.db"
RETENTION_DAYS = 90        # chats not touched for this long are deleted at sign-in
TITLE_CHARS = 45

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY, username TEXT NOT NULL, title TEXT NOT NULL,
    created REAL NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT NOT NULL, username TEXT NOT NULL,
    role TEXT NOT NULL, content TEXT NOT NULL, sources TEXT, files TEXT, route TEXT,
    is_error INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_chats_user ON chats (username, updated);
CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages (chat_id, username);
"""


@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        with conn:                      # commits on success, rolls back on error
            yield conn
    finally:
        conn.close()


def new_chat(username: str) -> str:
    chat_id, now = uuid.uuid4().hex, time.time()
    with _db() as db:
        db.execute("INSERT INTO chats (id, username, title, created, updated) VALUES (?, ?, ?, ?, ?)",
                   (chat_id, username, "New chat", now, now))
    return chat_id


def list_chats(username: str, limit: int = 30) -> list[dict]:
    with _db() as db:
        rows = db.execute("SELECT id, title, updated FROM chats WHERE username = ? "
                          "ORDER BY updated DESC LIMIT ?", (username, limit)).fetchall()
    return [dict(r) for r in rows]


def load_messages(username: str, chat_id: str) -> list[dict]:
    with _db() as db:
        rows = db.execute("SELECT role, content, sources, files, route, is_error FROM messages "
                          "WHERE chat_id = ? AND username = ? ORDER BY id", (chat_id, username)).fetchall()
    return [{"role": r["role"], "content": r["content"], "sources": json.loads(r["sources"] or "[]"),
             "files": json.loads(r["files"] or "[]"), "route": r["route"], "error": bool(r["is_error"])}
            for r in rows]


def add_message(username: str, chat_id: str, role: str, content: str, sources: list | None = None,
                files: list | None = None, route: str | None = None, error: bool = False) -> None:
    now = time.time()
    with _db() as db:
        chat = db.execute("SELECT title FROM chats WHERE id = ? AND username = ?",
                          (chat_id, username)).fetchone()
        if chat is None:
            raise PermissionError("That chat does not belong to this user.")
        db.execute("INSERT INTO messages (chat_id, username, role, content, sources, files, route, is_error, created) "
                   "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (chat_id, username, role, content, json.dumps(sources or []), json.dumps(files or []),
                    route, int(error), now))
        title = chat["title"]
        if role == "user" and title == "New chat":
            title = content.strip().replace("\n", " ")[:TITLE_CHARS] or "New chat"
        db.execute("UPDATE chats SET title = ?, updated = ? WHERE id = ? AND username = ?",
                   (title, now, chat_id, username))


def delete_chat(username: str, chat_id: str) -> None:
    with _db() as db:
        db.execute("DELETE FROM messages WHERE chat_id = ? AND username = ?", (chat_id, username))
        db.execute("DELETE FROM chats WHERE id = ? AND username = ?", (chat_id, username))


def purge_old(days: int = RETENTION_DAYS) -> int:
    """Delete chats not updated for `days` days. Returns how many chats were removed."""
    cutoff = time.time() - days * 86400
    with _db() as db:
        db.execute("DELETE FROM messages WHERE chat_id IN (SELECT id FROM chats WHERE updated < ?)", (cutoff,))
        return db.execute("DELETE FROM chats WHERE updated < ?", (cutoff,)).rowcount