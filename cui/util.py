# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH
import os
import subprocess
import sys
import time
from pathlib import Path

import requests
from getpass import getuser
from pamela import authenticate, PAMError
from typing import Any, Dict, List, Tuple, Union, Iterable
from datetime import datetime
import ipaddress
import locale
import platform
import psutil
import socket
import shlex

from requests import Response

import cui
import urwid


def T_(msg):
    """Dummy func"""
    return msg


def reset_states():
    global STATES, T_
    new_states = {}
    for k in STATES.keys():
        new_states[k] = T_(STATES[k])
    STATES = new_states
    return STATES


def get_button_type(key, open_func_on_ok, mb_func, cancel_msgbox_params, size):
    def open_cancel_msg(msg_params, mb_size):
        mb_func(
            msg_params,
            size=mb_size
        )

    val: str = key.lower()
    if val.endswith("enter"):
        val = " ".join(val.split(" ")[:-1])
        open_func_on_ok()
        if val.startswith("hidden"):
            val = " ".join(val.split(" ")[1:])
        else:
            val = T_("Cancel").lower()
        if val == T_("Cancel").lower():
            open_cancel_msg(cancel_msgbox_params, size)
    elif val == 'esc':
        open_func_on_ok()
        open_cancel_msg(cancel_msgbox_params, size)
    return val


def restart_gui():
    """Restart complete GUI to source language in again."""
    ret_val = T_
    langfile = '/etc/sysconfig/language'
    config = cui.parser.ConfigParser(infile=langfile)
    config['ROOT_USES_LANG'] = '"yes"'
    config.write()
    # assert os.getenv('PPID') == 1, 'Gugg mal rein da!'
    locale_conf = minishell_read('/etc/locale.conf')
    # T_ = util.init_localization()
    # mainapp()
    if os.getppid() == 1:
        ret_val = init_localization(language=locale_conf.get('LANG', ''))
        cui.main_app()
        # raise ExitMainLoop()
    else:
        env = {}
        for k in os.environ:
            env[k] = os.environ.get(k)
        for k in locale_conf:
            env[k] = locale_conf.get(k)
        os.execve(sys.executable, [sys.executable] + sys.argv, env)
    return ret_val


