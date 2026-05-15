#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Local-install helper for grommunio-cui.
#
# Installs the runtime dependencies for the current operator system and
# drops a wrapper script in /usr/local/bin so cui can be invoked as
# `grommunio-cui` for development.
#
# Tested on: openSUSE Leap 15.6/16.0, Debian 13, Ubuntu 24.04/26.04, RHEL 10.

set -euo pipefail

TARGET="/usr/local/bin"
WRAPPER="cui.sh"
TMPDIR_REL="./tmp"

if [ "$(id -u)" -ne 0 ]; then
    echo "This installer needs root privileges. Re-run with sudo." >&2
    exit 1
fi

detect_pm() {
    if command -v zypper >/dev/null 2>&1; then
        echo "zypper"
    elif command -v dnf >/dev/null 2>&1; then
        echo "dnf"
    elif command -v apt-get >/dev/null 2>&1; then
        echo "apt"
    elif command -v yum >/dev/null 2>&1; then
        echo "yum"
    else
        echo ""
    fi
}

install_pkgs() {
    local pm="$1"
    shift
    case "$pm" in
        zypper)
            zypper --non-interactive install "$@"
            ;;
        dnf)
            dnf -y install "$@"
            ;;
        yum)
            yum -y install "$@"
            ;;
        apt)
            DEBIAN_FRONTEND=noninteractive apt-get update
            DEBIAN_FRONTEND=noninteractive apt-get -y install "$@"
            ;;
        *)
            echo "No supported package manager found; install Python deps manually." >&2
            return 1
            ;;
    esac
}

PM="$(detect_pm)"
echo "Detected package manager: ${PM:-<none>}"

# Distribution-specific Python package names. systemd-python in particular is
# called differently on every distro family.
case "$PM" in
    zypper)
        PYDEPS=(python3 python3-pip python3-cffi python3-configobj python3-pamela
                python3-psutil python3-systemd python3-urwid python3-PyYAML python3-requests)
        ;;
    dnf|yum)
        PYDEPS=(python3 python3-pip python3-cffi python3-configobj python3-pamela
                python3-psutil python3-systemd python3-urwid python3-pyyaml python3-requests)
        ;;
    apt)
        PYDEPS=(python3 python3-pip python3-cffi python3-configobj python3-pamela
                python3-psutil python3-systemd python3-urwid python3-yaml python3-requests)
        ;;
    *)
        PYDEPS=()
        ;;
esac

if [ -n "$PM" ] && [ "${#PYDEPS[@]}" -gt 0 ]; then
    echo "Installing system packages: ${PYDEPS[*]}"
    install_pkgs "$PM" "${PYDEPS[@]}" || true
fi

# Anything still missing falls back to pip. We pin via requirements.txt rather
# than guessing; pip handles "already installed" gracefully.
if [ -r requirements.txt ]; then
    echo "Installing Python deps from requirements.txt"
    python3 -m pip install --break-system-packages -r requirements.txt \
        || python3 -m pip install -r requirements.txt
fi

mkdir -p "${TMPDIR_REL}"

cat > "${TMPDIR_REL}/${WRAPPER}" <<EOF
#!/bin/bash
export PYTHONPATH="\${PYTHONPATH:-}:$(pwd):$(pwd)/cui"
exec python3 "$(pwd)/cui/__init__.py" "\$@"
EOF
chmod 755 "${TMPDIR_REL}/${WRAPPER}"

echo "Installing wrapper to ${TARGET}/${WRAPPER}"
install -m 0755 "${TMPDIR_REL}/${WRAPPER}" "${TARGET}/${WRAPPER}"

echo "Done. Run \`${WRAPPER}\` (or \`${TARGET}/${WRAPPER}\`) to start grommunio-cui."
