# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2022 grommunio GmbH
"""The module contains the handling code of grommunio-cui"""
import os
import subprocess
from pathlib import Path
from typing import Any, Tuple
from getpass import getuser

import requests
import urwid

import cui.classes
from cui.classes.application import setup_state
from cui.classes.menu import MenuItem
from cui.symbol import LOG_VIEWER, MAIN, MESSAGE_BOX, INPUT_BOX, TERMINAL, PASSWORD, LOGIN, \
    REBOOT, SHUTDOWN, MAIN_MENU, UNSUPPORTED, ADMIN_WEB_PW, TIMESYNCD, REPO_SELECTION, \
    KEYBOARD_SWITCH, PRODUCTION
from cui import util, parameter
from cui.classes.model import ApplicationModel
from cui.util import _
from cui.classes.interface import WidgetDrawer
from cui.classes.button import GButton
from cui.classes.gwidgets import GText

_ = cui.util.init_localization()


class ApplicationHandler(ApplicationModel):
    """Add the handler functionality in this class"""
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
        if self.control.log_control.log_finished and \
                self.control.app_control.current_window != LOG_VIEWER:
            self.control.log_control.log_finished = False
        (func, var) = {
            MAIN: (self._key_ev_main, key),
            MESSAGE_BOX: (self._key_ev_mbox, key),
            INPUT_BOX: (self._key_ev_ibox, key),
            TERMINAL: (self._key_ev_term, key),
            PASSWORD: (self._key_ev_pass, key),
            LOGIN: (self._key_ev_login, key),
            REBOOT: (self._key_ev_reboot, key),
            SHUTDOWN: (self._key_ev_shutdown, key),
            MAIN_MENU: (self._key_ev_mainmenu, key),
            LOG_VIEWER: (self._key_ev_logview, key),
            UNSUPPORTED: (self._key_ev_unsupp, key),
            ADMIN_WEB_PW: (self._key_ev_aapi, key),
            TIMESYNCD: (self._key_ev_timesyncd, key),
            REPO_SELECTION: (self._key_ev_repo_selection, key),
            KEYBOARD_SWITCH: (self._key_ev_kbd_switch, key),
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
                    body=urwid.LineBox(urwid.Padding(
                        urwid.Filler(self.view.login_window.login_body)
                    )),
                    header=self.view.login_window.login_header,
                    footer=self.view.login_window.login_footer,
                    focus_part="body",
                )
                self.dialog(frame)
                self.control.app_control.current_window = LOGIN
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
            if self.control.app_control.message_box_caller not in \
                    (self.control.app_control.current_window, MESSAGE_BOX):
                self.control.app_control.current_window = \
                    self.control.app_control.message_box_caller
                self.control.app_control.body = self.control.app_control.message_box_caller_body
            if self.view.gscreen.old_layout:
                self.view.gscreen.layout = self.view.gscreen.old_layout
            self._reset_layout()
            if self.control.app_control.current_window not in [
                LOGIN, MAIN_MENU, TIMESYNCD, REPO_SELECTION
            ]:
                if self.control.app_control.key_counter.get(key, 0) < 10:
                    self.control.app_control.key_counter[key] = \
                        self.control.app_control.key_counter.get(key, 0) + 1
                    self.handle_event(key)
                else:
                    self.control.app_control.key_counter[key] = 0

    def _key_ev_ibox(self, key):
        """Handle event on input box."""
        self._handle_standard_tab_behaviour(key)
        if key.endswith("enter") or key == "esc":
            if key.lower().endswith("enter"):
                self.control.app_control.last_input_box_value = (
                    self.control.app_control.loop.widget.top_w.base_widget.body.base_widget[
                        1
                    ].edit_text
                )
            else:
                self.control.app_control.last_input_box_value = ""
            self.control.app_control.current_window = \
                self.control.app_control.current_window_input_box
            self.control.app_control.body = self.control.app_control.input_box_caller_body
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
        success_msg = _("NOTHING")
        if key.lower().endswith("enter"):
            if key.lower().startswith("hidden"):
                button_type = key.lower().split(" ")[1]
            else:
                button_type = "ok"
            if button_type == "ok":
                success_msg = _("was successful")
                pw1 = self.control.app_control.loop.widget.top_w.base_widget.body.base_widget[
                    2
                ].edit_text
                pw2 = self.control.app_control.loop.widget.top_w.base_widget.body.base_widget[
                    4
                ].edit_text
                if pw1 == pw2:
                    res = util.reset_system_passwd(pw1)
                else:
                    res = 2
                    success_msg = _("failed due to mismatching password values")
                if not res:
                    success_msg = _("failed")
                self._open_main_menu()
            else:
                success_msg = _("aborted")
                self._open_main_menu()
        elif key.lower().find("cancel") >= 0 or key.lower() in ["esc"]:
            success_msg = _("aborted")
            self._open_main_menu()
        if key.lower().endswith("enter") or key in ["esc", "enter"]:
            self.control.app_control.current_window = self.control.app_control.input_box_caller
            self.message_box(
                parameter.MsgBoxParams(
                    _(f"System password reset {success_msg}!"),
                    _("System password reset"),
                ),
                size=parameter.Size(height=10)
            )

    def _key_ev_login(self, key):
        """Handle event on login menu."""
        self._handle_standard_tab_behaviour(key)
        if key.endswith("enter"):
            self.check_login()
        elif key == "esc":
            self._open_mainframe()

    def _key_ev_reboot(self, key):
        """Handle event on power off menu."""
        # Restore cursor etc. before going off.
        if key.endswith("enter") and self.control.app_control.last_pressed_button.lower().endswith(
            "ok"
        ):
            self.control.app_control.loop.stop()
            self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.old_termios)
            os.system("reboot")
            raise urwid.ExitMainLoop()
        self.control.app_control.current_window = MAIN_MENU

    def _key_ev_shutdown(self, key):
        """Handle event on shutdown menu."""
        # Restore cursor etc. before going off.
        if key.endswith("enter") and self.control.app_control.last_pressed_button.lower().endswith(
            "ok"
        ):
            self.control.app_control.loop.stop()
            self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.old_termios)
            os.system("poweroff")
            raise urwid.ExitMainLoop()
        self.control.app_control.current_window = MAIN_MENU

    def _key_ev_mainmenu(self, key):
        """Handle event on main menu menu."""
        def menu_language():
            pre = cui.classes.parser.ConfigParser(infile='/etc/locale.conf')
            self._run_yast_module("language")
            post = cui.classes.parser.ConfigParser(infile='/etc/locale.conf')
            if pre != post:
                util._ = util.restart_gui()

        def exit_main_loop():
            raise urwid.ExitMainLoop()

        menu_selected: int = self._handle_standard_menu_behaviour(
            self.view.top_main_menu.main_menu_list,
            key,
            self.view.top_main_menu.main_menu.base_widget.body[1]
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
            setup_state.set_setup_states()
            self._open_mainframe()

    def _key_ev_logview(self, key):
        """Handle event on log viewer menu."""
        if key in ["ctrl f1", "H", "h", "L", "l", "esc"]:
            self.control.app_control.current_window = self.control.app_control.log_file_caller
            self.control.app_control.body = self.control.app_control.log_file_caller_body
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
            self.control.log_control.log_line_count = \
                max(min(self.control.log_control.log_line_count, 10000), 200)
            self.control.log_control.current_log_unit = max(min(
                self.control.log_control.current_log_unit,
                len(self.control.log_control.log_units) - 1),
                0
            )
            self._open_log_viewer(
                self._get_log_unit_by_id(self.control.log_control.current_log_unit),
                self.control.log_control.log_line_count,
            )
        elif (
                self.control.log_control.hidden_pos < len(UNSUPPORTED)
                and key == UNSUPPORTED.lower()[self.control.log_control.hidden_pos]
        ):
            self.control.log_control.hidden_input += key
            self.control.log_control.hidden_pos += 1
            if self.control.log_control.hidden_input == UNSUPPORTED.lower():
                self._open_log_viewer("syslog")
        else:
            self.control.log_control.hidden_input = ""
            self.control.log_control.hidden_pos = 0

    def _key_ev_unsupp(self, key):
        """Handle event on unsupported."""
        if key in ["ctrl d", "esc", "ctrl f1", "H", "h", "l", "L"]:
            self.control.app_control.current_window = self.control.app_control.log_file_caller
            self.control.app_control.body = self.control.app_control.log_file_caller_body
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
                and self.control.app_control.current_window != LOG_VIEWER
                and self.control.app_control.current_window != UNSUPPORTED
                and not self.control.log_control.log_finished
        ):
            self._open_log_viewer("gromox-http", self.control.log_control.log_line_count)

    def _key_ev_aapi(self, key):
        """Handle event on admin api password reset menu."""
        self._handle_standard_tab_behaviour(key)
        success_msg = _("NOTHING")
        if key.lower().endswith("enter"):
            if key.lower().startswith("hidden"):
                button_type = key.lower().split(" ")[1]
            else:
                button_type = "ok"
            if button_type == "ok":
                success_msg = _("was successful")
                pw1 = self.control.app_control.loop.widget.top_w.base_widget.body.base_widget[
                    2
                ].edit_text
                pw2 = self.control.app_control.loop.widget.top_w.base_widget.body.base_widget[
                    4
                ].edit_text
                if pw1 == pw2:
                    res = util.reset_aapi_passwd(pw1)
                else:
                    res = 2
                    success_msg = _("failed due to mismatching password values")
                if not res:
                    success_msg = _("failed")
                self._open_main_menu()
            else:
                success_msg = _("aborted")
                self._open_main_menu()
        elif key.lower().find("cancel") >= 0 or key.lower() in ["esc"]:
            success_msg = _("aborted")
            self._open_main_menu()
        if key.lower().endswith("enter") or key in ["esc", "enter"]:
            self.control.app_control.current_window = self.control.app_control.input_box_caller
            self.message_box(
                parameter.MsgBoxParams(
                    _(f"Admin password reset {success_msg}!"),
                    _("Admin password reset"),
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
                config2 = cui.classes.parser.ConfigParser(infile=repo_res.get("repofile", None))
                repo_res.get("config", None).write()
                if repo_res.get("config", None) == config2:
                    self.message_box(
                        parameter.MsgBoxParams(
                            _('The repo file has not been changed.')
                        ),
                        size=parameter.Size(height=height-1)
                    )
                else:
                    self._process_changed_repo_config(height, repo_res)

    def _process_changed_repo_config(self, height, repo_res):
        header = GText(_("One moment, please ..."))
        footer = GText(_('Fetching GPG-KEY file and refreshing '
                          'repositories. This may take a while ...'))
        self.control.app_control.progressbar = self._create_progress_bar()
        pad = urwid.Padding(self.control.app_control.progressbar)
        fil = urwid.Filler(pad)
        linebox = urwid.LineBox(fil)
        frame: parameter.Frame = parameter.Frame(linebox, header, footer)
        self.dialog(frame)
        self._draw_progress(20)
        res: requests.Response = requests.get(repo_res.get("keyurl", None))
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
                    _('Software repository selection has been '
                       'updated.'),
                ),
                size=parameter.Size(height=height)
            )
        else:
            self.message_box(
                parameter.MsgBoxParams(
                    _('Software repository selection has not been '
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
        config = cui.classes.parser.ConfigParser(infile=repofile)
        # config.filename = repofile
        if not config.get('grommunio'):
            config['grommunio'] = {}
            config['grommunio']['enabled'] = 1
            config['grommunio']['auorefresh'] = 1
        button_type = util.get_button_type(
            key,
            self._open_main_menu,
            self.message_box,
            cui.parameter.MsgBoxParams(
                _('Software repository selection has been canceled.'),
                _('Repository selection')
            ),
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
        success_msg = _("was successful")
        button_type = util.get_button_type(
            key,
            self._open_main_menu,
            self.message_box,
            parameter.MsgBoxParams(
                _("Timesyncd configuration change canceled."),
                _("Timesyncd Configuration"),
            ),
            size=parameter.Size(height=10)
        )
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
                success_msg = _("was successful")
                if not res:
                    success_msg = _("failed")
            self.message_box(
                parameter.MsgBoxParams(
                    _(f"Timesyncd configuration change {success_msg}!"),
                    _("Timesyncd Configuration"),
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

    def handle_click(self, creator: urwid.Widget, option: bool = False):
        """
        Handles urwid.RadioButton clicks.

        :param creator: The widget creating calling the function.
        :param option: On if True, off otherwise.
        """
        self.print(_(f"Creator ({creator}) clicked {option}."))

    def _open_terminal(self):
        """
        Jump to a shell prompt
        """
        self.control.app_control.loop.stop()
        self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.old_termios)
        print("\x1b[K")
        print(
            "\x1b[K \x1b[36m▼\x1b[0m",
            _("To return to the CUI, issue the `exit` command.")
        )
        print("\x1b[J")
        # We have no environment, and so need su instead of just bash to launch
        # a proper PAM session and set $HOME, etc.
        os.system("/usr/bin/su -l")
        self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.blank_termios)
        self.control.app_control.loop.start()

    def _reboot_confirm(self):
        """Confirm reboot."""
        msg = _("Are you sure?\n")
        msg += _("After pressing OK, ")
        msg += _("the system will reboot.")
        title = _("Reboot")
        self.control.app_control.current_window = REBOOT
        self.message_box(
            parameter.MsgBoxParams(msg, title),
            size=parameter.Size(width=80, height=10),
            view_buttons=parameter.ViewOkCancel(view_ok=True, view_cancel=True)
        )

    def _shutdown_confirm(self):
        """Confirm shutdown."""
        msg = _("Are you sure?\n")
        msg += _("After pressing OK, ")
        msg += _("the system will shut down and power off.")
        title = _("Shutdown")
        self.control.app_control.current_window = SHUTDOWN
        self.message_box(
            parameter.MsgBoxParams(msg, title),
            size=parameter.Size(width=80, height=10),
            view_buttons=parameter.ViewOkCancel(view_ok=True, view_cancel=True)
        )

    def _run_yast_module(self, modulename: str):
        """Run yast module `modulename`."""
        self.control.app_control.loop.stop()
        self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.old_termios)
        print("\x1b[K")
        print(
            "\x1b[K \x1b[36m▼\x1b[0m",
            _("Please wait while `yast2 %s` is being run.") % modulename
        )
        print("\x1b[J")
        os.system(f"yast2 {modulename}")
        self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.blank_termios)
        self.control.app_control.loop.start()

    def _run_zypper(self, subcmd: str):
        """Run zypper modul `subcmd`."""
        self.control.app_control.loop.stop()
        self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.old_termios)
        print("\x1b[K")
        print("\x1b[K \x1b[36m▼\x1b[0m Please wait while zypper is invoked.")
        print("\x1b[J")
        os.system(f"zypper {subcmd}")
        input("\n \x1b[36m▼\x1b[0m Press ENTER to return to the CUI.")
        self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.blank_termios)
        self.control.app_control.loop.start()

    def check_login(self):
        """
        Checks login data and switch to authenticate on if successful.
        """
        if self.view.button_store.user_edit.get_edit_text() != getuser() and os.getegid() != 0:
            self.message_box(
                parameter.MsgBoxParams(_("You need root privileges to use another user.")),
                size=parameter.Size(height=10)
            )
            return
        msg = _("checking user %s with pass ") % self.view.button_store.user_edit.get_edit_text()
        if self.control.app_control.current_window == LOGIN:
            if util.authenticate_user(self.view.button_store.user_edit.get_edit_text(),
                                      self.view.button_store.pass_edit.get_edit_text()):
                self.view.button_store.pass_edit.set_edit_text("")
                self.view.header.set_authorized_options(_(", <F4> for Main-Menu"))
                self._open_main_menu()
            else:
                self.message_box(
                    parameter.MsgBoxParams(
                        _("Incorrect credentials. Access denied!"),
                        _("Password verification"),
                    )
                )
                self.print(_("Login wrong! (%s)") % msg)

    def press_button(self, button: urwid.Widget, *args, **kwargs):
        """
        Handles general events if a button is pressed.

        :param button: The button been clicked.
        """
        label: str = _("UNKNOWN LABEL")
        if isinstance(button, (GButton, urwid.RadioButton, WidgetDrawer)):
            label = button.label
        self.control.app_control.last_pressed_button = label
        if self.control.app_control.current_window not in [MAIN]:
            self.print(
                f"{self.__class__}.press_button(button={button}, "
                f"*args={args}, kwargs={kwargs})"
            )
            self.handle_event(f"{label} enter")

    def _switch_next_colormode(self):
        """Switch to next color scheme."""
        original = self.view.header.get_colormode()
        color_name = util.get_next_palette_name(original)
        palette = util.get_palette(color_name)
        show_next = color_name
        self.view.header.set_colormode(show_next)
        self.view.header.refresh_header()
        self.control.app_control.loop.screen.register_palette(palette)
        self.control.app_control.loop.screen.clear()
        self._return_to()

    def get_focused_menu(self, menu: urwid.ListBox, event: Any) -> int:
        """
        Returns idx of focused menu item. Returns current idx on enter or 1-9 or
        click, and returns the next idx if
        key is up or down.

        :param menu: The menu from which you want to know the idx.
        :type: urwid.ListBox
        :param event: The event passed to the menu.
        :type: Any
        :returns: The idx of the selected menu item. (>=1)
        :rtype: int
        """
        self.view.top_main_menu.current_menu_focus = super().view.top_main_menu.get_focused_menu(
            menu, event
        )
        return self.view.top_main_menu.current_menu_focus

    def _handle_standard_menu_behaviour(
        self, menu: urwid.ListBox, event: Any, description_box: urwid.ListBox = None
    ) -> int:
        """
        Handles standard menu behaviour and returns the focused idx, if any.

        :param menu: The menu to be handled.
        :param event: The event to be handled.
        :param description_box: The urwid.ListBox containing the menu content that
        may be refreshed with the next description.
        :return: The idx of the menu having the focus (1+)
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
            non_sels_current = current + 1 - count_selectables(
                part.base_widget.widget_list, current
            )
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