def create_application_buttons(app):
    # Login Dialog
    app.login_header = urwid.AttrMap(
        cui.gwidgets.GText(("header", T_("Login")), align="center"), "header"
    )
    app.user_edit = cui.gwidgets.GEdit(
        (T_("Username: "),), edit_text=getuser(), edit_pos=0
    )
    app.pass_edit = cui.gwidgets.GEdit(
        T_("Password: "), edit_text="", edit_pos=0, mask="*"
    )
    app.login_body = urwid.Pile(
        [
            app.user_edit,
            app.pass_edit,
        ]
    )
    login_button = cui.button.GBoxButton(T_("Login"), app._check_login)
    urwid.connect_signal(
        login_button,
        "click",
        lambda button: app.handle_event("login enter"),
    )
    app.login_footer = urwid.AttrMap(
        urwid.Columns([cui.gwidgets.GText(""), login_button, cui.gwidgets.GText("")]), "buttonbar"
    )
    # Common OK Button
    app.ok_button = cui.button.GBoxButton(T_("OK"), app._press_button)
    urwid.connect_signal(
        app.ok_button,
        "click",
        lambda button: app.handle_event("ok enter"),
    )
    app.ok_button = (len(app.ok_button.label) + 6, app.ok_button)
    app.ok_button_footer = urwid.AttrMap(
        urwid.Columns(
            [
                ("weight", 1, cui.gwidgets.GText("")),
                (
                    "weight",
                    1,
                    urwid.Columns(
                        [
                            ("weight", 1, cui.gwidgets.GText("")),
                            app.ok_button,
                            ("weight", 1, cui.gwidgets.GText("")),
                        ]
                    ),
                ),
                ("weight", 1, cui.gwidgets.GText("")),
            ]
        ),
        "buttonbar",
    )
    # Common Cancel Button
    app.cancel_button = cui.button.GBoxButton(T_("Cancel"), app._press_button)
    urwid.connect_signal(
        app.cancel_button,
        "click",
        lambda button: app.handle_event("cancel enter"),
    )
    app.cancel_button = (len(app.cancel_button.label) + 6, app.cancel_button)
    app.cancel_button_footer = urwid.GridFlow(
        [app.cancel_button[1]], 10, 1, 1, "center"
    )
    # Common Close Button
    app.close_button = cui.button.GBoxButton(T_("Close"), app._press_button)
    urwid.connect_signal(
        app.close_button,
        "click",
        lambda button: app.handle_event("close enter"),
    )
    app.close_button = (len(app.close_button.label) + 6, app.close_button)
    app.close_button_footer = urwid.AttrMap(
        urwid.Columns(
            [
                ("weight", 1, cui.gwidgets.GText("")),
                (
                    "weight",
                    1,
                    urwid.Columns(
                        [
                            ("weight", 1, cui.gwidgets.GText("")),
                            app.close_button,
                            ("weight", 1, cui.gwidgets.GText("")),
                        ]
                    ),
                ),
                ("weight", 1, cui.gwidgets.GText("")),
            ]
        ),
        "buttonbar",
    )
    # Common Add Button
    app.add_button = cui.button.GBoxButton(T_("Add"), app._press_button)
    urwid.connect_signal(
        app.add_button,
        "click",
        lambda button: app.handle_event("add enter"),
    )
    app.add_button = (len(app.add_button.label) + 6, app.add_button)
    app.add_button_footer = urwid.GridFlow(
        [app.add_button[1]], 10, 1, 1, "center"
    )
    # Common Edit Button
    app.edit_button = cui.button.GBoxButton(T_("Edit"), app._press_button)
    urwid.connect_signal(
        app.edit_button,
        "click",
        lambda button: app.handle_event("edit enter"),
    )
    app.edit_button = (len(app.edit_button.label) + 6, app.edit_button)
    app.edit_button_footer = urwid.GridFlow(
        [app.edit_button[1]], 10, 1, 1, "center"
    )
    # Common Details Button
    app.details_button = cui.button.GBoxButton(T_("Details"), app._press_button)
    urwid.connect_signal(
        app.details_button,
        "click",
        lambda button: app.handle_event("details enter"),
    )
    app.details_button = (len(app.details_button.label) + 6, app.details_button)
    app.details_button_footer = urwid.GridFlow(
        [app.details_button[1]], 10, 1, 1, "center"
    )
    # Common Toggle Button
    app.toggle_button = cui.button.GBoxButton(T_("Space to toggle"), app._press_button)
    app.toggle_button._selectable = False
    app.toggle_button = (len(app.toggle_button.label) + 6, app.toggle_button)
    app.toggle_button_footer = urwid.GridFlow(
        [app.toggle_button[1]], 10, 1, 1, "center"
    )
    # Common Apply Button
    app.apply_button = cui.button.GBoxButton(T_("Apply"), app._press_button)
    urwid.connect_signal(
        app.apply_button,
        "click",
        lambda button: app.handle_event("apply enter"),
    )
    app.apply_button = (len(app.apply_button.label) + 6, app.apply_button)
    app.apply_button_footer = urwid.GridFlow(
        [app.apply_button[1]], 10, 1, 1, "center"
    )
    # Common Save Button
    app.save_button = cui.button.GBoxButton(T_("Save"), app._press_button)
    urwid.connect_signal(
        app.save_button,
        "click",
        lambda button: app.handle_event("save enter"),
    )
    app.save_button = (len(app.save_button.label) + 6, app.save_button)
    app.save_button_footer = urwid.GridFlow(
        [app.save_button[1]], 10, 1, 1, "center"
    )


def create_main_loop(app):
    urwid.set_encoding("utf-8")
    app.gscreen = cui.appclass.GScreen()
    app.gscreen.screen = urwid.raw_display.Screen()
    app.gscreen.old_termios = app.gscreen.screen.tty_signal_keys()
    app.gscreen.blank_termios = ["undefined" for _ in range(0, 5)]
    app.gscreen.screen.tty_signal_keys(*app.gscreen.blank_termios)
    app.prepare_mainscreen()
    # Loop
    return urwid.MainLoop(
        app._body,
        get_palette(app.header.get_colormode()),
        unhandled_input=app.handle_event,
        screen=app.gscreen.screen,
        handle_mouse=False,
    )


