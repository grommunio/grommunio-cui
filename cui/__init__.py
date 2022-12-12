#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH
"""The main module of grommunio-cui."""
import datetime
import time
import re
import subprocess
import sys
from asyncio.events import AbstractEventLoop
from pathlib import Path
from typing import Any, List, Tuple, Dict, Union, Set
import os
from getpass import getuser
import requests
from requests import Response

from gwidgets import GText, GEdit

import yaml
# from pudb.remote import set_trace
from yaml import SafeLoader
from systemd import journal
from urwid.widget import SPACE
import urwid
from urwid import (
    AttrWrap,
    ExitMainLoop,
    Padding,
    Columns,
    ListBox,
    Frame,
    LineBox,
    SimpleListWalker,
    MainLoop,
    LEFT,
    CENTER,
    Filler,
    Pile,
    connect_signal,
    AttrMap,
    GridFlow,
    Overlay,
    Widget,
    Terminal,
    SimpleFocusListWalker,
    set_encoding,
    MIDDLE,
    TOP,
    RadioButton,
    raw_display,
    RELATIVE_100,
)
from cui import util, parameter
import cui.parser
from cui.scroll import ScrollBar, Scrollable
from cui.button import GButton, GBoxButton
from cui.menu import MenuItem, MultiMenuItem
from cui.interface import ApplicationHandler, WidgetDrawer


try:
    import asyncio
except ImportError:
    import trollius as asyncio

PRODUCTION: bool = True
loop: AbstractEventLoop
_MAIN: str = "MAIN"
_MAIN_MENU: str = "MAIN-MENU"
_TERMINAL: str = "TERMINAL"
_LOGIN: str = "LOGIN"
_REBOOT: str = "REBOOT"
_SHUTDOWN: str = "SHUTDOWN"
_NETWORK_CONFIG_MENU: str = "NETWORK-CONFIG-MENU"
_UNSUPPORTED: str = "UNSUPPORTED"
_PASSWORD: str = "PASSWORD"
_DEVICE_CONFIG: str = "DEVICE-CONFIG"
_IP_CONFIG: str = "IP-CONFIG"
_IP_ADDRESS_CONFIG: str = "IP-ADDRESS-CONFIG"
_DNS_CONFIG: str = "DNS-CONFIG"
_MESSAGE_BOX: str = "MESSAGE-BOX"
_INPUT_BOX: str = "INPUT-BOX"
_LOG_VIEWER: str = "LOG-VIEWER"
_ADMIN_WEB_PW: str = "ADMIN-WEB-PW"
_TIMESYNCD: str = "TIMESYNCD"
_KEYBOARD_SWITCH: str = "KEYBOARD_SWITCH"
_REPO_SELECTION: str = "REPOSITORY-SELECTION"


T_ = util.init_localization()


