# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH
from pathlib import Path

from pamela import authenticate, PAMError
from typing import Any, Dict, List, Tuple, Union
from datetime import datetime
import ipaddress
import platform
import psutil
import socket


_PALETTES: Dict[str, List[Tuple[str, ...]]] = {
    "light" : [
        ('body', 'white', 'dark blue', 'standout', '#fff', '#00a'),
        ('reverse', 'dark blue', 'light gray', '', '#00a', '#aaa'),
        ('header', 'white', 'light blue', 'bold', '#fff', '#49a'),
        ('footer', 'white', 'light blue', 'bold', '#fff', '#3cf'),
        ('important', 'dark red', 'light gray', ('bold', 'standout', 'underline'), '#800', '#aaa'),
        ('buttonbar', 'white', 'dark blue', '', '#fff', '#00a'),
        ('buttn', 'white', 'dark blue', '', '#fff', '#00a'),
        ('buttnf', 'dark blue', 'light gray', ('bold', 'standout', 'underline'), '#00a', '#aaa'),
        ('selectable', 'white', 'black', '', '#fff', '#111'),
        ('focus', 'black', 'light gray', '', '#111', '#ccc'),
        ('divider', 'black', 'light gray', ('bold', 'standout'), '#111', '#ccc'),
        ('MMI.selectable', 'white', 'black', '', '#fff', '#111'),
        ('MMI.focus', 'black', 'light gray', '', '#111', '#ccc'),
    ],
    "dark" : [
        ('body', 'black', 'dark cyan', 'standout', '#111', '#0aa'),
        ('reverse', 'dark cyan', 'black', '', '#0aa', '#111'),
        ('header', 'white', 'dark blue', 'bold', '#fff', '#49b'),
        ('footer', 'white', 'dark blue', 'bold', '#fff', '#49b'),
        ('important', 'white', 'dark red', ('bold', 'standout', 'underline'), '#fff', '#800'),
        ('buttonbar', 'black', 'dark cyan', '', '#111', '#0aa'),
        ('buttn', 'black', 'dark cyan', '', '#111', '#0aa'),
        ('buttnf', 'dark cyan', 'black', ('bold', 'standout', 'underline'), '#0aa', '#111'),
        ('selectable', 'black', 'white', '', '#111', '#fff'),
        ('focus', 'white', 'dark gray', '', '#fff', '#888'),
        ('divider', 'white', 'dark gray', ('bold', 'standout'), '#fff', '#888'),
        ('MMI.selectable', 'black', 'white', '', '#111', '#fff'),
        ('MMI.focus', 'white', 'dark gray', '', '#fff', '#888'),
    ],
    "orange light" : [
        ('body', 'white', 'brown', 'standout', '#fff', '#880'),
        ('reverse', 'brown', 'white', '', '#880', '#fff'),
        ('header', 'white', 'dark blue', 'bold', '#fff', '#49b'),
        ('footer', 'white', 'dark blue', 'bold', '#fff', '#49b'),
        ('important', 'dark red', 'white', ('bold', 'standout', 'underline'), '#800', '#fff'),
        ('buttonbar', 'white', 'brown', '', '#fff', '#880'),
        ('buttn', 'white', 'brown', '', '#fff', '#880'),
        ('buttnf', 'brown', 'white', ('bold', 'standout', 'underline'), '#880', '#fff'),
        ('selectable', 'white', 'black', '', '#fff', '#111'),
        ('focus', 'black', 'light gray', '', '#111', '#ccc'),
        ('divider', 'white', 'light gray', ('bold', 'standout'), '#fff', '#ccc'),
        ('MMI.selectable', 'white', 'black', '', '#fff', '#111'),
        ('MMI.focus', 'black', 'light gray', '', '#111', '#ccc'),
    ],
    "orange dark" : [
        ('body', 'black', 'yellow', 'standout', '#111', '#ff0'),
        ('reverse', 'yellow', 'black', '', '#ff0', '#111'),
        ('header', 'white', 'light blue', 'bold', '#fff', '#49a'),
        ('footer', 'white', 'light blue', 'bold', '#fff', '#49a'),
        ('important', 'light red', 'black', ('bold', 'standout', 'underline'), '#f00', '#111'),
        ('buttonbar', 'black', 'yellow', '', '#111', '#ff0'),
        ('buttn', 'black', 'yellow', '', '#111', '#ff0'),
        ('buttnf', 'yellow', 'black', ('bold', 'standout', 'underline'), '#ff0', '#111'),
        ('selectable', 'black', 'white', '', '#111', '#fff'),
        ('focus', 'white', 'dark gray', '', '#fff', '#888'),
        ('divider', 'white', 'dark gray', ('bold', 'standout'), '#fff', '#888'),
        ('MMI.selectable', 'black', 'white', '', '#111', '#fff'),
        ('MMI.focus', 'white', 'dark gray', '', '#fff', '#888'),
    ]
}


def authenticate_user(username: str, password: str, service: str = 'login') -> bool:
    """
    Authenticates username against password on service.

    :param username: The user to authenticate.
    :param password: Tge password in clear.
    :param service: PAM service to use. "login" is default.
    :return: True on success, False if not.
    """
    try:
        authenticate(username, password, service)
        return True
    except PAMError as e:
        return False


def get_os_release() -> Tuple[str, str]:
    osr: Path = Path('/etc/os-release')
    name: str = 'No name found'
    version: str = 'No version detectable'
    with osr.open('r') as f:
        for line in f:
            if line.startswith('NAME'):
                k, name = line.strip().split('=')
            elif line.startswith('VERSION'):
                k, version = line.strip().split('=')
    return name.strip('"'), version.strip('"')


