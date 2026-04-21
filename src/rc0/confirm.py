"""Confirmation prompts for destructive commands.

Mission plan §7:

* Show a dry-run-style summary first.
* For zone-level destructive ops, require the user to type the zone name
  (``gh`` style). Type mismatch raises :class:`ConfirmationDeclined`.
* For other destructive ops, a simple ``y/N`` prompt.
"""

from __future__ import annotations

import sys

from rc0.client.errors import ConfirmationDeclined


def _prompt(message: str) -> str:
    sys.stderr.write(message)
    sys.stderr.flush()
    line = sys.stdin.readline()
    if not line:
        raise ConfirmationDeclined("No input received.")
    return line.strip()


def confirm_typed(expected: str, *, summary: str) -> None:
    """Zone-style confirmation: user must type ``expected`` verbatim."""
    sys.stderr.write(summary.rstrip("\n") + "\n")
    answer = _prompt(f'Type "{expected}" to confirm: ')
    if answer != expected:
        raise ConfirmationDeclined(
            f"Confirmation did not match (expected {expected!r}, got {answer!r}).",
        )


def confirm_yes_no(summary: str, *, default_no: bool = True) -> None:
    """Simple ``y/N`` confirmation. Empty input accepts the default."""
    sys.stderr.write(summary.rstrip("\n") + "\n")
    suffix = "[y/N]" if default_no else "[Y/n]"
    answer = _prompt(f"Continue? {suffix} ").lower()
    accepted = {"y", "yes"}
    if answer in accepted:
        return
    if not answer and not default_no:
        return
    raise ConfirmationDeclined("User declined.")
