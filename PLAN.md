# hostpanel-php Development Plan

This plan defines the first implementation of `hostpanel-package-php` as a HostPanel package. The package should behave like a native HostPanel hosting feature, follow the HostPanel Package Development Guide and Package UI Guide, and integrate cleanly with the existing nginx domain registry.

## Goal

Provide PHP hosting through PHP-FPM:

- Bundle one controlled PHP 8.4 runtime.
- Let admins and hosting users enable PHP for an existing main domain or subdomain.
- Exclude reserved hostnames such as `cpanel.*` and `ftp.*`.
- Use the domain's existing document root from the HostPanel domain registry.
- Generate one PHP-FPM pool per domain/subdomain assignment.
- Add nginx FastCGI handling for `index.php` and other PHP scripts.
- Store PHP assignments, pool settings, and lifecycle state in the HostPanel database.
- Audit-log every mutating operation.
- Expose per-domain PHP-FPM logs.
- Allow assignments to be edited, restarted, disabled, and deleted.
- Preserve DNS, SSL, static files, FTP accounts, databases, and Linux users.

## Current State

`hostpanel-package-php` is currently an empty placeholder repository:

- No package layout.
- No Python plugin.
- No frontend.
- No PHP binaries or source archives.
- No service/sudoers.
- No build or release workflow.

This is a greenfield package.

## Recommended v1 Scope

Build a PHP-FPM hosting package, not a full application deployer.

v1 should manage:

- PHP 8.4 runtime availability.
- Domain PHP enablement.
- PHP-FPM service/pool lifecycle.
- nginx FastCGI config for assigned domains.
- Common PHP settings per assignment.
- Logs and audit trail.

v1 should not manage:

- Composer installs.
- Framework deployment.
- Database creation.
- WordPress installer workflows.
- Source builds on the production server during package install.

Those can be later packages or v1.1 features.

## Target Structure

```text
hostpanel-package-php/
  README.md
  PLAN.md
  build.sh
  test.scenario
  .gitignore
  .github/
    workflows/
      release.yml
  plugin/
    setup.py
    hostpanel_php/
      __init__.py
      plugin.py
      routes.py
      lifecycle.py
      store.py
      validators.py
      fpm.py
      nginx.py
      audit.py
      logs.py
  frontend/
    main.js
  sources/
    php-8.4-linux-arm64.tar.xz
  bin/
    .gitkeep
  conf/
    php-fpm.conf
    pool-template.conf
    php.ini
  service/
    hostpanel-php-fpm.service
  sudoers/
    hostpanel-php
```

`sources/` should hold compressed runtime archives under GitHub's per-file limit. `build.sh` extracts only the required runtime files into `bin/` before creating the release zip, similar to the Node.js package strategy.

## Runtime Strategy

Supported v1 PHP version:

```text
8.4
```

Future PHP version changes should ship as plugin updates. For example, v1.1 can replace PHP 8.4 with a newer stable PHP runtime, or add a selector if multi-version support becomes necessary.

Recommended installed runtime layout:

```text
/opt/hostpanel/plugins/php/
  bin/php-8.4
  sbin/php-fpm-8.4
  etc/php-fpm.conf
  etc/php.ini
  pools/
    <assignment_id>.conf
  logs/
    <assignment_id>.log
```

Open runtime decision:

- Preferred: compile PHP on the actual ARM64 server, package compressed runtime archives in `sources/`, and let `build.sh` extract release assets.
- Avoid committing raw PHP binaries directly if any file approaches GitHub's limits.
- If PHP-FPM needs shared libraries, package the full runtime tree, not isolated binaries.

Acceptance criteria:

- `php-8.4 -v` works on the target server.
- `php-fpm-8.4 -t` validates with generated config.
- PHP-FPM can run pools as the assigned Linux owner.
- Package install fails clearly if runtime assets are absent.
- Runtime does not depend on `apt install php`.

## Package Metadata