def get_first_ip_not_localhost() -> str:
    for ip in get_ip_list():
        if not ip.strip().startswith('127.'):
            return ip.strip()
    return ""


def get_ip_list() -> List[str]:
    rv: List[str] = []
    addr: psutil._common.snicaddr
    addrs: Dict[str, psutil._common.snicaddr] = psutil.net_if_addrs()
    for dev, addrlist in addrs.items():
        for addr in addrlist:
            if addr.family == socket.AF_INET:
                rv.append(addr.address)
    return rv


def get_system_info(which: str) -> List[Union[str, Tuple[str, str]]]:
    """
    Creates list of informations formatted in urwid stye.

    :param which: Kind of information to return. (top or bottom)
    :return: List of tuples or strings descibing urwid attributes and content.
    """
    rv: List[Union[str, Tuple[str, str]]] = []
    if which == "grammm_top":
        uname = platform.uname()
        cpufreq = psutil.cpu_freq()
        svmem = psutil.virtual_memory()
        distro, version = get_os_release()
        rv += [
            u"\n", "Console User Interface", "\n", u"© 2021 ", "grammm GmbH", u"\n",
        ]
        rv.append(f"Distribution: {distro} Version: {version}" if distro.lower().startswith('grammm') else '')
        rv.append("\n")
        rv.append("\n")
        if cpufreq:
             rv.append(f"{psutil.cpu_count(logical=False)} x {uname.processor} CPUs a {get_hr(cpufreq.current * 1000 * 1000, 'Hz', 1000)}")
        else:
             rv.append(f"{psutil.cpu_count(logical=False)} x {uname.processor} CPUs")
        rv.append("\n")
        rv.append(f"Memory {get_hr(svmem.used)} used of {get_hr(svmem.total)}. {get_hr(svmem.available)} free.")
        rv.append("\n")
        rv.append("\n")
    elif which == "grammm_bottom":
        uname = platform.uname()
        if_addrs = psutil.net_if_addrs()
        boot_time_timestamp = psutil.boot_time()
        bt = datetime.fromtimestamp(boot_time_timestamp)
        rv += [
            u"\n", "For further configuration, these URLs can be used:", u"\n"
        ]
        rv.append("\n")
        rv.append(f"http://{uname.node}:8080/\n");
        for interface_name, interface_addresses in if_addrs.items():
            if interface_name in ['lo']:
                continue
            for address in interface_addresses:
                if address.family != socket.AF_INET6:
                    continue
                adr = ipaddress.IPv6Address(address.address.split('%')[0])
                if adr.is_link_local is True:
                    continue
                rv.append(f"http://[{address.address}]:8080/ (interface {interface_name})\n")
            for address in interface_addresses:
                if address.family != socket.AF_INET:
                    continue
                rv.append(f"http://{address.address}:8080/ (interface {interface_name})\n")
        rv.append(f"Boot Time: ")
        rv.append(('reverse', f'{bt.isoformat()}'))
        rv.append("\n")
        rv.append("\n")
    else:
        rv.append("Oups!")
        rv.append("There should be nothing.")
    return rv


def pad(text: Any, sign: str = ' ', length: int = 2, left_pad: bool = True) -> str:
    """
    Is padding text to length filling with sign chars  Can pad from right or left.

    :param text: The text to be padded.
    :param sign: The character used to pad.
    :param length: The length to pad to.
    :param left_pad: Pad left side instead of right.
    :return: The padded text.
    """
    text_len: int = len(str(text))
    diff: int = length - text_len
    suffix: str = sign * diff
    rv: str
    slice_pos: int
    if left_pad:
        rv = f"{suffix}{text}"
        slice_pos = length
    else:
        rv = f"{text}{suffix}"
        slice_pos = length * -1
    return rv[:slice_pos]


def get_hr(bytes, suffix="B", factor=1024):
    """
    Scale bytes to its human readable format

    e.g:
        1253656 => '1.20MB'
        1253656678 => '1.17GB'
    """
    for unit in ["", "K", "M", "G", "T", "P"]:
        if bytes < factor:
            return f"{bytes:.2f} {unit}{suffix}"
        bytes /= factor


def get_clockstring() -> str:
    """
    Returns the current date and clock formatted correctly.

    :return: The formatted clockstring.
    """
    bt: datetime = datetime.now()
    year: str = pad(bt.year, '0', 4)
    month: str = pad(bt.month, '0', 2)
    day: str = pad(bt.day, '0', 2)
    hour: str = pad(bt.hour, '0', 2)
    minute: str = pad(bt.minute, '0', 2)
    second: str = pad(bt.second, '0', 2)
    return f"{year}-{month}-{day} {hour}:{minute}:{second}"


def get_palette_list() -> List[str]:
    global _PALETTES
    l = list(_PALETTES.keys())
    return l


def get_next_palette_name(cur_palette: str = "") -> str:
    l = get_palette_list()
    i = iter(l)
    for p in i:
        if p == l[len(l) - 1]:
            return l[0]
        elif p == cur_palette:
            return next(i)
    return l[0]


def get_palette(mode: str = 'light') -> List[Tuple[str, ...]]:
    global _PALETTES
    rv: List[Tuple[str, ...]] = _PALETTES[mode]
    return rv


def fast_tail(file: str, n: int = 0) -> List[str]:
    assert n >= 0, "Line count n musst be greater equal 0!"
    pos: int = n + 1
    lines: List[str] = []
    fname: Path = Path(file)
    with fname.open('r') as f:
        while len(lines) <= n:
            try:
                f.seek(-pos, 2)
            except IOError as e:
                f.seek(0)
                break
            finally:
                lines = list(f)
            pos *= 2
    return [line.strip() for line in lines[-n:]]
