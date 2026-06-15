#!/usr/bin/env bash
set -euo pipefail

VERSION="$(python3 - <<'PY'
import re
from pathlib import Path
text = Path("plugin/setup.py").read_text()
match = re.search(r'version="([^"]+)"', text)
if not match:
    raise SystemExit("Could not find version in plugin/setup.py")
print(match.group(1))
PY
)"

ZIP="hostpanel-php-${VERSION}.zip"
SOURCE="sources/php-8.4-linux-arm64.tar.xz"

if [ ! -f "$SOURCE" ]; then
  echo "Missing runtime source archive: $SOURCE" >&2
  exit 1
fi

mkdir -p bin
tar -xOf "$SOURCE" "php-8.4/bin/php-8.4" > bin/php-8.4
tar -xOf "$SOURCE" "php-8.4/sbin/php-fpm-8.4" > bin/php-fpm-8.4
chmod +x bin/php-8.4 bin/php-fpm-8.4

for path in bin/php-8.4 bin/php-fpm-8.4
do
  if [ ! -x "$path" ]; then
    echo "Missing executable runtime asset: $path" >&2
    exit 1
  fi
done

rm -f "$ZIP"

zip -qr "$ZIP" \
  plugin \
  frontend \
  bin \
  conf \
  service \
  sudoers \
  README.md \
  test.scenario \
  -x "*.DS_Store" \
  -x "*/.DS_Store" \
  -x "__pycache__/*" \
  -x "*/__pycache__/*" \
  -x "*.pyc" \
  -x "*.tar.gz" \
  -x "*.tar.xz" \
  -x "*.tgz" \
  -x "*.zip"

echo "Built $ZIP"
