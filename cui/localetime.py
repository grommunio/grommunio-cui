# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH
"""Wrappers around localectl / timedatectl / hostnamectl.

Previously the CUI shelled out to yast2 for language, keyboard, timezone and
hostname configuration. yast2 is openSUSE-specific; the systemd tools used here
work on all supported distributions (openSUSE, Debian, Ubuntu, RHEL, Fedora).
"""
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


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


# --- /etc/hosts -------------------------------------------------------------
#
# `hostname -f` (and thereby grommunio-setup's FQDN) needs the hostname to
# resolve. Like YaST's "Assign Hostname to Loopback IP" we map it to 127.0.0.2,
# which, unlike the primary address, stays valid when DHCP hands out a new
# lease. The 127.0.0.2 line is treated as ours and replaced on every change.

_HOSTS = Path("/etc/hosts")
# openSUSE ships the stock hosts file in /usr/etc when /etc/hosts is absent.
_HOSTS_VENDOR = Path("/usr/etc/hosts")
_HOSTS_IP = "127.0.0.2"


def _hosts_line(name: str) -> str:
    """Return the hosts line for name: '<ip> <fqdn> <short>' or '<ip> <short>'."""
    short = name.split(".", 1)[0]
    if short != name:
        return f"{_HOSTS_IP}\t{name} {short}\n"
    return f"{_HOSTS_IP}\t{name}\n"


