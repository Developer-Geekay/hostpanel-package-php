from __future__ import annotations

import os
import subprocess

from hostpanel_php import fpm, store
from hostpanel_php.validators import validate_assignment_id


def assignment_logs(assignment_id: str, limit: int = 200) -> list[dict[str, str]]:
    assignment_id = validate_assignment_id(assignment_id)
    entries = store.list_lifecycle_logs(assignment_id, limit=50)
    path = fpm.error_log_path(assignment_id)
    if os.path.exists(path):
        try:
            result = subprocess.run(
                ["tail", "-n", str(limit), path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=False,
            )
            for line in result.stdout.splitlines():
                entries.append({"created_at": "", "level": "php-fpm", "message": line})
        except Exception as exc:
            entries.append({"created_at": "", "level": "warning", "message": str(exc)})
    result = subprocess.run(
        ["sudo", "journalctl", "-u", fpm.SERVICE_NAME, "-n", "80", "--no-pager", "--output=short-iso"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=15,
        check=False,
    )
    if result.stdout:
        for line in result.stdout.splitlines():
            entries.append({"created_at": "", "level": "journal", "message": line})
    return entries[-limit:]
