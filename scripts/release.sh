#!/usr/bin/env bash
# Usage: scripts/release.sh <version>
#
# Bumps version strings, updates CHANGELOG, commits, tags, and pushes so
# the GitHub Actions release workflow takes over from there.
#
# Example:
#   scripts/release.sh 1.0.3

set -euo pipefail

# ── helpers ──────────────────────────────────────────────────────────────────

die() { echo "error: $*" >&2; exit 1; }

# ── validate input ───────────────────────────────────────────────────────────

[[ $# -eq 1 ]] || die "usage: $0 <version>  (e.g. 1.0.3)"

VERSION="${1#v}"   # strip leading 'v' if supplied
TAG="v${VERSION}"

[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || \
    die "version must be semver (MAJOR.MINOR.PATCH), got: $VERSION"

# ── pre-flight checks ────────────────────────────────────────────────────────

command -v uv  >/dev/null || die "'uv' not found"
command -v git >/dev/null || die "'git' not found"

# Must be on main with a clean working tree
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
[[ "$BRANCH" == "main" ]] || die "must be on main (currently on '$BRANCH')"

[[ -z "$(git status --porcelain)" ]] || \
    die "working tree is dirty — commit or stash changes first"

# Tag must not already exist
git rev-parse "$TAG" >/dev/null 2>&1 && \
    die "tag $TAG already exists"

echo "→ releasing $TAG"

# ── run tests ────────────────────────────────────────────────────────────────

echo "→ running lint, format, and tests …"
uv run ruff check .
uv run ruff format .
uv run mypy
uv run pytest

# ── bump version strings ─────────────────────────────────────────────────────

echo "→ bumping version to $VERSION"

PYPROJECT="pyproject.toml"
INIT_PY="src/rc0/__init__.py"

# pyproject.toml: version = "X.Y.Z"
sed -i.bak "s/^version = \"[^\"]*\"/version = \"${VERSION}\"/" "$PYPROJECT"
rm -f "${PYPROJECT}.bak"

# src/rc0/__init__.py: __version__ = "X.Y.Z"
sed -i.bak "s/__version__ = \"[^\"]*\"/__version__ = \"${VERSION}\"/" "$INIT_PY"
rm -f "${INIT_PY}.bak"

# Verify the substitutions landed
grep -q "version = \"${VERSION}\"" "$PYPROJECT"     || die "version not updated in $PYPROJECT"
grep -q "__version__ = \"${VERSION}\"" "$INIT_PY"  || die "version not updated in $INIT_PY"

# ── update CHANGELOG ─────────────────────────────────────────────────────────

echo "→ updating CHANGELOG.md"

CHANGELOG="CHANGELOG.md"
TODAY="$(date +%Y-%m-%d)"

# Replace the first occurrence of "## [Unreleased]" with a released header,
# then insert a fresh [Unreleased] section above it.
sed -i.bak \
    "s|^## \[Unreleased\]|## [Unreleased]\n\n## [${VERSION}] — ${TODAY}|" \
    "$CHANGELOG"
rm -f "${CHANGELOG}.bak"

# ── commit, tag, push ────────────────────────────────────────────────────────

echo "→ committing"
git add "$PYPROJECT" "$INIT_PY" "$CHANGELOG"
git commit -m "chore: release $TAG"

echo "→ tagging $TAG"
git tag -a "$TAG" -m "$TAG"

echo "→ pushing"
git push origin main
git push origin "$TAG"

echo ""
echo "✓ $TAG pushed — GitHub Actions will handle the rest."
echo "  https://github.com/zoltanf/rc0-cli/actions"