`plugin/setup.py`:

```python
from setuptools import find_packages, setup

setup(
    name="hostpanel-php",
    version="1.0.0",
    packages=find_packages(),
    install_requires=["fastapi", "pydantic"],
    entry_points={
        "hostpanel.modules": [
            "php = hostpanel_php.plugin",
        ],
        "hostpanel.setup": [
            "hostpanel-php = hostpanel_php.lifecycle:on_install",
        ],
        "hostpanel.lifecycle": [
            "hostpanel-php = hostpanel_php.lifecycle:pre_uninstall",
        ],
        "hostpanel.hooks.on_startup": [
            "hostpanel-php = hostpanel_php.lifecycle:on_startup",
        ],
        "hostpanel.hooks.user_delete": [
            "hostpanel-php = hostpanel_php.lifecycle:on_user_delete",
        ],
        "hostpanel.hooks.domain_delete": [
            "hostpanel-php = hostpanel_php.lifecycle:on_domain_delete",
        ],
        "hostpanel.hooks.ssl_cert_imported": [
            "hostpanel-php = hostpanel_php.lifecycle:on_ssl_cert_imported",
        ],
        "hostpanel.hooks.ssl_cert_deleted": [
            "hostpanel-php = hostpanel_php.lifecycle:on_ssl_cert_deleted",
        ],
    },
)
```

`PLUGIN_MANIFEST`:

```python
PLUGIN_MANIFEST = {
    "requires_core": [1, 0, 0],
    "repository": "https://github.com/Developer-Geekay/hostpanel-package-php",
    "nav_items": [{
        "nav_route": "php",
        "nav_label": "PHP",
        "nav_icon": "code",
        "nav_section": "hosting",
        "nav_section_label": "Hosting",
        "nav_section_order": 30,
        "admin_only": False,
    }],
    "dashboard_blocks": [{
        "type": "stat",
        "label": "PHP Sites",
        "icon": "code",
        "endpoint": "php/count",
        "size": "sm",
    }],
    "service": {
        "name": "php",
        "unit": "hostpanel-php-fpm",
        "label": "PHP-FPM 8.4",
        "icon": "code",
        "can_reload": True,
    },
}
```

## Database Model

Store PHP assignment state in SQLite.

Recommended tables:

```sql
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
```

Rules:

- One active PHP assignment per domain/subdomain.
- Domain choices come from main domains and subdomains.
- Exclude `cpanel.*` and `ftp.*`.
- Standard users only see domains and assignments owned by their `linux_user`.
- Admins can see and manage all assignments.
- Document root comes from the domain registry and should not be manually changed in v1.
- Every mutating operation is audit logged.

## Provisioning Flow

Frontend flow:

1. User clicks `Add PHP Site`.
2. A base-theme modal opens.
3. Modal loads eligible target domains from `/cpanelapi/php/domains`.
4. Domain dropdown includes:
   - Main domains.
   - Subdomains.
   - Only domains the current user may access.
   - No `cpanel.*`.
   - No `ftp.*`.
   - No domain already assigned to PHP unless editing that assignment.
5. User selects a domain.
6. Document root auto-fills from the selected domain registry record.
7. User optionally adjusts safe PHP settings.
8. User clicks `Enable PHP`.

Backend provision operation:

1. Validate domain access.
2. Validate domain is not reserved.
3. Resolve document root from domain registry.
4. Validate PHP 8.4 runtime exists.
5. Create assignment DB record.
6. Generate PHP-FPM pool config.
7. Validate PHP-FPM config.
8. Reload or restart PHP-FPM service.
9. Update nginx vhost with PHP FastCGI location.
10. Validate nginx config.
11. Reload nginx.
12. Write audit entries and lifecycle logs.

If a later step fails, mark assignment as `failed` and preserve diagnostic logs.

## PHP-FPM Pool Strategy

Generate one pool per assignment:

