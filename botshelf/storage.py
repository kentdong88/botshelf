import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, created TEXT, kind TEXT, scope TEXT, payload TEXT)")

    def connect(self):
        return sqlite3.connect(self.path)

    def save(self, kind, scope, payload):
        with self.connect() as db:
            cursor = db.execute("INSERT INTO events(created,kind,scope,payload) VALUES(?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), kind, scope, json.dumps(payload)))
            return cursor.lastrowid

    def events(self, kind=None):
        with self.connect() as db:
            rows = db.execute("SELECT id,created,kind,scope,payload FROM events " +
                ("WHERE kind=? " if kind else "") + "ORDER BY id DESC", (kind,) if kind else ()).fetchall()
        return [{"id": r[0], "created": r[1], "kind": r[2], "scope": r[3], "payload": json.loads(r[4])} for r in rows]
