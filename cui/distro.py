# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH
"""Platform abstraction: detect distribution and pick the right command stack.

The grommunio appliance has historically targeted openSUSE Leap with yast2 and
zypper. We support Debian, Ubuntu, RHEL and Fedora flavors as well, so each
operation that touches the host (package install, network config, locale,
timezone, repo file) needs to dispatch to the right backend.
"""
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


_DISTRO_CACHE: Optional[Dict[str, str]] = None
_BACKEND_CACHE: Optional[str] = None


def _read_os_release() -> Dict[str, str]:
    """Parse /etc/os-release into a dict. Returns {} if the file is unreadable."""
    items: Dict[str, str] = {}
    for path in ("/etc/os-release", "/usr/lib/os-release"):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    items[key.strip()] = value.strip().strip('"').strip("'")
            if items:
                break
        except OSError:
            continue
    return items


def get_distro_info() -> Dict[str, str]:
    """Return cached os-release fields (ID, ID_LIKE, VERSION_ID, VERSION_CODENAME, ...)."""
    global _DISTRO_CACHE
    if _DISTRO_CACHE is None:
        _DISTRO_CACHE = _read_os_release()
    return _DISTRO_CACHE


def get_distro_id() -> str:
    """Return the os-release ID (e.g. opensuse-leap, ubuntu, debian, rhel, fedora)."""
    return get_distro_info().get("ID", "").lower()


def get_distro_id_like() -> List[str]:
    """Return os-release ID_LIKE tokens, lowercased."""
    raw = get_distro_info().get("ID_LIKE", "")
    return [tok for tok in raw.lower().split() if tok]


def get_distro_version() -> str:
    """Return os-release VERSION_ID, or '' if unknown."""
    return get_distro_info().get("VERSION_ID", "")


def is_suse_family() -> bool:
    return get_distro_id() in {"opensuse-leap", "opensuse-tumbleweed", "sles", "sled"} \
        or "suse" in get_distro_id_like()


def is_debian_family() -> bool:
    return get_distro_id() in {"debian", "ubuntu"} or "debian" in get_distro_id_like()


def is_rhel_family() -> bool:
    return get_distro_id() in {"rhel", "centos", "rocky", "almalinux", "fedora", "ol"} \
        or any(x in get_distro_id_like() for x in ("rhel", "fedora"))


def get_package_manager() -> str:
    """Return 'zypper', 'apt', 'dnf' or '' if no known PM is found."""
    for cmd in ("zypper", "dnf", "apt-get", "yum"):
        if shutil.which(cmd):
            return "apt" if cmd == "apt-get" else cmd
    return ""


def _is_unit_active(unit: str) -> bool:
    try:
        out = subprocess.run(
            ["systemctl", "is-active", unit],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, timeout=5,
        )
        return out.stdout.decode().strip() == "active"
    except (OSError, subprocess.SubprocessError):
        return False


def _is_unit_enabled(unit: str) -> bool:
    try:
        out = subprocess.run(
            ["systemctl", "is-enabled", unit],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, timeout=5,
        )
        state = out.stdout.decode().strip()
        return state in ("enabled", "static", "alias", "indirect", "enabled-runtime")
    except (OSError, subprocess.SubprocessError):
        return False


def get_network_backend() -> str:
    """Return the active network backend.

    Returns one of: 'networkd', 'NetworkManager', 'wicked', 'netplan', 'ifupdown', ''.

    Preference order: active over enabled, with systemd-networkd preferred when
    multiple are present, since it is the lowest common denominator across all
    supported distributions.
    """
    global _BACKEND_CACHE
    if _BACKEND_CACHE is not None:
        return _BACKEND_CACHE

    backend = ""
    candidates = [
        ("systemd-networkd.service", "networkd"),
        ("NetworkManager.service", "NetworkManager"),
        ("wicked.service", "wicked"),
    ]

    for unit, name in candidates:
        if _is_unit_active(unit):
            backend = name
            break

    if not backend:
        for unit, name in candidates:
            if _is_unit_enabled(unit):
                backend = name
                break

    if not backend:
        if Path("/etc/netplan").is_dir() and any(Path("/etc/netplan").glob("*.yaml")):
            backend = "netplan"
        elif Path("/etc/network/interfaces").is_file():
            backend = "ifupdown"

    _BACKEND_CACHE = backend
    return backend


def get_repo_file_path() -> str:
    """Return the path to the grommunio repository config file for this distro."""
    if is_suse_family():
        return "/etc/zypp/repos.d/grommunio.repo"
    if is_rhel_family():
        return "/etc/yum.repos.d/grommunio.repo"
    if is_debian_family():
        return "/etc/apt/sources.list.d/grommunio.list"
    return "/etc/zypp/repos.d/grommunio.repo"


def get_repo_baseurl(channel: str = "community",
                     user: Optional[str] = None,
                     password: Optional[str] = None) -> str:
    """Return the grommunio repo baseurl matching the running distribution.

    channel: 'community' or 'supported'.
    """
    code = _repo_code()
    auth = ""
    if channel == "supported" and user and password is not None:
        auth = f"{user}:{password}@"
    if channel == "supported":
        return f"https://{auth}download.grommunio.com/supported/{code}/"
    return f"https://download.grommunio.com/community/{code}/"


