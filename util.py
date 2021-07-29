# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH
import os
import subprocess
from pathlib import Path

from pamela import authenticate, PAMError
from typing import Any, Dict, List, Tuple, Union
from datetime import datetime
import ipaddress
import platform
import psutil
import socket


STATES = {
    1: 'System password is not set!!',
    2: 'Network configuration is missing!',
    4: 'grommunio-setup not executed yet!',
    8: 'Timesyncd configuration is missing!',
    16: 'nginx is not running!',
}

_PALETTES: Dict[str, List[Tuple[str, ...]]] = {
    "light": [
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
        ('footerbar.short', 'white', 'black', '', '#fff', '#111'),
        ('footerbar.long', 'white', 'dark blue', '', '#111', '#00a'),
    ],
    "dark": [
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
        ('footerbar.short', 'black', 'white', '', '#111', '#fff'),
        ('footerbar.long', 'black', 'dark cyan', '', '#fff', '#111'),
    ],
    "orange light": [
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
        ('footerbar.short', 'white', 'black', '', '#fff', '#111'),
        ('footerbar.long', 'white', 'brown', '', '#111', '#ccc'),
    ],
    "orange dark": [
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
        ('footerbar.short', 'black', 'white', '', '#111', '#fff'),
        ('footerbar.long', 'black', 'yellow', '', '#fff', '#888'),
    ]
}


def extract_bits(binary):
    c = ''
    i = 0
    rv = []
    while c != 'b':
        s = str(bin(binary))[::-1]
        c = s[i]
        if c == '1':
            rv.append(2**i)
        i += 1
    return rv


def check_socket(host='127.0.0.1', port=22):
    try:
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error:
        return False


def tlen(tuple_list, idx=0):
    """Return length of all id'th element in a tuple over all tuple lists.
    The tuples can be nested in list in list in list ...
    tlen([(1, 'bla'), (2, 'blubb')], 1)
    will return 8. It doesn't matter how many nested Lists there are.
    [(1, a), ..., (23, b)] will return the same as [[[(1, a), ...]], (23, b)]
    """
    rv = 0
    tl = tuple_list
    if not tl:
        return 0
    if isinstance(tl, list):
        for elem in tl:
            rv += tlen(elem, idx)
    elif isinstance(tl, tuple):
        rv += len(tl[idx])
    elif isinstance(tl, str):
        rv += len(tl)
    else:
        rv += 0
    return rv


def rebase_list(deep_list):
    rv = []
    dl = deep_list
    if isinstance(dl, list):
        for elem in dl:
            rv += rebase_list(elem)
    else:
        rv += [dl]
    return rv


def make_list_gtext(list_wowo_gtext):
    from cui import GText
    wowolist = list_wowo_gtext
    rv = []
    for wowo in wowolist:
        if not isinstance(wowo, GText):
            rv += [GText(wowo)]
        else:
            rv += [wowo]
    return rv


def check_setup_state():
    """Check states of setup and returns a combined binary number"""
    def check_if_password_is_set(user):
        file = '/etc/shadow'
        items = {}
        if os.access(file, os.R_OK):
            with open(file) as fh:
                for line in fh:
                    parts = line.split(":")
                    username = parts[0]
                    password = parts[1]
                    items[username.strip()] = password.strip()
        if len(items.get(user)) > 0:
            return True
        return False

    def check_network_config():
        return check_socket('127.0.0.1', 22)

    def check_grommunio_setup():
        # return os.path.isfile('/etc/grommunio/setup_done')
        return os.path.isfile('/etc/grammm/setup_done') or os.path.isfile('/etc/grommunio-common/setup_done')

    def check_timesyncd_config():
        out = subprocess.check_output(['timedatectl', 'status']).decode()
        items = {}
        for line in out.splitlines():
            key, value = line.partition(':')[::2]
            items[key.strip()] = value.strip()
        if items.get('Network time on') == 'yes' and items.get('NTP synchronized') == 'yes':
            return True
        return False

    def check_nginx_config():
        return check_socket('127.0.0.1', 8080)

    rv = 0
    # check if pw is set
    if not check_if_password_is_set('root'):
        rv += 1
    # check network config (2)
    if not check_network_config():
        rv += 2
    # check grommunio-setup config (4)
    if not check_grommunio_setup():
        rv += 4
    # check timesyncd config (8)
    if not check_timesyncd_config():
        rv += 0  # give 0 error points cause timesyncd configuration is not necessarily needed.
    # check nginx config (16)
    if not check_nginx_config():
        rv += 16
    return rv


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
    except PAMError:
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
    addrs = psutil.net_if_addrs()
    for dev, addrlist in addrs.items():
        for addr in addrlist:
            if addr.family == socket.AF_INET:
                rv.append(addr.address)
    return rv


def get_last_login_time():
    p = subprocess.Popen(['last', '-1', 'root'], stderr=subprocess.DEVNULL, stdout=subprocess.PIPE)
    res, _ = p.communicate()
    out = bytes(res).decode()
    lines = out.splitlines()
    last_login = ''
    if len(lines) > 0:
        parts = out.splitlines()[0].split('              ')
        if len(parts) > 1:
            last_login = parts[1].strip()
    return last_login


def get_load():
    p = subprocess.Popen(['cat', '/proc/loadavg'], stderr=subprocess.DEVNULL, stdout=subprocess.PIPE)
    res, _ = p.communicate()
    out = bytes(res).decode()
    lines = out.splitlines()
    load_1min = 0
    load_5min = 0
    load_15min = 0
    if len(lines) > 0:
        parts = lines[0].split()
        if len(parts) > 1:
            load_1min = float(parts[0].strip())
            load_5min = float(parts[1].strip())
            load_15min = float(parts[2].strip())
    return load_1min, load_5min, load_15min