```text
/opt/hostpanel/plugins/php/pools/<assignment_id>.conf
```

Example pool:

```ini
[<assignment_id>]
user = <username>
group = <username>
listen = /run/hostpanel-php/<assignment_id>.sock
listen.owner = <username>
listen.group = nginx
listen.mode = 0660
pm = ondemand
pm.max_children = 10
pm.process_idle_timeout = 10s
pm.max_requests = 500
chdir = <document_root>
php_admin_value[open_basedir] = <document_root>:/tmp
php_admin_value[error_log] = /opt/hostpanel/plugins/php/logs/<assignment_id>.error.log
php_admin_flag[log_errors] = on
php_value[memory_limit] = 256M
php_value[upload_max_filesize] = 64M
php_value[post_max_size] = 64M
php_value[max_execution_time] = 60
php_value[max_input_vars] = 3000
php_flag[display_errors] = off
```

Important constraints:

- Run pools as the hosting Linux user, not root.
- Validate assignment IDs before writing files.
- Validate setting values with strict allowlists.
- Keep generated pool files owned by root.
- Preserve app/site files.

## Service Strategy

Preferred v1 service:

```text
hostpanel-php-fpm.service
```

The service should launch a controlled PHP-FPM master using the package config:

```ini
[Unit]
Description=HostPanel PHP-FPM
After=network.target

[Service]
Type=simple
ExecStart=/opt/hostpanel/plugins/php/sbin/php-fpm-8.4 --nodaemonize --fpm-config /opt/hostpanel/plugins/php/etc/php-fpm.conf
ExecReload=/bin/kill -USR2 $MAINPID
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Recommended implementation:

- Use one package service: `hostpanel-php-fpm`.
- The service runs PHP-FPM 8.4.
- All generated pools are PHP 8.4 pools.
- Future plugin updates may replace the PHP runtime and rewrite pools if needed.

## Nginx Integration

The PHP package does not own nginx, domains, DNS, or SSL. It updates only PHP-related FastCGI behavior for assigned domains.

Preferred integration model:

- Preserve nginx-owned vhost files.
- Add a managed PHP block to the selected domain's vhost.
- Do not overwrite unrelated custom vhost content.
- Validate with nginx `-t` before reload.
- On delete/disable, remove only the managed PHP block.

Managed block marker:

```nginx
# BEGIN hostpanel-php <assignment_id>
index index.php index.html index.htm;

location ~ \.php$ {
    try_files $uri =404;
    include /opt/hostpanel/plugins/nginx/fastcgi_params;
    fastcgi_pass unix:/run/hostpanel-php/<assignment_id>.sock;
    fastcgi_index index.php;
    fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
    fastcgi_param DOCUMENT_ROOT $document_root;
}
# END hostpanel-php <assignment_id>
```

If nginx lacks `fastcgi_params`, the PHP package should ship a compatible snippet under:

```text
/opt/hostpanel/plugins/php/conf/fastcgi-php.conf
```

and include that snippet instead.

Guardrails:

- Check domain ownership through `domain_registry._load_domains()` and `_load_subdomains()`.
- Standard users can only attach domains they own.
- Exclude `cpanel.*` and `ftp.*`.
- If a vhost has a non-HostPanel custom PHP block, block changes and ask admin to edit manually.
- Audit nginx writes/removals.
- Reload nginx only after config validation.

## Backend API

Prefix:

```text
/cpanelapi/php
```

Endpoints:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/assignments` | List visible PHP assignments |
| `POST` | `/assignments` | Enable PHP for a domain/subdomain |
| `GET` | `/assignments/{id}` | Get assignment details |
| `PUT` | `/assignments/{id}` | Edit PHP settings |
| `DELETE` | `/assignments/{id}` | Disable PHP and remove generated pool/nginx block |
| `POST` | `/assignments/{id}/restart` | Restart/reload PHP-FPM |
| `GET` | `/assignments/{id}/logs` | Return assignment logs |
| `GET` | `/domains` | List eligible main domains and subdomains |
| `GET` | `/runtime` | Return PHP 8.4 runtime info |
| `GET` | `/count` | Dashboard count |

