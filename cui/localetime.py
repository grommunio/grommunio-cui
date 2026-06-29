# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH
"""Wrappers around localectl / timedatectl / hostnamectl.

Previously the CUI shelled out to yast2 for language, keyboard, timezone and
hostname configuration. yast2 is openSUSE-specific; the systemd tools used here
work on all supported distributions (openSUSE, Debian, Ubuntu, RHEL, Fedora).
"""
import subprocess
from typing import List


def _run(cmd: List[str], timeout: int = 15) -> str:
    try:
        out = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            check=False, timeout=timeout,
        )
        return out.stdout.decode(errors="replace")
    except (OSError, subprocess.SubprocessError):
        return ""


def list_locales() -> List[str]:
    raw = _run(["localectl", "list-locales"])
    locales = [line.strip() for line in raw.splitlines() if line.strip()]
    if locales:
        return locales
    # Fallback: parse `locale -a` if localectl is mute (e.g. in containers).
    raw = _run(["locale", "-a"])
    return [line.strip() for line in raw.splitlines() if line.strip()]


def get_current_locale() -> str:
    raw = _run(["localectl", "status"])
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("System Locale:"):
            tail = line.split(":", 1)[1].strip()
            if tail in ("(unset)", "n/a", "-"):
                return ""
            for token in tail.split():
                if token.startswith("LANG="):
                    return token.split("=", 1)[1]
    return ""


def set_locale(lang: str) -> bool:
    if not lang:
        return False
    try:
        rc = subprocess.run(
            ["localectl", "set-locale", f"LANG={lang}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False, timeout=15,
        )
        return rc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def list_keymaps() -> List[str]:
    raw = _run(["localectl", "list-keymaps"])
    return [line.strip() for line in raw.splitlines() if line.strip()]


def get_current_keymap() -> str:
    raw = _run(["localectl", "status"])
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("VC Keymap:"):
            value = line.split(":", 1)[1].strip()
            # localectl prints `(unset)` when no keymap has been configured;
            # treat that as an empty answer so callers can fall back to the
            # file-based lookup or a sane default.
            if value in ("(unset)", "n/a", "-"):
                return ""
            return value
    return ""


def set_keymap(keymap: str) -> bool:
    if not keymap:
        return False
    try:
        rc = subprocess.run(
            ["localectl", "set-keymap", keymap],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False, timeout=15,
        )
        return rc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def list_timezones() -> List[str]:
    raw = _run(["timedatectl", "list-timezones"])
    return [line.strip() for line in raw.splitlines() if line.strip()]


def get_current_timezone() -> str:
    raw = _run(["timedatectl", "show", "--property=Timezone", "--value"])
    return raw.strip()


def set_timezone(tz: str) -> bool:
    if not tz:
        return False
    try:
        rc = subprocess.run(
            ["timedatectl", "set-timezone", tz],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False, timeout=15,
        )
        return rc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def get_hostname() -> str:
    raw = _run(["hostnamectl", "--static"]).strip()
    if raw and raw not in ("(unset)", "n/a", "-"):
        return raw
    try:
        with open("/etc/hostname", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def set_hostname(name: str) -> bool:
    if not name:
        return False
    try:
        rc = subprocess.run(
            ["hostnamectl", "set-hostname", name],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False, timeout=15,
        )
        return rc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
