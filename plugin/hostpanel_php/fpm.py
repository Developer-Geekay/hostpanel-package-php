from __future__ import annotations

import os
import subprocess
from typing import Optional

from fastapi import HTTPException

from hostpanel_php import store
from hostpanel_php.validators import PHP_VERSION, validate_assignment_id


PLUGIN_DIR = "/opt/hostpanel/plugins/php"
SERVICE_NAME = "hostpanel-php-fpm"
SERVICE_PATH = f"/etc/systemd/system/{SERVICE_NAME}.service"
COMMAND_TIMEOUT = 60


def php_bin() -> str:
    return f"{PLUGIN_DIR}/php-{PHP_VERSION}"


def php_fpm_bin() -> str:
    return f"{PLUGIN_DIR}/php-fpm-{PHP_VERSION}"


def fpm_config_path() -> str:
    return f"{PLUGIN_DIR}/conf/php-fpm.conf"


def pool_path(assignment_id: str) -> str:
    return f"{PLUGIN_DIR}/pools/{validate_assignment_id(assignment_id)}.conf"


def socket_path(assignment_id: str) -> str:
    return f"/run/hostpanel-php/{validate_assignment_id(assignment_id)}.sock"


def error_log_path(assignment_id: str) -> str:
    return f"{PLUGIN_DIR}/logs/{validate_assignment_id(assignment_id)}.error.log"


def _run(command: list[str], check: bool = False, input_data: Optional[str] = None, timeout: int = COMMAND_TIMEOUT):
    try:
        return subprocess.run(
            command,
            input=input_data,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="PHP operation timed out")
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "PHP operation failed").strip()
        raise HTTPException(status_code=500, detail=detail)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def _sudo(command: list[str], check: bool = False, input_data: Optional[str] = None, timeout: int = COMMAND_TIMEOUT):
    return _run(["sudo"] + command, check=check, input_data=input_data, timeout=timeout)


def runtime_info() -> dict[str, str]:
    data = {"php_version": PHP_VERSION}
    try:
        result = _run([php_bin(), "-v"], timeout=10)
        data["php"] = result.stdout.splitlines()[0] if result.stdout else "unknown"
    except Exception:
        data["php"] = "unavailable" if os.path.exists(php_bin()) else "missing"
    try:
        result = _run([php_fpm_bin(), "-v"], timeout=10)
        data["php_fpm"] = (result.stderr or result.stdout).splitlines()[0] if (result.stderr or result.stdout) else "unknown"
    except Exception:
        data["php_fpm"] = "unavailable" if os.path.exists(php_fpm_bin()) else "missing"
    return data


def ensure_runtime_dirs() -> None:
    for path in (f"{PLUGIN_DIR}/pools", f"{PLUGIN_DIR}/logs", f"{PLUGIN_DIR}/run", "/run/hostpanel-php"):
        _sudo(["mkdir", "-p", path], check=False)


def write_pool(assignment: dict) -> None:
    assignment_id = validate_assignment_id(assignment["id"])
    content = f"""[{assignment['pool_name']}]
user = {assignment['username']}
group = {assignment['username']}
listen = {assignment['socket_path']}
listen.owner = {assignment['username']}
listen.group = {assignment['username']}
listen.mode = 0600
pm = ondemand
pm.max_children = 10
pm.process_idle_timeout = 10s
pm.max_requests = 500
chdir = {assignment['document_root']}
catch_workers_output = yes
php_admin_value[open_basedir] = {assignment['document_root']}:/tmp
php_admin_value[error_log] = {error_log_path(assignment_id)}
php_admin_flag[log_errors] = on
php_value[memory_limit] = {assignment['memory_limit']}
php_value[upload_max_filesize] = {assignment['upload_max_filesize']}
php_value[post_max_size] = {assignment['post_max_size']}
php_value[max_execution_time] = {assignment['max_execution_time']}
php_value[max_input_vars] = {assignment['max_input_vars']}
php_flag[display_errors] = {'on' if assignment['display_errors'] else 'off'}
"""
    ensure_runtime_dirs()
    _sudo(["tee", pool_path(assignment_id)], input_data=content, check=True)
    _sudo(["chmod", "644", pool_path(assignment_id)], check=False)
    store.add_log(assignment_id, "info", "PHP-FPM pool written")


def remove_pool(assignment_id: str) -> None:
    _sudo(["rm", "-f", pool_path(assignment_id)], check=False)
    _sudo(["rm", "-f", socket_path(assignment_id)], check=False)


def validate_config() -> None:
    if os.path.exists(php_fpm_bin()):
        _sudo([php_fpm_bin(), "-t", "--fpm-config", fpm_config_path()], check=True)


def write_service() -> None:
    content = f"""[Unit]
Description=HostPanel PHP-FPM 8.4
After=network.target

[Service]
Type=simple
RuntimeDirectory=hostpanel-php
RuntimeDirectoryMode=0755
ExecStart={php_fpm_bin()} --nodaemonize --fpm-config {fpm_config_path()}
ExecReload=/bin/kill -USR2 $MAINPID
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
    _sudo(["tee", SERVICE_PATH], input_data=content, check=True)
    _sudo(["chmod", "644", SERVICE_PATH], check=False)
    _sudo(["systemctl", "daemon-reload"], check=False)


def start() -> None:
    _sudo(["systemctl", "enable", SERVICE_NAME], check=False)
    _sudo(["systemctl", "start", SERVICE_NAME], check=True)


def reload() -> None:
    result = _sudo(["systemctl", "is-active", SERVICE_NAME], check=False, timeout=10)
    if result.returncode == 0:
        _sudo(["systemctl", "reload", SERVICE_NAME], check=False)
    else:
        start()


def restart() -> None:
    _sudo(["systemctl", "restart", SERVICE_NAME], check=True)


def stop() -> None:
    _sudo(["systemctl", "stop", SERVICE_NAME], check=False)


def status() -> str:
    result = _sudo(["systemctl", "is-active", SERVICE_NAME], check=False, timeout=10)
    return "running" if result.returncode == 0 else "stopped"