def _repo_code() -> str:
    """Return the URL-segment grommunio uses for this distro's repo path.

    Lines up with download.grommunio.com layout. Falls back to openSUSE_Leap_15.6
    on unknown distros — matches what older grommunio-cui releases did.
    """
    distro_id = get_distro_id()
    version = get_distro_version()
    major = version.split(".")[0] if version else ""

    if distro_id == "opensuse-leap":
        # 15.4 -> openSUSE_Leap_15.4 ; 16.0 -> openSUSE_Leap_16.0 etc.
        return f"openSUSE_Leap_{version}" if version else "openSUSE_Leap_15.6"
    if distro_id == "opensuse-tumbleweed":
        return "openSUSE_Tumbleweed"
    if distro_id in ("sles", "sled"):
        # download.grommunio.com publishes SLE_<major>_SP<minor>, e.g. SLE_15_SP6.
        minor = version.split(".")[1] if "." in version else ""
        if major and minor:
            return f"SLE_{major}_SP{minor}"
        return f"SLE_{major}" if major else "SLE_15_SP6"
    if distro_id == "debian":
        return f"Debian_{major}" if major else "Debian_13"
    if distro_id == "ubuntu":
        # download.grommunio.com publishes Ubuntu_xx.yy (no leading x).
        return f"Ubuntu_{version}" if version else "Ubuntu_24.04"
    if distro_id in ("rhel", "centos", "rocky", "almalinux", "ol"):
        # download.grommunio.com publishes EL<major>, e.g. EL10, EL9.
        return f"EL{major}" if major else "EL10"
    if distro_id == "fedora":
        return f"Fedora_{version}" if version else "Fedora_43"
    # Best-effort fallback
    return "openSUSE_Leap_15.6"


def pkg_refresh_cmd() -> List[str]:
    pm = get_package_manager()
    if pm == "zypper":
        return ["zypper", "--non-interactive", "--gpg-auto-import-keys", "refresh"]
    if pm == "dnf":
        return ["dnf", "-y", "makecache"]
    if pm == "yum":
        return ["yum", "-y", "makecache"]
    if pm == "apt":
        return ["apt-get", "update"]
    return []


def pkg_update_cmd() -> List[str]:
    pm = get_package_manager()
    if pm == "zypper":
        return ["zypper", "--non-interactive", "--gpg-auto-import-keys", "up"]
    if pm == "dnf":
        return ["dnf", "-y", "upgrade"]
    if pm == "yum":
        return ["yum", "-y", "update"]
    if pm == "apt":
        return ["apt-get", "-y", "dist-upgrade"]
    return []


def pkg_import_key_cmd(keyfile: str) -> List[str]:
    pm = get_package_manager()
    if pm in ("zypper", "dnf", "yum"):
        return ["rpm", "--import", keyfile]
    if pm == "apt":
        # The .list file will reference signed-by; the key is moved into place
        # rather than imported via a command.
        return []
    return []


def get_keyfile_destination() -> str:
    """Return the path where the imported GPG key should live on this system.

    On apt-based distros we use a .asc filename inside /etc/apt/keyrings/ —
    apt (>= 2.4) accepts ASCII-armored keys at that path when referenced via
    `signed-by=`. Older releases need a dearmored .gpg file; download.grommunio
    .com publishes the ASCII-armored variant and we install it as-is.
    """
    if is_debian_family():
        return "/etc/apt/keyrings/grommunio.asc"
    return "/tmp/RPM-GPG-KEY-grommunio"


def render_repo_file(baseurl: str, key_destination: str) -> str:
    """Return the full repo file body appropriate for this distro."""
    if is_debian_family():
        # Debian/Ubuntu use deb822/sources.list flat format.
        # We use the simpler one-line form, signed-by the key we placed.
        suite = baseurl.rstrip('/').split('/')[-1]
        return (
            f"deb [signed-by={key_destination}] {baseurl} {suite} main\n"
        )
    # rpm-md style for zypper/dnf/yum
    return (
        "[grommunio]\n"
        "name=grommunio\n"
        f"baseurl={baseurl}\n"
        "enabled=1\n"
        "autorefresh=1\n"
        "type=rpm-md\n"
        "gpgcheck=1\n"
        f"gpgkey={key_destination}\n"
    )


def has_localectl() -> bool:
    return shutil.which("localectl") is not None


def has_timedatectl() -> bool:
    return shutil.which("timedatectl") is not None


def get_locale_conf_path() -> str:
    """Return the system locale config file. /etc/locale.conf is the systemd-standard;
    SUSE additionally keeps /etc/sysconfig/language for ROOT_USES_LANG."""
    return "/etc/locale.conf"


def get_suse_language_path() -> Optional[str]:
    """The SUSE-specific /etc/sysconfig/language file, if it exists."""
    p = Path("/etc/sysconfig/language")
    return str(p) if p.is_file() else None


def reset_caches():
    """Reset cached lookups (used in tests)."""
    global _DISTRO_CACHE, _BACKEND_CACHE
    _DISTRO_CACHE = None
    _BACKEND_CACHE = None
