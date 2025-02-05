# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH
"""The module contains all cui utilities/functions"""
import cffi
import os
import subprocess
import sys
import time
from pathlib import Path
import ipaddress
import locale
import platform
import socket
import shlex
from typing import Any, Dict, List, Tuple, Union, Iterable
from datetime import datetime
import re

import psutil
import requests
from pamela import authenticate, PAMError

from requests import Response

import urwid
import cui


def _(msg):
    """Dummy func"""
    return msg


STATES = {
    1: _("System password is not set."),
    2: _("Network configuration is missing."),
    4: _("grommunio-setup has not been run yet."),
    8: _("timesyncd configuration is missing."),
    16: _("nginx is not running."),
    32: _("grommunio-admin is not installed."),
}


def reset_states():
    """Reset states"""
    # pylint: disable=global-statement
    # because that is needed for on the fly translation
    global STATES
    new_states = {}
    if STATES:
        for key, val in STATES.items():
            new_states[key] = _(val)
    STATES = new_states
    return STATES


def init_localization(language: Union[str, str, Iterable[Union[str, str]], None] = ''):
    """Initialize localisation"""
    locale.setlocale(locale.LC_ALL, language)
    try:
        locale.bindtextdomain(
            'cui', 'locale' if os.path.exists("locale/de/LC_MESSAGES/cui.mo") else None
        )
        locale.textdomain('cui')
        _ = locale.gettext
        reset_states()
        return _
    except (OSError, AttributeError):
        def _(msg):
            """
            Function for tagging text for translations.
            """
            return msg
        reset_states()
        return _


_ = init_localization()


def get_button_type(key, open_func_on_ok, mb_func, cancel_msgbox_params, size):
    """Return button type (Ok, Cancel, Save, Add, ....)
    Be aware the types are translated!
    """
    def open_cancel_msg(msg_params, mb_size):
        if mb_func is not None and msg_params is not None:
            mb_func(msg_params, size=mb_size)

    val: str = key.lower()
    if val.endswith("enter"):
        val = " ".join(val.split(" ")[:-1])
        open_func_on_ok()
        if val.startswith("hidden"):
            val = " ".join(val.split(" ")[1:])
        else:
            val = _("Cancel").lower()
        if val == _("Cancel").lower():
            open_cancel_msg(cancel_msgbox_params, size)
    elif val == 'esc':
        open_func_on_ok()
        open_cancel_msg(cancel_msgbox_params, size)
    return val


def restart_gui():
    """Restart complete GUI to source language in again."""
    ret_val = _
    langfile = '/etc/sysconfig/language'
    config = cui.classes.parser.ConfigParser(infile=langfile)
    config['ROOT_USES_LANG'] = '"yes"'
    config.write()
    # assert os.getenv('PPID') == 1, 'Gugg mal rein da!'
    locale_conf = minishell_read('/etc/locale.conf')
    # _ = util.init_localization()
    # mainapp()
    if os.getppid() == 1:
        # from pudb.remote import set_trace; set_trace(term_size=(230, 60))
        ret_val = init_localization(language=locale_conf.get('LANG', ''))
        cui.main_app(True)
        # raise ExitMainLoop()
    else:
        env = {}
        for k in os.environ:
            env[k] = os.environ.get(k)
        for k in locale_conf:
            env[k] = locale_conf.get(k)
        os.execve(sys.executable, [sys.executable] + sys.argv, env)
    return ret_val


def create_main_loop(app):
    """Create urwid main loop"""
    urwid.set_encoding("utf-8")
    app.view.gscreen = cui.classes.application.GScreen()
    app.view.gscreen.screen = urwid.raw_display.Screen()
    app.view.gscreen.old_termios = app.view.gscreen.screen.tty_signal_keys()
    app.view.gscreen.blank_termios = ["undefined" for _ in range(0, 5)]
    app.view.gscreen.screen.tty_signal_keys(*app.view.gscreen.blank_termios)
    app.prepare_mainscreen()
    # Loop
    return urwid.MainLoop(
        app.control.app_control.body,
        get_palette(app.view.header.get_colormode()),
        unhandled_input=app.handle_event,
        screen=app.view.gscreen.screen,
        handle_mouse=False,
    )