Models:

- `PhpAssignmentCreateRequest`
- `PhpAssignmentUpdateRequest`
- `PhpAssignmentResponse`
- `PhpDomainOption`
- `PhpRuntimeInfo`
- `PhpSettings`

Validation:

- PHP version is fixed to `8.4` in v1.
- Domains: must come from eligible registry records.
- Domains: reject `cpanel.*` and `ftp.*`.
- Memory/upload/post sizes: allow values like `64M`, `128M`, `256M`, `512M`, `1G`.
- Execution time: bounded integer, for example `10-300`.
- Max input vars: bounded integer, for example `1000-10000`.
- Display errors: boolean.

## Audit Logging

Use HostPanel audit logging for every mutating operation.

Suggested actions:

```text
php.assignment_create
php.assignment_update
php.assignment_delete
php.assignment_restart
php.pool_write
php.pool_remove
php.nginx_php_enable
php.nginx_php_disable
php.service_reload
```

Audit details should include:

- `assignment_id`.
- `username`.
- `domain`.
- `php_version`, always `8.4` in v1.
- Changed fields for edits.

Do not log sensitive environment or request data.

## Logs

Expose logs through:

```text
GET /cpanelapi/php/assignments/{id}/logs
```

Sources:

- PHP-FPM pool error log.
- PHP-FPM service journal.
- `php_assignment_logs` lifecycle table.

UI:

- Add row action: `Logs`.
- Use a base-theme modal.
- Use `log-output` class.
- Include refresh action.
- Scope access to assignment owner/admin.

## Lifecycle Hooks

`on_install()`:

- Create `/opt/hostpanel/plugins/php`.
- Create `/run/hostpanel-php` through systemd runtime directory or install-time mkdir.
- Run DB migrations.
- Validate PHP 8.4 and PHP-FPM 8.4 binaries.
- Install default config files if absent.
- Run `systemctl daemon-reload`.
- Do not create pools until assignments are created.

`on_startup()`:

- Run DB migrations.
- Load assignments from DB.
- Repair missing pool files.
- Ensure PHP-FPM service is enabled/started.
- Refresh assignment status.
- Do not overwrite site files.

`pre_uninstall(force=False)`:

- If assignments exist and `force` is false, raise `409`.
- If forced:
  - Stop PHP-FPM services.
  - Remove generated pool files.
  - Remove PHP-managed nginx blocks.
  - Remove PHP assignment DB records.
  - Remove `/opt/hostpanel/plugins/php`.
  - Remove `/etc/sudoers.d/hostpanel-php`.
- Preserve Linux users, home directories, domains, DNS zones, SSL certs, FTP accounts, databases, and website files.

`on_user_delete(username, **kwargs)`:

- Stop/remove assignments owned by that user.
- Remove generated pools.
- Remove PHP-managed nginx blocks.
- Write audit records.
- Preserve files if core is not removing home.

`on_domain_delete(domain_name, **kwargs)`:

- Remove assignment for that domain.
- Remove generated pool.
- Remove PHP-managed nginx block.
- Write audit records.

`on_ssl_cert_imported(domain, **kwargs)` and `on_ssl_cert_deleted(domain, **kwargs)`:

- Reapply PHP-managed nginx block after nginx rewrites vhosts for SSL changes.
- Do not manage certs directly.

## Sudoers

`sudoers/hostpanel-php` should be narrow.

Likely required commands:

