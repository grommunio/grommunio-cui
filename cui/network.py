# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH
"""Network configuration backends.

The grommunio appliance needs to expose a basic network configuration to the
operator: pick an interface, choose DHCP or static, set address/gateway/DNS,
and persist the change in a way the running network backend will pick up.

Earlier grommunio-cui releases shelled out to yast2 for this. yast2 only exists
on openSUSE, so on Debian/Ubuntu/RHEL we now configure the network directly,
preferring systemd-networkd.

Implemented backends:
    - networkd   : /etc/systemd/network/*.network (preferred everywhere)
    - wicked     : /etc/sysconfig/network/ifcfg-* (legacy openSUSE Leap)
    - NetworkManager: nmcli (RHEL/Fedora/Ubuntu Desktop)

Unimplemented: netplan, ifupdown. On those we still write a networkd file and
ask the operator to disable the other backend manually.
"""
import ipaddress
import os
import socket
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import psutil

from cui import distro


@dataclass
class InterfaceConfig:
    """In-memory representation of an interface's intended configuration."""
    name: str
    dhcp4: bool = True
    dhcp6: bool = True
    addresses: List[str] = field(default_factory=list)  # CIDR notation, e.g. 192.168.1.10/24
    gateway4: str = ""
    gateway6: str = ""
    dns: List[str] = field(default_factory=list)
    enabled: bool = True

    def is_static(self) -> bool:
        return not (self.dhcp4 or self.dhcp6) and bool(self.addresses)


def list_interfaces() -> List[str]:
    """Return non-loopback, non-virtual interface names sorted by name."""
    skip_prefixes = ("lo", "docker", "br-", "veth", "virbr", "tun", "tap", "wg", "vnet")
    result: List[str] = []
    for name in psutil.net_if_addrs():
        if name.startswith(skip_prefixes):
            continue
        result.append(name)
    return sorted(result)


def current_runtime_state(iface: str) -> Dict[str, object]:
    """Return what's actually configured on the running interface right now."""
    addrs = psutil.net_if_addrs().get(iface, [])
    stats = psutil.net_if_stats().get(iface)
    v4: List[str] = []
    v6: List[str] = []
    mac = ""
    for a in addrs:
        if a.family == socket.AF_INET:
            cidr = _netmask_to_prefix(a.netmask) if a.netmask else 32
            v4.append(f"{a.address}/{cidr}")
        elif a.family == socket.AF_INET6:
            cidr = _v6_netmask_to_prefix(a.netmask) if a.netmask else 128
            v6.append(f"{a.address.split('%')[0]}/{cidr}")
        elif a.family == psutil.AF_LINK:
            mac = a.address
    return {
        "addresses_v4": v4,
        "addresses_v6": v6,
        "mac": mac,
        "is_up": bool(stats and stats.isup),
        "speed_mbps": stats.speed if stats else 0,
    }


def _netmask_to_prefix(netmask: str) -> int:
    try:
        return ipaddress.IPv4Network(f"0.0.0.0/{netmask}").prefixlen
    except (ValueError, TypeError):
        return 32


def _v6_netmask_to_prefix(netmask: str) -> int:
    try:
        return ipaddress.IPv6Network(f"::/{netmask}").prefixlen
    except (ValueError, TypeError):
        return 128