def get_distribution_level():
    """Return the distribution level depending on os-release"""
    if lineconfig_read('/etc/os-release').get('VERSION', '"2022.05.2"').startswith('"2022.12'):
        return '15.4'
    elif lineconfig_read('/etc/os-release').get('VERSION', '"2022.05.2"').startswith('"2023'):
        return '15.5'
    return '15.6'


def get_repo_url(user: str = None, password: str = None):
    """Return the repository url depending on os-release"""
    distro_level = get_distribution_level()
    if user and password:
        url = f'{user}:{password}@download.grommunio.com/supported/openSUSE_Leap_{distro_level}/'
    else:
        url = f'download.grommunio.com/community/openSUSE_Leap_{distro_level}/'
    return ''.join([url, '?ssl_verify=no'])


def check_repo_dialog(app, height):
    """Check the repository selection dialog"""
    updateable = False
    if app.control.menu_control.repo_selection_body.base_widget[3].state:
        # supported selected
        user = app.control.menu_control.repo_selection_body.base_widget[4][1].edit_text
        password = app.control.menu_control.repo_selection_body.base_widget[5][1].edit_text
        testurl = f"https://download.grommunio.com/supported/open" \
                  f"SUSE_Leap_{get_distribution_level()}/repodata/repomd.xml"
        req: Response = requests.get(testurl, auth=(user, password))
        if req.status_code == 200:
            updateable = True
        else:
            app.message_box(
                cui.parameter.MsgBoxParams(
                    _('Please check the credentials for "supported"'
                      '-version or use "community"-version.'),
                ),
                size=cui.parameter.Size(height=height + 1)
            )
    else:
        # community selected
        updateable = True
        user = None
        password = None
    return updateable, get_repo_url(user, password)


def check_if_gradmin_exists():
    exe = "/usr/sbin/grommunio-admin"
    if Path(exe).exists():
        return True
    return False


BG_LIGHT_GRAY: str = "light gray"
BG_DARK_CYAN: str = "dark cyan"
BG_DARK_MAGENTA: str = "dark magenta"
BG_DARK_BLUE: str = "dark blue"
BG_BROWN: str = "brown"
BG_DARK_GREEN: str = "dark green"
BG_DARK_RED: str = "dark red"
BG_BLACK: str = "black"

FG_BLACK: str = "black"
FG_DARK_RED: str = "dark red"
FG_DARK_GREEN: str = "dark green"
FG_BROWN: str = "brown"
FG_DARK_BLUE: str = "dark blue"
FG_DARK_MAGENTA: str = "dark magenta"
FG_DARK_CYAN: str = "dark cyan"
FG_LIGHT_GRAY: str = "light gray"
FG_DARK_GRAY: str = "dark gray"
FG_LIGHT_RED: str = "light red"
FG_LIGHT_GREEN: str = "light green"
FG_YELLOW: str = "yellow"
FG_LIGHT_BLUE: str = "light blue"
FG_LIGHT_MAGENTA: str = "light magenta"
FG_LIGHT_CYAN: str = "light cyan"
FG_WHITE: str = "white"