```text
%hostpanel ALL=(root) NOPASSWD: /bin/systemctl daemon-reload
%hostpanel ALL=(root) NOPASSWD: /bin/systemctl enable hostpanel-php-fpm
%hostpanel ALL=(root) NOPASSWD: /bin/systemctl disable hostpanel-php-fpm
%hostpanel ALL=(root) NOPASSWD: /bin/systemctl start hostpanel-php-fpm
%hostpanel ALL=(root) NOPASSWD: /bin/systemctl stop hostpanel-php-fpm
%hostpanel ALL=(root) NOPASSWD: /bin/systemctl restart hostpanel-php-fpm
%hostpanel ALL=(root) NOPASSWD: /bin/systemctl reload hostpanel-php-fpm
%hostpanel ALL=(root) NOPASSWD: /bin/systemctl is-active hostpanel-php-fpm
%hostpanel ALL=(root) NOPASSWD: /bin/journalctl -u hostpanel-php-fpm
%hostpanel ALL=(root) NOPASSWD: /usr/bin/tee /etc/systemd/system/hostpanel-php-fpm.service
%hostpanel ALL=(root) NOPASSWD: /bin/rm -f /etc/systemd/system/hostpanel-php-fpm.service
%hostpanel ALL=(root) NOPASSWD: /usr/bin/tee /opt/hostpanel/plugins/php/pools/*
%hostpanel ALL=(root) NOPASSWD: /bin/rm -f /opt/hostpanel/plugins/php/pools/*
%hostpanel ALL=(root) NOPASSWD: /opt/hostpanel/plugins/nginx/nginx -t
%hostpanel ALL=(root) NOPASSWD: /opt/hostpanel/plugins/nginx/nginx -s reload
```

Validate with:

```bash
sudo visudo -c -f sudoers/hostpanel-php
```

## Frontend UI

Use the HostPanel Package UI Guide.

Route:

```text
/app/php
```

Registered as:

```javascript
window.__hpkg_sdk.register('php', PhpPlugin)
```

Main UI:

- Page header:
  - Title: `PHP`
  - Description: `Manage PHP for hosted sites`
- Card: `Sites`
- Primary action: `Enable PHP`
- `SdkDataTable` columns:
  - Domain
  - Owner
  - Runtime
  - Document Root
  - Status
- Row actions:
  - Restart
  - Logs
  - Edit
  - Disable

Enable PHP modal fields:

| Field | Type | Behavior |
|---|---|---|
| Target domain | Select | Main domains and subdomains; excludes `cpanel.*` and `ftp.*` |
| Document root | Read-only text | Auto-filled from registry |
| Runtime | Read-only text | PHP 8.4 |
| Memory limit | Select | Safe preset values |
| Upload max filesize | Select | Safe preset values |
| Post max size | Select | Safe preset values |
| Max execution time | Number | Bounded |
| Max input vars | Number | Bounded |
| Display errors | Toggle | Default off |

Do not create a custom PHP-specific theme. Reuse:

```text
page
page-header
page-title
page-desc
card
card-title
btn
btn-primary
btn-ghost
btn-danger
modal
field
empty
badge
log-output
```

## Build Script

`build.sh` should:

1. Read version from `plugin/setup.py`.
2. Fail if required source archives are absent:
   - `sources/php-8.4-linux-arm64.tar.xz`
3. Extract/prepare runtime assets into `bin/` for the release package.
4. Build `hostpanel-php-<version>.zip`.
5. Include `plugin/`, `bin/`, `conf/`, `service/`, `sudoers/`, and `frontend/`.
6. Exclude dotfiles, source build directories, previous zips, `__pycache__`, `.pyc`, and local build artifacts.

## Release Workflow

Add:

```text
.github/workflows/release.yml
```

Use the safe pattern:

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Get version from tag
        id: version
        run: echo "VERSION=${GITHUB_REF_NAME#v}" >> "$GITHUB_OUTPUT"

      - name: Build zip
        run: |
          ./build.sh
          ZIP="hostpanel-php-${{ steps.version.outputs.VERSION }}.zip"
          test -f "$ZIP"
          echo "ZIP=$ZIP" >> "$GITHUB_ENV"

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          name: "hostpanel-php v${{ steps.version.outputs.VERSION }}"
          files: ${{ env.ZIP }}
          generate_release_notes: true
