#!/bin/sh
set -eu
FRESHEYE_TEST_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$FRESHEYE_TEST_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m unittest discover -s "$FRESHEYE_TEST_ROOT/tests" -v