_PALETTES: Dict[str, List[Tuple[str, ...]]] = {
    "light": [
        ("body", FG_WHITE, BG_DARK_BLUE, "standout", "#fff", "#00a"),
        ("reverse", FG_DARK_BLUE, BG_LIGHT_GRAY, "", "#00a", "#aaa"),
        ("header", FG_WHITE, BG_DARK_BLUE, "bold", "#fff", "#49a"),
        ("footer", FG_WHITE, BG_DARK_BLUE, "bold", "#fff", "#3cf"),
        (
            "important",
            FG_DARK_RED,
            BG_LIGHT_GRAY,
            ("bold", "standout", "underline"),
            "#800",
            "#aaa",
        ),
        ("buttonbar", FG_WHITE, BG_DARK_BLUE, "", "#fff", "#00a"),
        ("buttn", FG_WHITE, BG_DARK_BLUE, "", "#fff", "#00a"),
        (
            "buttnf",
            FG_DARK_BLUE,
            BG_LIGHT_GRAY,
            ("bold", "standout", "underline"),
            "#00a",
            "#aaa",
        ),
        ("disabled", FG_DARK_GRAY, BG_BLACK, "", "#fff", "#111"),
        ("selectable", FG_WHITE, BG_BLACK, "", "#fff", "#111"),
        ("focus", FG_BLACK, BG_LIGHT_GRAY, "", "#111", "#ccc"),
        (
            "divider",
            FG_BLACK,
            BG_LIGHT_GRAY,
            ("bold", "standout"),
            "#111",
            "#ccc",
        ),
        ("MMI.selectable", FG_WHITE, BG_BLACK, "", "#fff", "#111"),
        ("MMI.focus", FG_BLACK, BG_LIGHT_GRAY, "", "#111", "#ccc"),
        ("footerbar.short", FG_WHITE, BG_BLACK, "", "#fff", "#111"),
        ("footerbar.long", FG_WHITE, BG_DARK_BLUE, "", "#111", "#00a"),
        ("GEdit.selectable", FG_BLACK, BG_LIGHT_GRAY, "", "", ""),
        ("GEdit.focus", FG_DARK_GRAY, BG_LIGHT_GRAY, "", "", ""),
        ("PB.normal", FG_BLACK, BG_LIGHT_GRAY, "", "", ""),
        ("PB.complete", FG_WHITE, BG_BLACK, "", "", ""),
        ("PB.satt", FG_DARK_GRAY, BG_LIGHT_GRAY, "", "", ""),
    ],
    "dark": [
        ("body", FG_BLACK, BG_DARK_CYAN, "standout", "#111", "#0aa"),
        ("reverse", FG_DARK_CYAN, BG_BLACK, "", "#0aa", "#111"),
        ("header", FG_WHITE, BG_DARK_BLUE, "bold", "#fff", "#49b"),
        ("footer", FG_WHITE, BG_DARK_BLUE, "bold", "#fff", "#49b"),
        (
            "important",
            FG_WHITE,
            "dark red",
            ("bold", "standout", "underline"),
            "#fff",
            "#800",
        ),
        ("buttonbar", FG_BLACK, BG_DARK_CYAN, "", "#111", "#0aa"),
        ("buttn", FG_BLACK, BG_DARK_CYAN, "", "#111", "#0aa"),
        (
            "buttnf",
            FG_DARK_CYAN,
            BG_BLACK,
            ("bold", "standout", "underline"),
            "#0aa",
            "#111",
        ),
        ("disabled", FG_DARK_GRAY, BG_LIGHT_GRAY, "", "#111", "#fff"),
        ("selectable", FG_BLACK, BG_LIGHT_GRAY, "", "#111", "#fff"),
        ("focus", FG_WHITE, BG_BLACK, "", "#fff", "#888"),
        (
            "divider",
            FG_WHITE,
            BG_BLACK,
            ("bold", "standout"),
            "#fff",
            "#888",
        ),
        ("MMI.selectable", FG_BLACK, BG_LIGHT_GRAY, "", "#111", "#fff"),
        ("MMI.focus", FG_WHITE, BG_BLACK, "", "#fff", "#888"),
        ("footerbar.short", FG_BLACK, BG_LIGHT_GRAY, "", "#111", "#fff"),
        ("footerbar.long", FG_BLACK, BG_DARK_CYAN, "", "#fff", "#111"),
        ("GEdit.selectable", FG_LIGHT_GRAY, BG_BLACK, "", "", ""),
        ("GEdit.focus", FG_WHITE, BG_BLACK, "", "", ""),
        ("PB.normal", FG_WHITE, BG_BLACK, "", "", ""),
        ("PB.complete", FG_BLACK, BG_LIGHT_GRAY, "", "", ""),
        ("PB.satt", FG_LIGHT_GRAY, BG_BLACK, "", "", ""),
    ],
    "orange light": [
        ("body", FG_WHITE, BG_BROWN, "standout", "#fff", "#880"),
        ("reverse", FG_BROWN, BG_LIGHT_GRAY, "", "#880", "#fff"),
        ("header", FG_WHITE, BG_DARK_BLUE, "bold", "#fff", "#49b"),
        ("footer", FG_WHITE, BG_DARK_BLUE, "bold", "#fff", "#49b"),
        (
            "important",
            FG_DARK_RED,
            BG_LIGHT_GRAY,
            ("bold", "standout", "underline"),
            "#800",
            "#fff",
        ),
        ("buttonbar", FG_WHITE, BG_BROWN, "", "#fff", "#880"),
        ("buttn", FG_WHITE, BG_BROWN, "", "#fff", "#880"),
        (
            "buttnf",
            FG_BROWN,
            BG_LIGHT_GRAY,
            ("bold", "standout", "underline"),
            "#880",
            "#fff",
        ),
        ("disabled", FG_DARK_GRAY, BG_BLACK, "", "#fff", "#111"),
        ("selectable", FG_WHITE, BG_BLACK, "", "#fff", "#111"),
        ("focus", FG_BLACK, BG_LIGHT_GRAY, "", "#111", "#ccc"),
        (
            "divider",
            FG_WHITE,
            BG_LIGHT_GRAY,
            ("bold", "standout"),
            "#fff",
            "#ccc",
        ),
        ("MMI.selectable", FG_WHITE, BG_BLACK, "", "#fff", "#111"),
        ("MMI.focus", FG_BLACK, BG_LIGHT_GRAY, "", "#111", "#ccc"),
        ("footerbar.short", FG_WHITE, BG_BLACK, "", "#fff", "#111"),
        ("footerbar.long", FG_WHITE, BG_BROWN, "", "#111", "#ccc"),
        ("GEdit.selectable", FG_BLACK, BG_LIGHT_GRAY, "", "", ""),
        ("GEdit.focus", FG_BLACK, BG_LIGHT_GRAY, "", "", ""),
        ("PB.normal", FG_BLACK, BG_LIGHT_GRAY, "", "", ""),
        ("PB.complete", FG_WHITE, BG_BLACK, "", "", ""),
        ("PB.satt", FG_DARK_GRAY, BG_LIGHT_GRAY, "", "", ""),
    ],
    "orange dark": [
        ("body", FG_BLACK, BG_BROWN, "standout", "#111", "#ff0"),
        ("reverse", FG_YELLOW, BG_BLACK, "", "#ff0", "#111"),
        ("header", FG_WHITE, BG_DARK_BLUE, "bold", "#fff", "#49a"),
        ("footer", FG_WHITE, BG_DARK_BLUE, "bold", "#fff", "#49a"),
        (
            "important",
            FG_LIGHT_RED,
            BG_BLACK,
            ("bold", "standout", "underline"),
            "#f00",
            "#111",
        ),
        ("buttonbar", FG_BLACK, BG_BROWN, "", "#111", "#ff0"),
        ("buttn", FG_BLACK, BG_BROWN, "", "#111", "#ff0"),
        (
            "buttnf",
            FG_YELLOW,
            BG_BLACK,
            ("bold", "standout", "underline"),
            "#ff0",
            "#111",
        ),
        ("disabled", FG_DARK_GRAY, BG_LIGHT_GRAY, "", "#111", "#fff"),
        ("selectable", FG_BLACK, BG_LIGHT_GRAY, "", "#111", "#fff"),
        ("focus", FG_WHITE, BG_BLACK, "", "#fff", "#888"),
        (
            "divider",
            FG_WHITE,
            BG_BLACK,
            ("bold", "standout"),
            "#fff",
            "#888",
        ),
        ("MMI.selectable", FG_BLACK, BG_LIGHT_GRAY, "", "#111", "#fff"),
        ("MMI.focus", FG_WHITE, BG_BLACK, "", "#fff", "#888"),
        ("footerbar.short", FG_BLACK, BG_LIGHT_GRAY, "", "#111", "#fff"),
        ("footerbar.long", FG_BLACK, BG_BROWN, "", "#fff", "#888"),
        ("GEdit.selectable", FG_LIGHT_GRAY, BG_BLACK, "", "", ""),
        ("GEdit.focus", FG_WHITE, BG_BLACK, "", "", ""),
        ("PB.normal", FG_WHITE, BG_BLACK, "", "", ""),
        ("PB.complete", FG_BLACK, BG_LIGHT_GRAY, "", "", ""),
        ("PB.satt", FG_LIGHT_GRAY, BG_BLACK, "", "", ""),
    ],
}


