"""Binary-startup performance budget.

Runs the PyInstaller-built ``rc0`` binary repeatedly and asserts the
median wall-clock time stays under the budget. The first run is
discarded because macOS Gatekeeper and the kernel page cache make the
very first invocation an outlier.

Gated by ``RC0_PERF=1`` (and a built binary at ``dist/rc0/rc0``) so the
default ``pytest`` invocation does not require a build step.
"""

from __future__ import annotations

import os
import statistics
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BINARY = REPO_ROOT / "dist" / "rc0" / "rc0"

# Budget per project goal: cold-cache-warmed startup < 200ms for trivial commands.
BUDGET_SECONDS = 0.200
RUNS = 7
WARMUPS = 2

pytestmark = pytest.mark.skipif(
    os.environ.get("RC0_PERF") != "1" or not BINARY.exists(),
    reason="Set RC0_PERF=1 and build the binary (uv run pyinstaller rc0.spec) to run.",
)


def _measure(args: list[str]) -> float:
    start = time.perf_counter()
    result = subprocess.run(  # noqa: S603  # invokes our own built binary
        [str(BINARY), *args],
        capture_output=True,
        check=False,
    )
    elapsed = time.perf_counter() - start
    assert result.returncode == 0, (
        f"rc0 {args} exited {result.returncode}: {result.stderr.decode(errors='replace')}"
    )
    return elapsed


def _median_over_runs(args: list[str]) -> float:
    for _ in range(WARMUPS):
        _measure(args)
    samples = [_measure(args) for _ in range(RUNS)]
    return statistics.median(samples)


def test_version_startup_under_budget() -> None:
    """`rc0 --version` is the cheapest invocation and must stay under 200ms."""
    median = _median_over_runs(["--version"])
    assert median < BUDGET_SECONDS, (
        f"rc0 --version median startup {median * 1000:.1f}ms "
        f"exceeds budget {BUDGET_SECONDS * 1000:.0f}ms"
    )


def test_help_startup_under_budget() -> None:
    """`rc0 --help` lists every subcommand and must also stay under budget."""
    median = _median_over_runs(["--help"])
    assert median < BUDGET_SECONDS, (
        f"rc0 --help median startup {median * 1000:.1f}ms "
        f"exceeds budget {BUDGET_SECONDS * 1000:.0f}ms"
    )