def check_repo_dialog(app, height):
    updateable = False
    url = 'download.grommunio.com/community/openSUSE_Leap_15.3/' \
          '?ssl_verify=no'
    if app.repo_selection_body.base_widget[3].state:
        # supported selected
        user = app.repo_selection_body.base_widget[4][1].edit_text
        password = app.repo_selection_body.base_widget[5][1].edit_text
        testurl = "https://download.grommunio.com/supported/open" \
                  "SUSE_Leap_15.3/repodata/repomd.xml"
        req: Response = requests.get(testurl, auth=(user, password))
        if req.status_code == 200:
            url = f'{user}:{password}@download.grommunio.com/supported/open' \
                  'SUSE_Leap_15.3/?ssl_verify=no'
            updateable = True
        else:
            app.message_box(
                cui.parameter.MsgBoxParams(
                    T_('Please check the credentials for "supported"'
                       '-version or use "community"-version.'),
                ),
                size=cui.parameter.Size(height=height + 1)
            )
    else:
        # community selected
        updateable = True
    return updateable, url


def init_localization(language: Union[str, str, Iterable[Union[str, str]], None] = ''):
    locale.setlocale(locale.LC_ALL, language)
    try:
        locale.bindtextdomain('cui', 'locale' if os.path.exists("locale/de/LC_MESSAGES/cui.mo") else None)
        locale.textdomain('cui')
        T_ = locale.gettext
        reset_states()
        return T_
    except OSError as e:
        def T_(msg):
            """
            Function for tagging text for translations.
            """
            return msg
        reset_states()
        return T_


STATES = {
    1: T_("System password is not set."),
    2: T_("Network configuration is missing."),
    4: T_("grommunio-setup has not been run yet."),
    8: T_("timesyncd configuration is missing."),
    16: T_("nginx is not running."),
}

T_ = init_localization()