def extract_bits(binary):
    """Return extracted bits"""
    char = ""
    i = 0
    ret_val = []
    while char != "b":
        string = str(bin(binary))[::-1]
        char = string[i]
        if char == "1":
            ret_val.append(2**i)
        i += 1
    return ret_val


def check_socket(host="127.0.0.1", port=22):
    """Check if socket is open"""
    try:
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error:
        return False


def tlen(tuple_list, idx=0):
    """Return length of all idx'th element in a tuple over all tuple lists.
    The tuples can be nested in list in list in list ...
    tlen([(1, 'bla'), (2, 'blubb')], 1)
    will return 8. It doesn't matter how many nested Lists there are.
    [(1, a), ..., (23, b)] will return the same as [[[(1, a), ...]], (23, b)]
    """
    ret_val = 0
    if not tuple_list:
        return 0
    if isinstance(tuple_list, list):
        for elem in tuple_list:
            ret_val += tlen(elem, idx)
    elif isinstance(tuple_list, tuple):
        ret_val += len(tuple_list[idx])
    elif isinstance(tuple_list, str):
        ret_val += len(tuple_list)
    else:
        ret_val += 0
    return ret_val


def rebase_list(deep_list):
    """Extract all list components recursively"""
    ret_val = []
    if isinstance(deep_list, list):
        for elem in deep_list:
            ret_val += rebase_list(elem)
    else:
        ret_val += [deep_list]
    return ret_val