class Application(ApplicationHandler):
    """
    The console UI. Main application class.
    """

    current_window: str = _MAIN
    last_current_window: str = ""
    current_window_input_box: str = ""
    message_box_caller: str = ""
    _message_box_caller_body: Widget = None
    last_pressed_button: str = ""
    input_box_caller: str = ""
    _input_box_caller_body: Widget = None
    last_input_box_value: str = ""
    log_file_caller: str = ""
    _log_file_caller_body: Widget = None
    current_event = ""
    current_bottom_info = T_("Idle")
    menu_items: List[str] = []
    layout: Frame = None
    old_layout: Frame = None
    debug: bool = False
    quiet: bool = False
    current_menu_state: int = -1
    maybe_menu_state: int = -1
    active_device: str = "lo"
    active_ips: Dict[str, List[Tuple[str, str, str, str]]] = {}
    config: Dict[str, Any] = {}
    timesyncd_vars: Dict[str, str] = {}
    log_units: Dict[str, Dict[str, str]] = {}
    current_log_unit: int = 0
    log_line_count: int = 200
    log_finished: bool = False
    footer_content = []
    key_counter: Dict[str, int] = {}
    progressbar: urwid.ProgressBar

    _current_kbdlayout = util.get_current_kbdlayout()

    # The default color palette
    _current_colormode: str = "light"

    # The hidden input string
    _hidden_input: str = ""
    _hidden_pos: int = 0
    _body: Widget
    tb_header: GText
    authorized_options: str
    footer: Pile
    header: AttrMap
    log_viewer: LineBox
    repo_selection_body: LineBox
    loaded_kbd: str
    keyboard_rb: List
    keyboard_content: List
    keyboard_list: ScrollBar
    keyboard_switch_body: ScrollBar

    def __init__(self):
        # MAIN Page
        set_encoding("utf-8")
        self.screen = raw_display.Screen()
        self.old_termios = self.screen.tty_signal_keys()
        self.blank_termios = ["undefined" for _ in range(0, 5)]
        self.screen.tty_signal_keys(*self.blank_termios)
        self._prepare_mainscreen()

        # Loop
        self._loop = MainLoop(
            self._body,
            util.get_palette(self._current_colormode),
            unhandled_input=self.handle_event,
            screen=self.screen,
            handle_mouse=False,
        )
        self._loop.set_alarm_in(1, self._update_clock)

        # Login Dialog
        self.login_header = AttrMap(
            GText(("header", T_("Login")), align="center"), "header"
        )
        self.user_edit = GEdit(
            (T_("Username: "),), edit_text=getuser(), edit_pos=0
        )
        self.pass_edit = GEdit(
            T_("Password: "), edit_text="", edit_pos=0, mask="*"
        )
        self.login_body = Pile(
            [
                self.user_edit,
                self.pass_edit,
            ]
        )
        login_button = GBoxButton(T_("Login"), self._check_login)
        connect_signal(
            login_button,
            "click",
            lambda button: self.handle_event("login enter"),
        )
        self.login_footer = AttrMap(
            Columns([GText(""), login_button, GText("")]), "buttonbar"
        )

        # Common OK Button
        self.ok_button = GBoxButton(T_("OK"), self._press_button)
        connect_signal(
            self.ok_button,
            "click",
            lambda button: self.handle_event("ok enter"),
        )
        self.ok_button = (len(self.ok_button.label) + 6, self.ok_button)
        self.ok_button_footer = AttrMap(
            Columns(
                [
                    ("weight", 1, GText("")),
                    (
                        "weight",
                        1,
                        Columns(
                            [
                                ("weight", 1, GText("")),
                                self.ok_button,
                                ("weight", 1, GText("")),
                            ]
                        ),
                    ),
                    ("weight", 1, GText("")),
                ]
            ),
            "buttonbar",
        )

        # Common Cancel Button
        self.cancel_button = GBoxButton(T_("Cancel"), self._press_button)
        connect_signal(
            self.cancel_button,
            "click",
            lambda button: self.handle_event("cancel enter"),
        )
        self.cancel_button = (len(self.cancel_button.label) + 6, self.cancel_button)
        self.cancel_button_footer = GridFlow(
            [self.cancel_button[1]], 10, 1, 1, "center"
        )

        # Common Close Button
        self.close_button = GBoxButton(T_("Close"), self._press_button)
        connect_signal(
            self.close_button,
            "click",
            lambda button: self.handle_event("close enter"),
        )
        self.close_button = (len(self.close_button.label) + 6, self.close_button)
        self.close_button_footer = AttrMap(
            Columns(
                [
                    ("weight", 1, GText("")),
                    (
                        "weight",
                        1,
                        Columns(
                            [
                                ("weight", 1, GText("")),
                                self.close_button,
                                ("weight", 1, GText("")),
                            ]
                        ),
                    ),
                    ("weight", 1, GText("")),
                ]
            ),
            "buttonbar",
        )

        # Common Add Button
        self.add_button = GBoxButton(T_("Add"), self._press_button)
        connect_signal(
            self.add_button,
            "click",
            lambda button: self.handle_event("add enter"),
        )
        self.add_button = (len(self.add_button.label) + 6, self.add_button)
        self.add_button_footer = GridFlow(
            [self.add_button[1]], 10, 1, 1, "center"
        )

        # Common Edit Button
        self.edit_button = GBoxButton(T_("Edit"), self._press_button)
        connect_signal(
            self.edit_button,
            "click",
            lambda button: self.handle_event("edit enter"),
        )
        self.edit_button = (len(self.edit_button.label) + 6, self.edit_button)
        self.edit_button_footer = GridFlow(
            [self.edit_button[1]], 10, 1, 1, "center"
        )

        # Common Details Button
        self.details_button = GBoxButton(T_("Details"), self._press_button)
        connect_signal(
            self.details_button,
            "click",
            lambda button: self.handle_event("details enter"),
        )
        self.details_button = (len(self.details_button.label) + 6, self.details_button)
        self.details_button_footer = GridFlow(
            [self.details_button[1]], 10, 1, 1, "center"
        )

        # Common Toggle Button
        self.toggle_button = GBoxButton(T_("Space to toggle"), self._press_button)
        self.toggle_button._selectable = False
        self.toggle_button = (len(self.toggle_button.label) + 6, self.toggle_button)
        self.toggle_button_footer = GridFlow(
            [self.toggle_button[1]], 10, 1, 1, "center"
        )

        # Common Apply Button
        self.apply_button = GBoxButton(T_("Apply"), self._press_button)
        connect_signal(
            self.apply_button,
            "click",
            lambda button: self.handle_event("apply enter"),
        )
        self.apply_button = (len(self.apply_button.label) + 6, self.apply_button)
        self.apply_button_footer = GridFlow(
            [self.apply_button[1]], 10, 1, 1, "center"
        )

        # Common Save Button
        self.save_button = GBoxButton(T_("Save"), self._press_button)
        connect_signal(
            self.save_button,
            "click",
            lambda button: self.handle_event("save enter"),
        )
        self.save_button = (len(self.save_button.label) + 6, self.save_button)
        self.save_button_footer = GridFlow(
            [self.save_button[1]], 10, 1, 1, "center"
        )

        self._refresh_main_menu()

        # Password Dialog
        self._prepare_password_dialog()

        # Read in logging units
        self._load_journal_units()

        # Log file viewer
        self.log_file_content: List[str] = [
            T_("If this is not that what you expected to see, you probably have insufficient "
               "permissions."),
        ]
        self._prepare_log_viewer("NetworkManager", self.log_line_count)

        self._prepare_timesyncd_config()

        # some settings
        MultiMenuItem.application = self
        GButton.application = self

    def _refresh_main_menu(self):
        """Refresh main menu."""
        # The common menu description column
        self.menu_description = Pile(
            [
                GText(T_("Main Menu"), CENTER),
                GText(T_("Here you can do the main actions"), LEFT),
            ]
        )
        # Main Menu
        items = {
            T_("Language configuration"): Pile(
                [
                    GText(T_("Language"), CENTER),
                    GText(""),
                    GText(
                        T_("Opens the yast2 configurator for setting language settings.")
                    ),
                ]
            ),
            T_("Change system password"): Pile(
                [
                    GText(T_("Password change"), CENTER),
                    GText(""),
                    GText(T_("Opens a dialog for changing the password of the system root user. When a password is set, you can login via ssh and rerun grommunio-cui.")),
                ]
            ),
            T_("Network interface configuration"): Pile(
                [
                    GText(T_("Configuration of network"), CENTER),
                    GText(""),
                    GText(
                        T_("Opens the yast2 configurator for setting up devices, interfaces, IP addresses, DNS and more.")
                    ),
                ]
            ),
            T_("Timezone configuration"): Pile(
                [
                    GText(T_("Timezone"), CENTER),
                    GText(""),
                    GText(
                        T_("Opens the yast2 configurator for setting country and timezone settings.")
                    ),
                ]
            ),
            T_("timesyncd configuration"): Pile(
                [
                    GText(T_("timesyncd"), CENTER),
                    GText(""),
                    GText(
                        T_("Opens a simple configurator for configuring systemd-timesyncd as a lightweight NTP client for time synchronization.")
                    ),
                ]
            ),
            T_("Select software repositories"): Pile([
                GText(T_("Software repositories selection"), CENTER),
                GText(""),
                GText(T_("Opens dialog for choosing software repositories.")),
            ]),
            T_("Update the system"): Pile([
                GText(T_("System update"), CENTER),
                GText(""),
                GText(T_("Executes the system package manager for the installation of newer component versions.")),
            ]),
            T_("grommunio setup wizard"): Pile(
                [
                    GText(T_("Setup wizard"), CENTER),
                    GText(""),
                    GText(
                        T_("Executes the grommunio-setup script for the initial configuration of grommunio databases, TLS certificates, services and the administration web user interface.")
                    ),
                ]
            ),
            T_("Change admin-web password"): Pile(
                [
                    GText(T_("Password change"), CENTER),
                    GText(""),
                    GText(
                        T_("Opens a dialog for changing the password used by the administration web interface.")
                    ),
                ]
            ),
            T_("Terminal"): Pile(
                [
                    GText(T_("Terminal"), CENTER),
                    GText(""),
                    GText(
                        T_("Starts terminal for advanced system configuration.")
                    ),
                ]
            ),
            T_("Reboot"): Pile(
                [GText(T_("Reboot system."), CENTER), GText(""), GText("")]
            ),
            T_("Shutdown"): Pile(
                [
                    GText(T_("Shutdown system."), CENTER),
                    GText(""),
                    GText(T_("Shuts down the system and powers off.")),
                ]
            ),
        }
        if os.getppid() != 1:
            items["Exit"] = Pile([GText(T_("Exit CUI"), CENTER)])
        self.main_menu_list = self._prepare_menu_list(items)
        if self.current_window == _MAIN_MENU and self.current_menu_focus > 0:
            off: int = 1
            if self.last_current_window == _MAIN_MENU:
                off = 1
            self.main_menu_list.focus_position = self.current_menu_focus - off
        self.main_menu = self._menu_to_frame(self.main_menu_list)
        if self.current_window == _MAIN_MENU:
            self._loop.widget = self.main_menu
            self._body = self.main_menu

    def _prepare_mainscreen(self):
        """Prepare main screen."""
        colormode: str = self._current_colormode
        self.text_header = [T_("grommunio console user interface")]
        self.text_header += ["\n"]
        self.text_header += [
            T_("Active keyboard layout: {kbd}; color set: {colormode}.")
        ]
        self.authorized_options = ""
        text_intro = [
            "\n",
            T_("If you need help, press the 'L' key to view logs."),
            "\n",
        ]
        self.tb_intro = GText(text_intro, align=CENTER, wrap=SPACE)
        text_sysinfo_top = util.get_system_info("top")
        self.tb_sysinfo_top = GText(text_sysinfo_top, align=LEFT, wrap=SPACE)
        text_sysinfo_bottom = util.get_system_info("bottom")
        self.tb_sysinfo_bottom = GText(
            text_sysinfo_bottom, align=LEFT, wrap=SPACE
        )
        self.main_top = ScrollBar(
            Scrollable(
                Pile(
                    [
                        Padding(self.tb_intro, left=2, right=2, min_width=20),
                        Padding(
                            self.tb_sysinfo_top,
                            align=LEFT,
                            left=6,
                            width=("relative", 80),
                        ),
                    ]
                )
            )
        )
        self.main_bottom = ScrollBar(
            Scrollable(
                Pile(
                    [
                        AttrWrap(
                            Padding(
                                self.tb_sysinfo_bottom,
                                align=LEFT,
                                left=6,
                                width=("relative", 80),
                            ),
                            "reverse",
                        )
                    ]
                )
            )
        )
        self.tb_header = GText(
            "".join(self.text_header).format(
                colormode=colormode,
                kbd=self._current_kbdlayout,
                authorized_options="",
            ),
            align=CENTER,
            wrap=SPACE,
        )
        self._refresh_header(colormode, self._current_kbdlayout, "")
        self.vsplitbox = Pile(
            [
                ("weight", 50, AttrMap(self.main_top, "body")),
                ("weight", 50, self.main_bottom),
            ]
        )
        self.footer = Pile(self.footer_content)
        frame = Frame(
            AttrMap(self.vsplitbox, "reverse"),
            header=self.header,
            footer=self.footer,
        )
        self.mainframe = frame
        self._body = self.mainframe
        # self.print(T_("Idle"))

    def _refresh_header(self, colormode, kbd, auth_options):
        """Refresh header"""
        self._refresh_head_text(colormode, kbd, auth_options)
        self.header = AttrMap(Padding(self.tb_header, align=CENTER), "header")
        if getattr(self, "footer", None):
            self._refresh_main_menu()

    def _refresh_head_text(self, colormode, kbd, authorized_options):
        """Refresh head text."""
        self.tb_header.set_text(
            "".join(self.text_header).format(
                colormode=colormode,
                kbd=kbd,
                authorized_options=authorized_options,
            )
        )

    def handle_event(self, event: Any):
        """
        Handles user input to the console UI.

            :param event: A mouse or keyboard input sequence. While the mouse
                event has the form ('mouse press or release', button, column,
                line), the key stroke is represented as is a single key or even
                the represented value like 'enter', 'up', 'down', etc.
            :type: Any
        """
        self.current_event = event
        if type(event) == str:
            self._handle_key_event(event)
        elif type(event) == tuple:
            self._handle_mouse_event(event)
        self.print(self.current_bottom_info)

    def _handle_key_event(self, event: Any):
        """Handle keyboard event."""
        # event was a key stroke
        key: str = str(event)
        if self.log_finished and self.current_window != _LOG_VIEWER:
            self.log_finished = False
        if self.current_window == _MAIN:
            self._key_ev_main(key)
        elif self.current_window == _MESSAGE_BOX:
            self._key_ev_mbox(key)
        elif self.current_window == _INPUT_BOX:
            self._key_ev_ibox(key)
        elif self.current_window == _TERMINAL:
            self._key_ev_term(key)
        elif self.current_window == _PASSWORD:
            self._key_ev_pass(key)
        elif self.current_window == _LOGIN:
            self._key_ev_login(key)
        elif self.current_window == _REBOOT:
            self._key_ev_reboot(key)
        elif self.current_window == _SHUTDOWN:
            self._key_ev_shutdown(key)
        elif self.current_window == _MAIN_MENU:
            self._key_ev_mainmenu(key)
        elif self.current_window == _LOG_VIEWER:
            self._key_ev_logview(key)
        elif self.current_window == _UNSUPPORTED:
            self._key_ev_unsupp(key)
        elif self.current_window == _ADMIN_WEB_PW:
            self._key_ev_aapi(key)
        elif self.current_window == _TIMESYNCD:
            self._key_ev_timesyncd(key)
        elif self.current_window == _REPO_SELECTION:
            self._key_ev_repo_selection(key)
        elif self.current_window == _KEYBOARD_SWITCH:
            self._key_ev_kbd_switch(key)
        self._key_ev_anytime(key)

    def _key_ev_main(self, key):
        """Handle event on mainframe."""
        if key == "f2":
            if util.check_if_password_is_set(getuser()):
                self.login_body.focus_position = (
                    0 if getuser() == "" else 1
                )  # focus on passwd if user detected
                frame: parameter.Frame = parameter.Frame(
                    body=LineBox(Padding(Filler(self.login_body))),
                    header=self.login_header,
                    footer=self.login_footer,
                    focus_part="body",
                )
                self.dialog(frame)
                self.current_window = _LOGIN
            else:
                self._open_main_menu()
        elif key == "l" and not PRODUCTION:
            self._open_main_menu()
        elif key == "tab":
            self.vsplitbox.focus_position = (
                0 if self.vsplitbox.focus_position == 1 else 1
            )

    def _key_ev_mbox(self, key):
        """Handle event on message box."""
        if key.endswith("enter") or key == "esc":
            if self.current_window != self.message_box_caller \
                    and self.message_box_caller != _MESSAGE_BOX:
                self.current_window = self.message_box_caller
                self._body = self._message_box_caller_body
            if self.old_layout:
                self.layout = self.old_layout
            self._reset_layout()
            if self.current_window not in [
                _LOGIN, _MAIN_MENU, _TIMESYNCD, _REPO_SELECTION
            ]:
                if self.key_counter.get(key, 0) < 10:
                    self.key_counter[key] = self.key_counter.get(key, 0) + 1
                    self.handle_event(key)
                else:
                    self.key_counter[key] = 0

    def _key_ev_ibox(self, key):
        """Handle event on input box."""
        self._handle_standard_tab_behaviour(key)
        if key.endswith("enter") or key == "esc":
            if key.lower().endswith("enter"):
                self.last_input_box_value = (
                    self._loop.widget.top_w.base_widget.body.base_widget[
                        1
                    ].edit_text
                )
            else:
                self.last_input_box_value = ""
            self.current_window = self.current_window_input_box
            self._body = self._input_box_caller_body
            if self.old_layout:
                self.layout = self.old_layout
            self._reset_layout()
            self.handle_event(key)

    def _key_ev_term(self, key):
        """Handle event on terminal."""
        self._handle_standard_tab_behaviour(key)
        if key == "f10":
            raise ExitMainLoop()
        elif key.endswith("enter") or key == "esc":
            self._open_main_menu()

    def _key_ev_pass(self, key):
        """Handle event on system password reset menu."""
        self._handle_standard_tab_behaviour(key)
        success_msg = T_("NOTHING")
        if key.lower().endswith("enter"):
            if key.lower().startswith("hidden"):
                button_type = key.lower().split(" ")[1]
            else:
                button_type = "ok"
            if button_type == "ok":
                success_msg = T_("was successful")
                pw1 = self._loop.widget.top_w.base_widget.body.base_widget[
                    2
                ].edit_text
                pw2 = self._loop.widget.top_w.base_widget.body.base_widget[
                    4
                ].edit_text
                if pw1 == pw2:
                    res = self._reset_system_passwd(pw1)
                else:
                    res = 2
                    success_msg = T_("failed due to mismatching password values")
                if not res:
                    success_msg = T_("failed")
                self._open_main_menu()
            else:
                success_msg = T_("aborted")
                self._open_main_menu()
        elif key.lower().find("cancel") >= 0 or key.lower() in ["esc"]:
            success_msg = T_("aborted")
            self._open_main_menu()
        if key.lower().endswith("enter") or key in ["esc", "enter"]:
            self.current_window = self.input_box_caller
            self.message_box(
                parameter.MsgBoxParams(
                    T_(f"System password reset {success_msg}!"),
                    T_("System password reset"),
                ),
                size=parameter.Size(height=10)
            )

    def _key_ev_login(self, key):
        """Handle event on login menu."""
        self._handle_standard_tab_behaviour(key)
        if key.endswith("enter"):
            self._check_login()
        elif key == "esc":
            self._open_mainframe()

    def _key_ev_reboot(self, key):
        """Handle event on power off menu."""
        # Restore cursor etc. before going off.
        if key.endswith("enter") and self.last_pressed_button.lower().endswith(
            "ok"
        ):
            self._loop.stop()
            self.screen.tty_signal_keys(*self.old_termios)
            os.system("reboot")
            raise ExitMainLoop()
        else:
            self.current_window = _MAIN_MENU

    def _key_ev_shutdown(self, key):
        """Handle event on shutdown menu."""
        # Restore cursor etc. before going off.
        if key.endswith("enter") and self.last_pressed_button.lower().endswith(
            "ok"
        ):
            self._loop.stop()
            self.screen.tty_signal_keys(*self.old_termios)
            os.system("poweroff")
            raise ExitMainLoop()
        else:
            self.current_window = _MAIN_MENU

    def _key_ev_mainmenu(self, key):
        """Handle event on main menu menu."""
        menu_selected: int = self._handle_standard_menu_behaviour(
            self.main_menu_list, key, self.main_menu.base_widget.body[1]
        )
        if key.endswith("enter") or key in range(ord("1"), ord("9") + 1):
            if menu_selected == 1:
                pre = cui.parser.ConfigParser(infile='/etc/locale.conf')
                self._run_yast_module("language")
                post = cui.parser.ConfigParser(infile='/etc/locale.conf')
                if pre != post:
                    self.restart_gui()
            elif menu_selected == 2:
                self._open_change_password()
            elif menu_selected == 3:
                self._run_yast_module("lan")
            elif menu_selected == 4:
                self._run_yast_module("timezone")
            elif menu_selected == 5:
                self._open_timesyncd_conf()
            elif menu_selected == 6:
                self._open_repo_conf()
            elif menu_selected == 7:
                self._run_zypper("up")
            elif menu_selected == 8:
                self._open_setup_wizard()
            elif menu_selected == 9:
                self._open_reset_aapi_pw()
            elif menu_selected == 10:
                self._open_terminal()
            elif menu_selected == 11:
                self._reboot_confirm()
            elif menu_selected == 12:
                self._shutdown_confirm()
            elif menu_selected == 13:
                # Exit, not always visible
                raise ExitMainLoop()
        elif key == "esc":
            self._open_mainframe()

    def _key_ev_logview(self, key):
        """Handle event on log viewer menu."""
        if key in ["ctrl f1", "H", "h", "L", "l", "esc"]:
            self.current_window = self.log_file_caller
            self._body = self._log_file_caller_body
            self._reset_layout()
            self.log_finished = True
        elif key in ["left", "right", "+", "-"]:
            if key == "-":
                self.log_line_count -= 100
            elif key == "+":
                self.log_line_count += 100
            elif key == "left":
                self.current_log_unit -= 1
            elif key == "right":
                self.current_log_unit += 1
            if self.log_line_count < 200:
                self.log_line_count = 200
            elif self.log_line_count > 10000:
                self.log_line_count = 10000
            if self.current_log_unit < 0:
                self.current_log_unit = 0
            elif self.current_log_unit >= len(self.log_units):
                self.current_log_unit = len(self.log_units) - 1
            self._open_log_viewer(
                self._get_log_unit_by_id(self.current_log_unit),
                self.log_line_count,
            )
        elif (
            self._hidden_pos < len(_UNSUPPORTED)
            and key == _UNSUPPORTED.lower()[self._hidden_pos]
        ):
            self._hidden_input += key
            self._hidden_pos += 1
            if self._hidden_input == _UNSUPPORTED.lower():
                self._open_log_viewer("syslog")
        else:
            self._hidden_input = ""
            self._hidden_pos = 0

    def _key_ev_unsupp(self, key):
        """Handle event on unsupported."""
        if key in ["ctrl d", "esc", "ctrl f1", "H", "h", "l", "L"]:
            self.current_window = self.log_file_caller
            self._body = self._log_file_caller_body
            self.log_finished = True
            self._reset_layout()

    def _key_ev_anytime(self, key):
        """Handle event at anytime."""
        if key in ["f10", "Q"]:
            raise ExitMainLoop()
        elif key == "f4" and len(self.authorized_options) > 0:
            self._open_main_menu()
        elif key == "f1" or key == "c":
            self._switch_next_colormode()
        elif key == "f5":
            self._open_keyboard_selection_menu()
        elif (
            key in ["ctrl f1", "H", "h", "L", "l"]
            and self.current_window != _LOG_VIEWER
            and self.current_window != _UNSUPPORTED
            and not self.log_finished
        ):
            self._open_log_viewer("gromox-http", self.log_line_count)

    def _key_ev_aapi(self, key):
        """Handle event on admin api password reset menu."""
        self._handle_standard_tab_behaviour(key)
        success_msg = T_("NOTHING")
        if key.lower().endswith("enter"):
            if key.lower().startswith("hidden"):
                button_type = key.lower().split(" ")[1]
            else:
                button_type = "ok"
            if button_type == "ok":
                success_msg = T_("was successful")
                pw1 = self._loop.widget.top_w.base_widget.body.base_widget[
                    2
                ].edit_text
                pw2 = self._loop.widget.top_w.base_widget.body.base_widget[
                    4
                ].edit_text
                if pw1 == pw2:
                    res = self._reset_aapi_passwd(pw1)
                else:
                    res = 2
                    success_msg = T_("failed due to mismatching password values")
                if not res:
                    success_msg = T_("failed")
                self._open_main_menu()
            else:
                success_msg = T_("aborted")
                self._open_main_menu()
        elif key.lower().find("cancel") >= 0 or key.lower() in ["esc"]:
            success_msg = T_("aborted")
            self._open_main_menu()
        if key.lower().endswith("enter") or key in ["esc", "enter"]:
            self.current_window = self.input_box_caller
            self.message_box(
                parameter.MsgBoxParams(
                    T_(f"Admin password reset {success_msg}!"),
                    T_("Admin password reset"),
                ),
                size=parameter.Size(height=10)
            )

    def _key_ev_repo_selection(self, key):
        """Handle event on repository selection menu."""
        self._handle_standard_tab_behaviour(key)
        updateable = False
        keyurl = 'https://download.grommunio.com/RPM-GPG-KEY-grommunio'
        keyfile = '/tmp/RPM-GPG-KEY-grommunio'
        repofile = '/etc/zypp/repos.d/grommunio.repo'
        config = cui.parser.ConfigParser(infile=repofile)
        # config.filename = repofile
        if not config.get('grommunio'):
            config['grommunio'] = {}
            config['grommunio']['enabled'] = 1
            config['grommunio']['auorefresh'] = 1
        height = 10
        if key.lower().endswith("enter"):
            self._open_main_menu()
            if key.lower().startswith("hidden"):
                button_type = T_(key.split(" ")[1]).lower()
            else:
                button_type = T_("Cancel").lower()
            if button_type == T_("Cancel").lower():
                self.message_box(
                    parameter.MsgBoxParams(
                        T_('Software repository selection has been canceled.')
                    ),
                    size=parameter.Size(height=height)
                )
            else:
                url = 'download.grommunio.com/community/openSUSE_Leap_15.3/' \
                      '?ssl_verify=no'
                if self.repo_selection_body.base_widget[3].state:
                    # supported selected
                    user = self.repo_selection_body.base_widget[4][1].edit_text
                    password = self.repo_selection_body.base_widget[5][1].edit_text
                    testurl="https://download.grommunio.com/supported/open" \
                            "SUSE_Leap_15.3/repodata/repomd.xml"
                    req: Response = requests.get(testurl, auth=(user, password))
                    if req.status_code == 200:
                        url = '%s:%s@download.grommunio.com/supported/open' \
                              'SUSE_Leap_15.3/?ssl_verify=no' % (user, password)
                        updateable = True
                    else:
                        self.message_box(
                            parameter.MsgBoxParams(
                                T_('Please check the credentials for "supported"'
                                   '-version or use "community"-version.'),
                            ),
                            size=parameter.Size(height=height+1)
                        )
                else:
                    # community selected
                    updateable = True
                if updateable:
                    config['grommunio']['baseurl'] = 'https://%s' % url
                    config['grommunio']['type'] = 'rpm-md'
                    config2 = cui.parser.ConfigParser(infile=repofile)
                    config.write()
                    if config == config2:
                        self.message_box(
                            parameter.MsgBoxParams(
                                T_('The repo file has not been changed.')
                            ),
                            size=parameter.Size(height=height-1)
                        )
                    else:
                        # self.message_box(
                        #     T_('Fetching GPG-KEY file and refreshing '
                        #        'repositories. This may take a while ...'),
                        #     height=height, modal=False
                        # )
                        header = GText(T_("One moment, please ..."))
                        footer = GText(T_('Fetching GPG-KEY file and refreshing '
                                          'repositories. This may take a while ...'))
                        self.progressbar = self._create_progress_bar()
                        pad = urwid.Padding(self.progressbar)  # do not use pg! use self.progressbar.
                        fil = urwid.Filler(pad)
                        linebox = urwid.LineBox(fil)
                        frame: parameter.Frame = parameter.Frame(linebox, header, footer)
                        self.dialog(frame)
                        self._draw_progress(20)
                        res: Response = requests.get(keyurl)
                        got_keyfile: bool = False
                        if res.status_code == 200:
                            self._draw_progress(30)
                            tmp = Path(keyfile)
                            with tmp.open('w') as file:
                                file.write(res.content.decode())
                            self._draw_progress(40)
                            ret_code = subprocess.Popen(
                                ["rpm", "--import", keyfile],
                                stderr=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL,
                            )
                            if ret_code.wait() == 0:
                                self._draw_progress(60)
                                ret_code = subprocess.Popen(
                                    ["zypper", "--non-interactive", "refresh"],
                                    stderr=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL,
                                )
                                if ret_code.wait() == 0:
                                    self._draw_progress(100)
                                    got_keyfile = True
                        if got_keyfile:
                            self.message_box(
                                parameter.MsgBoxParams(
                                    T_('Software repository selection has been '
                                       'updated.'),
                                ),
                                size=parameter.Size(height=height)
                            )
                        else:
                            self.message_box(
                                parameter.MsgBoxParams(
                                    T_('Software repository selection has not been '
                                       'updated. Something went wrong while importing '
                                       'key file.'),
                                ),
                                size=parameter.Size(height=height+1)
                            )
        elif key == 'esc':
            self._open_main_menu()
            self.message_box(
                parameter.MsgBoxParams(
                    T_('Software repository selection has been canceled.'),
                ),
                size=parameter.Size(height=height)
            )

    def _key_ev_timesyncd(self, key):
        """Handle event on timesyncd menu."""
        self._handle_standard_tab_behaviour(key)
        success_msg = T_("NOTHING")
        if key.lower().endswith("enter"):
            if key.lower().startswith("hidden"):
                button_type = key.lower().split(" ")[1]
            else:
                button_type = "ok"
            if button_type == "ok":
                # Save config and return to mainmenu
                self.timesyncd_vars["NTP"] = self.timesyncd_body.base_widget[
                    1
                ].edit_text
                self.timesyncd_vars[
                    "FallbackNTP"
                ] = self.timesyncd_body.base_widget[2].edit_text
                util.lineconfig_write(
                    "/etc/systemd/timesyncd.conf", self.timesyncd_vars
                )
                ret_code = subprocess.Popen(
                    ["timedatectl", "set-ntp", "true"],
                    stderr=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                )
                res = ret_code.wait() == 0
                success_msg = T_("was successful")
                if not res:
                    success_msg = T_("failed")
                self._open_main_menu()
            else:
                success_msg = T_("aborted")
                self._open_main_menu()
        elif key.lower().find("cancel") >= 0 or key.lower() in ["esc"]:
            success_msg = T_("aborted")
            self._open_main_menu()
        if key.lower().endswith("enter") or key in ["esc", "enter"]:
            self.message_box(
                parameter.MsgBoxParams(
                    T_(f"Timesyncd configuration change {success_msg}!"),
                    T_("Timesyncd Configuration"),
                ),
                size=parameter.Size(height=10)
            )

    def _key_ev_kbd_switch(self, key: str):
        """Handle event on keyboard switch."""
        self._handle_standard_tab_behaviour(key)
        menu_id = self._handle_standard_menu_behaviour(
            self.keyboard_switch_body, key
        )
        stay = False
        if (
            key.lower().endswith("enter") and key.lower().startswith("hidden")
        ) or key.lower() in ["space"]:
            kbd = self.keyboard_content[menu_id - 1]
            self._set_kbd_layout(kbd)
        elif key.lower() == "esc":
            print()
        else:
            stay = True
        if not stay:
            self._return_to()

    def _handle_mouse_event(self, event: Any):
        """Handle mouse event while event is a mouse event in the
        form ('mouse press or release', button, column, line)"""
        event: Tuple[str, float, int, int] = tuple(event)
        if event[0] == "mouse press" and event[1] == 1:
            # self.handle_event('mouseclick left enter')
            self.handle_event("my mouseclick left button")

    def _return_to(self):
        """Return to mainframe or mainmenu depending on situation and state."""
        if self.last_current_window in [_MAIN_MENU]:
            self._open_main_menu()
        else:
            self._open_mainframe()

    def _load_journal_units(self):
        exe = "/usr/sbin/grommunio-admin"
        out = ""
        if Path(exe).exists():
            process = subprocess.Popen(
                [exe, "config", "dump"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            out = process.communicate()[0]
            if type(out) is bytes:
                out = out.decode()
        if out == "":
            self.config = {
                "logs": {"gromox-http": {"source": "gromox-http.service"}}
            }
        else:
            self.config = yaml.load(out, Loader=SafeLoader)
        self.log_units = self.config.get(
            "logs", {"gromox-http": {"source": "gromox-http.service"}}
        )
        for i, k in enumerate(self.log_units.keys()):
            if k == "Gromox http":
                self.current_log_unit = i
                break

    def _get_logging_formatter(self) -> str:
        """Get logging formatter."""
        default = (
            self.config.get("logging", {})
            .get("formatters", {})
            .get("mi-default", {})
        )
        return default.get(
            "format",
            '[%(asctime)s] [%(levelname)s] (%(module)s): "%(message)s"',
        )

    def _get_log_unit_by_id(self, idx) -> str:
        """Get logging unit by idx."""
        for i, k in enumerate(self.log_units.keys()):
            if idx == i:
                return self.log_units[k].get("source")[:-8]
        return ""

    @staticmethod
    def get_pure_menu_name(label: str) -> str:
        """
        Reduces label with id to original label-only form.

        :param label: The label in form "ID) LABEL" or "LABEL".
        :return: Only LABEL without "ID) ".
        """
        if label.find(") ") > 0:
            parts = label.split(") ")
            if len(parts) < 2:
                return label
            return parts[1]
        return label

    def handle_click(self, creator: Widget, option: bool = False):
        """
        Handles RadioButton clicks.

        :param creator: The widget creating calling the function.
        :param option: On if True, off otherwise.
        """
        self.print(T_("Creator (%s) clicked %r." % creator, option))

    def _open_terminal(self):
        """
        Jump to a shell prompt
        """
        self._loop.stop()
        self.screen.tty_signal_keys(*self.old_termios)
        print("\x1b[K")
        print(
            "\x1b[K \x1b[36m▼\x1b[0m",
            T_("To return to the CUI, issue the `exit` command.")
        )
        print("\x1b[J")
        # We have no environment, and so need su instead of just bash to launch
        # a proper PAM session and set $HOME, etc.
        os.system("/usr/bin/su -l")
        self.screen.tty_signal_keys(*self.blank_termios)
        self._loop.start()

    def _reboot_confirm(self):
        """Confirm reboot."""
        msg = T_("Are you sure?\n")
        msg += T_("After pressing OK, ")
        msg += T_("the system will reboot.")
        title = T_("Reboot")
        self.current_window = _REBOOT
        self.message_box(
            parameter.MsgBoxParams(msg, title),
            size=parameter.Size(width=80, height=10),
            view_buttons=parameter.ViewOkCancel(view_ok=True, view_cancel=True)
        )

    def _shutdown_confirm(self):
        """Confirm shutdown."""
        msg = T_("Are you sure?\n")
        msg += T_("After pressing OK, ")
        msg += T_("the system will shut down and power off.")
        title = T_("Shutdown")
        self.current_window = _SHUTDOWN
        self.message_box(
            parameter.MsgBoxParams(msg, title),
            size=parameter.Size(width=80, height=10),
            view_buttons=parameter.ViewOkCancel(view_ok=True, view_cancel=True)
        )

    def _open_change_password(self):
        """
        Opens password changing dialog.
        """
        self._reset_layout()
        self.print(T_("Changing system password"))
        self._open_change_system_pw_dialog()

    def _open_change_system_pw_dialog(self):
        """Open the change system password Dialog."""
        title = T_("System Password Change")
        msg = T_("Enter the new system password:")
        self._create_password_dialog(msg, title, _PASSWORD)

    def _create_password_dialog(self, msg, title, current_window):
        width = 60
        input_text = ""
        height = 14
        mask = "*"
        view_ok = True
        view_cancel = True
        align = CENTER
        valign = MIDDLE
        self.input_box_caller = self.current_window
        self._input_box_caller_body = self._loop.widget
        self.current_window = current_window
        body = LineBox(
            Padding(
                Filler(
                    Pile(
                        [
                            GText(msg, CENTER),
                            urwid.Divider(),
                            GEdit("", input_text, False, CENTER, mask=mask),
                            urwid.Divider(),
                            GEdit("", input_text, False, CENTER, mask=mask),
                        ]
                    ),
                    TOP,
                )
            )
        )
        footer = self._create_footer(view_ok, view_cancel)
        if title is None:
            title = "Input expected"
        frame: parameter.Frame = parameter.Frame(
            body=body,
            header=GText(title, CENTER),
            footer=footer,
            focus_part="body",
        )
        alignment: parameter.Alignment = parameter.Alignment(align, valign)
        size: parameter.Size = parameter.Size(width, height)
        self.dialog(frame, alignment=alignment, size=size)

    def _reset_system_passwd(self, new_pw: str) -> bool:
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

    def _prepare_password_dialog(self):
        """Prepare the QuickNDirty password dialog."""
        self.password = Terminal(["passwd"])
        self.password_frame = LineBox(
            Pile(
                [
                    ("weight", 70, self.password),
                ]
            ),
        )

    def _prepare_log_viewer(self, unit: str = "syslog", lines: int = 0):
        """
        Prepares the log file viewer widget and fills the last lines of the file content.

        :param unit: The journal unit to be viewed.
        :param lines: The number of lines to be viewed. (0 = unlimited)
        """
        unitname: str = (
            unit if unit.strip().endswith(".service") else f"{unit}.service"
        )

        reader = journal.Reader()
        reader.this_boot()
        # reader.log_level(sj.LOG_INFO)
        reader.add_match(_SYSTEMD_UNIT=unitname)
        # h = 60 * 60
        # d = 24 * h
        # sincetime = time.time() - 4 * d
        # reader.seek_realtime(sincetime)
        line_list: List[str] = []
        for entry in reader:
            if entry.get("__REALTIME_TIMESTAMP", "") == "":
                continue
            format_dict = {
                "asctime": entry.get(
                    "__REALTIME_TIMESTAMP",
                    datetime.datetime(1970, 1, 1, 0, 0, 0),
                ).isoformat(),
                "levelname": entry.get("PRIORITY", ""),
                "module": entry.get(
                    "_SYSTEMD_UNIT", "gromox-http.service"
                ).split(".service")[0],
                "message": entry.get("MESSAGE", ""),
            }
            line_list.append(self._get_logging_formatter() % format_dict)
        self.log_file_content = line_list[-lines:]
        found: bool = False
        pre: List[str] = []
        post: List[str] = []
        cur: str = f" {unitname[:-8]} "
        for uname in self.log_units.keys():
            src = self.log_units[uname].get("source")
            if src == unitname:
                found = True
            else:
                if not found:
                    pre.append(src[:-8])
                else:
                    post.append(src[:-8])
        header = (
            T_("Use the arrow keys to switch between logfiles. <LEFT> and <RIGHT> switch the logfile, while <+> and <-> changes the line count to view. (%s)") % self.log_line_count
        )
        self.log_viewer = LineBox(
            AttrMap(
                Pile(
                    [
                        (
                            2,
                            Filler(
                                Padding(
                                    GText(("body", header), CENTER),
                                    CENTER,
                                    RELATIVE_100,
                                )
                            ),
                        ),
                        (
                            1,
                            Columns(
                                [
                                    Filler(
                                        GText(
                                            [
                                                ("body", "*** "),
                                                (
                                                    "body",
                                                    " ".join(
                                                        [u for u in pre[-3:]]
                                                    ),
                                                ),
                                                ("reverse", cur),
                                                (
                                                    "body",
                                                    " ".join(
                                                        [u for u in post[:3]]
                                                    ),
                                                ),
                                                ("body", " ***"),
                                            ],
                                            CENTER,
                                        )
                                    )
                                ]
                            ),
                        ),
                        AttrMap(
                            ScrollBar(
                                Scrollable(
                                    Pile(
                                        [
                                            GText(line)
                                            for line in self.log_file_content
                                        ]
                                    )
                                )
                            ),
                            "default",
                        ),
                    ]
                ),
                "body",
            )
        )

    def _open_log_viewer(self, unit: str, lines: int = 0):
        """
        Opens log file viewer.
        """
        if self.current_window != _LOG_VIEWER:
            self.log_file_caller = self.current_window
            self._log_file_caller_body = self._body
            self.current_window = _LOG_VIEWER
        self.print(T_("Log file viewer has to open file {%s} ...") % unit)
        self._prepare_log_viewer(unit, lines)
        self._body = self.log_viewer
        self._loop.widget = self._body

    def _run_yast_module(self, modulename: str):
        """Run yast module `modulename`."""
        self._loop.stop()
        self.screen.tty_signal_keys(*self.old_termios)
        print("\x1b[K")
        print(
            "\x1b[K \x1b[36m▼\x1b[0m",
            T_("Please wait while `yast2 %s` is being run.") % modulename
        )
        print("\x1b[J")
        os.system("yast2 {}".format(modulename))
        self.screen.tty_signal_keys(*self.blank_termios)
        self._loop.start()

    def _run_zypper(self, subcmd: str):
        """Run zypper modul `subcmd`."""
        self._loop.stop()
        self.screen.tty_signal_keys(*self.old_termios)
        print("\x1b[K")
        print("\x1b[K \x1b[36m▼\x1b[0m Please wait while zypper is invoked.")
        print("\x1b[J")
        os.system("zypper {}".format(subcmd))
        input("\n \x1b[36m▼\x1b[0m Press ENTER to return to the CUI.")
        self.screen.tty_signal_keys(*self.blank_termios)
        self._loop.start()

    def restart_gui(self):
        """Restart complete GUI to source language in again."""
        global T_
        langfile = '/etc/sysconfig/language'
        config = cui.parser.ConfigParser(infile=langfile)
        config['ROOT_USES_LANG'] = '"yes"'
        config.write()
        # assert os.getenv('PPID') == 1, 'Gugg mal rein da!'
        locale_conf = util.minishell_read('/etc/locale.conf')
        # T_ = util.init_localization()
        # mainapp()
        if os.getppid() == 1:
            T_ = util.init_localization(language=locale_conf.get('LANG', ''))
            main_app()
            # raise ExitMainLoop()
        else:
            env = {}
            for k in os.environ:
                env[k] = os.environ.get(k)
            for k in locale_conf:
                env[k] = locale_conf.get(k)
            os.execve(sys.executable, [sys.executable] + sys.argv, env)

    def _open_reset_aapi_pw(self):
        """Open reset admin-API password."""
        title = T_("admin-web Password Change")
        msg = T_("Enter the new admin-web password:")
        self._create_password_dialog(msg, title, _ADMIN_WEB_PW)

    def _reset_aapi_passwd(self, new_pw: str) -> bool:
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

    def _open_timesyncd_conf(self):
        """Open timesyncd configuration form."""
        self._reset_layout()
        self.print(T_("Opening timesyncd configuration"))
        self.current_window = _TIMESYNCD
        header = AttrMap(GText(T_("Timesyncd Configuration"), CENTER), "header")
        self._prepare_timesyncd_config()
        self._open_conf_dialog(self.timesyncd_body, header, [self.ok_button, self.cancel_button])

    def _open_conf_dialog(
            self,
            body_widget: urwid.Widget,
            header: Any,
            footer_buttons: List[Tuple[int, GBoxButton]]
    ):
        footer = AttrMap(
            Columns(footer_buttons), "buttonbar"
        )
        frame: parameter.Frame = parameter.Frame(
            body=AttrMap(body_widget, "body"),
            header=header,
            footer=footer,
            focus_part="body",
        )
        alignment: parameter.Alignment = parameter.Alignment(urwid.CENTER, urwid.MIDDLE)
        size: parameter.Size = parameter.Size(60, 15)
        self.dialog(frame, alignment=alignment, size=size)

    def _prepare_timesyncd_config(self):
        """Prepare timesyncd configuration form."""
        ntp_server: List[str] = [
            "0.arch.pool.ntp.org",
            "1.arch.pool.ntp.org",
            "2.arch.pool.ntp.org",
            "3.arch.pool.ntp.org",
        ]
        fallback_server: List[str] = [
            "0.opensuse.pool.ntp.org",
            "1.opensuse.pool.ntp.org",
            "2.opensuse.pool.ntp.org",
            "3.opensuse.pool.ntp.org",
        ]
        self.timesyncd_vars = util.lineconfig_read(
            "/etc/systemd/timesyncd.conf"
        )
        ntp_from_file = self.timesyncd_vars.get("NTP", " ".join(ntp_server))
        fallback_from_file = self.timesyncd_vars.get(
            "FallbackNTP", " ".join(fallback_server)
        )
        ntp_server = ntp_from_file.split(" ")
        fallback_server = fallback_from_file.split(" ")
        text = T_("Insert the NTP servers separated by <SPACE> char.")
        self.timesyncd_body = LineBox(
            Padding(
                Filler(
                    Pile(
                        [
                            GText(text, LEFT, wrap=SPACE),
                            GEdit(
                                (15, "NTP: "), " ".join(ntp_server), wrap=SPACE
                            ),
                            GEdit(
                                (15, "FallbackNTP: "),
                                " ".join(fallback_server),
                                wrap=SPACE,
                            ),
                        ]
                    ),
                    TOP,
                )
            )
        )

    def _open_repo_conf(self):
        """Open repository configuration form."""
        self._reset_layout()
        self.print(T_("Opening repository selection"))
        self.current_window = _REPO_SELECTION
        header = AttrMap(GText(T_("Software repository selection"), CENTER), "header")
        self._prepare_repo_config()
        self._open_conf_dialog(self.repo_selection_body, header, [self.save_button, self.cancel_button])

    def _prepare_repo_config(self):
        """Prepare repository configuration form."""
        baseurl = 'https://download.grommunio.com/community/openSUSE_Leap_' \
                  '15.3/?ssl_verify=no'
        repofile = '/etc/zypp/repos.d/grommunio.repo'
        config = cui.parser.ConfigParser(infile=repofile)
        default_type = 'community'
        default_user = ''
        default_pw = ''
        is_community: bool = True
        is_supported: bool = False
        if config.get('grommunio', None):
            match = re.match(
                'https://([^:]*):?([^@]*)@?download.grommunio.com/(.+)/open.+',
                config['grommunio'].get('baseurl', baseurl)
            )
            if match:
                (default_user, default_pw, default_type) = match.groups()
        if default_type == 'supported':
            is_community = False
            is_supported = True
        blank = urwid.Divider('-')
        vblank = (2, GText(' '))
        rbg = []
        body_content = [
            blank,
            urwid.RadioButton(
                rbg, T_('Use "community" repository'), state=is_community
            ),
            blank,
            urwid.RadioButton(
                rbg, T_('Use "supported" repository'), state=is_supported
            ),
            urwid.Columns([
                vblank, GEdit(T_('Username: '), edit_text=default_user), vblank
            ]),
            urwid.Columns([
                vblank, GEdit(T_('Password: '), edit_text=default_pw), vblank
            ])
        ]
        self.repo_selection_body = LineBox(Padding(Filler(Pile(body_content), TOP)))

    def _open_setup_wizard(self):
        """Open grommunio setup wizard."""
        self._loop.stop()
        self.screen.tty_signal_keys(*self.old_termios)
        if Path("/usr/sbin/grommunio-setup").exists():
            os.system("/usr/sbin/grommunio-setup")
        else:
            os.system("/usr/sbin/grammm-setup")
        self.screen.tty_signal_keys(*self.blank_termios)
        self._loop.start()

    def _open_main_menu(self):
        """
        Opens amin menu,
        """
        self._reset_layout()
        self.print(T_("Login successful"))
        self.current_window = _MAIN_MENU
        self.authorized_options = T_(", <F4> for Main-Menu")
        self._prepare_mainscreen()
        self._body = self.main_menu
        self._loop.widget = self._body

    def _open_mainframe(self):
        """
        Opens main window. (Welcome screen)
        """
        self._reset_layout()
        self.print(T_("Returning to main screen."))
        self.current_window = _MAIN
        self._prepare_mainscreen()
        self._loop.widget = self._body

    def _check_login(self, widget: Widget = None):
        """
        Checks login data and switch to authenticate on if successful.
        """
        if self.user_edit.get_edit_text() != getuser() and os.getegid() != 0:
            self.message_box(
                parameter.MsgBoxParams(T_("You need root privileges to use another user.")),
                size=parameter.Size(height=10)
            )
            return
        msg = T_("checking user %s with pass ") % self.user_edit.get_edit_text()
        if self.current_window == _LOGIN:
            if util.authenticate_user(
                self.user_edit.get_edit_text(), self.pass_edit.get_edit_text()
            ):
                self.pass_edit.set_edit_text("")
                self._open_main_menu()
            else:
                self.message_box(
                    parameter.MsgBoxParams(
                        T_("Incorrect credentials. Access denied!"),
                        T_("Password verification"),
                    )
                )
                self.print(T_("Login wrong! (%s)") % msg)

    def _press_button(self, button: Widget, *args, **kwargs):
        """
        Handles general events if a button is pressed.

        :param button: The button been clicked.
        """
        label: str = T_("UNKNOWN LABEL")
        if (
            isinstance(button, RadioButton)
            or isinstance(button, WidgetDrawer)
            or isinstance(button, GButton)
        ):
            label = button.label
        self.last_pressed_button = label
        if self.current_window not in [_MAIN]:
            self.print(
                f"{self.__class__}.press_button(button={button}, "
                f"*args={args}, kwargs={kwargs})"
            )
            self.handle_event(f"{label} enter")

    def _prepare_menu_list(self, items: Dict[str, Widget]) -> ListBox:
        """
        Prepare general menu list.

        :param items: A dictionary of widgets representing the menu items.
        :return: ListBox containing menu items.
        """
        menu_items: List[MenuItem] = self._create_menu_items(items)
        return ListBox(SimpleFocusListWalker(menu_items))

    def _menu_to_frame(self, listbox: ListBox):
        """Put menu(ListBox) into a Frame."""
        fopos: int = listbox.focus_position
        menu = Columns([
            AttrMap(listbox, "body"), AttrMap(ListBox(SimpleListWalker([
                listbox.body[fopos].original_widget.get_description()
            ])), "reverse",),
        ])
        return Frame(menu, header=self.header, footer=self.footer)

    def _switch_next_colormode(self):
        """Switch to next color scheme."""
        original = self._current_colormode
        color_name = util.get_next_palette_name(original)
        palette = util.get_palette(color_name)
        show_next = color_name
        self._refresh_header(
            show_next, self._current_kbdlayout, self.authorized_options
        )
        self._loop.screen.register_palette(palette)
        self._loop.screen.clear()
        self._current_colormode = show_next

    def _set_kbd_layout(self, layout):
        """Set and save selected keyboard layout."""
        # Do read the file again so newly added keys do not get lost
        file = "/etc/vconsole.conf"
        var = util.minishell_read(file)
        var["KEYMAP"] = layout
        util.minishell_write(file, var)
        os.system("systemctl restart systemd-vconsole-setup")
        self._current_kbdlayout = layout
        self._refresh_head_text(
            self._current_colormode,
            self._current_kbdlayout,
            self.authorized_options,
        )

    def _open_keyboard_selection_menu(self):
        """Open keyboard selection menu form."""
        self._reset_layout()
        self.print(T_("Opening keyboard configuration"))
        self.last_current_window = self.current_window
        self.current_window = _KEYBOARD_SWITCH
        header = None
        self._prepare_kbd_config()
        footer = None
        frame: parameter.Frame = parameter.Frame(
            body=AttrMap(self.keyboard_switch_body, "body"),
            header=header,
            footer=footer,
            focus_part="body",
        )
        alignment: parameter.Alignment = parameter.Alignment(urwid.CENTER, urwid.MIDDLE)
        size: parameter.Size = parameter.Size(30, 10)
        self.dialog(frame, alignment=alignment, size=size)

    def _prepare_kbd_config(self):
        """Prepare keyboard config form."""
        def sub_press(button, is_set=True, **kwargs):
            if is_set:
                layout = button.label
                self._set_kbd_layout(layout)
                self._return_to()

        keyboards: Set[str] = {"de-latin1-nodeadkeys", "us"}
        all_kbds = [
            y.split(".")
            for x in os.walk("/usr/share/kbd/keymaps")
            for y in x[2]
        ]
        all_kbds = [x[0] for x in all_kbds if len(x) >= 2 and x[1] == "map"]
        _ = [
            keyboards.add(kbd)
            for kbd in all_kbds
            if re.match("^[a-z][a-z]$", kbd)
        ]
        self.loaded_kbd = util.get_current_kbdlayout()
        keyboard_list = [self.loaded_kbd]
        _ = [
            keyboard_list.append(kbd)
            for kbd in sorted(keyboards)
            if kbd != self.loaded_kbd
        ]
        self.keyboard_rb = []
        self.keyboard_content = []
        for kbd in keyboard_list:
            self.keyboard_content.append(
                AttrMap(
                    urwid.RadioButton(
                        self.keyboard_rb, kbd, "first True", sub_press
                    ),
                    "focus" if kbd == self.loaded_kbd else "selectable",
                )
            )
        self.keyboard_list = ScrollBar(Scrollable(Pile(self.keyboard_content)))
        self.keyboard_switch_body = self.keyboard_list

    def redraw(self):
        """
        Redraws screen.
        """
        if getattr(self, "_loop", None):
            if self._loop:
                self._loop.draw_screen()

    def _reset_layout(self):
        """
        Resets the console UI to the default layout
        """

        if getattr(self, "_loop", None):
            self._loop.widget = self._body
            self._loop.draw_screen()

    def _create_menu_items(self, items: Dict[str, Widget]) -> List[MenuItem]:
        """
        Takes a dictionary with menu labels as keys and widget(lists) as
        content and creates a list of menu items.

        :param items: Dictionary in the form {'label': Widget}.
        :return: List of MenuItems.
        """
        menu_items: List[MenuItem] = []
        for idx, caption in enumerate(items.keys(), 1):
            item = MenuItem(idx, caption, items.get(caption), self)
            connect_signal(item, "activate", self.handle_event)
            menu_items.append(AttrMap(item, "selectable", "focus"))
        return menu_items

    def print(self, string="", align="left"):
        """
        Prints a string to the console UI

        Args:
            string (str): The string to print
            align (str): The alignment of the printed text
        """

        def glen(widget_list):
            wlist = widget_list
            res = 0
            if not wlist:
                res = 0
            elif isinstance(wlist, list):
                for elem in wlist:
                    if elem:
                        res += glen(elem)
            elif isinstance(wlist, GText):
                res += len(wlist.view)
            elif isinstance(wlist, str):
                res += len(wlist)
            else:
                res += 0
            return res

        clock = GText(util.get_clockstring(), right=1)
        footerbar = GText(util.get_footerbar(2, 10), left=1, right=0)
        avg_load = GText(util.get_load_avg_format_list(), left=1, right=2)
        gstring = GText(("footer", string), left=1, right=2)
        gdebug = GText(
            [
                "\n",
                ("", f"({self.current_event})"),
                ("", f" on {self.current_window}"),
            ]
        )
        mainwidth = self.screen.get_cols_rows()[0]
        footer_elements = [clock, footerbar, avg_load]
        if not self.quiet:
            footer_elements += [gstring]
        content = []
        rest = []
        for elem in footer_elements:
            if glen([content, elem]) < mainwidth:
                content.append(elem)
            else:
                rest.append(elem)
        col_list = [Columns([(len(elem), elem) for elem in content])]
        if len(rest) > 0:
            col_list += [Columns([(len(elem), elem) for elem in rest])]
        if self.debug:
            col_list += [Columns([gdebug])]
        self.footer_content = col_list
        self.footer = AttrMap(Pile(self.footer_content), "footer")
        swap_widget = getattr(self, "_body", None)
        if swap_widget:
            swap_widget.footer = self.footer
            self.redraw()
        self.current_bottom_info = string

    def _create_progress_bar(self, max_progress=100):
        """Create progressbar"""
        self.progressbar = urwid.ProgressBar('PB.normal', 'PB.complete', 0, max_progress, 'PB.satt')
        return self.progressbar

    def _draw_progress(self, progress, max_progress=100):
        """Draw progress at progressbar"""
        # completion = float(float(progress)/float(max_progress))
        # self.progressbar.set_completion(completion)
        time.sleep(0.1)
        self.progressbar.done = max_progress
        self.progressbar.current = progress
        if progress == max_progress:
            self._reset_layout()
        self._loop.draw_screen()

    def message_box(
            self,
            mb_params: parameter.MsgBoxParams = parameter.MsgBoxParams(None, None, True),
            alignment: parameter.Alignment = parameter.Alignment(urwid.CENTER, urwid.MIDDLE),
            size: parameter.Size = parameter.Size(45, 9),
            view_buttons: parameter.ViewOkCancel = parameter.ViewOkCancel(True, False)
    ):
        """
        Creates a message box dialog with an optional title. The message also
        can be a list of urwid formatted tuples.

        To use the box as standard message box always returning to it's parent,
        then you have to implement something like this in the event handler:
        (f.e. **self**.handle_event)

            elif self.current_window == _MESSAGE_BOX:
                if key.endswith('enter') or key == 'esc':
                    self.current_window = self.message_box_caller
                    self._body = self._message_box_caller_body
                    self.reset_layout()

        Args:
            @param mb_params: Messagebox parameters like msg, title and modal.
            @param alignment: The alignment in align and valign.
            @param size: The size in width and height.
            @param view_buttons: The viewed buttons ok or cancel.
        """
        if self.current_window != _MESSAGE_BOX:
            self.message_box_caller = self.current_window
            self._message_box_caller_body = self._loop.widget
            self.current_window = _MESSAGE_BOX
        body = LineBox(Padding(Filler(Pile([GText(mb_params.msg, CENTER)]), TOP)))
        footer = self._create_footer(view_buttons.view_ok, view_buttons.view_cancel)

        if mb_params.title is None:
            title = T_("Message")
        else:
            title = mb_params.title
        frame: parameter.Frame = parameter.Frame(
            body=body,
            header=GText(title, CENTER),
            footer=footer,
            focus_part="footer",
        )
        self.dialog(frame, alignment=alignment, size=size, modal=mb_params.modal)

    def input_box(
        self,
        msg: Any,
        title: str = None,
        input_text: str = "",
        multiline: bool = False,
        align: str = CENTER,
        width: int = 45,
        valign: str = MIDDLE,
        height: int = 9,
        mask: Union[bytes, str] = None,
        view_ok: bool = True,
        view_cancel: bool = False,
        modal: bool = False,
    ):
        """Creates an input box dialog with an optional title and a default
        value.
        The message also can be a list of urwid formatted tuples.

        To use the box as standard input box always returning to it's parent,
        then you have to implement something like this in the event handler:
        (f.e. **self**.handle_event) and you MUST set
        the self.current_window_input_box

            self.current_window_input_box = _ANY_OF_YOUR_CURRENT_WINDOWS
            self.input_box('Y/n', 'Question', 'yes')

            # and later on event handling
            elif self.current_window == _ANY_OF_YOUR_CURRENT_WINDOWS:
                if key.endswith('enter') or key == 'esc':
                    self.current_window = self.input_box_caller  # here you
                                         # have to set the current window

        :param msg: List or one element of urwid formatted tuple containing
                    the message content.
        :type: Any
        :param title: Optional title as simple string.
        :param input_text: Default text as input text.
        :param multiline: If True then inputs can have more than one line.
        :param align: Horizontal align.
        :param width: The width of the box.
        :param valign: Vertical align.
        :param height: The height of the box.
        :param mask: hide text entered by this character. If None, mask will
                     be disabled.
        :param view_ok: Should the OK button be visible?
        :param view_cancel: Should the Cancel button be visible?
        """
        self.input_box_caller = self.current_window
        self._input_box_caller_body = self._loop.widget
        self.current_window = _INPUT_BOX
        body = LineBox(
            Padding(
                Filler(
                    Pile(
                        [
                            GText(msg, CENTER),
                            GEdit(
                                "", input_text, multiline, CENTER, mask=mask
                            ),
                        ]
                    ),
                    TOP,
                )
            )
        )
        footer = self._create_footer(view_ok, view_cancel)

        if title is None:
            title = T_("Input expected")
        frame: parameter.Frame = parameter.Frame(
            body=body,
            header=GText(title, CENTER),
            footer=footer,
            focus_part="body",
        )
        alignment: parameter.Alignment = parameter.Alignment(align, valign)
        size: parameter.Size = parameter.Size(width, height)
        self.dialog(frame, alignment=alignment, size=size, modal=modal)

    def _create_footer(self, view_ok: bool = True, view_cancel: bool = False):
        """Create and return footer."""
        cols = [("weight", 1, GText(""))]
        if view_ok:
            cols += [
                (
                    "weight",
                    1,
                    Columns(
                        [
                            ("weight", 1, GText("")),
                            self.ok_button,
                            ("weight", 1, GText("")),
                        ]
                    ),
                )
            ]
        if view_cancel:
            cols += [
                (
                    "weight",
                    1,
                    Columns(
                        [
                            ("weight", 1, GText("")),
                            self.cancel_button,
                            ("weight", 1, GText("")),
                        ]
                    ),
                )
            ]
        cols += [("weight", 1, GText(""))]
        footer = AttrMap(Columns(cols), "buttonbar")
        return footer

    def get_focused_menu(self, menu: ListBox, event: Any) -> int:
        """
        Returns id of focused menu item. Returns current id on enter or 1-9 or
        click, and returns the next id if
        key is up or down.

        :param menu: The menu from which you want to know the id.
        :type: ListBox
        :param event: The event passed to the menu.
        :type: Any
        :returns: The id of the selected menu item. (>=1)
        :rtype: int
        """
        self.current_menu_focus = super(Application, self).get_focused_menu(
            menu, event
        )
        if not self.last_menu_focus == self.current_menu_focus:
            cid: int = self.last_menu_focus - 1
            nid: int = self.current_menu_focus - 1
            current_widget: Widget = menu.body[cid].base_widget
            next_widget: Widget = menu.body[nid].base_widget
            if isinstance(current_widget, MultiMenuItem) and isinstance(next_widget, MultiMenuItem):
                cmmi: MultiMenuItem = current_widget
                nmmi: MultiMenuItem = next_widget
                cmmi.mark_as_dirty()
                nmmi.mark_as_dirty()
                nmmi.set_focus()
                cmmi.refresh_content()
        return self.current_menu_focus

    def _handle_standard_menu_behaviour(
        self, menu: ListBox, event: Any, description_box: ListBox = None
    ) -> int:
        """
        Handles standard menu behaviour and returns the focused id, if any.

        :param menu: The menu to be handled.
        :param event: The event to be handled.
        :param description_box: The ListBox containing the menu content that
        may be refreshed with the next description.
        :return: The id of the menu having the focus (1+)
        """
        if event == "esc":
            return 1
        idx: int = self.get_focused_menu(menu, event)
        if str(event) not in ["up", "down"]:
            return idx
        if description_box is not None:
            focused_item: MenuItem = menu.body[idx - 1].base_widget
            description_box.body[0] = focused_item.get_description()
        return idx

    def _handle_standard_tab_behaviour(self, key: str = "tab"):
        """
        Handles standard tabulator behaviour in dialogs. Switching from body
        to footer and vice versa.

        :param key: The key to be handled.
        """
        top_keys = ['shift tab', 'up', 'left', 'meta tab']
        bottom_keys = ['tab', 'down', 'right']

        def switch_body_footer():
            if self.layout.focus_position == "body":
                self.layout.focus_position = "footer"
            elif self.layout.focus_position == "footer":
                self.layout.focus_position = "body"

        def count_selectables(widget_list, up_to: int = None):
            if up_to is None:
                up_to = len(widget_list) - 1
            limit = up_to + 1
            non_sels = 0
            sels = 0
            for widget in widget_list:
                if widget.selectable():
                    sels = sels + 1
                else:
                    non_sels = non_sels + 1
                if non_sels + sels == limit:
                    break
            return sels

        def jump_part(part):
            """Within this function we ignore all not _selectables."""
            first = 0
            try:
                last = len(part.base_widget.widget_list) - 1
            except IndexError:
                last = 0
            current = part.base_widget.focus_position
            # Reduce last and current by non selectables
            non_sels_current = current + 1 - count_selectables(part.base_widget.widget_list, current)
            non_sels_last = last + 1 - count_selectables(part.base_widget.widget_list, last)
            last = last - non_sels_last
            current = current - non_sels_current
            if current <= first and key in top_keys \
                    and self.layout.focus_part == 'footer':
                switch_body_footer()
            if current >= last and key in bottom_keys \
                    and self.layout.focus_part == 'body':
                switch_body_footer()
            else:
                move: int = 0
                if first <= current < last and key in bottom_keys:
                    move = 1
                elif first < current <= last and key in top_keys:
                    move = -1
                new_focus = part.base_widget.focus_position + move
                while 0 <= new_focus < len(part.base_widget.widget_list):
                    if part.base_widget.widget_list[new_focus].selectable():
                        part.base_widget.focus_position = new_focus
                        break
                    else:
                        new_focus += move
        # self.print(f"key is {key}")
        if key.endswith("tab") or key.endswith("down") or key.endswith('up'):
            current_part = self.layout.focus_part
            if current_part == 'body':
                jump_part(self.layout.body)
            elif current_part == 'footer':
                jump_part(self.layout.footer)

    def set_debug(self, yes: bool):
        """
        Sets debug mode on or off.

        :param yes: True for on and False for off.
        """
        self.debug = yes

    def _update_clock(self, cb_loop: MainLoop, data: Any = None):
        """
        Updates taskbar every second.

        :param cb_loop: The event loop calling next update_clock()
        :param data: Optional user data
        """
        self.print(self.current_bottom_info)
        cb_loop.set_alarm_in(1, self._update_clock, data)

    def start(self):
        """
        Starts the console UI
        """
        # set_trace(term_size=(129, 18))
        # set_trace()
        self._loop.run()
        if self.old_termios is not None:
            self.screen.tty_signal_keys(*self.old_termios)

    def dialog(
            self, frame: parameter.Frame,
            alignment: parameter.Alignment = parameter.Alignment(),
            size: parameter.Size = parameter.Size(),
            modal: bool = False
    ):
        """
        Overlays a dialog box on top of the console UI

        Args:
            @param frame: The frame with body, footer, header and focus_part.
            @param alignment: The alignment in align and valign.
            @param size: The size with width and height.
            @param modal: Dialog is locked / modal until user closes it.
        """
        # Body
        if isinstance(frame.body, str) and frame.body == "":
            body = GText(T_("No body"), align="center")
            body = Filler(body, valign="top")
            body = Padding(body, left=1, right=1)
            body = LineBox(body)
        else:
            body = frame.body

        # Footer
        if isinstance(frame.footer, str) and frame.footer == "":
            footer = GBoxButton("Okay", self._reset_layout())
            footer = AttrWrap(footer, "selectable", "focus")
            footer = GridFlow([footer], 8, 1, 1, "center")
        else:
            footer = frame.footer

        # Header
        if isinstance(frame.header, str) and frame.header == "":
            header = GText("No header", align=urwid.CENTER)
        else:
            header = frame.header

        # Focus
        if frame.focus_part is None:
            focus_part = "footer"
        else:
            focus_part = frame.focus_part

        # Layout
        if self.layout is not None:
            self.old_layout = self.layout

        self.layout = Frame(
            body, header=header, footer=footer, focus_part=focus_part
        )

        # self._body = body

        widget = Overlay(
            LineBox(self.layout),
            self._body,
            align=alignment.align,
            width=size.width,
            valign=alignment.valign,
            height=size.height,
        )

        if getattr(self, "_loop", None):
            self._loop.widget = widget
            if not modal:
                self._loop.draw_screen()


def create_application() -> Tuple[Union[Application, None], bool]:
    """Creates and returns the main application"""
    set_encoding("utf-8")
    production = True
    if "--help" in sys.argv:
        print(T_("Usage: {%s} [OPTIONS]") % sys.argv[0])
        print(T_("\tOPTIONS:"))
        print(T_("\t\t--help: Show this message."))
        print(T_("\t\t-v/--debug: Verbose/Debugging mode."))
        return None, PRODUCTION
    app = Application()
    if "-v" in sys.argv:
        app.set_debug(True)
    else:
        app.set_debug(False)

    app.quiet = True

    if "--hidden-login" in sys.argv:
        production = False

    return app, production


def main_app():
    """Starts main application."""
    # application, PRODUCTION = create_application()
    application = create_application()[0]
    # application.set_debug(True)
    # application.quiet = False
    # # PRODUCTION = False
    application.start()
    print("\n\x1b[J")


if __name__ == "__main__":
    main_app()