def get_load_avg_format_list():
    load_avg = get_load()
    load_format = [('footer', ' Average load: ')]
    _ = [load_format.append(('footer', f'{t} min:')) or
         load_format.append(('body', f' {load_avg[i]:0.2f}')) or
         load_format.append(('footer', ' | '))
         for i, t in enumerate([1, 5, 15])]
    return load_format[:-1]


def get_system_info(which: str) -> List[Union[str, Tuple[str, str]]]:
    """
    Creates list of informations formatted in urwid stye.

    :param which: Kind of information to return. (top or bottom)
    :return: List of tuples or strings descibing urwid attributes and content.
    """
    rv: List[Union[str, Tuple[str, str]]] = []
    if which == "top":
        uname = platform.uname()
        cpufreq = psutil.cpu_freq()
        svmem = psutil.virtual_memory()
        distro, version = get_os_release()
        rv += [
            "Console User Interface", "\n", u"© 2021 ", "grommunio GmbH", u"\n",
        ]
        if distro.lower().startswith('grammm') or distro.lower().startswith('grommunio'):
            rv.append(f"Distribution: {distro} Version: {version}")
            rv.append("\n")
        rv.append("\n")
        if cpufreq:
            rv.append(f"{psutil.cpu_count(logical=False)} x {uname.processor} CPUs"
                      f" a {get_hr(cpufreq.current * 1000 * 1000, 'Hz', 1000)}")
        else:
            rv.append(f"{psutil.cpu_count(logical=False)} x {uname.processor} CPUs")
        rv.append("\n")
        rv.append(f"Memory {get_hr(svmem.used)} used of {get_hr(svmem.total)}. {get_hr(svmem.available)} free.")
        rv.append("\n")
        rv.append("\n")
    elif which == "bottom":
        uname = platform.uname()
        if_addrs = psutil.net_if_addrs()
        boot_time_timestamp = psutil.boot_time()
        bt = datetime.fromtimestamp(boot_time_timestamp)
        proto = 'http'
        if check_setup_state() == 0:
            rv += [
                u"\n", "For further configuration, these URLs can be used:", u"\n"
            ]
            rv.append("\n")
            if uname.node.lower().startswith('localhost.'):
                rv.append(('important', 'It is generally NOT the best idea to use localhost as hostname!'))
                rv.append('\n')
            rv.append(f"{proto}://{uname.node}:8080/\n")
            for interface_name, interface_addresses in if_addrs.items():
                if interface_name in ['lo']:
                    continue
                for address in interface_addresses:
                    if address.family != socket.AF_INET6:
                        continue
                    adr = ipaddress.IPv6Address(address.address.split('%')[0])
                    if adr.is_link_local is True:
                        continue
                    rv.append(f"{proto}://[{address.address}]:8080/ (interface {interface_name})\n")
                for address in interface_addresses:
                    if address.family != socket.AF_INET:
                        continue
                    rv.append(f"{proto}://{address.address}:8080/ (interface {interface_name})\n")
        else:
            rv.append('\n')
            rv.append('There are still some things missing to run grommunio.')
            rv.append('\n')
            statelist = extract_bits(check_setup_state())
            for state in statelist:
                rv.append('\n')
                rv.append(('important', STATES.get(state)))
            rv.append("\n")
        rv.append("\n")
        rv.append(f"Boot Time: ")
        rv.append(('reverse', f'{bt.isoformat()}'))
        rv.append("\n")
        last_login = get_last_login_time()
        if last_login != '':
            rv.append(f"Last login time: {last_login}")
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


def get_hr(formatbytes, suffix="B", factor=1024):
    """
    Scale formatbytes to its human readable format

    e.g:
        1253656 => '1.20MB'
        1253656678 => '1.17GB'
    """
    for unit in ["", "K", "M", "G", "T", "P"]:
        if formatbytes < factor:
            return f"{formatbytes:.2f} {unit}{suffix}"
        formatbytes /= factor


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


def get_footerbar(key_size=2, name_size=10):
    """Return footerbar description"""
    rv = []
    menu = {'F1': 'Color', 'F2': 'Login', 'F5': 'KBD-Layout', 'H': 'Logfiles'}
    spacebar = ''.join(' ' for _ in range(name_size))
    for item in menu.items():
        nr = ('footerbar.short', f"  {item[0]}"[-key_size:])
        name = ('footerbar.long', f"{item[1]}{spacebar}"[:name_size])
        field = [nr, name]
        rv.append(field)
    return rv


def get_palette_list() -> List[str]:
    global _PALETTES
    return list(_PALETTES.keys())


def get_next_palette_name(cur_palette: str = "") -> str:
    palette_list = get_palette_list()
    i = iter(palette_list)
    for p in i:
        if p == palette_list[len(palette_list) - 1]:
            return palette_list[0]
        elif p == cur_palette:
            return next(i)
    return palette_list[0]


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
            except IOError:
                f.seek(0)
                break
            finally:
                lines = list(f)
            pos *= 2
    return [line.strip() for line in lines[-n:]]


def minishell_read(file):
    # should use shlex, but it's not included
    items = {}
    try:
        with open(file) as fh:
            for line in fh:
                key, value = line.partition("=")[::2]
                items[key.strip()] = value.strip()
    except IOError:
        pass
    return items


def minishell_write(file, items):
    with open(file, "w") as fh:
        for key in items:
            fh.write(key)
            fh.write("=")
            fh.write(items[key])
            fh.write("\n")


def get_current_kbdlayout():
    items = minishell_read("/etc/vconsole.conf")
    return items.get("KEYMAP", 'us').strip('"')
