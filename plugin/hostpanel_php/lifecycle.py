from __future__ import annotations

import logging
import os
import subprocess

from fastapi import HTTPException

from hostpanel_php import fpm, nginx, store


logger = logging.getLogger(__name__)

PLUGIN_DIR = "/opt/hostpanel/plugins/php"
SUDOERS_DST = "/etc/sudoers.d/hostpanel-php"


def _sudo(command: list[str], check: bool = False):
    return subprocess.run(["sudo"] + command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check)


def _runtime_ready() -> bool:
    return os.path.isfile(fpm.php_bin()) and os.access(fpm.php_bin(), os.X_OK) and os.path.isfile(fpm.php_fpm_bin())


def on_install():
    logger.info("PHP on_install: initializing runtime state")
    store.migrate()
    fpm.ensure_runtime_dirs()
    if not _runtime_ready():
        logger.warning("PHP runtime missing or not executable")
    try:
        fpm.write_service()
        fpm.validate_config()
    except Exception as exc:
        logger.warning("PHP service/config initialization failed: %s", exc)
    _sudo(["systemctl", "daemon-reload"], check=False)


def on_startup():
    logger.info("PHP on_startup: repairing assignments")
    store.migrate()
    fpm.ensure_runtime_dirs()
    for assignment in store.list_assignments():
        try:
            fpm.write_pool(assignment)
            nginx.enable_php(assignment)
            store.update_assignment(assignment["id"], {"status": fpm.status()})
        except Exception as exc:
            logger.warning("PHP repair failed for %s: %s", assignment.get("id"), exc)
            store.update_assignment(assignment["id"], {"status": "failed"})


def pre_uninstall(force: bool = False):
    assignments = store.list_assignments()
    if assignments and not force:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot uninstall: {len(assignments)} PHP assignment(s) still exist. Use force=True to remove them.",
        )
    for assignment in assignments:
        try:
            nginx.disable_php(assignment)
        except Exception:
            pass
        fpm.remove_pool(assignment["id"])
    if assignments:
        store.delete_assignments([assignment["id"] for assignment in assignments])
    fpm.stop()
    _sudo(["systemctl", "disable", fpm.SERVICE_NAME], check=False)
    _sudo(["rm", "-f", fpm.SERVICE_PATH], check=False)
    _sudo(["systemctl", "daemon-reload"], check=False)
    if force and os.path.isdir(PLUGIN_DIR):
        _sudo(["rm", "-rf", PLUGIN_DIR], check=False)
    _sudo(["rm", "-f", SUDOERS_DST], check=False)


def on_user_delete(username: str, **kwargs):
    if not username:
        return
    for assignment in store.list_assignments(username=username):
        try:
            nginx.disable_php(assignment)
        except Exception:
            pass
        fpm.remove_pool(assignment["id"])
        store.delete_assignment(assignment["id"])


def on_domain_delete(domain_name: str, **kwargs):
    if not domain_name:
        return
    assignment = store.get_by_domain(domain_name)
    if not assignment:
        return
    try:
        nginx.disable_php(assignment)
    except Exception:
        pass
    fpm.remove_pool(assignment["id"])
    store.delete_assignment(assignment["id"])


def on_ssl_cert_imported(domain: str, **kwargs):
    assignment = store.get_by_domain(domain)
    if assignment:
        nginx.enable_php(assignment)


def on_ssl_cert_deleted(domain: str, **kwargs):
    assignment = store.get_by_domain(domain)
    if assignment:
        nginx.enable_php(assignment)
