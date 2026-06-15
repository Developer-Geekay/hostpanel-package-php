from __future__ import annotations

import os
import re
import subprocess

from fastapi import HTTPException

from hostpanel_php.validators import validate_assignment_id, validate_domain_name


NGINX_BIN = "/opt/hostpanel/plugins/nginx/nginx"
VHOSTS_DIR = "/opt/hostpanel/plugins/nginx/vhosts"


def _sudo(command: list[str], input_data: str | None = None, check: bool = False, timeout: int = 30):
    try:
        return subprocess.run(
            ["sudo"] + command,
            input=input_data,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="nginx operation timed out")
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "nginx operation failed").strip()
        raise HTTPException(status_code=500, detail=detail)


def _vhost_path(domain: str) -> str:
    return f"{VHOSTS_DIR}/{validate_domain_name(domain)}.conf"


def _read(domain: str) -> str:
    path = _vhost_path(domain)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="nginx vhost does not exist for this domain")
    with open(path, "r") as handle:
        return handle.read()


def _write(domain: str, content: str) -> None:
    _sudo(["tee", _vhost_path(domain)], input_data=content, check=True)


def _markers(assignment_id: str) -> tuple[str, str]:
    assignment_id = validate_assignment_id(assignment_id)
    return f"# BEGIN hostpanel-php {assignment_id}", f"# END hostpanel-php {assignment_id}"


def _remove_all_php_blocks(content: str) -> str:
    return re.sub(
        r"\n?# BEGIN hostpanel-php [a-z0-9-]+\n.*?# END hostpanel-php [a-z0-9-]+\n?",
        "\n",
        content,
        flags=re.S,
    )


def _insert_before_last_brace(content: str, block: str) -> str:
    index = content.rfind("}")
    if index == -1:
        raise HTTPException(status_code=500, detail="nginx vhost has invalid structure")
    return content[:index].rstrip() + "\n\n" + block.rstrip() + "\n" + content[index:]


def enable_php(assignment: dict) -> None:
    domain = validate_domain_name(assignment["domain"])
    assignment_id = validate_assignment_id(assignment["id"])
    begin, end = _markers(assignment_id)
    block = f"""{begin}
index index.php index.html index.htm;

location ~ \\.php$ {{
    try_files $uri =404;
    fastcgi_pass unix:{assignment['socket_path']};
    fastcgi_index index.php;
    include /opt/hostpanel/plugins/php/conf/fastcgi-php.conf;
    fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
    fastcgi_param DOCUMENT_ROOT $document_root;
}}
{end}
"""
    existing = _remove_all_php_blocks(_read(domain))
    if "location ~ \\.php" in existing or "location ~ \\.php$" in existing:
        raise HTTPException(status_code=409, detail="A custom PHP nginx block already exists for this domain")
    updated = _insert_before_last_brace(existing, block)
    _write(domain, updated)
    validate_config()
    reload()


def disable_php(assignment: dict) -> None:
    domain = validate_domain_name(assignment["domain"])
    existing = _read(domain)
    updated = _remove_all_php_blocks(existing)
    if updated != existing:
        _write(domain, updated)
        validate_config()
        reload()


def validate_config() -> None:
    if os.path.exists(NGINX_BIN):
        _sudo([NGINX_BIN, "-t"], check=True)


def reload() -> None:
    if os.path.exists(NGINX_BIN):
        _sudo([NGINX_BIN, "-s", "reload"], check=False)
