"""Unit tests for `rc0 skill install` / `rc0 skill uninstall`."""

from __future__ import annotations

from importlib import resources
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from rc0.app import app

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def cli() -> CliRunner:
    # Pin terminal env so Rich renders error panels as plain text with a
    # predictable width; otherwise CI (FORCE_COLOR=1) injects ANSI escapes
    # that split flag names across sequences and break substring asserts.
    return CliRunner(env={"COLUMNS": "200", "NO_COLOR": "1", "TERM": "dumb"})


@pytest.fixture
def scoped_fs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Sandbox both HOME and CWD into ``tmp_path`` so scope paths are isolated."""
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"
    home.mkdir()
    cwd.mkdir()
    monkeypatch.setenv("HOME", str(home))
    # Windows' Path.home() consults USERPROFILE before HOME — patch both so
    # `--global` targets the sandbox on every platform.
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.chdir(cwd)
    # Prevent the keyring fixture or real credentials from leaking in.
    monkeypatch.delenv("RC0_API_TOKEN", raising=False)
    monkeypatch.delenv("RC0_CONFIG", raising=False)
    return tmp_path


def _project_target(tmp_path: Path) -> Path:
    return tmp_path / "cwd" / ".claude" / "skills" / "rc0" / "SKILL.md"


def _global_target(tmp_path: Path) -> Path:
    return tmp_path / "home" / ".claude" / "skills" / "rc0" / "SKILL.md"


def _bundled_body() -> str:
    return resources.files("rc0.skill").joinpath("SKILL.md").read_text(encoding="utf-8")


# ================================================================== install


def test_install_project_writes_expected_payload(cli: CliRunner, scoped_fs: Path) -> None:
    r = cli.invoke(app, ["skill", "install", "--project"])
    assert r.exit_code == 0, r.output
    target = _project_target(scoped_fs)
    assert target.exists()
    assert target.read_text(encoding="utf-8") == _bundled_body()
    assert f"wrote {target}" in r.output


def test_install_global_uses_home_dir(cli: CliRunner, scoped_fs: Path) -> None:
    r = cli.invoke(app, ["skill", "install", "--global"])
    assert r.exit_code == 0, r.output
    target = _global_target(scoped_fs)
    assert target.exists()
    assert target.read_text(encoding="utf-8") == _bundled_body()
    assert not _project_target(scoped_fs).exists()


def test_install_short_global_flag(cli: CliRunner, scoped_fs: Path) -> None:
    r = cli.invoke(app, ["skill", "install", "-g"])
    assert r.exit_code == 0, r.output
    assert _global_target(scoped_fs).exists()


def test_install_requires_scope_flag(cli: CliRunner, scoped_fs: Path) -> None:
    r = cli.invoke(app, ["skill", "install"])
    assert r.exit_code != 0
    assert "--project" in r.output and "--global" in r.output
    assert not _project_target(scoped_fs).exists()
    assert not _global_target(scoped_fs).exists()


def test_install_rejects_both_scope_flags(cli: CliRunner, scoped_fs: Path) -> None:
    r = cli.invoke(app, ["skill", "install", "--project", "--global"])
    assert r.exit_code != 0
    assert not _project_target(scoped_fs).exists()
    assert not _global_target(scoped_fs).exists()


def test_install_prompts_on_overwrite_and_decline_preserves_file(
    cli: CliRunner, scoped_fs: Path
) -> None:
    # First install lays down the real body.
    assert cli.invoke(app, ["skill", "install", "--project"]).exit_code == 0
    target = _project_target(scoped_fs)
    # Tamper with it to detect whether the decline left it untouched.
    sentinel = "SENTINEL-DO-NOT-OVERWRITE"
    target.write_text(sentinel, encoding="utf-8")

    r = cli.invoke(app, ["skill", "install", "--project"], input="n\n")
    assert r.exit_code == 12  # ConfirmationDeclined
    assert target.read_text(encoding="utf-8") == sentinel


def test_install_overwrites_with_yes_flag(cli: CliRunner, scoped_fs: Path) -> None:
    assert cli.invoke(app, ["skill", "install", "--project"]).exit_code == 0
    target = _project_target(scoped_fs)
    target.write_text("stale", encoding="utf-8")

    r = cli.invoke(app, ["-y", "skill", "install", "--project"])
    assert r.exit_code == 0, r.output
    assert target.read_text(encoding="utf-8") == _bundled_body()


def test_install_dry_run_does_not_write(cli: CliRunner, scoped_fs: Path) -> None:
    r = cli.invoke(app, ["--dry-run", "skill", "install", "--project"])
    assert r.exit_code == 0, r.output
    target = _project_target(scoped_fs)
    assert f"would write {target}" in r.output
    assert not target.exists()


# ================================================================= uninstall


def test_uninstall_removes_file_and_parent_dir(cli: CliRunner, scoped_fs: Path) -> None:
    assert cli.invoke(app, ["skill", "install", "--project"]).exit_code == 0
    target = _project_target(scoped_fs)
    assert target.exists()

    r = cli.invoke(app, ["-y", "skill", "uninstall", "--project"])
    assert r.exit_code == 0, r.output
    assert not target.exists()
    # The rc0/ parent directory should have been cleaned up too.
    assert not target.parent.exists()
    # But .claude/skills/ itself should be untouched.
    assert target.parent.parent.exists()


def test_uninstall_missing_is_idempotent(cli: CliRunner, scoped_fs: Path) -> None:
    r = cli.invoke(app, ["skill", "uninstall", "--project"])
    assert r.exit_code == 0, r.output
    assert "not installed" in r.output


def test_uninstall_prompt_declined_leaves_file(cli: CliRunner, scoped_fs: Path) -> None:
    assert cli.invoke(app, ["skill", "install", "--project"]).exit_code == 0
    target = _project_target(scoped_fs)

    r = cli.invoke(app, ["skill", "uninstall", "--project"], input="n\n")
    assert r.exit_code == 12
    assert target.exists()


def test_uninstall_dry_run_does_not_remove(cli: CliRunner, scoped_fs: Path) -> None:
    assert cli.invoke(app, ["skill", "install", "--project"]).exit_code == 0
    target = _project_target(scoped_fs)

    r = cli.invoke(app, ["--dry-run", "skill", "uninstall", "--project"])
    assert r.exit_code == 0, r.output
    assert f"would remove {target}" in r.output
    assert target.exists()


# ======================================================== bundled resource


def test_skill_resource_is_bundled() -> None:
    body = _bundled_body()
    assert body.startswith("---\nname: rc0\n")
    assert "description: Use when the user wants to manage DNS zones" in body
    assert "rc0 zone list" in body
    # Binary-path line must be portable — no Homebrew hardcoded path.
    assert "/opt/homebrew/bin/rc0" not in body
    assert "Binary: `rc0`" in body