_PALETTES: Dict[str, List[Tuple[str, ...]]] = {
    "light": [
        ("body", "white", "dark blue", "standout", "#fff", "#00a"),
        ("reverse", "dark blue", "light gray", "", "#00a", "#aaa"),
        ("header", "white", "light blue", "bold", "#fff", "#49a"),
        ("footer", "white", "light blue", "bold", "#fff", "#3cf"),
        (
            "important",
            "dark red",
            "light gray",
            ("bold", "standout", "underline"),
            "#800",
            "#aaa",
        ),
        ("buttonbar", "white", "dark blue", "", "#fff", "#00a"),
        ("buttn", "white", "dark blue", "", "#fff", "#00a"),
        (
            "buttnf",
            "dark blue",
            "light gray",
            ("bold", "standout", "underline"),
            "#00a",
            "#aaa",
        ),
        ("selectable", "white", "black", "", "#fff", "#111"),
        ("focus", "black", "light gray", "", "#111", "#ccc"),
        (
            "divider",
            "black",
            "light gray",
            ("bold", "standout"),
            "#111",
            "#ccc",
        ),
        ("MMI.selectable", "white", "black", "", "#fff", "#111"),
        ("MMI.focus", "black", "light gray", "", "#111", "#ccc"),
        ("footerbar.short", "white", "black", "", "#fff", "#111"),
        ("footerbar.long", "white", "dark blue", "", "#111", "#00a"),
        ("GEdit.selectable", "black", "light gray", "", "", ""),
        ("GEdit.focus", "black", "white", "", "", ""),
        ("PB.normal", "black", "white", "", "", ""),
        ("PB.complete", "white", "black", "", "", ""),
        ("PB.satt", "dark gray", "light gray", "", "", ""),
    ],
    "dark": [
        ("body", "black", "dark cyan", "standout", "#111", "#0aa"),
        ("reverse", "dark cyan", "black", "", "#0aa", "#111"),
        ("header", "white", "dark blue", "bold", "#fff", "#49b"),
        ("footer", "white", "dark blue", "bold", "#fff", "#49b"),
        (
            "important",
            "white",
            "dark red",
            ("bold", "standout", "underline"),
            "#fff",
            "#800",
        ),
        ("buttonbar", "black", "dark cyan", "", "#111", "#0aa"),
        ("buttn", "black", "dark cyan", "", "#111", "#0aa"),
        (
            "buttnf",
            "dark cyan",
            "black",
            ("bold", "standout", "underline"),
            "#0aa",
            "#111",
        ),
        ("selectable", "black", "white", "", "#111", "#fff"),
        ("focus", "white", "dark gray", "", "#fff", "#888"),
        (
            "divider",
            "white",
            "dark gray",
            ("bold", "standout"),
            "#fff",
            "#888",
        ),
        ("MMI.selectable", "black", "white", "", "#111", "#fff"),
        ("MMI.focus", "white", "dark gray", "", "#fff", "#888"),
        ("footerbar.short", "black", "white", "", "#111", "#fff"),
        ("footerbar.long", "black", "dark cyan", "", "#fff", "#111"),
        ("GEdit.selectable", "light gray", "black", "", "", ""),
        ("GEdit.focus", "light gray", "dark gray", "", "", ""),
        ("PB.normal", "white", "black", "", "", ""),
        ("PB.complete", "black", "white", "", "", ""),
        ("PB.satt", "light gray", "dark gray", "", "", ""),
    ],
    "orange light": [
        ("body", "white", "brown", "standout", "#fff", "#880"),
        ("reverse", "brown", "white", "", "#880", "#fff"),
        ("header", "white", "dark blue", "bold", "#fff", "#49b"),
        ("footer", "white", "dark blue", "bold", "#fff", "#49b"),
        (
            "important",
            "dark red",
            "white",
            ("bold", "standout", "underline"),
            "#800",
            "#fff",
        ),
        ("buttonbar", "white", "brown", "", "#fff", "#880"),
        ("buttn", "white", "brown", "", "#fff", "#880"),
        (
            "buttnf",
            "brown",
            "white",
            ("bold", "standout", "underline"),
            "#880",
            "#fff",
        ),
        ("selectable", "white", "black", "", "#fff", "#111"),
        ("focus", "black", "light gray", "", "#111", "#ccc"),
        (
            "divider",
            "white",
            "light gray",
            ("bold", "standout"),
            "#fff",
            "#ccc",
        ),
        ("MMI.selectable", "white", "black", "", "#fff", "#111"),
        ("MMI.focus", "black", "light gray", "", "#111", "#ccc"),
        ("footerbar.short", "white", "black", "", "#fff", "#111"),
        ("footerbar.long", "white", "brown", "", "#111", "#ccc"),
        ("GEdit.selectable", "black", "light gray", "", "", ""),
        ("GEdit.focus", "black", "white", "", "", ""),
        ("PB.normal", "black", "white", "", "", ""),
        ("PB.complete", "white", "black", "", "", ""),
        ("PB.satt", "dark gray", "light gray", "", "", ""),
    ],
    "orange dark": [
        ("body", "black", "yellow", "standout", "#111", "#ff0"),
        ("reverse", "yellow", "black", "", "#ff0", "#111"),
        ("header", "white", "light blue", "bold", "#fff", "#49a"),
        ("footer", "white", "light blue", "bold", "#fff", "#49a"),
        (
            "important",
            "light red",
            "black",
            ("bold", "standout", "underline"),
            "#f00",
            "#111",
        ),
        ("buttonbar", "black", "yellow", "", "#111", "#ff0"),
        ("buttn", "black", "yellow", "", "#111", "#ff0"),
        (
            "buttnf",
            "yellow",
            "black",
            ("bold", "standout", "underline"),
            "#ff0",
            "#111",
        ),
        ("selectable", "black", "white", "", "#111", "#fff"),
        ("focus", "white", "dark gray", "", "#fff", "#888"),
        (
            "divider",
            "white",
            "dark gray",
            ("bold", "standout"),
            "#fff",
            "#888",
        ),
        ("MMI.selectable", "black", "white", "", "#111", "#fff"),
        ("MMI.focus", "white", "dark gray", "", "#fff", "#888"),
        ("footerbar.short", "black", "white", "", "#111", "#fff"),
        ("footerbar.long", "black", "yellow", "", "#fff", "#888"),
        ("GEdit.selectable", "light gray", "black", "", "", ""),
        ("GEdit.focus", "light gray", "dark gray", "", "", ""),
        ("PB.normal", "white", "black", "", "", ""),
        ("PB.complete", "black", "white", "", "", ""),
        ("PB.satt", "light gray", "dark gray", "", "", ""),
    ],
}


def extract_bits(binary):
    c = ""
    i = 0
    rv = []
    while c != "b":
        s = str(bin(binary))[::-1]
        c = s[i]
        if c == "1":
            rv.append(2**i)
        i += 1
    return rv


def check_socket(host="127.0.0.1", port=22):
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
    wowolist = list_wowo_gtext
    rv = []
    for wowo in wowolist:
        if not isinstance(wowo, cui.gwidgets.GText):
            rv += [cui.gwidgets.GText(wowo)]
        else:
            rv += [wowo]
    return rv


def check_if_password_is_set(user):
    """Check if user exists in /etc/shadow and has his pw set."""
    file = "/etc/shadow"
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


