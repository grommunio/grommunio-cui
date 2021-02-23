#
#  Copyright (c) 2020 by grammm GmbH.
#
from pathlib import Path

from pamela import authenticate, PAMError
from typing import Any, Dict, List, Tuple, Union
from datetime import datetime

import platform
import psutil


_PALETTES: Dict[str, List[Tuple[str, ...]]] = {
    "light" : [
        ('body', 'white', 'dark cyan', 'standout', '#fcfcfc', '#32add6'),
        ('reverse', 'dark cyan', 'white', '', '#1ebdf4', '#fcfcfc'),
        ('HL.body', 'light red', 'dark cyan', 'standout', '#ff0000', '#32add6'),
        ('HL.reverse', 'dark red', 'white', '', '#800000', '#fcfcfc'),
        ('header', 'white', 'light blue', 'bold', '#fcfcfc', '#3989a5'),
        ('footer', 'white', 'light blue', 'bold', '#fcfcfc', '#33c6f5'),
        ('important', 'dark red', 'white', ('bold', 'standout', 'underline'), '#800000', '#fcfcfc'),
        ('buttonbar', 'white', 'dark cyan', '', '#fcfcfc', '#32add6'),
        ('buttn', 'white', 'dark cyan', '', '#fcfcfc', '#32add6'),
        ('buttnf', 'dark cyan', 'white', ('bold', 'standout', 'underline'), '#32add6', '#fcfcfc'),
        ('clock', 'black', 'light gray', '', '#161616', '#c0c0c0'),
        ('selectable', 'black', 'white', '', '#161616', '#fcfcfc'),
        ('focus', 'black', 'light gray', '', '#161616', '#c0c0c0'),
        ('divider', 'black', 'light gray', ('bold', 'standout'), '#161616', '#c0c0c0'),
        ('MMI.selectable', 'black', 'white', '', '#161616', '#fcfcfc'),
        ('MMI.focus', 'black', 'light gray', '', '#161616', '#c0c0c0'),
    ],
    "dark" : [
        ('body', 'black', 'light cyan', 'standout', '#161616', '#2abced'),
        ('reverse', 'light cyan', 'black', '', '#2abced', '#161616'),
        ('HL.body', 'dark red', 'light cyan', 'standout', '#800000', '#2abced'),
        ('HL.reverse', 'light red', 'black', '', '#ff0000', '#161616'),
        ('header', 'white', 'dark blue', 'bold', '#fcfcfc', '#3b8daa'),
        ('footer', 'white', 'dark blue', 'bold', '#fcfcfc', '#3b8daa'),
        ('important', 'white', 'dark red', ('bold', 'standout', 'underline'), '#fcfcfc', '#800000'),
        ('buttonbar', 'black', 'light cyan', '', '#161616', '#2abced'),
        ('buttn', 'black', 'light cyan', '', '#161616', '#2abced'),
        ('buttnf', 'light cyan', 'black', ('bold', 'standout', 'underline'), '#2abced', '#161616'),
        ('clock', 'white', 'dark gray', '', '#fcfcfc', '#808080'),
        ('selectable', 'white', 'black', '', '#fcfcfc', '#161616'),
        ('focus', 'white', 'dark gray', '', '#fcfcfc', '#808080'),
        ('divider', 'white', 'dark gray', ('bold', 'standout'), '#fcfcfc', '#808080'),
        ('MMI.selectable', 'white', 'black', '', '#fcfcfc', '#161616'),
        ('MMI.focus', 'white', 'dark gray', '', '#fcfcfc', '#808080'),
    ],
    "orange light" : [
        ('body', 'white', 'brown', 'standout', '#fcfcfc', '#808000'),
        ('reverse', 'brown', 'white', '', '#808000', '#fcfcfc'),
        ('HL.body', 'dark red', 'brown', 'standout', '#800000', '#808000'),
        ('HL.reverse', 'dark red', 'white', '', '#800000', '#fcfcfc'),
        ('header', 'white', 'dark blue', 'bold', '#fcfcfc', '#3b8daa'),
        ('footer', 'white', 'dark blue', 'bold', '#fcfcfc', '#3b8daa'),
        ('important', 'dark red', 'white', ('bold', 'standout', 'underline'), '#800000', '#fcfcfc'),
        ('buttonbar', 'white', 'brown', '', '#fcfcfc', '#808000'),
        ('buttn', 'white', 'brown', '', '#fcfcfc', '#808000'),
        ('buttnf', 'brown', 'white', ('bold', 'standout', 'underline'), '#808000', '#fcfcfc'),
        ('clock', 'white', 'light gray', '', '#fcfcfc', '#c0c0c0'),
        ('selectable', 'black', 'white', '', '#161616', '#fcfcfc'),
        ('focus', 'black', 'light gray', '', '#161616', '#c0c0c0'),
        ('divider', 'white', 'light gray', ('bold', 'standout'), '#fcfcfc', '#c0c0c0'),
        ('MMI.selectable', 'black', 'white', '', '#161616', '#fcfcfc'),
        ('MMI.focus', 'black', 'light gray', '', '#161616', '#c0c0c0'),
    ],
    "orange dark" : [
        ('body', 'black', 'yellow', 'standout', '#161616', '#ffff00'),
        ('reverse', 'yellow', 'black', '', '#ffff00', '#161616'),
        ('HL.body', 'light red', 'yellow', 'standout', '#ff0000', '#ffff00'),
        ('HL.reverse', 'light red', 'black', '', '#ff0000', '#161616'),
        ('header', 'white', 'light blue', 'bold', '#fcfcfc', '#3989a5'),
        ('footer', 'white', 'light blue', 'bold', '#fcfcfc', '#3989a5'),
        ('important', 'light red', 'black', ('bold', 'standout', 'underline'), '#ff0000', '#161616'),
        ('buttonbar', 'black', 'yellow', '', '#161616', '#ffff00'),
        ('buttn', 'black', 'yellow', '', '#161616', '#ffff00'),
        ('buttnf', 'yellow', 'black', ('bold', 'standout', 'underline'), '#ffff00', '#161616'),
        ('clock', 'white', 'dark gray', '', '#fcfcfc', '#808080'),
        ('selectable', 'white', 'black', '', '#fcfcfc', '#161616'),
        ('focus', 'white', 'dark gray', '', '#fcfcfc', '#808080'),
        ('divider', 'white', 'dark gray', ('bold', 'standout'), '#fcfcfc', '#808080'),
        ('MMI.selectable', 'white', 'black', '', '#fcfcfc', '#161616'),
        ('MMI.focus', 'white', 'dark gray', '', '#fcfcfc', '#808080'),
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
    return name, version


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
            u"\n", "Console User Interface", "\n", u"\xa9 2020 ", "grammm GmbH", u"\n",
        ]
        rv.append(f"Distribution: {distro} Version: {version}" if distro.lower().startswith('grammm') else '')
        rv.append("\n")
        rv.append("\n")
        rv.append(f"{psutil.cpu_count(logical=False)} x {uname.processor} CPUs a {get_hr(cpufreq.current * 1000 * 1000, 'Hz', 1000)}")
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
            u"\n", "For further configuration you can use following URLs:", u"\n"
        ]
        rv.append("\n")
        for interface_name, interface_addresses in if_addrs.items():
            if interface_name in ['lo']:
                continue
            for address in interface_addresses:
                if str(address.family) == 'AddressFamily.AF_INET':
                    rv.append(f"Interface: ")
                    rv.append(('reverse', f"{interface_name}"))
                    rv.append(f"  Address: https://{address.address}/grammm/admin/interface")
                    rv.append("\n")
                    rv.append(f"  or https://{uname.node}/grammm/admin/interface")
                    rv.append("\n")
                    rv.append("\n")
                else:
                    continue
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
