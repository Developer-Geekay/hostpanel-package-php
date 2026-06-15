from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from domain_registry import _load_domains, _load_subdomains

from hostpanel_php import store


PHP_VERSION = "8.4"
ASSIGNMENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,251}[a-z0-9]$")
SIZE_VALUES = {"32M", "64M", "128M", "256M", "512M", "1G", "2G"}


def is_admin(current_user: Any) -> bool:
    return getattr(current_user, "role", None) == "admin"


def current_username(current_user: Any) -> str:
    username = getattr(current_user, "linux_user", None) or getattr(current_user, "username", None)
    if not username:
        raise HTTPException(status_code=403, detail="Current user has no Linux user")
    return username


def is_reserved_domain(domain: str) -> bool:
    value = domain.lower().strip(".")
    return value.startswith("cpanel.") or value.startswith("ftp.")


def validate_domain_name(domain: str) -> str:
    value = domain.lower().strip()
    if not DOMAIN_RE.fullmatch(value) or ".." in value:
        raise HTTPException(status_code=400, detail="Invalid domain")
    if is_reserved_domain(value):
        raise HTTPException(status_code=400, detail="Reserved domains cannot use PHP")
    return value


def slugify(value: str, fallback: str = "php-site") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)[:63]
    return slug or fallback


def make_assignment_id(domain: str) -> str:
    base = slugify(domain)
    assignment_id = base
    index = 2
    while store.get_assignment(assignment_id):
        suffix = f"-{index}"
        assignment_id = f"{base[:63 - len(suffix)]}{suffix}"
        index += 1
    return assignment_id


def validate_assignment_id(assignment_id: str) -> str:
    if not ASSIGNMENT_ID_RE.fullmatch(assignment_id):
        raise HTTPException(status_code=400, detail="Invalid assignment id")
    return assignment_id


def eligible_domains(current_user: Any, include_assigned_id: str | None = None) -> list[dict[str, str]]:
    username = current_username(current_user)
    assigned = {
        item["domain"]: item["id"]
        for item in store.list_assignments()
    }
    options: list[dict[str, str]] = []
    for record in _load_domains():
        domain = record.get("domain_name", "")
        owner = record.get("username", "")
        if is_reserved_domain(domain):
            continue
        if not is_admin(current_user) and owner != username:
            continue
        if domain in assigned and assigned[domain] != include_assigned_id:
            continue
        options.append(
            {
                "domain": domain,
                "username": owner,
                "document_root": record.get("document_root") or f"/home/{owner}/public_html",
                "type": "main",
            }
        )
    for record in _load_subdomains():
        domain = record.get("fqdn", "")
        owner = record.get("username", "")
        if is_reserved_domain(domain):
            continue
        if not is_admin(current_user) and owner != username:
            continue
        if domain in assigned and assigned[domain] != include_assigned_id:
            continue
        options.append(
            {
                "domain": domain,
                "username": owner,
                "document_root": record.get("document_root") or f"/home/{owner}/public_html/{domain}",
                "type": "subdomain",
            }
        )
    return sorted(options, key=lambda item: item["domain"])


def resolve_domain(domain: str, current_user: Any, include_assigned_id: str | None = None) -> dict[str, str]:
    value = validate_domain_name(domain)
    for option in eligible_domains(current_user, include_assigned_id=include_assigned_id):
        if option["domain"] == value:
            return option
    raise HTTPException(status_code=404, detail="Domain is not available for PHP")


def validate_document_root(path: str, username: str) -> str:
    base = (Path("/home") / username).resolve(strict=False)
    resolved = Path(path).resolve(strict=False)
    if resolved != base and base not in resolved.parents:
        raise HTTPException(status_code=400, detail=f"Document root must stay within /home/{username}/")
    return str(resolved)


def validate_size(value: str, field: str, default: str) -> str:
    clean = (value or default).strip().upper()
    if clean not in SIZE_VALUES:
        raise HTTPException(status_code=400, detail=f"Invalid {field}")
    return clean


def validate_int(value: int, field: str, minimum: int, maximum: int, default: int) -> int:
    try:
        clean = int(value if value is not None else default)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid {field}")
    if clean < minimum or clean > maximum:
        raise HTTPException(status_code=400, detail=f"{field} must be between {minimum} and {maximum}")
    return clean


def validate_settings(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "memory_limit": validate_size(data.get("memory_limit"), "memory limit", "256M"),
        "upload_max_filesize": validate_size(data.get("upload_max_filesize"), "upload max filesize", "64M"),
        "post_max_size": validate_size(data.get("post_max_size"), "post max size", "64M"),
        "max_execution_time": validate_int(data.get("max_execution_time"), "max execution time", 10, 300, 60),
        "max_input_vars": validate_int(data.get("max_input_vars"), "max input vars", 1000, 10000, 3000),
        "display_errors": bool(data.get("display_errors", False)),
    }