def make_list_gtext(list_wowo_gtext):
    """Convert all list components to GText if not already done"""
    wowolist = list_wowo_gtext
    ret_val = []
    for wowo in wowolist:
        if not isinstance(wowo, cui.classes.gwidgets.GText):
            ret_val += [cui.classes.gwidgets.GText(wowo)]
        else:
            ret_val += [wowo]
    return ret_val


def check_if_password_is_set(user):
    """Check if user exists in /etc/shadow and has his password set."""
    file = "/etc/shadow"
    items = {}
    try:
        if os.access(file, os.R_OK):
            with open(file, encoding="utf-8") as file_handle:
                for line in file_handle:
                    parts = line.split(":")
                    username = parts[0]
                    password = parts[1]
                    items[username.strip()] = password.strip()
            if len(items.get(user)) > 0:
                return True
    except OSError:
        pass
    return False


def authenticate_user(username: str, password: str, service: str = "login") -> bool:
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
    """Return os release"""
    osr: Path = Path("/etc/os-release")
    name: str = _("No name found")
    version: str = _("No version detectable")
    try:
        with osr.open("r", encoding="utf-8") as file_handle:
            for line in file_handle:
                if line.startswith("NAME"):
                    name = line.strip().split("=")[1]
                elif line.startswith("VERSION"):
                    version = line.strip().split("=")[1]
    except OSError:
        pass
    return name.strip('"'), version.strip('"')


def get_first_ip_not_localhost() -> str:
    """Return first IP that is not localhost"""
    for ip_addr in get_ip_list():
        if not ip_addr.strip().startswith("127."):
            return ip_addr.strip()
    return ""


def get_ip_list() -> List[str]:
    """Return list of IPs on this computer"""
    ret_val: List[str] = []
    addrs = psutil.net_if_addrs()
    for _, addrlist in addrs.items():
        for addr in addrlist:
            if addr.family == socket.AF_INET:
                ret_val.append(addr.address)
    return ret_val