def check_setup_state():
    """Check states of setup and returns a combined binary number"""

    def check_network_config():
        return check_socket("127.0.0.1", 22)

    def check_grommunio_setup():
        # return os.path.isfile('/etc/grommunio/setup_done')
        return os.path.isfile("/etc/grammm/setup_done") or os.path.isfile(
            "/etc/grommunio-common/setup_done"
        )

    def check_timesyncd_config():
        out = subprocess.check_output(["timedatectl", "status"]).decode()
        items = {}
        for line in out.splitlines():
            key, value = line.partition(":")[::2]
            items[key.strip()] = value.strip()
        if (
            items.get("Network time on") == "yes"
            and items.get("NTP synchronized") == "yes"
        ):
            return True
        return False

    def check_nginx_config():
        return check_socket("127.0.0.1", 8080)

    rv = 0
    # check if pw is set
    if not check_if_password_is_set("root"):
        rv += 1
    # check network config (2)
    if not check_network_config():
        rv += 2
    # check grommunio-setup config (4)
    if not check_grommunio_setup():
        rv += 4
    # check timesyncd config (8)
    if not check_timesyncd_config():
        # give 0 error points cause timesyncd configuration is not necessarily
        # needed.
        rv += 0
    # check nginx config (16)
    if not check_nginx_config():
        rv += 16
    return rv


def authenticate_user(
    username: str, password: str, service: str = "login"
) -> bool:
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
    osr: Path = Path("/etc/os-release")
    name: str = T_("No name found")
    version: str = T_("No version detectable")
    with osr.open("r") as f:
        for line in f:
            if line.startswith("NAME"):
                k, name = line.strip().split("=")
            elif line.startswith("VERSION"):
                k, version = line.strip().split("=")
    return name.strip('"'), version.strip('"')


def get_first_ip_not_localhost() -> str:
    for ip in get_ip_list():
        if not ip.strip().startswith("127."):
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
    p = subprocess.Popen(
        ["last", "-1", "root"],
        stderr=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
    )
    res, _ = p.communicate()
    out = bytes(res).decode()
    lines = out.splitlines()
    last_login = ""
    if len(lines) > 0:
        parts = out.splitlines()[0].split("              ")
        if len(parts) > 1:
            last_login = parts[1].strip()
    return last_login


def get_load():
    with open("/proc/loadavg", "r") as f:
        out = f.read()
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
    load_format = [("footer", T_(" Average load: "))]
    _ = [
        load_format.append(("footer", f"{t} min:"))
        or load_format.append(("footer", f" {load_avg[i]:0.2f}"))
        or load_format.append(("footer", " | "))
        for i, t in enumerate([1, 5, 15])
    ]
    return load_format[:-1]


def get_system_info(which: str) -> List[Union[str, Tuple[str, str]]]:
    """
    Creates list of information formatted in urwid stye.

    :param which: Kind of information to return. (top or bottom)
    :return: List of tuples or strings describing urwid attributes and content.
    """
    rv: List[Union[str, Tuple[str, str]]] = []
    if which == "top":
        uname = platform.uname()
        cpufreq = psutil.cpu_freq()
        svmem = psutil.virtual_memory()
        distro, version = get_os_release()
        rv += [
            "Console User Interface",
            "\n",
            "© 2022 ",
            "grommunio GmbH",
            "\n",
        ]
        if distro.lower().startswith("grammm") or distro.lower().startswith(
            "grommunio"
        ):
            rv.append(f"Distribution: {distro} Version: {version}")
            rv.append("\n")
        rv.append("\n")
        if cpufreq:
            rv.append(
                f"{psutil.cpu_count()} x {uname.processor} CPUs"
                f" @ {get_hr(cpufreq.current * 1000 * 1000, 'Hz', 1000)}"
            )
        else:
            rv.append(
                f"{psutil.cpu_count(logical=False)} x {uname.processor} CPUs"
            )
        rv.append("\n")
        rv.append(
            T_("Memory {used} used of {total} ({available} free)").format(
                used=get_hr(svmem.used),
                total=get_hr(svmem.total),
                available=get_hr(svmem.available)
            )
        )
        rv.append("\n")
        rv.append("\n")
    elif which == "bottom":
        uname = platform.uname()
        if_addrs = psutil.net_if_addrs()
        boot_time_timestamp = psutil.boot_time()
        bt = datetime.fromtimestamp(boot_time_timestamp)
        proto = "http"
        if check_setup_state() == 0:
            rv += [
                "\n",
                T_("For further configuration, these URLs can be used:"),
                "\n",
            ]
            rv.append("\n")
            if uname.node.lower().startswith("localhost."):
                rv.append(
                    (
                        "important",
                        T_("It is generally NOT recommended to use localhost as hostname."),
                    )
                )
                rv.append("\n")
            rv.append(f"{proto}://{uname.node}:8080/\n")
            for interface_name, interface_addresses in if_addrs.items():
                if interface_name in ["lo"]:
                    continue
                for address in interface_addresses:
                    if address.family != socket.AF_INET6:
                        continue
                    adr = ipaddress.IPv6Address(address.address.split("%")[0])
                    if adr.is_link_local is True:
                        continue
                    rv.append(
                        f"{proto}://[{address.address}]:8080/ (interface {interface_name})\n"
                    )
                for address in interface_addresses:
                    if address.family != socket.AF_INET:
                        continue
                    rv.append(
                        f"{proto}://{address.address}:8080/ (interface {interface_name})\n"
                    )
        else:
            rv.append("\n")
            rv.append(
                T_("There are still some tasks missing to run/use grommunio.")
            )
            rv.append("\n")
            statelist = extract_bits(check_setup_state())
            for state in statelist:
                rv.append("\n")
                rv.append(("important", STATES.get(state)))
            rv.append("\n")
        rv.append("\n")
        rv.append(T_("Boot Time: "))
        rv.append(("reverse", f"{bt.isoformat()}"))
        rv.append("\n")
        last_login = get_last_login_time()
        if last_login != "":
            rv.append(T_("Last login time: {%s}") % last_login)
        rv.append("\n")
        rv.append("\n")
        rv.append(T_(f"Current language / PPID: {locale.getlocale()[0]} / {os.getppid()}"))
        rv.append("\n")
    else:
        rv.append(T_("Oops!"))
        rv.append(T_("There should be nothing."))
    return rv


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
    year: str = pad(bt.year, "0", 4)
    month: str = pad(bt.month, "0", 2)
    day: str = pad(bt.day, "0", 2)
    hour: str = pad(bt.hour, "0", 2)
    minute: str = pad(bt.minute, "0", 2)
    second: str = pad(bt.second, "0", 2)
    return f"{year}-{month}-{day} {hour}:{minute}:{second}"


