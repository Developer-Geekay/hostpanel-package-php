from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import User
from deps import get_current_user

from hostpanel_php import audit, fpm, logs, nginx, store, validators


router = APIRouter(prefix="/cpanelapi/php", tags=["PHP"])


class PhpAssignmentCreateRequest(BaseModel):
    domain: str
    memory_limit: str = Field(default="256M", max_length=8)
    upload_max_filesize: str = Field(default="64M", max_length=8)
    post_max_size: str = Field(default="64M", max_length=8)
    max_execution_time: int = Field(default=60)
    max_input_vars: int = Field(default=3000)
    display_errors: bool = Field(default=False)


class PhpAssignmentUpdateRequest(BaseModel):
    memory_limit: Optional[str] = Field(default=None, max_length=8)
    upload_max_filesize: Optional[str] = Field(default=None, max_length=8)
    post_max_size: Optional[str] = Field(default=None, max_length=8)
    max_execution_time: Optional[int] = None
    max_input_vars: Optional[int] = None
    display_errors: Optional[bool] = None


def _ensure_assignment_access(assignment: dict, current_user: User) -> None:
    if not validators.is_admin(current_user) and assignment["username"] != validators.current_username(current_user):
        raise HTTPException(status_code=403, detail="Access denied")


def _visible_assignments(current_user: User) -> list[dict]:
    username = None if validators.is_admin(current_user) else validators.current_username(current_user)
    items = store.list_assignments(username=username)
    service_status = fpm.status()
    for item in items:
        item["status"] = service_status if item["status"] != "failed" else item["status"]
    return items


def _settings_from_request(request: PhpAssignmentCreateRequest | PhpAssignmentUpdateRequest, existing: dict | None = None) -> dict:
    base = existing or {}
    return validators.validate_settings(
        {
            "memory_limit": request.memory_limit if request.memory_limit is not None else base.get("memory_limit", "256M"),
            "upload_max_filesize": request.upload_max_filesize if request.upload_max_filesize is not None else base.get("upload_max_filesize", "64M"),
            "post_max_size": request.post_max_size if request.post_max_size is not None else base.get("post_max_size", "64M"),
            "max_execution_time": request.max_execution_time if request.max_execution_time is not None else base.get("max_execution_time", 60),
            "max_input_vars": request.max_input_vars if request.max_input_vars is not None else base.get("max_input_vars", 3000),
            "display_errors": request.display_errors if request.display_errors is not None else base.get("display_errors", False),
        }
    )


@router.get("/domains")
async def list_domains(current_user: User = Depends(get_current_user)):
    return validators.eligible_domains(current_user)


@router.get("/runtime")
async def runtime_info(current_user: User = Depends(get_current_user)):
    return fpm.runtime_info()


@router.get("/assignments")
async def list_assignments(current_user: User = Depends(get_current_user)):
    return _visible_assignments(current_user)


@router.get("/assignments/{assignment_id}")
async def get_assignment(assignment_id: str, current_user: User = Depends(get_current_user)):
    assignment = store.get_assignment(validators.validate_assignment_id(assignment_id))
    if not assignment:
        raise HTTPException(status_code=404, detail="PHP assignment not found")
    _ensure_assignment_access(assignment, current_user)
    return assignment


@router.post("/assignments")
async def create_assignment(request: PhpAssignmentCreateRequest, current_user: User = Depends(get_current_user)):
    domain_option = validators.resolve_domain(request.domain, current_user)
    document_root = validators.validate_document_root(domain_option["document_root"], domain_option["username"])
    assignment_id = validators.make_assignment_id(domain_option["domain"])
    data = {
        "id": assignment_id,
        "username": domain_option["username"],
        "domain": domain_option["domain"],
        "document_root": document_root,
        "php_version": validators.PHP_VERSION,
        "pool_name": assignment_id,
        "socket_path": fpm.socket_path(assignment_id),
        "status": "provisioning",
        **_settings_from_request(request),
    }
    assignment = store.create_assignment(data)
    audit.log_action(current_user, "php.assignment_create", assignment_id, {"domain": assignment["domain"]})
    try:
        fpm.write_pool(assignment)
        fpm.validate_config()
        fpm.reload()
        nginx.enable_php(assignment)
        assignment = store.update_assignment(assignment_id, {"status": "running"})
        audit.log_action(current_user, "php.nginx_php_enable", assignment_id, {"domain": assignment["domain"]})
        return assignment
    except Exception as exc:
        store.update_assignment(assignment_id, {"status": "failed"})
        store.add_log(assignment_id, "error", str(exc))
        audit.log_action(current_user, "php.assignment_create", assignment_id, {"error": str(exc)}, status="failed")
        raise


@router.put("/assignments/{assignment_id}")
async def update_assignment(
    assignment_id: str,
    request: PhpAssignmentUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    assignment_id = validators.validate_assignment_id(assignment_id)
    existing = store.get_assignment(assignment_id)
    if not existing:
        raise HTTPException(status_code=404, detail="PHP assignment not found")
    _ensure_assignment_access(existing, current_user)
    patch = _settings_from_request(request, existing)
    updated = store.update_assignment(assignment_id, patch)
    fpm.write_pool(updated)
    fpm.validate_config()
    fpm.reload()
    nginx.enable_php(updated)
    audit.log_action(current_user, "php.assignment_update", assignment_id, {"domain": updated["domain"]})
    return updated


@router.delete("/assignments/{assignment_id}")
async def delete_assignment(assignment_id: str, current_user: User = Depends(get_current_user)):
    assignment_id = validators.validate_assignment_id(assignment_id)
    assignment = store.get_assignment(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="PHP assignment not found")
    _ensure_assignment_access(assignment, current_user)
    try:
        nginx.disable_php(assignment)
    except Exception as exc:
        store.add_log(assignment_id, "warning", f"Could not update nginx while disabling PHP: {exc}")
    fpm.remove_pool(assignment_id)
    fpm.reload()
    store.delete_assignment(assignment_id)
    audit.log_action(current_user, "php.assignment_delete", assignment_id, {"domain": assignment["domain"], "files_preserved": True})
    return {"status": "success", "message": "PHP disabled; website files preserved"}


@router.post("/assignments/{assignment_id}/restart")
async def restart_assignment(assignment_id: str, current_user: User = Depends(get_current_user)):
    assignment = await get_assignment(assignment_id, current_user)
    fpm.restart()
    store.update_assignment(assignment["id"], {"status": "running"})
    audit.log_action(current_user, "php.assignment_restart", assignment["id"], {"domain": assignment["domain"]})
    return store.get_assignment(assignment["id"])


@router.get("/assignments/{assignment_id}/logs")
async def get_logs(assignment_id: str, current_user: User = Depends(get_current_user)):
    assignment = await get_assignment(assignment_id, current_user)
    return logs.assignment_logs(assignment["id"])


@router.get("/count")
async def count_assignments(current_user: User = Depends(get_current_user)):
    return {"count": len(_visible_assignments(current_user))}
