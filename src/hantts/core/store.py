"""SQLite 저장소: 발음 사전, 프리셋, 히스토리, 라이선스 동의 (docs/02, 07, 11)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(slots=True, frozen=True)
class DictEntry:
    id: int
    pattern: str
    replacement: str
    scope: str
    engine_id: str
    is_regex: bool
    case_sensitive: bool
    enabled: bool


@dataclass(slots=True, frozen=True)
class Preset:
    id: int
    name: str
    engine_id: str
    voice: str
    lang: str
    params: dict[str, Any]


@dataclass(slots=True, frozen=True)
class HistoryItem:
    id: int
    created_at: str
    engine_id: str
    voice: str
    lang: str
    text: str
    path: str
    duration: float
    params: dict[str, Any]


class Store:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def close(self) -> None:
        self._conn.close()

    def _migrate(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS dictionary (
                id INTEGER PRIMARY KEY,
                pattern TEXT NOT NULL,
                replacement TEXT NOT NULL,
                scope TEXT NOT NULL DEFAULT 'global',
                engine_id TEXT NOT NULL DEFAULT '',
                is_regex INTEGER NOT NULL DEFAULT 0,
                case_sensitive INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS presets (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                engine_id TEXT NOT NULL,
                voice TEXT NOT NULL,
                lang TEXT NOT NULL,
                params_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL,
                engine_id TEXT NOT NULL,
                voice TEXT NOT NULL,
                lang TEXT NOT NULL,
                text TEXT NOT NULL,
                path TEXT NOT NULL,
                duration REAL NOT NULL,
                params_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS consents (
                id INTEGER PRIMARY KEY,
                engine_id TEXT NOT NULL,
                license_name TEXT NOT NULL,
                accepted_at TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    # ---- 사전 ----------------------------------------------------------
    def list_dict(self, engine_id: str | None = None) -> list[DictEntry]:
        rows = self._conn.execute("SELECT * FROM dictionary ORDER BY length(pattern) DESC, id").fetchall()
        items = [_dict_row(r) for r in rows]
        if engine_id is None:
            return items
        return [e for e in items if e.scope == "global" or e.engine_id == engine_id]

    def add_dict(
        self,
        pattern: str,
        replacement: str,
        *,
        scope: str = "global",
        engine_id: str = "",
        is_regex: bool = False,
        case_sensitive: bool = False,
    ) -> int:
        cur = self._conn.execute(
            """INSERT INTO dictionary(
                   pattern, replacement, scope, engine_id, is_regex, case_sensitive, enabled
               ) VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (pattern, replacement, scope, engine_id, int(is_regex), int(case_sensitive)),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def delete_dict(self, entry_id: int) -> None:
        self._conn.execute("DELETE FROM dictionary WHERE id = ?", (entry_id,))
        self._conn.commit()

    def set_dict_enabled(self, entry_id: int, enabled: bool) -> None:
        self._conn.execute("UPDATE dictionary SET enabled = ? WHERE id = ?", (int(enabled), entry_id))
        self._conn.commit()

    # ---- 프리셋 --------------------------------------------------------
    def list_presets(self) -> list[Preset]:
        rows = self._conn.execute("SELECT * FROM presets ORDER BY name").fetchall()
        return [
            Preset(
                int(r["id"]), r["name"], r["engine_id"], r["voice"], r["lang"], json.loads(r["params_json"])
            )
            for r in rows
        ]

    def save_preset(self, name: str, engine_id: str, voice: str, lang: str, params: dict[str, Any]) -> int:
        cur = self._conn.execute(
            """INSERT INTO presets(name, engine_id, voice, lang, params_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, engine_id, voice, lang, json.dumps(params, ensure_ascii=False), _now()),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def delete_preset(self, preset_id: int) -> None:
        self._conn.execute("DELETE FROM presets WHERE id = ?", (preset_id,))
        self._conn.commit()

    # ---- 히스토리 ------------------------------------------------------
    def add_history(
        self,
        *,
        engine_id: str,
        voice: str,
        lang: str,
        text: str,
        path: str,
        duration: float,
        params: dict[str, Any],
    ) -> int:
        cur = self._conn.execute(
            """INSERT INTO history(created_at, engine_id, voice, lang, text, path, duration, params_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (_now(), engine_id, voice, lang, text, path, duration, json.dumps(params, ensure_ascii=False)),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def list_history(self, limit: int = 200) -> list[HistoryItem]:
        rows = self._conn.execute("SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [
            HistoryItem(
                int(r["id"]),
                r["created_at"],
                r["engine_id"],
                r["voice"],
                r["lang"],
                r["text"],
                r["path"],
                float(r["duration"]),
                json.loads(r["params_json"]),
            )
            for r in rows
        ]

    def delete_history(self, item_id: int) -> None:
        self._conn.execute("DELETE FROM history WHERE id = ?", (item_id,))
        self._conn.commit()

    def clear_history(self) -> None:
        self._conn.execute("DELETE FROM history")
        self._conn.commit()

    # ---- 동의 ----------------------------------------------------------
    def record_consent(self, engine_id: str, license_name: str) -> None:
        self._conn.execute(
            "INSERT INTO consents(engine_id, license_name, accepted_at) VALUES (?, ?, ?)",
            (engine_id, license_name, _now()),
        )
        self._conn.commit()

    def consents(self, engine_id: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT license_name FROM consents WHERE engine_id = ? ORDER BY id", (engine_id,)
        ).fetchall()
        return [str(r["license_name"]) for r in rows]


def _dict_row(r: sqlite3.Row) -> DictEntry:
    return DictEntry(
        int(r["id"]),
        r["pattern"],
        r["replacement"],
        r["scope"],
        r["engine_id"],
        bool(r["is_regex"]),
        bool(r["case_sensitive"]),
        bool(r["enabled"]),
    )
