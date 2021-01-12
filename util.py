#
#  Copyright (c) 2020 by grammm GmbH.
#

from pamela import authenticate, change_password, PAMError
from typing import Any, Dict, List, Tuple, Union
from datetime import datetime
from tabulate import tabulate

import asyncio
import platform
import psutil
import GPUtil


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


def get_system_info(which: str) -> List[Union[str, Tuple[str, str]]]:
    """
    Creates list of informations formatted in urwid stye.
    
    :param which: Kind of information to return. (top or bottom)
    :return: List of tuples or strings descibing urwid attributes and content.
    """
    rv: List[Union[str, Tuple[str, str]]] = []
    if which == 'top':
        uname = platform.uname()
        boot_time_timestamp = psutil.boot_time()
        bt = datetime.fromtimestamp(boot_time_timestamp)
        cpufreq = psutil.cpu_freq()
        year: str = pad(bt.year, '0', 4)
        month: str = pad(bt.month, '0', 2)
        day: str = pad(bt.day, '0', 2)
        hour: str = pad(bt.hour, '0', 2)
        minute: str = pad(bt.minute, '0', 2)
        second: str = pad(bt.second, '0', 2)
        loop = asyncio.get_event_loop()
        # loop = asyncio.get_event_loop(loop)
        svmem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        partitions = psutil.disk_partitions()
        rv += [
            u"OS ", ('HL.body', f"{uname.system}"), u" ",
            u"rel. ", ('HL.body', f"{uname.release}"), u" ",
            u"ver. ", ('HL.body', f"{uname.version}"), u" ",
            u"on host ", ('HL.body', f"{uname.node}"), u"\n",
            u"Processor: ", ('HL.body', f"{uname.processor}"), u" ",
            u"Machine: ", ('HL.body', f"{uname.machine}"), u"\n",
            u"Boot Time: ", ('HL.body', f"{year}-{month}-{day} {hour}:{minute}:{second}"), u"\n",
            u"CPU(Phys/Log/Freq): ", ('HL.body', f"{psutil.cpu_count(logical=False)}"), "/",
            ('HL.body', f"{psutil.cpu_count(logical=True)}"), "/(", ('HL.body', f"{cpufreq.min}"), "/",
            ('HL.body', f"{cpufreq.current}"), "/", ('HL.body', f"{cpufreq.max}"), ")", "\n",
            u"CPU Usage/core: ",
            [f"Core {i}: {percentage}%\n" for i, percentage in enumerate(psutil.cpu_percent(percpu=True, interval=1))],
            f"Total CPU Usage: {psutil.cpu_percent()}%", "\n",
            f"MEM-Total: ", ('HL.body', f"{get_hr(svmem.total)}"), "",
            f"Available: ", ('HL.body', f"{get_hr(svmem.available)}"), "",
            f"Used: ", ('HL.body', f"{get_hr(svmem.used)}"), "",
            f"Percentage: ", ('HL.body', f"{svmem.percent}%"), "",
            f"Total: ", ('HL.body', f"{get_hr(swap.total)}"), "",
            f"Free: ", ('HL.body', f"{get_hr(swap.free)}"), "",
            f"Used: ", ('HL.body', f"{get_hr(swap.used)}"), "",
            f"Percentage: ", ('HL.body', f"{swap.percent}%"), "",
        ]
        rv.append("\n")
        for partition in partitions:
            rv.append(f"=== Device: ")
            rv.append(('HL.body', f"{partition.device} ==="))
            rv.append(f"  Mountpoint: ")
            rv.append(('HL.body', f"{partition.mountpoint}"))
            rv.append(f"  File system type: ")
            rv.append(('HL.body', f"{partition.fstype}"))
            try:
                partition_usage = psutil.disk_usage(partition.mountpoint)
            except PermissionError:
                continue
            rv.append(f"  Total Size: ")
            rv.append(('HL.body', f"{get_hr(partition_usage.total)}"))
            rv.append(f"  Used: ")
            rv.append(('HL.body', f"{get_hr(partition_usage.used)}"))
            rv.append(f"  Free: ")
            rv.append(('HL.body', f"{get_hr(partition_usage.free)}"))
            rv.append(f"  Percentage: ")
            rv.append(('HL.body', f"{partition_usage.percent}%"))
            rv.append("\n")
        disk_io = psutil.disk_io_counters()
        rv.append(f"Total read: ")
        rv.append(('HL.body', f"{get_hr(disk_io.read_bytes)}"))
        rv.append(f"Total write: ")
        rv.append(('HL.body', f"{get_hr(disk_io.write_bytes)}"))
        rv.append("\n")
    elif which == "bottom":
        rv += [
            u"Here are some links for you:", u"\n",
        ]
        rv.append(f'{"=" * 40} Network Information {"=" * 40}')
        rv.append("\n")
        if_addrs = psutil.net_if_addrs()
        for interface_name, interface_addresses in if_addrs.items():
            rv.append("interface_name: ")
            rv.append(('HL.reverse', str(interface_name)))
            rv.append("\n")
            for address in interface_addresses:
                rv.append(f"=== Interface: ")
                rv.append(('HL.reverse', f"{interface_name} ==="))
                if str(address.family) == 'AddressFamily.AF_INET':
                    rv.append(f"  IP Address: ")
                elif str(address.family) == 'AddressFamily.AF_PACKET':
                    rv.append(f"  MAC Address: ")
                rv.append(('HL.reverse', f"{address.address}"))
                rv.append(f"  Netmask: ")
                rv.append(('HL.reverse', f"{address.netmask}"))
                rv.append(f"  Broadcast MAC: ")
                rv.append(('HL.reverse', f"{address.broadcast}"))
                rv.append("\n")
        net_io = psutil.net_io_counters()
        rv.append(f"Total Bytes Sent: ")
        rv.append(('HL.reverse', f"{get_hr(net_io.bytes_sent)}"))
        rv.append(f"Total Bytes Received: ")
        rv.append(('HL.reverse', f"{get_hr(net_io.bytes_recv)}"))
        rv.append("\n")
        rv.append(f'{"=" * 40} GPU Details {"=" * 40}')
        rv.append("\n")
        gpus = GPUtil.getGPUs()
        list_gpus = []
        for gpu in gpus:
            # get the GPU id
            gpu_id = gpu.id
            # name of GPU
            gpu_name = gpu.name
            # get % percentage of GPU usage of that GPU
            gpu_load = f"{gpu.load * 100}%"
            # get free memory in MB format
            gpu_free_memory = f"{gpu.memoryFree}MB"
            # get used memory
            gpu_used_memory = f"{gpu.memoryUsed}MB"
            # get total memory
            gpu_total_memory = f"{gpu.memoryTotal}MB"
            # get GPU temperature in Celsius
            gpu_temperature = f"{gpu.temperature} °C"
            gpu_uuid = gpu.uuid
            list_gpus.append((
                gpu_id, gpu_name, gpu_load, gpu_free_memory, gpu_used_memory,
                gpu_total_memory, gpu_temperature, gpu_uuid
            ))
        rv.append(
            tabulate(list_gpus, headers=("id", "name", "load", "free memory", "used memory", "total memory",
                                         "temperature", "uuid")))
    elif which == "grammm_top":
        uname = platform.uname()
        cpufreq = psutil.cpu_freq()
        svmem = psutil.virtual_memory()
        rv += [
            u"\n", "Console User Interface", "\n", u"\xa9 2020 ", "grammm GmbH", u"\n",
        ]
        rv.append("Where do I find grammm version???")
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
        year: str = pad(bt.year, '0', 4)
        month: str = pad(bt.month, '0', 2)
        day: str = pad(bt.day, '0', 2)
        hour: str = pad(bt.hour, '0', 2)
        minute: str = pad(bt.minute, '0', 2)
        second: str = pad(bt.second, '0', 2)
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
        rv.append(('reverse', f'{hour}:{minute}:{second} {day}.{month}.{year}'))
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
