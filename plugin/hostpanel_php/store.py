from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Optional

from db import get_conn


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def migrate() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS php_assignments (
              id TEXT PRIMARY KEY,
              username TEXT NOT NULL,
              domain TEXT NOT NULL UNIQUE,
              document_root TEXT NOT NULL,
              php_version TEXT NOT NULL DEFAULT '8.4',
              pool_name TEXT NOT NULL UNIQUE,
              socket_path TEXT NOT NULL UNIQUE,
              status TEXT NOT NULL DEFAULT 'stopped',
              memory_limit TEXT NOT NULL DEFAULT '256M',
              upload_max_filesize TEXT NOT NULL DEFAULT '64M',
              post_max_size TEXT NOT NULL DEFAULT '64M',
              max_execution_time INTEGER NOT NULL DEFAULT 60,
              max_input_vars INTEGER NOT NULL DEFAULT 3000,
              display_errors INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS php_assignment_logs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              assignment_id TEXT NOT NULL,
              level TEXT NOT NULL,
              message TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )


def _row_to_assignment(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["display_errors"] = bool(item.get("display_errors"))
    return item


def list_assignments(username: Optional[str] = None) -> list[dict[str, Any]]:
    migrate()
    with get_conn() as conn:
        if username:
            rows = conn.execute(
                "SELECT * FROM php_assignments WHERE username=? ORDER BY created_at DESC",
                (username,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM php_assignments ORDER BY created_at DESC").fetchall()
    return [_row_to_assignment(row) for row in rows]


def get_assignment(assignment_id: str) -> Optional[dict[str, Any]]:
    migrate()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM php_assignments WHERE id=?", (assignment_id,)).fetchone()
    return _row_to_assignment(row) if row else None


def get_by_domain(domain: str) -> Optional[dict[str, Any]]:
    migrate()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM php_assignments WHERE domain=?", (domain,)).fetchone()
    return _row_to_assignment(row) if row else None


def create_assignment(data: dict[str, Any]) -> dict[str, Any]:
    migrate()
    now = utc_now()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO php_assignments (
              id, username, domain, document_root, php_version, pool_name, socket_path,
              status, memory_limit, upload_max_filesize, post_max_size, max_execution_time,
              max_input_vars, display_errors, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                data["id"],
                data["username"],
                data["domain"],
                data["document_root"],
                data.get("php_version", "8.4"),
                data["pool_name"],
                data["socket_path"],
                data.get("status", "provisioning"),
                data["memory_limit"],
                data["upload_max_filesize"],
                data["post_max_size"],
                data["max_execution_time"],
                data["max_input_vars"],
                int(bool(data["display_errors"])),
                now,
                now,
            ),
        )
    return get_assignment(data["id"]) or data


def update_assignment(assignment_id: str, data: dict[str, Any]) -> dict[str, Any]:
    migrate()
    fields = []
    values: list[Any] = []
    for key in (
        "username",
        "domain",
        "document_root",
        "php_version",
        "pool_name",
        "socket_path",
        "status",
        "memory_limit",
        "upload_max_filesize",
        "post_max_size",
        "max_execution_time",
        "max_input_vars",
        "display_errors",
    ):
        if key in data:
            fields.append(f"{key}=?")
            values.append(int(bool(data[key])) if key == "display_errors" else data[key])
    fields.append("updated_at=?")
    values.append(utc_now())
    values.append(assignment_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE php_assignments SET {', '.join(fields)} WHERE id=?", values)
    return get_assignment(assignment_id) or data


def delete_assignment(assignment_id: str) -> None:
    migrate()
    with get_conn() as conn:
        conn.execute("DELETE FROM php_assignment_logs WHERE assignment_id=?", (assignment_id,))
        conn.execute("DELETE FROM php_assignments WHERE id=?", (assignment_id,))


def delete_assignments(assignment_ids: Iterable[str]) -> None:
    for assignment_id in assignment_ids:
        delete_assignment(assignment_id)


def add_log(assignment_id: str, level: str, message: str) -> None:
    migrate()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO php_assignment_logs (assignment_id, level, message, created_at) VALUES (?,?,?,?)",
            (assignment_id, level, message[:8000], utc_now()),
        )


def list_lifecycle_logs(assignment_id: str, limit: int = 100) -> list[dict[str, Any]]:
    migrate()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT level, message, created_at FROM php_assignment_logs WHERE assignment_id=? ORDER BY id DESC LIMIT ?",
            (assignment_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]
