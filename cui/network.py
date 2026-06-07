# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH
"""Network configuration backends.

The grommunio appliance needs to expose interface configuration to the
operator: IPv4 and IPv6 addresses, default gateways, static routes, DNS
servers, and bond devices. Everything is persisted in the format the running
network backend expects and then applied live.

Implemented backends:
    - networkd: /etc/systemd/network/*.network and *.netdev
    - wicked  : /etc/sysconfig/network/ifcfg-* (and /routes, /config)
    - NetworkManager: nmcli connections

For each backend we own a file prefix (50-grommunio-...) and never touch
files we did not create, so operator-authored configs stay intact.
"""
import ipaddress
import os
import re
import socket
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psutil

from cui import distro


# --- Data model -------------------------------------------------------------

BOND_MODES = [
    "balance-rr",
    "active-backup",
    "balance-xor",
    "broadcast",
    "802.3ad",
    "balance-tlb",
    "balance-alb",
]


class InterfaceConfig:
    """In-memory representation of an interface's intended configuration.

    Used for both ethernet links and bond devices. For bond members the
    `bond_master` field carries the parent name; for bond devices the
    `bond_mode`/`bond_miimon`/`bond_members` fields are populated.

    Plain class rather than a dataclass on purpose: openSUSE Leap 15.6 ships
    Python 3.6, where the `dataclasses` module is not available.
    """

    def __init__(
        self,
        name: str,
        kind: str = "ethernet",  # 'ethernet' or 'bond'
        dhcp4: bool = False,
        dhcp6: bool = False,
        addresses: Optional[List[str]] = None,  # CIDR list
        gateway4: str = "",
        gateway6: str = "",
        dns: Optional[List[str]] = None,
        # Static routes: list of (destination_cidr, via_gateway). The via field
        # may be empty for on-link routes; the destination must always be set.
        routes: Optional[List[Tuple[str, str]]] = None,
        enabled: bool = True,
        # Bond settings (only meaningful when kind == 'bond'):
        bond_mode: str = "active-backup",
        bond_miimon: int = 100,
        bond_members: Optional[List[str]] = None,
        # If this interface is a bond member, this is the bond device name:
        bond_master: str = "",
    ):
        self.name = name
        self.kind = kind
        self.dhcp4 = dhcp4
        self.dhcp6 = dhcp6
        self.addresses = list(addresses) if addresses else []
        self.gateway4 = gateway4
        self.gateway6 = gateway6
        self.dns = list(dns) if dns else []
        self.routes = list(routes) if routes else []
        self.enabled = enabled
        self.bond_mode = bond_mode
        self.bond_miimon = bond_miimon
        self.bond_members = list(bond_members) if bond_members else []
        self.bond_master = bond_master
        # Preservation state, populated by the readers and consumed by the
        # writers so we never clobber operator-authored directives we do not
        # manage ourselves. Not part of the public constructor on purpose.
        # source_file: the on-disk file the config came from (write back there
        #   instead of creating a competing 50-grommunio-*.network file).
        self.source_file = None  # type: Optional[Path]
        # extra_network: unmanaged "[Network]" keys (Domains, IPForward, ...),
        #   each mapped to its list of raw string values.
        self.extra_network = {}  # type: Dict[str, List[str]]
        # raw_routes: the verbatim "[Route]" sections as parsed (list of dicts),
        #   re-emitted unchanged when the operator did not edit the route list.
        self.raw_routes = []  # type: List[Dict[str, str]]
        # extra_lines: unmanaged "ifcfg" keys for the wicked backend.
        self.extra_lines = {}  # type: Dict[str, str]

    def is_static(self) -> bool:
        return not (self.dhcp4 or self.dhcp6) and bool(self.addresses)


# --- Runtime inspection -----------------------------------------------------

def list_interfaces(include_bonds: bool = True) -> List[str]:
    """Return non-loopback, non-virtual interface names.

    Bond devices are included by default since the operator may need to edit
    one that already exists. Bridges, docker bridges, tunnels and wireguard
    are skipped.
    """
    skip_prefixes = ("lo", "docker", "br-", "veth", "virbr", "tun", "tap",
                     "wg", "vnet", "tailscale")
    result: List[str] = []
    for name in psutil.net_if_addrs():
        if name.startswith(skip_prefixes):
            continue
        if not include_bonds and _is_bond_device(name):
            continue
        result.append(name)
    return sorted(result)


def list_bondable_interfaces() -> List[str]:
    """Return physical-looking interfaces eligible to be bond members."""
    out = []
    for name in list_interfaces():
        if _is_bond_device(name):
            continue
        out.append(name)
    return out