def get_last_login_time():
	"""Return last login time as string"""
	last_login = ["Unknown"]
	bld = cffi.FFI()

	@bld.callback("int(void *, int, char **, char **)")
	def cb(llptr, argc, argv, _2):
		if argc < 3:
			return 0
		if bld.string(argv[2]).decode() != "root":
			return 0
		ts = int(int(bld.string(argv[3]).decode()) / 1000000)
		bld.from_handle(llptr)[0] = datetime.fromtimestamp(ts).strftime("%FT%T")
		return 1

	try:
		bld.cdef("extern int wtmpdb_read_all_v2(const char *, int (*)(void *, int, char **, char **), void *, char **);")
		wtmpdb = bld.dlopen("libwtmpdb.so.0")
		wtmpdb.wtmpdb_read_all_v2(cffi.FFI.NULL, cb, bld.new_handle(last_login), cffi.FFI.NULL)
		return last_login[0]
	finally:
		pass

	last_login = "Unknown"
	try:
		with subprocess.Popen(
			["last", "-1", "--time-format", "iso", "--nohostname", "root"],
			stderr=subprocess.DEVNULL,
			stdout=subprocess.PIPE,
		) as proc:
			res, _ = proc.communicate()
			out = bytes(res).decode()
			lines = out.splitlines()
		if len(lines) > 0:
			parts = re.split('\s+',out.splitlines()[0])
			if len(parts) > 1:
				last_login = parts[2].strip()
	except OSError:
		last_login = "Unknown"
	return last_login


def get_load():
    """Return current average load"""
    try:
        with open("/proc/loadavg", "r", encoding="utf-8") as file_handle:
            out = file_handle.read()
        lines = out.splitlines()
    except OSError:
        lines = []
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
    """Return list of average load"""
    load_avg = get_load()
    load_format = [("footer", _(" Average load: "))]
    for i, time_unit in enumerate([1, 5, 15]):
        load_format.append(("footer", f"{time_unit} min:"))
        load_format.append(("footer", f" {load_avg[i]:0.2f}"))
        load_format.append(("footer", " | "))
    return load_format[:-1]


def get_system_info_top():
    """Return top sysinfo"""
    ret_val: List[Union[str, Tuple[str, str]]] = []
    uname = platform.uname()
    cpufreq = psutil.cpu_freq()
    svmem = psutil.virtual_memory()
    distro, version = get_os_release()
    ret_val += [
        "Console User Interface",
        "\n",
        "© 2020-2025 ",
        "grommunio GmbH",
        "\n",
    ]
    if distro.lower().startswith("grammm") or distro.lower().startswith(
            "grommunio"
    ):
        ret_val.append(f"Distribution: {distro} Version: {version}")
        ret_val.append("\n")
    ret_val.append("\n")
    if cpufreq:
        ret_val.append(
            f"{psutil.cpu_count()} x {uname.processor} CPUs"
            f" @ {get_hr(cpufreq.current * 1000 * 1000, 'Hz', 1000)}"
        )
    else:
        ret_val.append(
            f"{psutil.cpu_count(logical=False)} x {uname.processor} CPUs"
        )
    ret_val.append("\n")
    ret_val.append(
        _("Memory {used} used of {total} ({available} free)").format(
            used=get_hr(svmem.used),
            total=get_hr(svmem.total),
            available=get_hr(svmem.available)
        )
    )
    ret_val.append("\n")
    ret_val.append("\n")
    return ret_val