def current_default_gateways() -> Dict[str, str]:
    """Best-effort: parse `ip route` to find default gateways per family.

    Returns dict {"v4": gateway_ip_or_empty, "v6": gateway_ip_or_empty}.
    """
    gws = {"v4": "", "v6": ""}
    try:
        out = subprocess.run(
            ["ip", "-4", "route", "show", "default"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, timeout=5,
        ).stdout.decode()
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "default" and parts[1] == "via":
                gws["v4"] = parts[2]
                break
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        out = subprocess.run(
            ["ip", "-6", "route", "show", "default"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, timeout=5,
        ).stdout.decode()
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "default" and parts[1] == "via":
                gws["v6"] = parts[2]
                break
    except (OSError, subprocess.SubprocessError):
        pass
    return gws


def current_dns_servers() -> List[str]:
    """Read /etc/resolv.conf for the configured DNS servers."""
    servers: List[str] = []
    for path in ("/etc/resolv.conf", "/run/systemd/resolve/resolv.conf"):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("nameserver"):
                        parts = line.split(maxsplit=1)
                        if len(parts) == 2:
                            servers.append(parts[1].strip())
            if servers:
                break
        except OSError:
            continue
    return servers


def load_interface_config(iface: str) -> InterfaceConfig:
    """Build an InterfaceConfig for `iface`, reading whatever backend file exists."""
    backend = distro.get_network_backend() or "networkd"
    if backend == "wicked":
        return _read_wicked(iface)
    if backend == "NetworkManager":
        return _read_nm(iface)
    return _read_networkd(iface)


def save_interface_config(cfg: InterfaceConfig) -> bool:
    """Persist InterfaceConfig to disk, then ask the backend to reload.

    The reload step is best-effort: a missing networkctl/wicked/nmcli binary or
    a non-running unit does not roll back the file we just wrote. The operator
    can still activate the new config manually, so we count the call as
    successful as long as the on-disk file was written.
    """
    backend = distro.get_network_backend() or "networkd"
    if backend == "wicked":
        ok = _write_wicked(cfg)
    elif backend == "NetworkManager":
        ok = _write_nm(cfg)
    else:
        ok = _write_networkd(cfg)
    if ok:
        _reload_backend(backend)
    return ok


def _reload_backend(backend: str) -> bool:
    cmds: List[List[str]] = []
    if backend == "wicked":
        cmds.append(["wicked", "ifreload", "all"])
    elif backend == "NetworkManager":
        cmds.append(["nmcli", "connection", "reload"])
    else:
        cmds.append(["networkctl", "reload"])
    for cmd in cmds:
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=False, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return False
    return True


# --- systemd-networkd backend ----------------------------------------------

_NETWORKD_DIR = Path("/etc/systemd/network")


def _networkd_file(iface: str) -> Path:
    return _NETWORKD_DIR / f"50-grommunio-{iface}.network"


def _read_networkd(iface: str) -> InterfaceConfig:
    cfg = InterfaceConfig(name=iface)
    path = _networkd_file(iface)
    if not path.is_file():
        # See if any existing .network file matches this interface.
        if _NETWORKD_DIR.is_dir():
            for f in sorted(_NETWORKD_DIR.glob("*.network")):
                if _networkd_matches(f, iface):
                    path = f
                    break
    if not path.is_file():
        # No on-disk config; reflect runtime state instead.
        rt = current_runtime_state(iface)
        if rt.get("addresses_v4") or rt.get("addresses_v6"):
            cfg.dhcp4 = False
            cfg.dhcp6 = False
            cfg.addresses = list(rt.get("addresses_v4", [])) + list(rt.get("addresses_v6", []))
        gws = current_default_gateways()
        cfg.gateway4 = gws["v4"]
        cfg.gateway6 = gws["v6"]
        cfg.dns = current_dns_servers()
        return cfg
    sections = _parse_ini(path)
    network = sections.get("Network", {})
    dhcp_val = network.get("DHCP", "no").lower()
    cfg.dhcp4 = dhcp_val in ("yes", "ipv4", "true")
    cfg.dhcp6 = dhcp_val in ("yes", "ipv6", "true")
    cfg.addresses = network.get("__list_Address__", [])
    cfg.dns = network.get("__list_DNS__", [])
    cfg.gateway4 = network.get("Gateway", "")
    return cfg


def _networkd_matches(path: Path, iface: str) -> bool:
    try:
        sections = _parse_ini(path)
    except OSError:
        return False
    match = sections.get("Match", {})
    return match.get("Name", "") == iface


def _parse_ini(path: Path) -> Dict[str, Dict[str, object]]:
    """Minimal ini parser preserving repeated keys (e.g. Address=, DNS=) as
    `__list_<key>__` lists, while still exposing the last value under <key>."""
    out: Dict[str, Dict[str, object]] = {}
    current = ""
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current = line[1:-1]
                out.setdefault(current, {})
                continue
            if "=" not in line or not current:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            out[current][key] = val
            list_key = f"__list_{key}__"
            lst = out[current].get(list_key)
            if not isinstance(lst, list):
                lst = []
                out[current][list_key] = lst
            lst.append(val)
    return out


def _write_networkd(cfg: InterfaceConfig) -> bool:
    try:
        _NETWORKD_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    body = ["[Match]\n", f"Name={cfg.name}\n", "\n", "[Network]\n"]
    if cfg.dhcp4 and cfg.dhcp6:
        body.append("DHCP=yes\n")
    elif cfg.dhcp4:
        body.append("DHCP=ipv4\n")
    elif cfg.dhcp6:
        body.append("DHCP=ipv6\n")
    else:
        body.append("DHCP=no\n")
        for addr in cfg.addresses:
            if not addr.strip():
                continue
            body.append(f"Address={addr.strip()}\n")
        if cfg.gateway4:
            body.append(f"Gateway={cfg.gateway4}\n")
        if cfg.gateway6:
            body.append(f"Gateway={cfg.gateway6}\n")
        for dns in cfg.dns:
            if dns.strip():
                body.append(f"DNS={dns.strip()}\n")
    path = _networkd_file(cfg.name)
    try:
        with path.open("w", encoding="utf-8") as fh:
            fh.writelines(body)
        os.chmod(path, 0o644)
    except OSError:
        return False
    return True


# --- wicked / sysconfig backend ---------------------------------------------

_WICKED_DIR = Path("/etc/sysconfig/network")


def _wicked_file(iface: str) -> Path:
    return _WICKED_DIR / f"ifcfg-{iface}"


def _read_wicked(iface: str) -> InterfaceConfig:
    cfg = InterfaceConfig(name=iface)
    path = _wicked_file(iface)
    if not path.is_file():
        return cfg
    entries: Dict[str, str] = {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                entries[key.strip()] = val.strip().strip('"').strip("'")
    except OSError:
        return cfg
    bootproto = entries.get("BOOTPROTO", "static").lower()
    cfg.dhcp4 = bootproto in ("dhcp", "dhcp4", "dhcp+dhcpv6")
    cfg.dhcp6 = bootproto in ("dhcp6", "dhcpv6", "dhcp+dhcpv6")
    if not cfg.dhcp4 and not cfg.dhcp6:
        addr = entries.get("IPADDR", "")
        if addr:
            if "/" not in addr:
                mask = entries.get("NETMASK", "24")
                addr = f"{addr}/{_netmask_to_prefix(mask) if '.' in mask else mask}"
            cfg.addresses = [addr]
    return cfg


def _write_wicked(cfg: InterfaceConfig) -> bool:
    try:
        _WICKED_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    path = _wicked_file(cfg.name)
    lines: List[str] = ["STARTMODE=auto\n"]
    if cfg.dhcp4 and cfg.dhcp6:
        lines.append("BOOTPROTO=dhcp\n")
    elif cfg.dhcp4:
        lines.append("BOOTPROTO=dhcp4\n")
    elif cfg.dhcp6:
        lines.append("BOOTPROTO=dhcp6\n")
    else:
        lines.append("BOOTPROTO=static\n")
        if cfg.addresses:
            lines.append(f"IPADDR='{cfg.addresses[0]}'\n")
    try:
        with path.open("w", encoding="utf-8") as fh:
            fh.writelines(lines)
        os.chmod(path, 0o644)
    except OSError:
        return False
    # Default route and DNS are global in sysconfig; only write IPv4 here.
    if cfg.gateway4:
        routes = _WICKED_DIR / "routes"
        try:
            with routes.open("w", encoding="utf-8") as fh:
                fh.write(f"default {cfg.gateway4} - -\n")
        except OSError:
            return False
    return True


# --- NetworkManager backend -------------------------------------------------

def _read_nm(iface: str) -> InterfaceConfig:
    cfg = InterfaceConfig(name=iface)
    try:
        out = subprocess.run(
            ["nmcli", "-t", "-f", "ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.dns",
             "device", "show", iface],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, timeout=10,
        ).stdout.decode()
    except (OSError, subprocess.SubprocessError):
        return cfg
    for raw in out.splitlines():
        if ":" not in raw:
            continue
        key, _, val = raw.partition(":")
        if key == "IP4.ADDRESS" and val:
            cfg.addresses.append(val.strip())
            cfg.dhcp4 = False
        elif key == "IP4.GATEWAY" and val:
            cfg.gateway4 = val.strip()
    return cfg


def _write_nm(cfg: InterfaceConfig) -> bool:
    """Create-or-modify a NetworkManager connection for `iface`."""
    conname = f"grommunio-{cfg.name}"
    base = ["nmcli", "connection"]
    # Delete any old grommunio-managed connection so settings start clean.
    subprocess.run(base + ["delete", conname], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, check=False, timeout=10)
    add_cmd = base + ["add", "type", "ethernet", "ifname", cfg.name, "con-name", conname]
    if cfg.dhcp4 or cfg.dhcp6:
        add_cmd += ["ipv4.method", "auto"]
        add_cmd += ["ipv6.method", "auto" if cfg.dhcp6 else "ignore"]
    else:
        if cfg.addresses:
            add_cmd += ["ipv4.method", "manual",
                        "ipv4.addresses", ",".join(cfg.addresses)]
        if cfg.gateway4:
            add_cmd += ["ipv4.gateway", cfg.gateway4]
        if cfg.dns:
            add_cmd += ["ipv4.dns", ",".join(cfg.dns)]
    try:
        rc = subprocess.run(add_cmd, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, check=False, timeout=30)
        if rc.returncode != 0:
            return False
        subprocess.run(base + ["up", conname], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def validate_cidr(value: str) -> Optional[str]:
    """Return None if `value` is a valid IPv4/IPv6 CIDR, otherwise an error message."""
    if not value:
        return "address required"
    try:
        ipaddress.ip_interface(value)
        return None
    except (ValueError, TypeError) as exc:
        return str(exc)


def validate_ip(value: str) -> Optional[str]:
    if not value:
        return None
    try:
        ipaddress.ip_address(value)
        return None
    except (ValueError, TypeError) as exc:
        return str(exc)