def set_hosts_entry(name: str) -> bool:
    """Point name at 127.0.0.2 in /etc/hosts, leaving all other lines alone."""
    if not name or name == "localhost":
        return True
    src = _HOSTS if _HOSTS.exists() else _HOSTS_VENDOR
    try:
        with src.open("r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        lines = []
    out: List[str] = []
    entry = _hosts_line(name)
    for line in lines:
        fields = line.split("#", 1)[0].split()
        if fields and fields[0] == _HOSTS_IP:
            # Replace the first previous entry in place, drop any duplicates.
            if entry:
                out.append(entry)
                entry = ""
            continue
        out.append(line)
    if entry:
        if out and not out[-1].endswith("\n"):
            out[-1] += "\n"
        out.append(entry)
    return _write_atomic(_HOSTS, "".join(out))


def _write_atomic(path: Path, body: str) -> bool:
    """Replace path with body via a temp file, keeping its permissions."""
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        mode = path.stat().st_mode & 0o7777
    except OSError:
        mode = 0o644
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(str(tmp), mode)
        os.replace(str(tmp), str(path))
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        return False
    _restore_selinux_context(path)
    return True


def _restore_selinux_context(path: Path) -> None:
    """Relabel path; the renamed temp file carries a generic SELinux label.

    Best-effort: a no-op where SELinux (restorecon) is not installed.
    """
    if not shutil.which("restorecon"):
        return
    try:
        subprocess.run(
            ["restorecon", str(path)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        pass


# --- systemd-timesyncd ------------------------------------------------------
#
# timesyncd only accepts assignments inside a [Time] section. We keep our
# servers in a drop-in of our own instead of editing the main file, so vendor
# and operator settings stay untouched. NTP= and FallbackNTP= are lists that
# add up across the main file and all drop-ins; only an empty assignment
# resets them. Our drop-in therefore resets each list before setting it, and
# sorts after the vendor drop-ins (SUSE asks for a priority above 70, its
# 25-defaults-openSUSE.conf sets FallbackNTP). Earlier CUI versions wrote
# NTP=/FallbackNTP= into /etc/systemd/timesyncd.conf without a section header;
# those stray lines are ignored by systemd ("Assignment outside of section")
# and are cleaned up on the next save.

TIMESYNCD_CONF = Path("/etc/systemd/timesyncd.conf")
TIMESYNCD_DROPIN = Path("/etc/systemd/timesyncd.conf.d/80-grommunio.conf")
_TIMESYNCD_KEYS = ("NTP", "FallbackNTP")
# systemd's search path, highest priority first: the first main file found is
# used, and a drop-in masks same-named drop-ins in later directories.
_TIMESYNCD_DIRS = (
    Path("/etc/systemd"),
    Path("/run/systemd"),
    Path("/usr/local/lib/systemd"),
    Path("/usr/lib/systemd"),
)


def _read_time_section(path: Path, values: Dict[str, Optional[str]]) -> None:
    """Apply NTP/FallbackNTP from the [Time] section of path to values.

    Like timesyncd, assignments append to the list and an empty one resets it.
    """
    section = ""
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line[0] in "#;":
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1].strip()
                    continue
                key, sep, val = line.partition("=")
                key = key.strip()
                if sep and section == "Time" and key in _TIMESYNCD_KEYS:
                    servers = val.split()
                    if servers and values[key]:
                        servers = values[key].split() + servers
                    values[key] = " ".join(servers)
    except OSError:
        pass


def get_ntp_config() -> Dict[str, Optional[str]]:
    """Return the effective NTP/FallbackNTP lists (None if never assigned)."""
    if _chrony_in_use():
        return _get_chrony_config()
    values: Dict[str, Optional[str]] = {key: None for key in _TIMESYNCD_KEYS}
    for directory in _TIMESYNCD_DIRS:
        main = directory / "timesyncd.conf"
        if main.exists():
            _read_time_section(main, values)
            break
    dropins: Dict[str, Path] = {}
    for directory in (d / "timesyncd.conf.d" for d in _TIMESYNCD_DIRS):
        if directory.is_dir():
            for candidate in directory.glob("*.conf"):
                dropins.setdefault(candidate.name, candidate)
    for name in sorted(dropins):
        _read_time_section(dropins[name], values)
    return values


def _strip_sectionless_ntp(path: Path) -> None:
    """Remove NTP assignments written outside any section by older CUIs."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return
    out: List[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_section = True
        key = stripped.partition("=")[0].strip()
        if not in_section and "=" in stripped and key in _TIMESYNCD_KEYS:
            continue
        out.append(line)
    if out == lines:
        return
    if not any(l.strip() and l.strip()[0] not in "#;" for l in out):
        # Nothing but comments left: the file was ours, remove it entirely.
        try:
            path.unlink()
        except OSError:
            pass
        return
    _write_atomic(path, "".join(out))


# Where chronyd is the time service (e.g. the Raspberry Pi image), timesyncd
# is inactive and its configuration is never read. chrony has no fallback
# list and every configured source is used, so both lists become sources in
# our drop-in; sources in other chrony files stay in effect.
CHRONY_DROPIN = Path("/etc/chrony.d/80-grommunio.conf")


def _chrony_in_use() -> bool:
    """True if chronyd, not timesyncd, keeps the clock in sync."""
    for verb in ("is-active", "is-enabled"):
        try:
            rc = subprocess.run(
                ["systemctl", "-q", verb, "chronyd.service"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=False, timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        if rc.returncode == 0:
            return True
    return False


def _get_chrony_config() -> Dict[str, Optional[str]]:
    servers: List[str] = []
    try:
        with CHRONY_DROPIN.open("r", encoding="utf-8") as fh:
            for raw in fh:
                words = raw.split()
                if len(words) >= 2 and words[0] in ("server", "pool"):
                    servers.append(words[1])
    except OSError:
        pass
    return {"NTP": " ".join(servers) or None, "FallbackNTP": None}


def _set_chrony_config(ntp: str, fallback: str) -> bool:
    servers = ntp.split() + [x for x in fallback.split() if x not in ntp.split()]
    body = "".join(f"server {server} iburst\n" for server in servers)
    try:
        CHRONY_DROPIN.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    if not _write_atomic(CHRONY_DROPIN, body):
        return False
    try:
        rc = subprocess.run(
            ["systemctl", "try-restart", "chronyd.service"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return rc.returncode == 0


def set_ntp_config(ntp: str, fallback: str) -> bool:
    """Write the NTP servers to our drop-in and restart timesyncd.

    Each list is reset first so it replaces, rather than extends, servers set
    by earlier files. An empty fallback leaves the inherited FallbackNTP alone.
    """
    if _chrony_in_use():
        return _set_chrony_config(ntp, fallback)
    body = ["[Time]\n", "NTP=\n", f"NTP={' '.join(ntp.split())}\n"]
    if fallback.split():
        body += ["FallbackNTP=\n", f"FallbackNTP={' '.join(fallback.split())}\n"]
    try:
        TIMESYNCD_DROPIN.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    if not _write_atomic(TIMESYNCD_DROPIN, "".join(body)):
        return False
    _strip_sectionless_ntp(TIMESYNCD_CONF)
    ok = True
    for cmd in (["timedatectl", "set-ntp", "true"],
                ["systemctl", "try-restart", "systemd-timesyncd.service"]):
        try:
            rc = subprocess.run(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=False, timeout=15,
            )
            ok = ok and rc.returncode == 0
        except (OSError, subprocess.SubprocessError):
            ok = False
    return ok