def get_system_info_bottom():
    from cui.classes.application import setup_state
    """Return bottom sysinfo"""
    ret_val: List[Union[str, Tuple[str, str]]] = []
    uname = platform.uname()
    if_addrs = psutil.net_if_addrs()
    boot_time_timestamp = psutil.boot_time()
    boot_time = datetime.fromtimestamp(boot_time_timestamp)
    proto = "https"
    if setup_state.check_setup_state() == 0:
        ret_val += [
            "\n",
            _("For further configuration, these URLs can be used:"),
            "\n",
        ]
        ret_val.append("\n")
        if uname.node.lower().startswith("localhost."):
            ret_val.append(
                (
                    "important",
                    _("It is generally NOT recommended to use localhost as hostname."),
                )
            )
            ret_val.append("\n")
        ret_val.append(f"{proto}://{uname.node}:8443/\n")
        for interface_name, interface_addresses in if_addrs.items():
            if interface_name in ["lo"]:
                continue
            for address in interface_addresses:
                if address.family != socket.AF_INET6:
                    continue
                adr = ipaddress.IPv6Address(address.address.split("%")[0])
                if adr.is_link_local is True:
                    continue
                ret_val.append(
                    f"{proto}://[{address.address}]:8443/ (interface {interface_name})\n"
                )
            for address in interface_addresses:
                if address.family != socket.AF_INET:
                    continue
                ret_val.append(
                    f"{proto}://{address.address}:8443/ (interface {interface_name})\n"
                )
    else:
        ret_val.append("\n")
        ret_val.append(
            _("There are still some tasks missing to run/use grommunio.")
        )
        ret_val.append("\n")
        statelist = extract_bits(setup_state.check_setup_state())
        for state in statelist:
            ret_val.append("\n")
            ret_val.append(("important", STATES.get(state)))
        ret_val.append("\n")
    ret_val.append("\n")
    ret_val.append(_("Boot Time: "))
    ret_val.append(("reverse", f"{boot_time.isoformat()}"))
    ret_val.append("\n")
    last_login = get_last_login_time()
    if last_login != "":
        ret_val.append(_("Last login time: {%s}") % last_login)
    ret_val.append("\n")
    ret_val.append("\n")
    ret_val.append(_(f"Current language / PPID: {locale.getlocale()[0]} / {os.getppid()}"))
    ret_val.append("\n")
    return ret_val


def get_system_info(which: str) -> List[Union[str, Tuple[str, str]]]:
    """
    Creates list of information formatted in urwid style.

    :param which: Kind of information to return. (top or bottom)
    :return: List of tuples or strings describing urwid attributes and content.
    """
    ret_val: List[Union[str, Tuple[str, str]]] = []
    if which == "top":
        ret_val = get_system_info_top()
    elif which == "bottom":
        ret_val = get_system_info_bottom()
    else:
        ret_val.append(_("Oops!"))
        ret_val.append(_("There should be nothing."))
    return ret_val


def pad(
    text: Any, sign: str = " ", length: int = 2, left_pad: bool = True
) -> str:
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
    ret_val: str
    slice_pos: int
    if left_pad:
        ret_val = f"{suffix}{text}"
        slice_pos = length
    else:
        ret_val = f"{text}{suffix}"
        slice_pos = length * -1
    return ret_val[:slice_pos]


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
    return f"{formatbytes:.2f} {suffix}"


def get_clockstring() -> str:
    """
    Returns the current date and clock formatted correctly.

    :return: The formatted clockstring.
    """
    current_time: datetime = datetime.now()
    year: str = pad(current_time.year, "0", 4)
    month: str = pad(current_time.month, "0", 2)
    day: str = pad(current_time.day, "0", 2)
    hour: str = pad(current_time.hour, "0", 2)
    minute: str = pad(current_time.minute, "0", 2)
    second: str = pad(current_time.second, "0", 2)
    return f"{year}-{month}-{day} {hour}:{minute}:{second}"


def get_footerbar(key_size=2, name_size=10):
    """Return footerbar description"""
    ret_val = []
    menu = {"F1": _("Color"), "F2": _("Login"), "F5": _("Keyboard")}
    if os.getppid() != 1:
        menu["F10"] = _("Exit")
    menu["L"] = _("Logs")
    spacebar = "".join(" " for i in range(name_size))
    for item in menu.items():
        ret_val.append([
            ("footerbar.short", f"  {item[0]}"[-key_size:]),
            ("footerbar.long", f" {item[1]}{spacebar}"[:name_size])
        ])
    return ret_val