```

Before tagging, ensure `plugin/setup.py` version matches the tag without the leading `v`.

## Documentation

`README.md` should cover:

- What the package provides.
- PHP runtime version.
- Runtime strategy.
- Package layout.
- Build instructions.
- Install/upload instructions.
- API prefix and routes.
- Frontend route.
- Domain selection behavior.
- PHP-FPM pool behavior.
- nginx integration behavior.
- SSL hook behavior.
- Audit and logs.
- What uninstall preserves.

## Test Scenarios

Create `test.scenario` with:

1. Build package with `./build.sh`.
2. Upload and install `hostpanel-php-1.0.0.zip`.
3. Verify package appears in installed packages.
4. Verify `/app/php` frontend loads.
5. Verify runtime endpoint returns PHP 8.4.
6. Enable PHP modal lists eligible main domains and subdomains.
7. Confirm `cpanel.*` and `ftp.*` are excluded.
8. Selecting a domain auto-fills document root from registry.
9. Enable PHP for a test domain.
10. Verify assignment DB row exists.
11. Verify PHP-FPM pool file exists.
12. Verify PHP-FPM service is active.
13. Verify nginx vhost includes the managed PHP block.
14. Upload `info.php` and confirm PHP executes through nginx.
15. Change PHP settings and verify pool rewrite.
16. Verify logs are visible in Logs modal.
17. Disable PHP and verify pool and PHP block are removed.
18. Verify website files are preserved.
19. User delete hook removes that user's PHP assignments.
20. Domain delete hook removes assignment and PHP block.
21. SSL cert import/deletion hooks preserve or reapply PHP block correctly.
22. Uninstall is blocked when assignments exist.
23. Force uninstall removes PHP-owned resources and preserves Linux users, home directories, DNS, SSL, FTP, databases, and site files.

## Security Notes

Highest-risk areas:

- Writing PHP-FPM pool configs.
- Writing nginx vhost changes.
- Running multiple users through one PHP-FPM master.
- PHP file access outside document root.
- Exposing logs that may contain paths or sensitive request data.

Guardrails:

- Restrict pools to domain document roots.
- Use `open_basedir` per assignment.
- Run pools as the domain's Linux owner.
- Validate all PHP setting values.
- Validate nginx and PHP-FPM configs before reload.
- Avoid exposing logs to users who do not own the assignment.
- Remove only PHP-managed blocks and files.
- Preserve all non-PHP-owned resources.

## Suggested Implementation Order

1. Scaffold package layout.
2. Add `plugin/setup.py` and manifest.
3. Decide runtime packaging format after compiling PHP 8.4 on the ARM64 server.
4. Add source archives and build extraction logic.
5. Implement DB migrations.
6. Implement domain and runtime endpoints.
7. Implement assignment store and validators.
8. Implement PHP-FPM pool generation.
9. Implement service generation/reload for PHP-FPM 8.4.
10. Implement nginx managed PHP block insertion/removal.
11. Implement logs and audit logging.
12. Implement backend API.
13. Implement lifecycle hooks.
14. Add frontend UI using base HostPanel theme.
15. Add sudoers and validate it.
16. Add build script and release workflow.
17. Write README and test scenarios.
18. Test on a real HostPanel Linux ARM64 server.
19. Tag and release `v1.0.0`.

## Open Decisions

- Whether to package full PHP runtime trees or only binaries plus required shared libraries.
- Whether to compile common extensions into PHP or ship extension modules separately.
- Whether Composer should be a separate package or a later PHP package feature.
- Whether users can edit arbitrary php.ini values or only safe presets.
- Whether PHP-FPM should use Unix sockets only or allow TCP for debugging.
- Whether nginx should expose a formal hook for package-managed vhost blocks to avoid direct file patching.
