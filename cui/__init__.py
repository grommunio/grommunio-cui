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
import yaml
# from pudb.remote import set_trace
from yaml import SafeLoader
from systemd import journal
import urwid
from cui.gwidgets import GText, GEdit
from cui import util, parameter
import cui.parser
from cui.appclass import Header, MainFrame, GScreen, ButtonStore
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
    admin_api_config: Dict[str, Any] = {}
    view: cui.appclass.View = cui.appclass.View()
    control: cui.appclass.Control = cui.appclass.Control(_MAIN)

    def __init__(self):
        # MAIN Page
        self.control.app_control._loop = util.create_main_loop(self)
        self.control.app_control._loop.set_alarm_in(1, self._update_clock)

        util.create_application_buttons(self)

        self.refresh_main_menu()

        # Password Dialog
        self._prepare_password_dialog()

        # Read in logging units
        self._load_journal_units()

        # Log file viewer
        self.log_file_content: List[str] = [
            T_("If this is not that what you expected to see, you probably have insufficient "
               "permissions."),
        ]
        self._prepare_log_viewer("NetworkManager", self.control.log_control.log_line_count)

        self._prepare_timesyncd_config()

        # some settings
        MultiMenuItem.application = self
        GButton.application = self

    def refresh_main_menu(self):
        """Refresh main menu."""
        # The common menu description column
        self.view.top_main_menu.menu_description = urwid.Pile(
            [
                GText(T_("Main Menu"), urwid.CENTER),
                GText(T_("Here you can do the main actions"), urwid.LEFT),
            ]
        )
        # Main Menu
        items = {
            T_("Language configuration"): urwid.Pile(
                [
                    GText(T_("Language"), urwid.CENTER),
                    GText(""),
                    GText(
                        T_("Opens the yast2 configurator for setting language settings.")
                    ),
                ]
            ),
            T_("Change system password"): urwid.Pile(
                [
                    GText(T_("Password change"), urwid.CENTER),
                    GText(""),
                    GText(T_("Opens a dialog for changing the password of the system root user. When a password is set, you can login via ssh and rerun grommunio-cui.")),
                ]
            ),
            T_("Network interface configuration"): urwid.Pile(
                [
                    GText(T_("Configuration of network"), urwid.CENTER),
                    GText(""),
                    GText(
                        T_("Opens the yast2 configurator for setting up devices, interfaces, IP addresses, DNS and more.")
                    ),
                ]
            ),
            T_("Timezone configuration"): urwid.Pile(
                [
                    GText(T_("Timezone"), urwid.CENTER),
                    GText(""),
                    GText(
                        T_("Opens the yast2 configurator for setting country and timezone settings.")
                    ),
                ]
            ),
            T_("timesyncd configuration"): urwid.Pile(
                [
                    GText(T_("timesyncd"), urwid.CENTER),
                    GText(""),
                    GText(
                        T_("Opens a simple configurator for configuring systemd-timesyncd as a lightweight NTP client for time synchronization.")
                    ),
                ]
            ),
            T_("Select software repositories"): urwid.Pile([
                GText(T_("Software repositories selection"), urwid.CENTER),
                GText(""),
                GText(T_("Opens dialog for choosing software repositories.")),
            ]),
            T_("Update the system"): urwid.Pile([
                GText(T_("System update"), urwid.CENTER),
                GText(""),
                GText(T_("Executes the system package manager for the installation of newer component versions.")),
            ]),
            T_("grommunio setup wizard"): urwid.Pile(
                [
                    GText(T_("Setup wizard"), urwid.CENTER),
                    GText(""),
                    GText(
                        T_("Executes the grommunio-setup script for the initial configuration of grommunio databases, TLS certificates, services and the administration web user interface.")
                    ),
                ]
            ),
            T_("Change admin-web password"): urwid.Pile(
                [
                    GText(T_("Password change"), urwid.CENTER),
                    GText(""),
                    GText(
                        T_("Opens a dialog for changing the password used by the administration web interface.")
                    ),
                ]
            ),
            T_("Terminal"): urwid.Pile(
                [
                    GText(T_("Terminal"), urwid.CENTER),
                    GText(""),
                    GText(
                        T_("Starts terminal for advanced system configuration.")
                    ),
                ]
            ),
            T_("Reboot"): urwid.Pile(
                [GText(T_("Reboot system."), urwid.CENTER), GText(""), GText("")]
            ),
            T_("Shutdown"): urwid.Pile(
                [
                    GText(T_("Shutdown system."), urwid.CENTER),
                    GText(""),
                    GText(T_("Shuts down the system and powers off.")),
                ]
            ),
        }
        if os.getppid() != 1:
            items["Exit"] = urwid.Pile([GText(T_("Exit CUI"), urwid.CENTER)])
        self.main_menu_list = self._prepare_menu_list(items)
        if self.control.app_control.current_window == _MAIN_MENU and self.view.top_main_menu.current_menu_focus > 0:
            off: int = 1
            if self.control.app_control.last_current_window == _MAIN_MENU:
                off = 1
            self.main_menu_list.focus_position = self.view.top_main_menu.current_menu_focus - off
        self.main_menu = self._menu_to_frame(self.main_menu_list)
        if self.control.app_control.current_window == _MAIN_MENU:
            self.control.app_control._loop.widget = self.main_menu
            self.control.app_control._body = self.main_menu

    def prepare_mainscreen(self):
        """Prepare main screen."""
        self.view.header = Header()
        self.view.main_frame = MainFrame(self)
        self.view.header.refresh_header()
        self.view.main_frame.vsplitbox = urwid.Pile(
            [
                ("weight", 50, urwid.AttrMap(self.view.main_frame.main_top, "body")),
                ("weight", 50, self.view.main_frame.main_bottom),
            ]
        )
        self.view.main_footer.footer = urwid.Pile(self.view.main_footer.footer_content)
        frame = urwid.Frame(
            urwid.AttrMap(self.view.main_frame.vsplitbox, "reverse"),
            header=self.view.header.info.header,
            footer=self.view.main_footer.footer,
        )
        self.view.main_frame.mainframe = frame
        self.control.app_control._body = self.view.main_frame.mainframe
        # self.print(T_("Idle"))

    def handle_event(self, event: Any):
        """
        Handles user input to the console UI.

            :param event: A mouse or keyboard input sequence. While the mouse
                event has the form ('mouse press or release', button, column,
                line), the key stroke is represented as is a single key or even
                the represented value like 'enter', 'up', 'down', etc.
            :type: Any
        """
        self.control.app_control.current_event = event
        if isinstance(event, str):
            self._handle_key_event(event)
        elif isinstance(event, tuple):
            self._handle_mouse_event(event)
        self.print(self.control.app_control.current_bottom_info)

    def _handle_key_event(self, event: Any):
        """Handle keyboard event."""
        # event was a key stroke
        key: str = str(event)
        if self.control.log_control.log_finished and self.control.app_control.current_window != _LOG_VIEWER:
            self.control.log_control.log_finished = False
        (func, var) = {
            _MAIN: (self._key_ev_main, key),
            _MESSAGE_BOX: (self._key_ev_mbox, key),
            _INPUT_BOX: (self._key_ev_ibox, key),
            _TERMINAL: (self._key_ev_term, key),
            _PASSWORD: (self._key_ev_pass, key),
            _LOGIN: (self._key_ev_login, key),
            _REBOOT: (self._key_ev_reboot, key),
            _SHUTDOWN: (self._key_ev_shutdown, key),
            _MAIN_MENU: (self._key_ev_mainmenu, key),
            _LOG_VIEWER: (self._key_ev_logview, key),
            _UNSUPPORTED: (self._key_ev_unsupp, key),
            _ADMIN_WEB_PW: (self._key_ev_aapi, key),
            _TIMESYNCD: (self._key_ev_timesyncd, key),
            _REPO_SELECTION: (self._key_ev_repo_selection, key),
            _KEYBOARD_SWITCH: (self._key_ev_kbd_switch, key),
        }.get(self.control.app_control.current_window)
        if var:
            func(var)
        else:
            func()
        self._key_ev_anytime(key)

    def _key_ev_main(self, key):
        """Handle event on mainframe."""
        if key == "f2":
            if util.check_if_password_is_set(getuser()):
                self.view.login_window.login_body.focus_position = (
                    0 if getuser() == "" else 1
                )  # focus on passwd if user detected
                frame: parameter.Frame = parameter.Frame(
                    body=urwid.LineBox(urwid.Padding(urwid.Filler(self.view.login_window.login_body))),
                    header=self.view.login_window.login_header,
                    footer=self.view.login_window.login_footer,
                    focus_part="body",
                )
                self.dialog(frame)
                self.control.app_control.current_window = _LOGIN
            else:
                self._open_main_menu()
        elif key == "l" and not PRODUCTION:
            self._open_main_menu()
        elif key == "tab":
            self.view.main_frame.vsplitbox.focus_position = (
                0 if self.view.main_frame.vsplitbox.focus_position == 1 else 1
            )

    def _key_ev_mbox(self, key):
        """Handle event on message box."""
        if key.endswith("enter") or key == "esc":
            if self.control.app_control.message_box_caller not in (self.control.app_control.current_window, _MESSAGE_BOX):
                self.control.app_control.current_window = self.control.app_control.message_box_caller
                self.control.app_control._body = self.control.app_control._message_box_caller_body
            if self.view.gscreen.old_layout:
                self.view.gscreen.layout = self.view.gscreen.old_layout
            self._reset_layout()
            if self.control.app_control.current_window not in [
                _LOGIN, _MAIN_MENU, _TIMESYNCD, _REPO_SELECTION
            ]:
                if self.control.app_control.key_counter.get(key, 0) < 10:
                    self.control.app_control.key_counter[key] = self.control.app_control.key_counter.get(key, 0) + 1
                    self.handle_event(key)
                else:
                    self.control.app_control.key_counter[key] = 0

    def _key_ev_ibox(self, key):
        """Handle event on input box."""
        self._handle_standard_tab_behaviour(key)
        if key.endswith("enter") or key == "esc":
            if key.lower().endswith("enter"):
                self.control.app_control.last_input_box_value = (
                    self.control.app_control._loop.widget.top_w.base_widget.body.base_widget[
                        1
                    ].edit_text
                )
            else:
                self.control.app_control.last_input_box_value = ""
            self.control.app_control.current_window = self.control.app_control.current_window_input_box
            self.control.app_control._body = self.control.app_control._input_box_caller_body
            if self.view.gscreen.old_layout:
                self.view.gscreen.layout = self.view.gscreen.old_layout
            self._reset_layout()
            self.handle_event(key)

    def _key_ev_term(self, key):
        """Handle event on terminal."""
        self._handle_standard_tab_behaviour(key)
        if key == "f10":
            raise urwid.ExitMainLoop()
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
                pw1 = self.control.app_control._loop.widget.top_w.base_widget.body.base_widget[
                    2
                ].edit_text
                pw2 = self.control.app_control._loop.widget.top_w.base_widget.body.base_widget[
                    4
                ].edit_text
                if pw1 == pw2:
                    res = util.reset_system_passwd(pw1)
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
            self.control.app_control.current_window = self.control.app_control.input_box_caller
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
        if key.endswith("enter") and self.control.app_control.last_pressed_button.lower().endswith(
            "ok"
        ):
            self.control.app_control._loop.stop()
            self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.old_termios)
            os.system("reboot")
            raise urwid.ExitMainLoop()
        self.control.app_control.current_window = _MAIN_MENU

    def _key_ev_shutdown(self, key):
        """Handle event on shutdown menu."""
        # Restore cursor etc. before going off.
        if key.endswith("enter") and self.control.app_control.last_pressed_button.lower().endswith(
            "ok"
        ):
            self.control.app_control._loop.stop()
            self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.old_termios)
            os.system("poweroff")
            raise urwid.ExitMainLoop()
        self.control.app_control.current_window = _MAIN_MENU

    def _key_ev_mainmenu(self, key):
        """Handle event on main menu menu."""
        def menu_language():
            pre = cui.parser.ConfigParser(infile='/etc/locale.conf')
            self._run_yast_module("language")
            post = cui.parser.ConfigParser(infile='/etc/locale.conf')
            if pre != post:
                util.T_ = util.restart_gui()

        def exit_main_loop():
            raise urwid.ExitMainLoop()

        menu_selected: int = self._handle_standard_menu_behaviour(
            self.main_menu_list, key, self.main_menu.base_widget.body[1]
        )
        if key.endswith("enter") or key in range(ord("1"), ord("9") + 1):
            (func, val) = {
                1: (menu_language, None),
                2: (self._open_change_password, None),
                3: (self._run_yast_module, "lan"),
                4: (self._run_yast_module, "timezone"),
                5: (self._open_timesyncd_conf, None),
                6: (self._open_repo_conf, None),
                7: (self._run_zypper, "up"),
                8: (self._open_setup_wizard, None),
                9: (self._open_reset_aapi_pw, None),
                10: (self._open_terminal, None),
                11: (self._reboot_confirm, None),
                12: (self._shutdown_confirm, None),
                13: (exit_main_loop, None),
            }.get(menu_selected)
            if val:
                func(val)
            else:
                func()
        elif key == "esc":
            self._open_mainframe()

    def _key_ev_logview(self, key):
        """Handle event on log viewer menu."""
        if key in ["ctrl f1", "H", "h", "L", "l", "esc"]:
            self.control.app_control.current_window = self.control.app_control.log_file_caller
            self.control.app_control._body = self.control.app_control._log_file_caller_body
            self._reset_layout()
            self.control.log_control.log_finished = True
        elif key in ["left", "right", "+", "-"]:
            line_offset = {
                "-": -100,
                "+": +100,
            }.get(key, 0)
            self.control.log_control.log_line_count += line_offset
            unit_offset = {
                "left": -1,
                "right": +1,
            }.get(key, 0)
            self.control.log_control.current_log_unit += unit_offset
            self.control.log_control.log_line_count = max(min(self.control.log_control.log_line_count, 10000), 200)
            self.control.log_control.current_log_unit = max(min(self.control.log_control.current_log_unit, len(self.control.log_control.log_units) - 1), 0)
            self._open_log_viewer(
                self._get_log_unit_by_id(self.control.log_control.current_log_unit),
                self.control.log_control.log_line_count,
            )
        elif (
            self.control.log_control._hidden_pos < len(_UNSUPPORTED)
            and key == _UNSUPPORTED.lower()[self.control.log_control._hidden_pos]
        ):
            self.control.log_control._hidden_input += key
            self.control.log_control._hidden_pos += 1
            if self.control.log_control._hidden_input == _UNSUPPORTED.lower():
                self._open_log_viewer("syslog")
        else:
            self.control.log_control._hidden_input = ""
            self.control.log_control._hidden_pos = 0

    def _key_ev_unsupp(self, key):
        """Handle event on unsupported."""
        if key in ["ctrl d", "esc", "ctrl f1", "H", "h", "l", "L"]:
            self.control.app_control.current_window = self.control.app_control.log_file_caller
            self.control.app_control._body = self.control.app_control._log_file_caller_body
            self.control.log_control.log_finished = True
            self._reset_layout()

    def _key_ev_anytime(self, key):
        """Handle event at anytime."""
        if key in ["f10", "Q"]:
            raise urwid.ExitMainLoop()
        if key == "f4" and len(self.view.header.get_authorized_options()) > 0:
            self._open_main_menu()
        elif key in ("f1", "c"):
            self._switch_next_colormode()
        elif key == "f5":
            self._open_keyboard_selection_menu()
        elif (
            key in ["ctrl f1", "H", "h", "L", "l"]
            and self.control.app_control.current_window != _LOG_VIEWER
            and self.control.app_control.current_window != _UNSUPPORTED
            and not self.control.log_control.log_finished
        ):
            self._open_log_viewer("gromox-http", self.control.log_control.log_line_count)

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
                pw1 = self.control.app_control._loop.widget.top_w.base_widget.body.base_widget[
                    2
                ].edit_text
                pw2 = self.control.app_control._loop.widget.top_w.base_widget.body.base_widget[
                    4
                ].edit_text
                if pw1 == pw2:
                    res = util.reset_aapi_passwd(pw1)
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
            self.control.app_control.current_window = self.control.app_control.input_box_caller
            self.message_box(
                parameter.MsgBoxParams(
                    T_(f"Admin password reset {success_msg}!"),
                    T_("Admin password reset"),
                ),
                size=parameter.Size(height=10)
            )

    def _key_ev_repo_selection(self, key):
        """Handle event on repository selection menu."""
        height = 10
        repo_res = self._init_repo_selection(key, height)
        if repo_res.get("button_type", None) in ("ok", "save"):
            updateable, url = util.check_repo_dialog(self, height)
            if updateable:
                repo_res.get("config", None)['grommunio']['baseurl'] = f'https://{url}'
                repo_res.get("config", None)['grommunio']['type'] = 'rpm-md'
                config2 = cui.parser.ConfigParser(infile=repo_res.get("repofile", None))
                repo_res.get("config", None).write()
                if repo_res.get("config", None) == config2:
                    self.message_box(
                        parameter.MsgBoxParams(
                            T_('The repo file has not been changed.')
                        ),
                        size=parameter.Size(height=height-1)
                    )
                else:
                    self._process_changed_repo_config(height, repo_res)

    def _process_changed_repo_config(self, height, repo_res):
        header = GText(T_("One moment, please ..."))
        footer = GText(T_('Fetching GPG-KEY file and refreshing '
                          'repositories. This may take a while ...'))
        self.control.app_control.progressbar = self._create_progress_bar()
        pad = urwid.Padding(self.control.app_control.progressbar)  # do not use pg! use self.control.app_control.progressbar.
        fil = urwid.Filler(pad)
        linebox = urwid.LineBox(fil)
        frame: parameter.Frame = parameter.Frame(linebox, header, footer)
        self.dialog(frame)
        self._draw_progress(20)
        res: Response = requests.get(repo_res.get("keyurl", None))
        got_keyfile: bool = False
        if res.status_code == 200:
            self._draw_progress(30)
            tmp = Path(repo_res.get("keyfile", None))
            with tmp.open('w', encoding="utf-8") as file:
                file.write(res.content.decode())
            self._draw_progress(40)
            with subprocess.Popen(
                    ["rpm", "--import", repo_res.get("keyfile", None)],
                    stderr=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
            ) as ret_code_rpm:
                if ret_code_rpm.wait() == 0:
                    self._draw_progress(60)
                    with subprocess.Popen(
                            ["zypper", "--non-interactive", "refresh"],
                            stderr=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                    ) as ret_code_zypper:
                        if ret_code_zypper.wait() == 0:
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
                size=parameter.Size(height=height + 1)
            )

    def _init_repo_selection(self, key, height):
        self._handle_standard_tab_behaviour(key)
        keyurl = 'https://download.grommunio.com/RPM-GPG-KEY-grommunio'
        keyfile = '/tmp/RPM-GPG-KEY-grommunio'
        repofile = '/etc/zypp/repos.d/grommunio.repo'
        config = cui.parser.ConfigParser(infile=repofile)
        # config.filename = repofile
        if not config.get('grommunio'):
            config['grommunio'] = {}
            config['grommunio']['enabled'] = 1
            config['grommunio']['auorefresh'] = 1
        button_type = util.get_button_type(
            key,
            self._open_main_menu,
            self.message_box,
            T_('Software repository selection has been canceled.'),
            size=parameter.Size(height=height)
        )
        return {
            "button_type": button_type,
            "config": config,
            "keyfile": keyfile,
            "keyurl": keyurl,
            "repofile": repofile
        }

    def _key_ev_timesyncd(self, key):
        """Handle event on timesyncd menu."""
        self._handle_standard_tab_behaviour(key)
        success_msg = T_("was successful")
        button_type = util.get_button_type(
            key,
            self._open_main_menu,
            self.message_box,
            parameter.MsgBoxParams(
                T_(f"Timesyncd configuration change {success_msg}!"),
                T_("Timesyncd Configuration"),
            ),
            size=parameter.Size(height=10)
        )
        success_msg = T_("NOTHING")
        if button_type == "ok":
            # Save config and return to mainmenu
            self.control.menu_control.timesyncd_vars["NTP"] = self.timesyncd_body.base_widget[
                1
            ].edit_text
            self.control.menu_control.timesyncd_vars[
                "FallbackNTP"
            ] = self.timesyncd_body.base_widget[2].edit_text
            util.lineconfig_write(
                "/etc/systemd/timesyncd.conf", self.control.menu_control.timesyncd_vars
            )
            with subprocess.Popen(
                ["timedatectl", "set-ntp", "true"],
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
            ) as ret_code:
                res = ret_code.wait() == 0
                success_msg = T_("was successful")
                if not res:
                    success_msg = T_("failed")
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
            self.control.menu_control.keyboard_switch_body, key
        )
        stay = False
        if (
            key.lower().endswith("enter") and key.lower().startswith("hidden")
        ) or key.lower() in ["space"]:
            kbd = self.control.menu_control.keyboard_content[menu_id - 1]
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
        if self.control.app_control.last_current_window in [_MAIN_MENU]:
            self._open_main_menu()
        else:
            self._open_mainframe()

    def _load_journal_units(self):
        exe = "/usr/sbin/grommunio-admin"
        out = ""
        if Path(exe).exists():
            with subprocess.Popen(
                [exe, "config", "dump"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as process:
                out = process.communicate()[0]
            if isinstance(out, bytes):
                out = out.decode()
        if out == "":
            self.admin_api_config = {
                "logs": {"gromox-http": {"source": "gromox-http.service"}}
            }
        else:
            self.admin_api_config = yaml.load(out, Loader=SafeLoader)
        self.control.log_control.log_units = self.admin_api_config.get(
            "logs", {"gromox-http": {"source": "gromox-http.service"}}
        )
        for i, k in enumerate(self.control.log_control.log_units.keys()):
            if k == "Gromox http":
                self.control.log_control.current_log_unit = i
                break

    def _get_logging_formatter(self) -> str:
        """Get logging formatter."""
        default = (
            self.admin_api_config.get("logging", {})
            .get("formatters", {})
            .get("mi-default", {})
        )
        return default.get(
            "format",
            '[%(asctime)s] [%(levelname)s] (%(module)s): "%(message)s"',
        )

    def _get_log_unit_by_id(self, idx) -> str:
        """Get logging unit by idx."""
        for i, k in enumerate(self.control.log_control.log_units.keys()):
            if idx == i:
                return self.control.log_control.log_units[k].get("source")[:-8]
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

    def handle_click(self, creator: urwid.Widget, option: bool = False):
        """
        Handles urwid.RadioButton clicks.

        :param creator: The widget creating calling the function.
        :param option: On if True, off otherwise.
        """
        self.print(T_(f"Creator ({creator}) clicked {option}."))

    def _open_terminal(self):
        """
        Jump to a shell prompt
        """
        self.control.app_control._loop.stop()
        self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.old_termios)
        print("\x1b[K")
        print(
            "\x1b[K \x1b[36m▼\x1b[0m",
            T_("To return to the CUI, issue the `exit` command.")
        )
        print("\x1b[J")
        # We have no environment, and so need su instead of just bash to launch
        # a proper PAM session and set $HOME, etc.
        os.system("/usr/bin/su -l")
        self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.blank_termios)
        self.control.app_control._loop.start()

    def _reboot_confirm(self):
        """Confirm reboot."""
        msg = T_("Are you sure?\n")
        msg += T_("After pressing OK, ")
        msg += T_("the system will reboot.")
        title = T_("Reboot")
        self.control.app_control.current_window = _REBOOT
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
        self.control.app_control.current_window = _SHUTDOWN
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
        self.control.app_control.input_box_caller = self.control.app_control.current_window
        self.control.app_control._input_box_caller_body = self.control.app_control._loop.widget
        self.control.app_control.current_window = current_window
        body = urwid.LineBox(
            urwid.Padding(
                urwid.Filler(
                    urwid.Pile(
                        [
                            GText(msg, urwid.CENTER),
                            urwid.Divider(),
                            GEdit("", input_text, False, urwid.CENTER, mask=mask),
                            urwid.Divider(),
                            GEdit("", input_text, False, urwid.CENTER, mask=mask),
                        ]
                    ),
                    urwid.TOP,
                )
            )
        )
        footer = self._create_footer(True, True)
        if title is None:
            title = "Input expected"
        frame: parameter.Frame = parameter.Frame(
            body=body,
            header=GText(title, urwid.CENTER),
            footer=footer,
            focus_part="body",
        )
        alignment: parameter.Alignment = parameter.Alignment(urwid.CENTER, urwid.MIDDLE)
        size: parameter.Size = parameter.Size(width, height)
        self.dialog(frame, alignment=alignment, size=size)

    def _prepare_password_dialog(self):
        """Prepare the QuickNDirty password dialog."""
        self.password = urwid.Terminal(["passwd"])
        self.password_frame = urwid.LineBox(
            urwid.Pile(
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
        for uname in self.control.log_control.log_units.keys():
            src = self.control.log_control.log_units[uname].get("source")
            if src == unitname:
                found = True
            else:
                if not found:
                    pre.append(src[:-8])
                else:
                    post.append(src[:-8])
        header = (
            T_("Use the arrow keys to switch between logfiles. <urwid.LEFT> and <RIGHT> switch the logfile, while <+> and <-> changes the line count to view. (%s)") % self.control.log_control.log_line_count
        )
        self.control.log_control.log_viewer = urwid.LineBox(
            urwid.AttrMap(
                urwid.Pile(
                    [
                        (
                            2,
                            urwid.Filler(
                                urwid.Padding(
                                    GText(("body", header), urwid.CENTER),
                                    urwid.CENTER,
                                    urwid.RELATIVE_100,
                                )
                            ),
                        ),
                        (
                            1,
                            urwid.Columns(
                                [
                                    urwid.Filler(
                                        GText(
                                            [
                                                ("body", "*** "),
                                                (
                                                    "body",
                                                    " ".join(pre[-3:]),
                                                ),
                                                ("reverse", cur),
                                                (
                                                    "body",
                                                    " ".join(post[:3]),
                                                ),
                                                ("body", " ***"),
                                            ],
                                            urwid.CENTER,
                                        )
                                    )
                                ]
                            ),
                        ),
                        urwid.AttrMap(
                            ScrollBar(
                                Scrollable(
                                    urwid.Pile(
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
        if self.control.app_control.current_window != _LOG_VIEWER:
            self.control.app_control.log_file_caller = self.control.app_control.current_window
            self.control.app_control._log_file_caller_body = self.control.app_control._body
            self.control.app_control.current_window = _LOG_VIEWER
        self.print(T_("Log file viewer has to open file {%s} ...") % unit)
        self._prepare_log_viewer(unit, lines)
        self.control.app_control._body = self.control.log_control.log_viewer
        self.control.app_control._loop.widget = self.control.app_control._body

    def _run_yast_module(self, modulename: str):
        """Run yast module `modulename`."""
        self.control.app_control._loop.stop()
        self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.old_termios)
        print("\x1b[K")
        print(
            "\x1b[K \x1b[36m▼\x1b[0m",
            T_("Please wait while `yast2 %s` is being run.") % modulename
        )
        print("\x1b[J")
        os.system(f"yast2 {modulename}")
        self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.blank_termios)
        self.control.app_control._loop.start()

    def _run_zypper(self, subcmd: str):
        """Run zypper modul `subcmd`."""
        self.control.app_control._loop.stop()
        self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.old_termios)
        print("\x1b[K")
        print("\x1b[K \x1b[36m▼\x1b[0m Please wait while zypper is invoked.")
        print("\x1b[J")
        os.system(f"zypper {subcmd}")
        input("\n \x1b[36m▼\x1b[0m Press ENTER to return to the CUI.")
        self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.blank_termios)
        self.control.app_control._loop.start()

    def _open_reset_aapi_pw(self):
        """Open reset admin-API password."""
        title = T_("admin-web Password Change")
        msg = T_("Enter the new admin-web password:")
        self._create_password_dialog(msg, title, _ADMIN_WEB_PW)

    def _open_timesyncd_conf(self):
        """Open timesyncd configuration form."""
        self._reset_layout()
        self.print(T_("Opening timesyncd configuration"))
        self.control.app_control.current_window = _TIMESYNCD
        header = urwid.AttrMap(GText(T_("Timesyncd Configuration"), urwid.CENTER), "header")
        self._prepare_timesyncd_config()
        self._open_conf_dialog(self.timesyncd_body, header, [self.view.button_store.ok_button, self.view.button_store.cancel_button])

    def _open_conf_dialog(
            self,
            body_widget: urwid.Widget,
            header: Any,
            footer_buttons: List[Tuple[int, GBoxButton]]
    ):
        footer = urwid.AttrMap(
            urwid.Columns(footer_buttons), "buttonbar"
        )
        frame: parameter.Frame = parameter.Frame(
            body=urwid.AttrMap(body_widget, "body"),
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
        self.control.menu_control.timesyncd_vars = util.lineconfig_read(
            "/etc/systemd/timesyncd.conf"
        )
        ntp_from_file = self.control.menu_control.timesyncd_vars.get("NTP", " ".join(ntp_server))
        fallback_from_file = self.control.menu_control.timesyncd_vars.get(
            "FallbackNTP", " ".join(fallback_server)
        )
        ntp_server = ntp_from_file.split(" ")
        fallback_server = fallback_from_file.split(" ")
        text = T_("Insert the NTP servers separated by <urwid.SPACE> char.")
        self.timesyncd_body = urwid.LineBox(
            urwid.Padding(
                urwid.Filler(
                    urwid.Pile(
                        [
                            GText(text, urwid.LEFT, wrap=urwid.SPACE),
                            GEdit(
                                (15, "NTP: "), " ".join(ntp_server), wrap=urwid.SPACE
                            ),
                            GEdit(
                                (15, "FallbackNTP: "),
                                " ".join(fallback_server),
                                wrap=urwid.SPACE,
                            ),
                        ]
                    ),
                    urwid.TOP,
                )
            )
        )

    def _open_repo_conf(self):
        """Open repository configuration form."""
        self._reset_layout()
        self.print(T_("Opening repository selection"))
        self.control.app_control.current_window = _REPO_SELECTION
        header = urwid.AttrMap(GText(T_("Software repository selection"), urwid.CENTER), "header")
        self._prepare_repo_config()
        self._open_conf_dialog(self.control.menu_control.repo_selection_body, header, [self.view.button_store.save_button, self.view.button_store.cancel_button])

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
        self.control.menu_control.repo_selection_body = urwid.LineBox(urwid.Padding(urwid.Filler(urwid.Pile(body_content), urwid.TOP)))

    def _open_setup_wizard(self):
        """Open grommunio setup wizard."""
        self.control.app_control._loop.stop()
        self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.old_termios)
        if Path("/usr/sbin/grommunio-setup").exists():
            os.system("/usr/sbin/grommunio-setup")
        else:
            os.system("/usr/sbin/grammm-setup")
        self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.blank_termios)
        self.control.app_control._loop.start()

    def _open_main_menu(self):
        """
        Opens amin menu,
        """
        self._reset_layout()
        self.print(T_("Login successful"))
        self.control.app_control.current_window = _MAIN_MENU
        self.view.header.set_authorized_options(T_(", <F4> for Main-Menu"))
        self.prepare_mainscreen()
        self.control.app_control._body = self.main_menu
        self.control.app_control._loop.widget = self.control.app_control._body

    def _open_mainframe(self):
        """
        Opens main window. (Welcome screen)
        """
        self._reset_layout()
        self.print(T_("Returning to main screen."))
        self.control.app_control.current_window = _MAIN
        self.prepare_mainscreen()
        self.control.app_control._loop.widget = self.control.app_control._body

    def _check_login(self):
        """
        Checks login data and switch to authenticate on if successful.
        """
        if self.view.button_store.user_edit.get_edit_text() != getuser() and os.getegid() != 0:
            self.message_box(
                parameter.MsgBoxParams(T_("You need root privileges to use another user.")),
                size=parameter.Size(height=10)
            )
            return
        msg = T_("checking user %s with pass ") % self.view.button_store.user_edit.get_edit_text()
        if self.control.app_control.current_window == _LOGIN:
            if util.authenticate_user(
                self.view.button_store.user_edit.get_edit_text(), self.view.button_store.pass_edit.get_edit_text()
            ):
                self.view.button_store.pass_edit.set_edit_text("")
                self._open_main_menu()
            else:
                self.message_box(
                    parameter.MsgBoxParams(
                        T_("Incorrect credentials. Access denied!"),
                        T_("Password verification"),
                    )
                )
                self.print(T_("Login wrong! (%s)") % msg)

    def _press_button(self, button: urwid.Widget, *args, **kwargs):
        """
        Handles general events if a button is pressed.

        :param button: The button been clicked.
        """
        label: str = T_("UNKNOWN LABEL")
        if isinstance(button, (GButton, urwid.RadioButton, WidgetDrawer)):
            label = button.label
        self.control.app_control.last_pressed_button = label
        if self.control.app_control.current_window not in [_MAIN]:
            self.print(
                f"{self.__class__}.press_button(button={button}, "
                f"*args={args}, kwargs={kwargs})"
            )
            self.handle_event(f"{label} enter")

    def _prepare_menu_list(self, items: Dict[str, urwid.Widget]) -> urwid.ListBox:
        """
        Prepare general menu list.

        :param items: A dictionary of widgets representing the menu items.
        :return: urwid.ListBox containing menu items.
        """
        menu_items: List[MenuItem] = self._create_menu_items(items)
        return urwid.ListBox(urwid.SimpleFocusListWalker(menu_items))

    def _menu_to_frame(self, listbox: urwid.ListBox):
        """Put menu(urwid.ListBox) into a urwid.Frame."""
        fopos: int = listbox.focus_position
        menu = urwid.Columns([
            urwid.AttrMap(listbox, "body"), urwid.AttrMap(urwid.ListBox(urwid.SimpleListWalker([
                listbox.body[fopos].original_widget.get_description()
            ])), "reverse",),
        ])
        return urwid.Frame(menu, header=self.view.header.info.header, footer=self.view.main_footer.footer)

    def _switch_next_colormode(self):
        """Switch to next color scheme."""
        original = self.view.header.get_colormode()
        color_name = util.get_next_palette_name(original)
        palette = util.get_palette(color_name)
        show_next = color_name
        self.view.header.set_colormode(show_next)
        self.view.header.refresh_header()
        self.control.app_control._loop.screen.register_palette(palette)
        self.control.app_control._loop.screen.clear()

    def _set_kbd_layout(self, layout):
        """Set and save selected keyboard layout."""
        # Do read the file again so newly added keys do not get lost
        file = "/etc/vconsole.conf"
        var = util.minishell_read(file)
        var["KEYMAP"] = layout
        util.minishell_write(file, var)
        os.system("systemctl restart systemd-vconsole-setup")
        self.view.header.set_kbdlayout(layout)
        self.view.header.refresh_head_text()

    def _open_keyboard_selection_menu(self):
        """Open keyboard selection menu form."""
        self._reset_layout()
        self.print(T_("Opening keyboard configuration"))
        self.control.app_control.last_current_window = self.control.app_control.current_window
        self.control.app_control.current_window = _KEYBOARD_SWITCH
        header = None
        self._prepare_kbd_config()
        footer = None
        frame: parameter.Frame = parameter.Frame(
            body=urwid.AttrMap(self.control.menu_control.keyboard_switch_body, "body"),
            header=header,
            footer=footer,
            focus_part="body",
        )
        alignment: parameter.Alignment = parameter.Alignment(urwid.CENTER, urwid.MIDDLE)
        size: parameter.Size = parameter.Size(30, 10)
        self.dialog(frame, alignment=alignment, size=size)

    def _prepare_kbd_config(self):
        """Prepare keyboard config form."""
        def sub_press(button, is_set=True):
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
        keyboard_list = [util.get_current_kbdlayout()]
        _ = [
            keyboard_list.append(kbd)
            for kbd in sorted(keyboards)
            if kbd != self.view.header.get_kbdlayout()
        ]
        self.control.menu_control.keyboard_rb = []
        self.control.menu_control.keyboard_content = []
        for kbd in keyboard_list:
            self.control.menu_control.keyboard_content.append(
                urwid.AttrMap(
                    urwid.RadioButton(
                        self.control.menu_control.keyboard_rb, kbd, "first True", sub_press
                    ),
                    "focus" if kbd == self.view.header.get_kbdlayout() else "selectable",
                )
            )
        self.control.menu_control.keyboard_list = ScrollBar(Scrollable(urwid.Pile(self.control.menu_control.keyboard_content)))
        self.control.menu_control.keyboard_switch_body = self.control.menu_control.keyboard_list

    def redraw(self):
        """
        Redraws screen.
        """
        if getattr(self.control.app_control, "_loop", None):
            if self.control.app_control._loop:
                self.control.app_control._loop.draw_screen()

    def _reset_layout(self):
        """
        Resets the console UI to the default layout
        """

        if getattr(self.control.app_control, "_loop", None):
            self.control.app_control._loop.widget = self.control.app_control._body
            self.control.app_control._loop.draw_screen()

    def _create_menu_items(self, items: Dict[str, urwid.Widget]) -> List[MenuItem]:
        """
        Takes a dictionary with menu labels as keys and widget(lists) as
        content and creates a list of menu items.

        :param items: Dictionary in the form {'label': urwid.Widget}.
        :return: List of MenuItems.
        """
        menu_items: List[MenuItem] = []
        for idx, caption in enumerate(items.keys(), 1):
            item = MenuItem(idx, caption, items.get(caption), self)
            urwid.connect_signal(item, "activate", self.handle_event)
            menu_items.append(urwid.AttrMap(item, "selectable", "focus"))
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
                ("", f"({self.control.app_control.current_event})"),
                ("", f" on {self.control.app_control.current_window}"),
            ]
        )
        footer_elements = [clock, footerbar, avg_load]
        if not self.view.gscreen.quiet:
            footer_elements += [gstring]
        content = []
        rest = []
        for elem in footer_elements:
            if glen([content, elem]) < self.view.gscreen.screen.get_cols_rows()[0]:
                content.append(elem)
            else:
                rest.append(elem)
        col_list = [urwid.Columns([(len(elem), elem) for elem in content])]
        if len(rest) > 0:
            col_list += [urwid.Columns([(len(elem), elem) for elem in rest])]
        if self.view.gscreen.debug:
            col_list += [urwid.Columns([gdebug])]
        self.view.main_footer.footer_content = col_list
        self.view.main_footer.footer = urwid.AttrMap(urwid.Pile(self.view.main_footer.footer_content), "footer")
        swap_widget = getattr(self.control.app_control, "_body", None)
        if swap_widget:
            swap_widget.footer = self.view.main_footer.footer
            self.redraw()
        self.control.app_control.current_bottom_info = string

    def _create_progress_bar(self, max_progress=100):
        """Create progressbar"""
        self.control.app_control.progressbar = urwid.ProgressBar('PB.normal', 'PB.complete', 0, max_progress, 'PB.satt')
        return self.control.app_control.progressbar

    def _draw_progress(self, progress, max_progress=100):
        """Draw progress at progressbar"""
        # completion = float(float(progress)/float(max_progress))
        # self.control.app_control.progressbar.set_completion(completion)
        time.sleep(0.1)
        self.control.app_control.progressbar.done = max_progress
        self.control.app_control.progressbar.current = progress
        if progress == max_progress:
            self._reset_layout()
        self.control.app_control._loop.draw_screen()

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

            elif self.control.app_control.current_window == _MESSAGE_BOX:
                if key.endswith('enter') or key == 'esc':
                    self.control.app_control.current_window = self.control.app_control.message_box_caller
                    self.control.app_control._body = self.control.app_control._message_box_caller_body
                    self.reset_layout()

        Args:
            @param mb_params: Messagebox parameters like msg, title and modal.
            @param alignment: The alignment in align and valign.
            @param size: The size in width and height.
            @param view_buttons: The viewed buttons ok or cancel.
        """
        if self.control.app_control.current_window != _MESSAGE_BOX:
            self.control.app_control.message_box_caller = self.control.app_control.current_window
            self.control.app_control._message_box_caller_body = self.control.app_control._loop.widget
            self.control.app_control.current_window = _MESSAGE_BOX
        body = urwid.LineBox(urwid.Padding(urwid.Filler(urwid.Pile([GText(mb_params.msg, urwid.CENTER)]), urwid.TOP)))
        footer = self._create_footer(view_buttons.view_ok, view_buttons.view_cancel)

        if mb_params.title is None:
            title = T_("Message")
        else:
            title = mb_params.title
        frame: parameter.Frame = parameter.Frame(
            body=body,
            header=GText(title, urwid.CENTER),
            footer=footer,
            focus_part="footer",
        )
        self.dialog(frame, alignment=alignment, size=size, modal=mb_params.modal)

    def input_box(
            self,
            ib_params: parameter.InputBoxParams = parameter.InputBoxParams(None, None, "", False, None, True),
            alignment: parameter.Alignment = parameter.Alignment(urwid.CENTER, urwid.MIDDLE),
            size: parameter.Size = parameter.Size(45, 9),
            view_buttons: parameter.ViewOkCancel = parameter.ViewOkCancel(True, False)
    ):
        """Creates an input box dialog with an optional title and a default
        value.
        The message also can be a list of urwid formatted tuples.

        To use the box as standard input box always returning to it's parent,
        then you have to implement something like this in the event handler:
        (f.e. **self**.handle_event) and you MUST set
        the self.control.app_control.app_control.current_window_input_box

            self.control.app_control.app_control.current_window_input_box = _ANY_OF_YOUR_CURRENT_WINDOWS
            self.input_box('Y/n', 'Question', 'yes')

            # and later on event handling
            elif self.control.app_control.current_window == _ANY_OF_YOUR_CURRENT_WINDOWS:
                if key.endswith('enter') or key == 'esc':
                    self.control.app_control.current_window = self.control.app_control.input_box_caller  # here you
                                         # have to set the current window

        Args:
            @param ib_params: Messagebox parameters like msg, title and modal and also
                input_text: Default text as input text.
                multiline: If True then inputs can have more than one line.
                mask: hide text entered by this character. If None, mask will
                 be disabled.
            @param alignment: The alignment in align and valign.
            @param size: The size in width and height.
            @param view_buttons: The viewed buttons ok or cancel.
        """
        self.control.app_control.input_box_caller = self.control.app_control.current_window
        self.control.app_control._input_box_caller_body = self.control.app_control._loop.widget
        self.control.app_control.current_window = _INPUT_BOX
        body = urwid.LineBox(
            urwid.Padding(
                urwid.Filler(
                    urwid.Pile(
                        [
                            GText(ib_params.msg, urwid.CENTER),
                            GEdit(
                                "", ib_params.input_text, ib_params.multiline, urwid.CENTER, mask=ib_params.mask
                            ),
                        ]
                    ),
                    urwid.TOP,
                )
            )
        )
        footer = self._create_footer(view_buttons.view_ok, view_buttons.view_cancel)

        if ib_params.title is None:
            title = T_("Input expected")
        else:
            title = ib_params.title
        frame: parameter.Frame = parameter.Frame(
            body=body,
            header=GText(title, urwid.CENTER),
            footer=footer,
            focus_part="body",
        )
        self.dialog(frame, alignment=alignment, size=size, modal=ib_params.modal)

    def _create_footer(self, view_ok: bool = True, view_cancel: bool = False):
        """Create and return footer."""
        cols = [("weight", 1, GText(""))]
        if view_ok:
            cols += [
                (
                    "weight",
                    1,
                    urwid.Columns(
                        [
                            ("weight", 1, GText("")),
                            self.view.button_store.ok_button,
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
                    urwid.Columns(
                        [
                            ("weight", 1, GText("")),
                            self.view.button_store.cancel_button,
                            ("weight", 1, GText("")),
                        ]
                    ),
                )
            ]
        cols += [("weight", 1, GText(""))]
        footer = urwid.AttrMap(urwid.Columns(cols), "buttonbar")
        return footer

    def get_focused_menu(self, menu: urwid.ListBox, event: Any) -> int:
        """
        Returns id of focused menu item. Returns current id on enter or 1-9 or
        click, and returns the next id if
        key is up or down.

        :param menu: The menu from which you want to know the id.
        :type: urwid.ListBox
        :param event: The event passed to the menu.
        :type: Any
        :returns: The id of the selected menu item. (>=1)
        :rtype: int
        """
        self.view.top_main_menu.current_menu_focus = super().get_focused_menu(
            menu, event
        )
        if not self.view.top_main_menu.last_menu_focus == self.view.top_main_menu.current_menu_focus:
            cid: int = self.view.top_main_menu.last_menu_focus - 1
            nid: int = self.view.top_main_menu.current_menu_focus - 1
            current_widget: urwid.Widget = menu.body[cid].base_widget
            next_widget: urwid.Widget = menu.body[nid].base_widget
            if isinstance(current_widget, MultiMenuItem) and isinstance(next_widget, MultiMenuItem):
                cmmi: MultiMenuItem = current_widget
                nmmi: MultiMenuItem = next_widget
                cmmi.mark_as_dirty()
                nmmi.mark_as_dirty()
                nmmi.set_focus()
                cmmi.refresh_content()
        return self.view.top_main_menu.current_menu_focus

    def _handle_standard_menu_behaviour(
        self, menu: urwid.ListBox, event: Any, description_box: urwid.ListBox = None
    ) -> int:
        """
        Handles standard menu behaviour and returns the focused id, if any.

        :param menu: The menu to be handled.
        :param event: The event to be handled.
        :param description_box: The urwid.ListBox containing the menu content that
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
            if self.view.gscreen.layout.focus_position == "body":
                self.view.gscreen.layout.focus_position = "footer"
            elif self.view.gscreen.layout.focus_position == "footer":
                self.view.gscreen.layout.focus_position = "body"

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
                    and self.view.gscreen.layout.focus_part == 'footer':
                switch_body_footer()
            if current >= last and key in bottom_keys \
                    and self.view.gscreen.layout.focus_part == 'body':
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
                    new_focus += move
        # self.print(f"key is {key}")
        if key.endswith("tab") or key.endswith("down") or key.endswith('up'):
            current_part = self.view.gscreen.layout.focus_part
            if current_part == 'body':
                jump_part(self.view.gscreen.layout.body)
            elif current_part == 'footer':
                jump_part(self.view.gscreen.layout.footer)

    def set_debug(self, yes: bool):
        """
        Sets debug mode on or off.

        :param yes: True for on and False for off.
        """
        self.view.gscreen.debug = yes

    def _update_clock(self, cb_loop: urwid.MainLoop, data: Any = None):
        """
        Updates taskbar every second.

        :param cb_loop: The event loop calling next update_clock()
        :param data: Optional user data
        """
        self.print(self.control.app_control.current_bottom_info)
        cb_loop.set_alarm_in(1, self._update_clock, data)

    def start(self):
        """
        Starts the console UI
        """
        # set_trace(term_size=(129, 18))
        # set_trace()
        self.control.app_control._loop.run()
        if self.view.gscreen.old_termios is not None:
            self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.old_termios)

    def dialog(
            self, frame: parameter.Frame,
            alignment: parameter.Alignment = parameter.Alignment(),
            size: parameter.Size = parameter.Size(),
            modal: bool = False
    ):
        """
        urwid.Overlays a dialog box on top of the console UI

        Args:
            @param frame: The frame with body, footer, header and focus_part.
            @param alignment: The alignment in align and valign.
            @param size: The size with width and height.
            @param modal: Dialog is locked / modal until user closes it.
        """
        # Body
        if isinstance(frame.body, str) and frame.body == "":
            body = GText(T_("No body"), align="center")
            body = urwid.Filler(body, valign="top")
            body = urwid.Padding(body, left=1, right=1)
            body = urwid.LineBox(body)
        else:
            body = frame.body

        # Footer
        if isinstance(frame.footer, str) and frame.footer == "":
            footer = GBoxButton("Okay", self._reset_layout())
            footer = urwid.AttrMap(footer, "selectable", "focus")
            footer = urwid.GridFlow([footer], 8, 1, 1, "center")
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
        if self.view.gscreen.layout is not None:
            self.view.gscreen.old_layout = self.view.gscreen.layout

        self.view.gscreen.layout = urwid.Frame(
            body, header=header, footer=footer, focus_part=focus_part
        )

        # self.control.app_control._body = body

        widget = urwid.Overlay(
            urwid.LineBox(self.view.gscreen.layout),
            self.control.app_control._body,
            align=alignment.align,
            width=size.width,
            valign=alignment.valign,
            height=size.height,
        )

        if getattr(self.control.app_control, "_loop", None):
            self.control.app_control._loop.widget = widget
            if not modal:
                self.control.app_control._loop.draw_screen()


def create_application() -> Tuple[Union[Application, None], bool]:
    """Creates and returns the main application"""
    urwid.set_encoding("utf-8")
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

    app.view.gscreen.quiet = True

    if "--hidden-login" in sys.argv:
        production = False

    return app, production


def main_app():
    """Starts main application."""
    # application, PRODUCTION = create_application()
    application = create_application()[0]
    # application.set_debug(True)
    # application.gscreen.quiet = False
    # # PRODUCTION = False
    application.start()
    print("\n\x1b[J")


if __name__ == "__main__":
    main_app()