def get_palette_list() -> List[str]:
    """Return color palette keys"""
    return list(_PALETTES.keys())


def get_next_palette_name(cur_palette: str = "") -> str:
    """Return next color palette name"""
    palette_list = get_palette_list()
    i = iter(palette_list)
    for palette in i:
        if palette == palette_list[len(palette_list) - 1]:
            return palette_list[0]
        if palette == cur_palette:
            return next(i)
    return palette_list[0]


def get_palette(mode: str = "light") -> List[Tuple[str, ...]]:
    """Return current color palette"""
    ret_val: List[Tuple[str, ...]] = _PALETTES[mode]
    return ret_val


def fast_tail(file: str, line_count: int = 0) -> List[str]:
    """Fast mini tail"""
    assert line_count >= 0, "Line count n must be greater equal 0."
    pos: int = line_count + 1
    lines: List[str] = []
    fname: Path = Path(file)
    with fname.open("r", encoding="utf-8") as file_handle:
        while len(lines) <= line_count:
            try:
                file_handle.seek(-pos, 2)
            except IOError:
                file_handle.seek(0)
                break
            finally:
                lines = list(file_handle)
            pos *= 2
    return [line.strip() for line in lines[-line_count:]]


def lineconfig_read(file):
    """Read file to items dictionary. lineconfig,
    does NOT recognize quotes and backslashes."""
    items = {}
    try:
        with open(file, "r", encoding="utf-8") as file_handle:
            for line in file_handle:
                key, value = line.partition("=")[::2]
                if "=" in line:
                    new_value = value.strip()
                else:
                    new_value = None
                items[key.strip()] = new_value
    except IOError:
        pass
    return items


def lineconfig_write(file, items):
    """Write items to file"""
    with open(file, "w", encoding="utf-8") as file_handle:
        for key in items:
            file_handle.write(key)
            if items[key] is not None:
                file_handle.write("=")
                file_handle.write(items[key])
            file_handle.write("\n")


def minishell_read(file):
    """Read file to items dictionary. minishell is like lineconfig,
    but must recognize quotes and backslashes."""
    items = {}
    try:
        with open(file, "r", encoding="utf-8") as file_handle:
            for line in file_handle:
                if line.strip()[0:1] == "#":
                    continue
                res = shlex.split(line.rstrip('\n'))
                if len(res) < 1:
                    continue
                res = res[0].partition("=")
                if len(res) != 3:
                    continue
                items[res[0]] = res[2]
    except IOError:
        pass
    return items


def minishell_write(file, items):
    """Write items to file"""
    with open(file, "w", encoding="utf-8") as file_handle:
        for key in items:
            file_handle.write(key)
            if items[key] is not None:
                file_handle.write("=")
                file_handle.write(shlex.quote(items[key]))
            file_handle.write("\n")


def get_current_kbdlayout():
    """Return current keyboard layout"""
    items = minishell_read("/etc/vconsole.conf")
    return items.get("KEYMAP", "us").strip('"')


def reset_system_passwd(new_pw: str) -> bool:
    """Reset the system password."""
    if new_pw:
        if new_pw != "":
            with subprocess.Popen(
                ["passwd"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ) as proc:
                proc.stdin.write(f"{new_pw}\n{new_pw}\n".encode())
                proc.stdin.flush()
                i = 0
                while i < 10 and proc.poll() is None:
                    time.sleep(0.1)
                    i += 1
                proc.terminate()
                proc.kill()
                return proc.returncode == 0
    return False


def reset_aapi_passwd(new_pw: str) -> bool:
    """Reset admin-API password."""
    if new_pw:
        if new_pw != "":
            exe = "grammm-admin"
            if Path("/usr/sbin/grommunio-admin").exists():
                exe = "grommunio-admin"
            with subprocess.Popen(
                [exe, "passwd", "--password", new_pw],
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
            ) as proc:
                return proc.wait() == 0
    return False
