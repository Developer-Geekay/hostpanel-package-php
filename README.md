# hostpanel-php

HostPanel package for enabling PHP 8.4 on hosted domains through PHP-FPM and nginx FastCGI.

## Features

- Bundles PHP 8.4 and PHP-FPM 8.4 for Linux ARM64.
- Enables PHP for existing main domains and subdomains.
- Excludes reserved `cpanel.*` and `ftp.*` hostnames.
- Stores assignments and lifecycle logs in HostPanel SQLite.
- Generates one PHP-FPM pool per assignment.
- Adds and removes only PHP-managed nginx FastCGI blocks.
- Preserves website files when PHP is disabled.

## Runtime Layout

Git tracks the compressed runtime archive:

```text
sources/php-8.4-linux-arm64.tar.xz
```

`build.sh` extracts these release files:

```text
bin/php-8.4
bin/php-fpm-8.4
```

Installed paths:

```text
/opt/hostpanel/plugins/php/php-8.4
/opt/hostpanel/plugins/php/php-fpm-8.4
```

## API

Prefix:

```text
/cpanelapi/php
```

Main routes:

```text
GET    /assignments
POST   /assignments
GET    /assignments/{id}
PUT    /assignments/{id}
DELETE /assignments/{id}
POST   /assignments/{id}/restart
GET    /assignments/{id}/logs
GET    /domains
GET    /runtime
GET    /count
```

## Build

```bash
chmod +x build.sh
./build.sh
```

The output is:

```text
hostpanel-php-1.0.0.zip
```

## Operational Notes

- PHP runtime is fixed to PHP 8.4 in v1.
- Future PHP runtime changes should ship as plugin updates.
- Domains and subdomains must already exist in HostPanel.
- Disable removes PHP-FPM pool and PHP nginx block, but preserves files.
- Uninstall is blocked while assignments exist unless forced.