def _is_bond_device(name: str) -> bool:
    """True if /sys/class/net/<name> is a bond master."""
    return Path(f"/sys/class/net/{name}/bonding").is_dir()


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
    is_bond = _is_bond_device(iface)
    bond_slaves: List[str] = []
    if is_bond:
        try:
            slaves_file = Path(f"/sys/class/net/{iface}/bonding/slaves")
            if slaves_file.is_file():
                bond_slaves = slaves_file.read_text().split()
        except OSError:
            pass
    return {
        "addresses_v4": v4,
        "addresses_v6": v6,
        "mac": mac,
        "is_up": bool(stats and stats.isup),
        "speed_mbps": stats.speed if stats else 0,
        "kind": "bond" if is_bond else "ethernet",
        "bond_slaves": bond_slaves,
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
    """Best-effort parse of `ip route` for the default gateways per family."""
    gws = {"v4": "", "v6": ""}
    for family, key in ((4, "v4"), (6, "v6")):
        try:
            out = subprocess.run(
                ["ip", f"-{family}", "route", "show", "default"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                check=False, timeout=5,
            ).stdout.decode()
        except (OSError, subprocess.SubprocessError):
            continue
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "default" and parts[1] == "via":
                gws[key] = parts[2]
                break
    return gws


def current_dns_servers() -> List[str]:
    """Read DNS nameservers from resolv.conf (systemd-resolved or static)."""
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


# --- Backend dispatch -------------------------------------------------------

def get_backend() -> str:
    """Return one of: 'networkd', 'NetworkManager', 'wicked'.

    Defaults to 'networkd' when nothing is auto-detected; cui.distro caches
    the result and falls back to networkd on systems where no unit is active.
    """
    backend = distro.get_network_backend()
    if backend in ("networkd", "NetworkManager", "wicked"):
        return backend
    return "networkd"


def load_interface_config(iface: str) -> InterfaceConfig:
    """Build an InterfaceConfig for iface from on-disk config files.

    If no config file exists for the interface we fall back to the current
    runtime state so the operator sees the live values.
    """
    backend = get_backend()
    if backend == "wicked":
        cfg = _read_wicked(iface)
    elif backend == "NetworkManager":
        cfg = _read_nm(iface)
    else:
        cfg = _read_networkd(iface)
    # Fill in runtime state for anything the file didn't define.
    if not cfg.addresses and not (cfg.dhcp4 or cfg.dhcp6):
        rt = current_runtime_state(iface)
        cfg.addresses = list(rt.get("addresses_v4", [])) + list(rt.get("addresses_v6", []))
    if not cfg.gateway4 and not cfg.gateway6:
        gws = current_default_gateways()
        cfg.gateway4 = gws["v4"]
        cfg.gateway6 = gws["v6"]
    if not cfg.dns:
        cfg.dns = current_dns_servers()
    # Reflect kernel state: this is a bond device?
    if cfg.kind == "ethernet" and _is_bond_device(iface):
        cfg.kind = "bond"
        rt = current_runtime_state(iface)
        if not cfg.bond_members:
            cfg.bond_members = list(rt.get("bond_slaves", []))
    return cfg


def save_interface_config(cfg: InterfaceConfig, member_for_bond: bool = False) -> bool:
    """Persist cfg and ask the backend to reload."""
    backend = get_backend()
    if backend == "wicked":
        ok = _write_wicked(cfg, member_for_bond=member_for_bond)
    elif backend == "NetworkManager":
        ok = _write_nm(cfg, member_for_bond=member_for_bond)
    else:
        ok = _write_networkd(cfg, member_for_bond=member_for_bond)
    if ok:
        apply_live(cfg.name)
    return ok


def create_bond(cfg: InterfaceConfig) -> bool:
    """Create a new bond device with the given config and member list.

    cfg.name is the bond device name, cfg.bond_members lists the slaves, and
    cfg.bond_mode/bond_miimon configure the bond driver. Per-member files
    are also written so the slaves attach automatically on reload.
    """
    if not cfg.bond_members:
        return False
    cfg.kind = "bond"
    backend = get_backend()
    if backend == "wicked":
        ok = _write_wicked(cfg)
        if ok:
            for member in cfg.bond_members:
                slave = InterfaceConfig(name=member, bond_master=cfg.name)
                _write_wicked(slave, member_for_bond=True)
    elif backend == "NetworkManager":
        ok = _create_nm_bond(cfg)
    else:
        ok = _write_networkd(cfg)
        if ok:
            _write_networkd_netdev_for_bond(cfg)
            for member in cfg.bond_members:
                slave = InterfaceConfig(name=member, bond_master=cfg.name)
                _write_networkd(slave, member_for_bond=True)
    if ok:
        apply_live(cfg.name)
    return ok


def delete_interface_config(iface: str) -> bool:
    """Remove the grommunio-managed config file for `iface`, then reload."""
    backend = get_backend()
    ok = False
    if backend == "wicked":
        for fname in (f"ifcfg-{iface}",):
            try:
                _unlink(_WICKED_DIR / fname)
                ok = True
            except OSError:
                pass
    elif backend == "NetworkManager":
        conname = f"grommunio-{iface}"
        try:
            rc = subprocess.run(
                ["nmcli", "connection", "delete", conname],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=False, timeout=15,
            )
            ok = (rc.returncode == 0)
        except (OSError, subprocess.SubprocessError):
            ok = False
    else:
        for ext in ("network", "netdev"):
            try:
                _unlink(_NETWORKD_DIR / f"50-grommunio-{iface}.{ext}")
                ok = True
            except OSError:
                pass
    if ok:
        apply_live(iface)
    return ok


# --- Apply / reload --------------------------------------------------------

def apply_live(iface: str = "") -> bool:
    """Reload the active backend and, if a specific interface name is given,
    reconfigure that interface so the changes take effect immediately."""
    backend = get_backend()
    ok = True
    if backend == "wicked":
        ok &= _run(["wicked", "ifreload", iface or "all"])
        # ifreload only reapplies the interface files; DNS lives in
        # NETCONFIG_DNS_STATIC_SERVERS and needs netconfig to regenerate
        # resolv.conf. Best-effort: ignore failure if netconfig is absent.
        _run(["netconfig", "update"])
    elif backend == "NetworkManager":
        ok &= _run(["nmcli", "connection", "reload"])
        if iface:
            conname = f"grommunio-{iface}"
            _run(["nmcli", "connection", "up", conname])
    else:
        ok &= _run(["networkctl", "reload"])
        if iface:
            _run(["networkctl", "reconfigure", iface])
    return ok


def _run(cmd: List[str]) -> bool:
    try:
        rc = subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False, timeout=30,
        )
        return rc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _unlink(path: Path) -> None:
    """Remove `path`, ignoring a missing file.

    Path.unlink(missing_ok=...) only exists from Python 3.8; openSUSE Leap
    15.6 ships Python 3.6, so we catch FileNotFoundError instead.
    """
    try:
        path.unlink()
    except FileNotFoundError:
        pass


# --- systemd-networkd backend ----------------------------------------------

_NETWORKD_DIR = Path("/etc/systemd/network")


def _networkd_file(iface: str, ext: str = "network") -> Path:
    return _NETWORKD_DIR / f"50-grommunio-{iface}.{ext}"


# "[Network]" keys we render ourselves; everything else in that section is an
# operator-authored directive we must preserve verbatim on write.
_NETWORKD_MANAGED_KEYS = {"DHCP", "Address", "Gateway", "DNS", "Bond"}


def _read_networkd(iface: str) -> InterfaceConfig:
    cfg = InterfaceConfig(name=iface)
    path = _networkd_file(iface)
    if not path.is_file() and _NETWORKD_DIR.is_dir():
        for candidate in sorted(_NETWORKD_DIR.glob("*.network")):
            if _networkd_matches(candidate, iface):
                path = candidate
                break
    if not path.is_file():
        return cfg
    cfg.source_file = path
    sections = _parse_ini(path)
    network = sections.get("Network", {})
    dhcp_val = str(network.get("DHCP", "no")).lower()
    cfg.dhcp4 = dhcp_val in ("yes", "ipv4", "true")
    cfg.dhcp6 = dhcp_val in ("yes", "ipv6", "true")
    cfg.addresses = list(network.get("__list_Address__", []))
    cfg.dns = list(network.get("__list_DNS__", []))
    for gw in network.get("__list_Gateway__", []):
        gw_s = str(gw)
        if ":" in gw_s:
            cfg.gateway6 = gw_s
        else:
            cfg.gateway4 = gw_s
    bond = network.get("Bond", "")
    if bond:
        cfg.bond_master = str(bond)
    # Stash any "[Network]" directives we do not manage so they survive a save
    # (e.g. Domains, IPForward, IPv6AcceptRA, LinkLocalAddressing).
    for key, vals in network.items():
        if key.startswith("__list_") or key.startswith("__sections_"):
            continue
        if key in _NETWORKD_MANAGED_KEYS:
            continue
        cfg.extra_network[key] = list(network.get(f"__list_{key}__", [str(vals)]))
    # Route sections: each [Route] section becomes one entry. The full section
    # dict is kept in raw_routes so attributes we do not surface in the UI
    # (Scope, Metric, Table, GatewayOnLink, ...) are not lost on save. A default
    # route expressed as a [Route] block is promoted to gateway4/gateway6 so it
    # shows in the gateway field and is not written out twice.
    for route in _iter_sections(sections, "Route"):
        dest = str(route.get("Destination", ""))
        via = str(route.get("Gateway", ""))
        if dest in ("0.0.0.0/0", "0.0.0.0") and via and not cfg.gateway4:
            cfg.gateway4 = via
            continue
        if dest == "::/0" and via and not cfg.gateway6:
            cfg.gateway6 = via
            continue
        cfg.raw_routes.append({k: v for k, v in route.items()
                               if not k.startswith("__list_")})
        if dest:
            cfg.routes.append((dest, via))
    # If a corresponding .netdev exists, this is a bond device.
    netdev = _networkd_file(iface, "netdev")
    if netdev.is_file():
        nd = _parse_ini(netdev)
        if nd.get("NetDev", {}).get("Kind", "").lower() == "bond":
            cfg.kind = "bond"
            bond_sec = nd.get("Bond", {})
            cfg.bond_mode = str(bond_sec.get("Mode", cfg.bond_mode))
            miimon = bond_sec.get("MIIMonitorSec", "")
            # MIIMonitorSec can be "100ms"; strip suffix.
            m = re.match(r"(\d+)", str(miimon))
            if m:
                cfg.bond_miimon = int(m.group(1))
            # Scan other .network files for members.
            if _NETWORKD_DIR.is_dir():
                for f in sorted(_NETWORKD_DIR.glob("*.network")):
                    nm_sections = _parse_ini(f)
                    if str(nm_sections.get("Network", {}).get("Bond", "")) == iface:
                        m_name = str(nm_sections.get("Match", {}).get("Name", ""))
                        if m_name and m_name not in cfg.bond_members:
                            cfg.bond_members.append(m_name)
    return cfg


def _networkd_matches(path: Path, iface: str) -> bool:
    try:
        sections = _parse_ini(path)
    except OSError:
        return False
    return str(sections.get("Match", {}).get("Name", "")) == iface


def _iter_sections(sections: Dict[str, object], name: str) -> List[Dict[str, object]]:
    """Return every parsed section called `name`, whether it occurs once or many.

    _parse_ini only fills '__sections_<name>__' once a section repeats, so a
    file with a single [Route] would otherwise be invisible. Normalise that
    here so callers always see a list.
    """
    multi = sections.get(f"__sections_{name}__")
    if isinstance(multi, list):
        return [s for s in multi if isinstance(s, dict)]
    single = sections.get(name)
    if isinstance(single, dict):
        return [single]
    return []


def _parse_ini(path: Path) -> Dict[str, object]:
    """Tolerant ini parser.

    Returns a dict where each section maps to a dict of {key: last_value}.
    Repeated keys are preserved under '__list_<key>__'. Repeated sections
    (e.g. multiple [Route]) are collected under '__sections_<name>__'.
    """
    out: Dict[str, object] = {}
    current = ""
    current_dict: Dict[str, object] = {}

    def _finish_section():
        if not current:
            return
        prev = out.get(current)
        if isinstance(prev, dict):
            # Promote to a list under '__sections_<name>__'.
            key = f"__sections_{current}__"
            existing = out.get(key)
            if not isinstance(existing, list):
                existing = [prev]
                out[key] = existing
            existing.append(current_dict)
            out[current] = current_dict  # latest one
        else:
            out[current] = current_dict

    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith(";"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    _finish_section()
                    current = line[1:-1]
                    current_dict = {}
                    continue
                if "=" not in line or not current:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip()
                current_dict[key] = val
                list_key = f"__list_{key}__"
                lst = current_dict.get(list_key)
                if not isinstance(lst, list):
                    lst = []
                    current_dict[list_key] = lst
                lst.append(val)
        _finish_section()
    except OSError:
        pass
    return out


def _networkd_target(cfg: InterfaceConfig) -> Path:
    """Return the file to write for cfg.

    If the config was read from an operator-authored file (e.g. eth0.network),
    write back to that same file so we do not leave two competing .network
    files matching the interface. Otherwise own a 50-grommunio-<iface>.network.
    """
    src = getattr(cfg, "source_file", None)
    if src is not None:
        return Path(src)
    return _networkd_file(cfg.name)


def _write_networkd(cfg: InterfaceConfig, member_for_bond: bool = False) -> bool:
    try:
        _NETWORKD_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    if member_for_bond or cfg.bond_master:
        # Slave file: only references the bond master.
        body = [
            "[Match]\n",
            f"Name={cfg.name}\n",
            "\n",
            "[Network]\n",
            f"Bond={cfg.bond_master}\n",
        ]
        return _write_file(_networkd_file(cfg.name), "".join(body))
    target = _networkd_target(cfg)
    lines: List[str] = ["[Match]\n", f"Name={cfg.name}\n", "\n", "[Network]\n"]
    if cfg.dhcp4 and cfg.dhcp6:
        lines.append("DHCP=yes\n")
    elif cfg.dhcp4:
        lines.append("DHCP=ipv4\n")
    elif cfg.dhcp6:
        lines.append("DHCP=ipv6\n")
    else:
        lines.append("DHCP=no\n")
    for addr in cfg.addresses:
        if addr.strip():
            lines.append(f"Address={addr.strip()}\n")
    if cfg.gateway4:
        lines.append(f"Gateway={cfg.gateway4}\n")
    if cfg.gateway6:
        lines.append(f"Gateway={cfg.gateway6}\n")
    for dns in cfg.dns:
        if dns.strip():
            lines.append(f"DNS={dns.strip()}\n")
    # Re-emit "[Network]" directives we do not manage but that the operator set.
    for key, vals in getattr(cfg, "extra_network", {}).items():
        for val in vals:
            lines.append(f"{key}={val}\n")
    lines.append(_networkd_routes_block(cfg))
    if not _write_file(target, "".join(lines)):
        return False
    # If we just wrote 50-grommunio-<iface>.network but a differently-named
    # operator file for the same interface still exists, both would be applied
    # by networkd (Address= is cumulative). Remove the stale duplicate.
    _drop_conflicting_networkd_files(cfg.name, keep=target)
    if cfg.kind == "bond":
        _write_networkd_netdev_for_bond(cfg)
    return True


def _networkd_routes_block(cfg: InterfaceConfig) -> str:
    """Render the [Route] sections.

    When the operator did not change the route list, re-emit the original
    sections verbatim so attributes we do not surface (Scope, Metric, Table,
    GatewayOnLink, ...) and IPv6 default routes are preserved. Otherwise emit
    the edited destination/gateway pairs.
    """
    raw = getattr(cfg, "raw_routes", [])
    raw_pairs = [(r.get("Destination", ""), r.get("Gateway", "")) for r in raw]
    if raw and raw_pairs == list(cfg.routes):
        out = []
        for section in raw:
            out.append("\n[Route]\n")
            for key, val in section.items():
                out.append(f"{key}={val}\n")
        return "".join(out)
    out = []
    for dest, via in cfg.routes:
        if not dest:
            continue
        out.append("\n[Route]\n")
        out.append(f"Destination={dest}\n")
        if via:
            out.append(f"Gateway={via}\n")
    return "".join(out)


def _drop_conflicting_networkd_files(iface: str, keep: Path) -> None:
    """Remove other .network files that also match `iface` via [Match] Name=.

    networkd applies every matching file, so a leftover operator file plus our
    own file would double up addresses. We only ever remove a file we are
    replacing the role of; the file we just wrote (`keep`) is never touched.
    """
    if not _NETWORKD_DIR.is_dir():
        return
    for candidate in _NETWORKD_DIR.glob("*.network"):
        if candidate == keep:
            continue
        if _networkd_matches(candidate, iface):
            _unlink(candidate)


def _write_networkd_netdev_for_bond(cfg: InterfaceConfig) -> bool:
    body = [
        "[NetDev]\n",
        f"Name={cfg.name}\n",
        "Kind=bond\n",
        "\n",
        "[Bond]\n",
        f"Mode={cfg.bond_mode}\n",
        f"MIIMonitorSec={cfg.bond_miimon}ms\n",
    ]
    return _write_file(_networkd_file(cfg.name, "netdev"), "".join(body))


def _write_file(path: Path, body: str) -> bool:
    """Atomically replace `path` with `body`.

    Write to a temp file in the same directory, fsync, then rename over the
    target so an interrupted write (disk full, kill) can never leave a
    truncated config behind — losing the interface config would cut the box off.
    """
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, 0o644)
        os.replace(str(tmp), str(path))
        return True
    except OSError:
        try:
            _unlink(tmp)
        except OSError:
            pass
        return False


# --- wicked / sysconfig backend ---------------------------------------------

_WICKED_DIR = Path("/etc/sysconfig/network")


def _wicked_file(iface: str) -> Path:
    return _WICKED_DIR / f"ifcfg-{iface}"


# ifcfg keys we render ourselves; everything else (ZONE, MTU, ETHTOOL_OPTIONS,
# LLADDR, ...) is operator-authored and must be preserved on write.
_WICKED_MANAGED_KEYS = {
    "STARTMODE", "BOOTPROTO", "IPADDR", "NETMASK", "PREFIXLEN", "REMOTE_IPADDR",
    "BONDING_MASTER", "BONDING_MODULE_OPTS",
}
_WICKED_MANAGED_PREFIXES = (
    "IPADDR_", "NETMASK_", "PREFIXLEN_", "LABEL_", "BONDING_SLAVE_",
)


def _wicked_key_managed(key: str) -> bool:
    if key in _WICKED_MANAGED_KEYS:
        return True
    return any(key.startswith(p) for p in _WICKED_MANAGED_PREFIXES)


def _read_wicked(iface: str) -> InterfaceConfig:
    cfg = InterfaceConfig(name=iface)
    path = _wicked_file(iface)
    if not path.is_file():
        return cfg
    cfg.source_file = path
    entries: Dict[str, str] = {}
    indexed: Dict[str, Dict[str, str]] = {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                entries[key] = val
                m = re.match(r"^([A-Z_]+?)_([0-9]+)$", key)
                if m:
                    base = m.group(1)
                    idx = m.group(2)
                    indexed.setdefault(base, {})[idx] = val
                if not _wicked_key_managed(key):
                    cfg.extra_lines[key] = val
    except OSError:
        return cfg
    bootproto = entries.get("BOOTPROTO", "static").lower()
    cfg.dhcp4 = bootproto in ("dhcp", "dhcp4", "dhcp+dhcpv6")
    cfg.dhcp6 = bootproto in ("dhcp6", "dhcpv6", "dhcp+dhcpv6")
    # Primary IPADDR.
    primary = entries.get("IPADDR", "")
    if primary:
        if "/" not in primary:
            mask = entries.get("NETMASK", "24")
            primary = _normalise_cidr(primary, mask)
        cfg.addresses.append(primary)
    # Additional aliases IPADDR_0, IPADDR_1, ...
    for idx in sorted(indexed.get("IPADDR", {})):
        addr = indexed["IPADDR"][idx]
        if "/" not in addr:
            mask = indexed.get("PREFIXLEN", {}).get(idx) \
                or indexed.get("NETMASK", {}).get(idx) or "24"
            addr = _normalise_cidr(addr, mask)
        cfg.addresses.append(addr)
    # BONDING settings.
    if entries.get("BONDING_MASTER", "").lower() == "yes":
        cfg.kind = "bond"
        opts = entries.get("BONDING_MODULE_OPTS", "")
        for tok in opts.split():
            if "=" not in tok:
                continue
            k, v = tok.split("=", 1)
            if k == "mode":
                cfg.bond_mode = v
            elif k == "miimon":
                try:
                    cfg.bond_miimon = int(v)
                except ValueError:
                    pass
        for idx in sorted(indexed.get("BONDING_SLAVE", {})):
            cfg.bond_members.append(indexed["BONDING_SLAVE"][idx])
    # If we have BOOTPROTO=none + STARTMODE=hotplug we are probably a slave;
    # the slave's master name isn't in the file though, so we just leave
    # bond_master empty here. The caller can fill it in from runtime state.
    # DNS: sysconfig/network has NETCONFIG_DNS_STATIC_SERVERS.
    netconfig = _WICKED_DIR / "config"
    if netconfig.is_file():
        try:
            with netconfig.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("NETCONFIG_DNS_STATIC_SERVERS"):
                        _, _, val = line.partition("=")
                        cfg.dns = val.strip().strip('"').split()
                        break
        except OSError:
            pass
    # Routes from /etc/sysconfig/network/routes for the default gateway, and
    # ifroute-<iface> for per-interface static routes.
    cfg.gateway4 = _wicked_default_gateway(family=4)
    cfg.gateway6 = _wicked_default_gateway(family=6)
    cfg.routes.extend(_wicked_iface_routes(iface))
    return cfg


def _normalise_cidr(addr: str, mask: str) -> str:
    """Turn IPv4 + netmask/prefix into CIDR notation."""
    if "/" in addr:
        return addr
    if mask.isdigit():
        return f"{addr}/{mask}"
    if "." in mask:
        return f"{addr}/{_netmask_to_prefix(mask)}"
    return f"{addr}/{mask}"


def _wicked_default_gateway(family: int) -> str:
    routes_file = _WICKED_DIR / "routes"
    if not routes_file.is_file():
        return ""
    try:
        with routes_file.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                # SUSE routes format: <dest> <gw> [netmask] [iface]
                if len(parts) < 2 or parts[0] != "default":
                    continue
                gw = parts[1]
                if family == 4 and ":" not in gw:
                    return gw
                if family == 6 and ":" in gw:
                    return gw
    except OSError:
        pass
    return ""


def _wicked_iface_routes(iface: str) -> List[Tuple[str, str]]:
    path = _WICKED_DIR / f"ifroute-{iface}"
    out: List[Tuple[str, str]] = []
    if not path.is_file():
        return out
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) < 2 or parts[0] == "default":
                    continue
                dest = parts[0]
                gw = parts[1] if parts[1] != "-" else ""
                out.append((dest, gw))
    except OSError:
        pass
    return out


def _write_wicked(cfg: InterfaceConfig, member_for_bond: bool = False) -> bool:
    try:
        _WICKED_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    path = _wicked_file(cfg.name)
    lines: List[str] = []
    if member_for_bond or cfg.bond_master:
        lines.append("STARTMODE='hotplug'\n")
        lines.append("BOOTPROTO='none'\n")
        if not _write_file(path, "".join(lines)):
            return False
        return True
    lines.append("STARTMODE='auto'\n")
    if cfg.dhcp4 and cfg.dhcp6:
        lines.append("BOOTPROTO='dhcp'\n")
    elif cfg.dhcp4:
        lines.append("BOOTPROTO='dhcp4'\n")
    elif cfg.dhcp6:
        lines.append("BOOTPROTO='dhcp6'\n")
    else:
        lines.append("BOOTPROTO='static'\n")
    if cfg.kind == "bond":
        lines.append("BONDING_MASTER='yes'\n")
        opts = f"mode={cfg.bond_mode} miimon={cfg.bond_miimon}"
        lines.append(f"BONDING_MODULE_OPTS='{opts}'\n")
        for i, member in enumerate(cfg.bond_members):
            lines.append(f"BONDING_SLAVE_{i}='{member}'\n")
    if cfg.addresses:
        lines.append(f"IPADDR='{cfg.addresses[0]}'\n")
        for i, extra in enumerate(cfg.addresses[1:]):
            lines.append(f"IPADDR_{i}='{extra}'\n")
    # Re-emit ifcfg keys we do not manage (ZONE, MTU, ETHTOOL_OPTIONS, ...).
    for key, val in getattr(cfg, "extra_lines", {}).items():
        lines.append(f"{key}='{val}'\n")
    if not _write_file(path, "".join(lines)):
        return False
    if cfg.dns:
        _write_wicked_dns(cfg.dns)
    _write_wicked_routes(cfg)
    return True


def _write_wicked_dns(servers: List[str]) -> bool:
    """Update NETCONFIG_DNS_STATIC_SERVERS in /etc/sysconfig/network/config.

    The file is operator-managed; we only rewrite the one key we control.
    """
    config = _WICKED_DIR / "config"
    new_key = f'NETCONFIG_DNS_STATIC_SERVERS="{" ".join(servers)}"'
    if not config.is_file():
        return _write_file(config, new_key + "\n")
    try:
        text = config.read_text(encoding="utf-8")
    except OSError:
        return False
    if re.search(r"^\s*NETCONFIG_DNS_STATIC_SERVERS=", text, re.M):
        text = re.sub(
            r"^\s*NETCONFIG_DNS_STATIC_SERVERS=.*$",
            new_key, text, count=1, flags=re.M,
        )
    else:
        text += "\n" + new_key + "\n"
    return _write_file(config, text)


def _write_wicked_routes(cfg: InterfaceConfig) -> bool:
    # Default gateway lands in /etc/sysconfig/network/routes; static routes
    # go in /etc/sysconfig/network/ifroute-<iface>.
    routes_file = _WICKED_DIR / "routes"
    existing: List[str] = []
    # Only replace the default route for a family when we have a value for it.
    # Otherwise keep the existing default line so editing one family (or other
    # interfaces sharing this file) never drops a working default gateway.
    drop_v4 = bool(cfg.gateway4)
    drop_v6 = bool(cfg.gateway6)
    if routes_file.is_file():
        try:
            with routes_file.open("r", encoding="utf-8") as fh:
                for line in fh:
                    stripped = line.strip()
                    if stripped.startswith("default"):
                        parts = stripped.split()
                        gw = parts[1] if len(parts) > 1 else ""
                        is_v6 = ":" in gw
                        if is_v6 and drop_v6:
                            continue
                        if not is_v6 and drop_v4:
                            continue
                    existing.append(line.rstrip("\n"))
        except OSError:
            pass
    if cfg.gateway4:
        existing.append(f"default {cfg.gateway4} - -")
    if cfg.gateway6:
        existing.append(f"default {cfg.gateway6} - -")
    _write_file(routes_file, "\n".join(existing) + "\n")
    ifroute = _WICKED_DIR / f"ifroute-{cfg.name}"
    if cfg.routes:
        body = "\n".join(f"{dest} {gw or '-'} - -" for dest, gw in cfg.routes if dest) + "\n"
        _write_file(ifroute, body)
    else:
        try:
            _unlink(ifroute)
        except OSError:
            pass
    return True


# --- NetworkManager backend -------------------------------------------------

def _read_nm(iface: str) -> InterfaceConfig:
    cfg = InterfaceConfig(name=iface)
    try:
        out = subprocess.run(
            ["nmcli", "-t", "-f", "GENERAL.TYPE,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS,"
             "IP6.ADDRESS,IP6.GATEWAY,IP6.DNS", "device", "show", iface],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            check=False, timeout=10,
        ).stdout.decode()
    except (OSError, subprocess.SubprocessError):
        return cfg
    for raw in out.splitlines():
        if ":" not in raw:
            continue
        key, _, val = raw.partition(":")
        val = val.strip()
        if not val:
            continue
        if key.startswith("IP4.ADDRESS") and val:
            cfg.addresses.append(val)
        elif key.startswith("IP6.ADDRESS") and val and not val.startswith("fe80"):
            cfg.addresses.append(val)
        elif key == "IP4.GATEWAY":
            cfg.gateway4 = val
        elif key == "IP6.GATEWAY":
            cfg.gateway6 = val
        elif key.startswith("IP4.DNS") or key.startswith("IP6.DNS"):
            cfg.dns.append(val)
        elif key == "GENERAL.TYPE":
            cfg.kind = "bond" if val == "bond" else "ethernet"
    cfg.dhcp4 = False
    cfg.dhcp6 = False
    # Static routes via nmcli (one connection per device under our control).
    try:
        out = subprocess.run(
            ["nmcli", "-t", "-f", "ipv4.routes,ipv4.method,ipv6.method",
             "connection", "show", f"grommunio-{iface}"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            check=False, timeout=10,
        ).stdout.decode()
        for raw in out.splitlines():
            if raw.startswith("ipv4.method:"):
                cfg.dhcp4 = (raw.split(":", 1)[1].strip() == "auto")
            elif raw.startswith("ipv6.method:"):
                cfg.dhcp6 = (raw.split(":", 1)[1].strip() == "auto")
            elif raw.startswith("ipv4.routes:"):
                for chunk in raw.split(":", 1)[1].split(";"):
                    chunk = chunk.strip()
                    if not chunk:
                        continue
                    parts = chunk.split()
                    if len(parts) >= 2:
                        cfg.routes.append((parts[0], parts[1]))
    except (OSError, subprocess.SubprocessError):
        pass
    if _is_bond_device(iface):
        cfg.kind = "bond"
        rt = current_runtime_state(iface)
        cfg.bond_members = list(rt.get("bond_slaves", []))
    return cfg


def _write_nm(cfg: InterfaceConfig, member_for_bond: bool = False) -> bool:
    conname = f"grommunio-{cfg.name}"
    base = ["nmcli", "connection"]
    subprocess.run(base + ["delete", conname], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, check=False, timeout=10)
    if member_for_bond or cfg.bond_master:
        add_cmd = base + ["add", "type", "ethernet", "ifname", cfg.name,
                          "con-name", conname,
                          "master", cfg.bond_master, "slave-type", "bond"]
        return _run(add_cmd)
    iftype = "bond" if cfg.kind == "bond" else "ethernet"
    add_cmd = base + ["add", "type", iftype, "ifname", cfg.name, "con-name", conname]
    if iftype == "bond":
        add_cmd += ["bond.options", f"mode={cfg.bond_mode},miimon={cfg.bond_miimon}"]
    if cfg.dhcp4:
        add_cmd += ["ipv4.method", "auto"]
    elif cfg.addresses:
        v4 = [a for a in cfg.addresses if ":" not in a]
        if v4:
            add_cmd += ["ipv4.method", "manual", "ipv4.addresses", ",".join(v4)]
            if cfg.gateway4:
                add_cmd += ["ipv4.gateway", cfg.gateway4]
            if cfg.dns:
                add_cmd += ["ipv4.dns", ",".join(cfg.dns)]
            if cfg.routes:
                add_cmd += ["ipv4.routes", " ".join(f"{d} {g}" for d, g in cfg.routes if d)]
    if cfg.dhcp6:
        add_cmd += ["ipv6.method", "auto"]
    else:
        v6 = [a for a in cfg.addresses if ":" in a]
        if v6:
            add_cmd += ["ipv6.method", "manual", "ipv6.addresses", ",".join(v6)]
            if cfg.gateway6:
                add_cmd += ["ipv6.gateway", cfg.gateway6]
    ok = _run(add_cmd)
    if ok:
        _run(base + ["up", conname])
    return ok


def _create_nm_bond(cfg: InterfaceConfig) -> bool:
    if not _write_nm(cfg):
        return False
    for member in cfg.bond_members:
        slave = InterfaceConfig(name=member, bond_master=cfg.name)
        _write_nm(slave, member_for_bond=True)
    return True


# --- Validation ------------------------------------------------------------

def validate_cidr(value: str) -> Optional[str]:
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


def validate_route(value: str) -> Optional[str]:
    """A route line is '<destination_cidr>' or '<destination_cidr> via <gw>'."""
    parts = value.strip().split()
    if not parts:
        return None
    try:
        ipaddress.ip_network(parts[0], strict=False)
    except (ValueError, TypeError) as exc:
        return str(exc)
    if len(parts) >= 3 and parts[1] == "via":
        try:
            ipaddress.ip_address(parts[2])
        except (ValueError, TypeError) as exc:
            return str(exc)
    return None


def parse_route_line(value: str) -> Optional[Tuple[str, str]]:
    """Parse '<dest>' or '<dest> via <gw>' into (dest, gw_or_empty)."""
    parts = value.strip().split()
    if not parts:
        return None
    dest = parts[0]
    gw = ""
    if len(parts) >= 3 and parts[1] == "via":
        gw = parts[2]
    return (dest, gw)