def get_footerbar(key_size=2, name_size=10):
    """Return footerbar description"""
    rv = []
    menu = {"F1": T_("Color"), "F2": T_("Login"), "F5": T_("Keyboard")}
    if os.getppid() != 1:
        menu["F10"] = T_("Exit")
    menu["L"] = T_("Logs")
    spacebar = "".join(" " for _ in range(name_size))
    for item in menu.items():
        nr = ("footerbar.short", f"  {item[0]}"[-key_size:])
        name = ("footerbar.long", f" {item[1]}{spacebar}"[:name_size])
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


def get_palette(mode: str = "light") -> List[Tuple[str, ...]]:
    global _PALETTES
    rv: List[Tuple[str, ...]] = _PALETTES[mode]
    return rv


def fast_tail(file: str, n: int = 0) -> List[str]:
    assert n >= 0, "Line count n must be greater equal 0."
    pos: int = n + 1
    lines: List[str] = []
    fname: Path = Path(file)
    with fname.open("r") as f:
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


def lineconfig_read(file):
    items = {}
    try:
        with open(file) as fh:
            for line in fh:
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
    with open(file, "w") as fh:
        for key in items:
            fh.write(key)
            if items[key] is not None:
                fh.write("=")
                fh.write(items[key])
            fh.write("\n")


'''
minishell is like lineconfig, but must recognize quotes and backslashes.
'''
def minishell_read(file):
    items = {}
    try:
        with open(file) as fh:
            for line in fh:
                if line.strip()[0:1] == "#":
                    continue
                r = shlex.split(line.rstrip('\n'))
                if len(r) < 1:
                    continue
                r = r[0].partition("=")
                if len(r) != 3:
                    continue
                items[r[0]] = r[2]
    except IOError:
        pass
    return items


def minishell_write(file, items):
    with open(file, "w") as fh:
        for key in items:
            fh.write(key)
            if items[key] is not None:
                fh.write("=")
                fh.write(shlex.quote(items[key]))
            fh.write("\n")


def get_current_kbdlayout():
    items = minishell_read("/etc/vconsole.conf")
    return items.get("KEYMAP", "us").strip('"')


def reset_system_passwd(new_pw: str) -> bool:
    """Reset the system password."""
    if new_pw:
        if new_pw != "":
            proc = subprocess.Popen(
                ["passwd"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
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
            proc = subprocess.Popen(
                [exe, "passwd", "--password", new_pw],
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
            )

            return proc.wait() == 0
    return False

