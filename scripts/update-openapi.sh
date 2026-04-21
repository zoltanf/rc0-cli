#!/usr/bin/env bash
# Refresh the pinned copy of the RcodeZero OpenAPI spec.
#
# Contract tests (tests/contract/) verify that every non-deprecated path in
# this pinned spec has a CLI implementation. Running this script bumps the
# pin; expect some contract-test failures on new endpoints until commands
# land.

set -euo pipefail

SPEC_URL="https://my.rcodezero.at/openapi/rcode0api-v2.json"
TARGET="tests/fixtures/openapi.json"

mkdir -p "$(dirname "$TARGET")"
echo "Fetching $SPEC_URL -> $TARGET"
curl --fail --silent --show-error --location "$SPEC_URL" > "$TARGET"
echo "Updated. Review the diff with: git diff -- $TARGET"
