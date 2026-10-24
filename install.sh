#!/bin/sh
set -eu
FRESHEYE_INSTALL_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$FRESHEYE_INSTALL_ROOT/tools/install.py" "$@"
