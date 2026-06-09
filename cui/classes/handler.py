# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2022–2024 grommunio GmbH
"""The module contains the handling code of grommunio-cui"""
import os
import subprocess
from pathlib import Path
from typing import Any, Tuple
from getpass import getuser

import requests
import urwid

import cui.classes
import cui.distro
import cui.network
import cui.localetime
from cui.classes.application import setup_state
from cui.classes.menu import MenuItem
from cui.symbol import LOG_VIEWER, MAIN, MESSAGE_BOX, INPUT_BOX, TERMINAL, PASSWORD, LOGIN, \
    REBOOT, SHUTDOWN, MAIN_MENU, UNSUPPORTED, ADMIN_WEB_PW, TIMESYNCD, REPO_SELECTION, \
    KEYBOARD_SWITCH, PRODUCTION, LOCALE_SELECTION, TIMEZONE_SELECTION, \
    NETWORK_INTERFACE_SELECT, NETWORK_INTERFACE_EDIT, NETWORK_BOND_CREATE
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
                line), the keystroke is represented as is a single key or even
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
        # event was a keystroke
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
            LOCALE_SELECTION: (self._key_ev_locale_selection, key),
            TIMEZONE_SELECTION: (self._key_ev_timezone_selection, key),
            NETWORK_INTERFACE_SELECT: (self._key_ev_network_iface_select, key),
            NETWORK_INTERFACE_EDIT: (self._key_ev_network_iface_edit, key),
            NETWORK_BOND_CREATE: (self._key_ev_network_bond_create, key),
        }.get(self.control.app_control.current_window, (lambda *_a: None, None))
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
                    body=urwid.Padding(
                        urwid.Filler(self.view.login_window.login_body)
                    ),
                    footer=self.view.login_window.login_footer,
                    focus_part="body",
                )
                self.dialog(frame, title=_("Login"))
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
        button_type = key
        if button_type.endswith("enter"):
            button_type = button_type.split(" enter", 1)[0]
        if button_type.startswith("hidden"):
            button_type = button_type.split("hidden ", 1)[1]
        if button_type.lower() in [t.lower() for t in [_("Ok"), _("ok"), _("OK"), "enter"]]:
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
            if key.lower().endswith("enter") or key in ["esc", "enter"]:
                self.control.app_control.current_window = self.control.app_control.input_box_caller
                self.message_box(
                    parameter.MsgBoxParams(
                        _("System password reset %s!") % success_msg,
                        _("System password reset"),
                    ),
                    size=parameter.Size(height=10)
                )
        elif button_type in [_("Cancel"), _("cancel")] or key.lower() in ["esc"]:
            self._open_main_menu()

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
        """Handle event on main menu."""
        def menu_language():
            locale_path = cui.distro.get_locale_conf_path()
            pre = cui.classes.parser.ConfigParser(infile=locale_path) \
                if Path(locale_path).is_file() else None
            self._open_locale_selection()
            post = cui.classes.parser.ConfigParser(infile=locale_path) \
                if Path(locale_path).is_file() else None
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
                3: (self._open_network_interface_select, None),
                4: (self._open_timezone_selection, None),
                5: (self._open_timesyncd_conf, None),
                6: (self._open_repo_conf, None),
                7: (self._run_update, None),
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
        button_type = key
        if button_type.endswith("enter"):
            button_type = button_type.split(" enter", 1)[0]
        if button_type.startswith("hidden"):
            button_type = button_type.split("hidden ", 1)[1]
        if button_type.lower() in [t.lower() for t in [_("Ok"), _("ok"), _("OK"), "enter"]]:
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
            if key.lower().endswith("enter") or key in ["esc", "enter"]:
                self.control.app_control.current_window = self.control.app_control.input_box_caller
                self.message_box(
                    parameter.MsgBoxParams(
                        _("Admin password reset %s!") % success_msg,
                        _("Admin password reset"),
                    ),
                    size=parameter.Size(height=10)
                )
        elif button_type in [_("Cancel"), _("cancel")] or key.lower() in ["esc"]:
            self._open_main_menu()

    def _key_ev_repo_selection(self, key):
        """Handle event on repository selection menu."""
        height = 10
        repo_res = self._init_repo_selection(key, height)
        if repo_res.get("button_type", "").lower() in [
            t.lower() for t in [_("Ok"), _("Save"), _("ok"), _("save"), _("OK"), _("SAVE")]
        ]:
            updateable, url = util.check_repo_dialog(self, height)
            if not updateable:
                return
            if cui.distro.is_debian_family():
                # apt: we rewrite the .list file from scratch below; nothing
                # to update in `config` here.
                self._process_changed_repo_config(height, repo_res, raw_url=url)
                return
            cfg = repo_res.get("config")
            if cfg is None:
                self._process_changed_repo_config(height, repo_res, raw_url=url)
                return
            cfg['grommunio']['baseurl'] = url if url.startswith("http") else f'https://{url}'
            cfg['grommunio']['type'] = 'rpm-md'
            config2 = cui.classes.parser.ConfigParser(infile=repo_res.get("repofile", None))
            cfg.write()
            if cfg == config2:
                self.message_box(
                    parameter.MsgBoxParams(
                        _('The repo file has not been changed.')
                    ),
                    size=parameter.Size(height=height)
                )
            else:
                self._process_changed_repo_config(height, repo_res)

    def _process_changed_repo_config(self, height, repo_res, raw_url: str = None):
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
        keyurl = repo_res.get("keyurl")
        keyfile = repo_res.get("keyfile")
        try:
            res = requests.get(keyurl, timeout=30)
        except requests.RequestException:
            self.message_box(
                parameter.MsgBoxParams(
                    _("Could not download the grommunio GPG key from %s.") % keyurl,
                ),
                size=parameter.Size(height=height + 1),
            )
            return
        got_keyfile: bool = False
        if res.status_code == 200:
            self._draw_progress(30)
            tmp = Path(keyfile)
            try:
                tmp.parent.mkdir(parents=True, exist_ok=True)
                with tmp.open('w', encoding="utf-8") as file:
                    file.write(res.content.decode())
                self._draw_progress(40)
            except OSError as exc:
                self.message_box(
                    parameter.MsgBoxParams(
                        _("Failed to write key file %(path)s: %(err)s")
                        % {"path": keyfile, "err": str(exc)},
                    ),
                    size=parameter.Size(height=height + 1),
                )
                return
            # On Debian/Ubuntu we also need to write the .list file from scratch.
            if cui.distro.is_debian_family() and raw_url:
                repofile = repo_res.get("repofile")
                body = cui.distro.render_repo_file(
                    baseurl=raw_url if raw_url.startswith("http") else f"https://{raw_url}",
                    key_destination=keyfile,
                )
                try:
                    with open(repofile, "w", encoding="utf-8") as fh:
                        fh.write(body)
                except OSError as exc:
                    self.message_box(
                        parameter.MsgBoxParams(
                            _("Failed to write repo file %(path)s: %(err)s")
                            % {"path": repofile, "err": str(exc)},
                        ),
                        size=parameter.Size(height=height + 1),
                    )
                    return
            import_cmd = cui.distro.pkg_import_key_cmd(keyfile)
            if import_cmd:
                try:
                    with subprocess.Popen(
                            import_cmd,
                            stderr=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                    ) as ret_code_imp:
                        ret_code_imp.wait()
                except OSError:
                    pass
            self._draw_progress(60)
            refresh_cmd = cui.distro.pkg_refresh_cmd()
            if refresh_cmd:
                try:
                    with subprocess.Popen(
                            refresh_cmd,
                            stderr=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                    ) as ret_code_ref:
                        if ret_code_ref.wait() == 0:
                            self._draw_progress(100)
                            got_keyfile = True
                except OSError:
                    pass
            else:
                # No package manager available; we've at least written the files.
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
        keyfile = cui.distro.get_keyfile_destination()
        repofile = cui.distro.get_repo_file_path()
        config = None
        if not cui.distro.is_debian_family():
            try:
                config = cui.classes.parser.ConfigParser(infile=repofile)
                if not config.get('grommunio'):
                    config['grommunio'] = {}
                    config['grommunio']['enabled'] = 1
                    config['grommunio']['autorefresh'] = 1
            except Exception:
                config = None
        button_type = util.get_button_type(
            key,
            self._open_main_menu,
            None, None,
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
            None, None,
            size=parameter.Size(height=10)
        )
        if button_type == _("ok"):
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
                    _("Timesyncd configuration change %s!") % success_msg,
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

    def _run_update(self):
        """Refresh package metadata and run a full upgrade via the system PM."""
        refresh = cui.distro.pkg_refresh_cmd()
        update = cui.distro.pkg_update_cmd()
        if not refresh or not update:
            self.message_box(
                parameter.MsgBoxParams(
                    _("No supported package manager (zypper, dnf, apt-get) was found."),
                    _("System update"),
                ),
                size=parameter.Size(height=10),
            )
            return
        self.control.app_control.loop.stop()
        self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.old_termios)
        print("\x1b[K")
        print("\x1b[K \x1b[36m▼\x1b[0m",
              _("Please wait while %s is invoked.") % refresh[0])
        print("\x1b[J")
        subprocess.run(refresh, check=False)
        subprocess.run(update, check=False)
        input("\n \x1b[36m▼\x1b[0m " + _("Press ENTER to return to the CUI."))
        self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.blank_termios)
        self.control.app_control.loop.start()

    def check_login(self, widget=None):
        """
        Checks login data and switch to authenticate on if successful.

        widget: that which triggered the action
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

    # ------------------------------------------------------------------
    # Helpers for matching translated button labels in a case-/locale-safe way.
    # ------------------------------------------------------------------

    @staticmethod
    def _button_aliases(*sources):
        """Lower-cased aliases for translatable button labels."""
        out = set()
        for src in sources:
            if src is None:
                continue
            out.add(src.lower())
        return out

    def _is_save_or_ok(self, button_type: str) -> bool:
        if not button_type:
            return False
        aliases = self._button_aliases(_("OK"), _("Ok"), _("ok"),
                                       _("Save"), _("save"))
        return button_type.lower() in aliases

    def _is_edit_or_ok(self, button_type: str) -> bool:
        if not button_type:
            return False
        aliases = self._button_aliases(_("OK"), _("Ok"), _("ok"),
                                       _("Edit"), _("edit"))
        return button_type.lower() in aliases

    def _is_cancel_or_esc(self, button_type: str, key: str) -> bool:
        if key and key.lower() == "esc":
            return True
        if not button_type:
            return False
        aliases = self._button_aliases(_("Cancel"), _("cancel"))
        return button_type.lower() in aliases

    # ------------------------------------------------------------------
    # Locale selection dialog
    # ------------------------------------------------------------------

    def _open_locale_selection(self):
        """Open the locale-picker dialog backed by localectl."""
        self._reset_layout()
        self.print(_("Opening language selection"))
        self.control.app_control.current_window = LOCALE_SELECTION
        locales = cui.localetime.list_locales()
        if not locales:
            self.message_box(
                parameter.MsgBoxParams(
                    _("Could not enumerate available locales (is localectl installed?)."),
                    _("Language configuration"),
                ),
                size=parameter.Size(height=10),
            )
            return
        current = cui.localetime.get_current_locale()
        self._locale_choices = locales
        self._locale_radiogroup = []
        items = []
        for loc in locales:
            rb = urwid.RadioButton(self._locale_radiogroup, loc, state=(loc == current))
            items.append(urwid.AttrMap(rb, "selectable", "focus"))
        body = cui.classes.scroll.ScrollBar(
            cui.classes.scroll.Scrollable(urwid.Pile(items))
        )
        footer = urwid.AttrMap(
            urwid.Columns([
                self.view.button_store.save_button,
                self.view.button_store.cancel_button,
            ]),
            "buttonbar",
        )
        frame = parameter.Frame(
            body=urwid.AttrMap(body, "body"),
            footer=footer,
            focus_part="body",
        )
        self.dialog(
            frame,
            alignment=parameter.Alignment(urwid.CENTER, urwid.MIDDLE),
            size=parameter.Size(width=60, height=20),
            title=_("Select system language"),
        )

    def _key_ev_locale_selection(self, key: str):
        """Handle key events on the locale selection dialog."""
        self._handle_standard_tab_behaviour(key)
        button_type = util.get_button_type(
            key, self._open_main_menu, None, None,
            size=parameter.Size(height=10),
        )
        if self._is_save_or_ok(button_type):
            selected = next(
                (rb.label for rb in self._locale_radiogroup if rb.state),
                "",
            )
            if selected and cui.localetime.set_locale(selected):
                self.message_box(
                    parameter.MsgBoxParams(
                        _("System language set to %s.") % selected,
                        _("Language configuration"),
                    ),
                    size=parameter.Size(height=10),
                )
            else:
                self.message_box(
                    parameter.MsgBoxParams(
                        _("Failed to set the system language."),
                        _("Language configuration"),
                    ),
                    size=parameter.Size(height=10),
                )
            self._open_main_menu()
        elif self._is_cancel_or_esc(button_type, key):
            self._open_main_menu()

    # ------------------------------------------------------------------
    # Timezone selection dialog
    # ------------------------------------------------------------------

    def _open_timezone_selection(self):
        """Open the timezone-picker dialog backed by timedatectl."""
        self._reset_layout()
        self.print(_("Opening timezone selection"))
        self.control.app_control.current_window = TIMEZONE_SELECTION
        timezones = cui.localetime.list_timezones()
        if not timezones:
            self.message_box(
                parameter.MsgBoxParams(
                    _("Could not enumerate timezones (is timedatectl installed?)."),
                    _("Timezone configuration"),
                ),
                size=parameter.Size(height=10),
            )
            return
        current = cui.localetime.get_current_timezone()
        self._timezone_choices = timezones
        self._timezone_radiogroup = []
        items = []
        for tz in timezones:
            rb = urwid.RadioButton(self._timezone_radiogroup, tz, state=(tz == current))
            items.append(urwid.AttrMap(rb, "selectable", "focus"))
        body = cui.classes.scroll.ScrollBar(
            cui.classes.scroll.Scrollable(urwid.Pile(items))
        )
        footer = urwid.AttrMap(
            urwid.Columns([
                self.view.button_store.save_button,
                self.view.button_store.cancel_button,
            ]),
            "buttonbar",
        )
        frame = parameter.Frame(
            body=urwid.AttrMap(body, "body"),
            footer=footer,
            focus_part="body",
        )
        self.dialog(
            frame,
            alignment=parameter.Alignment(urwid.CENTER, urwid.MIDDLE),
            size=parameter.Size(width=60, height=20),
            title=_("Select system timezone"),
        )

    def _key_ev_timezone_selection(self, key: str):
        """Handle key events on the timezone selection dialog."""
        self._handle_standard_tab_behaviour(key)
        button_type = util.get_button_type(
            key, self._open_main_menu, None, None,
            size=parameter.Size(height=10),
        )
        if self._is_save_or_ok(button_type):
            selected = next(
                (rb.label for rb in self._timezone_radiogroup if rb.state),
                "",
            )
            if selected and cui.localetime.set_timezone(selected):
                self.message_box(
                    parameter.MsgBoxParams(
                        _("System timezone set to %s.") % selected,
                        _("Timezone configuration"),
                    ),
                    size=parameter.Size(height=10),
                )
            else:
                self.message_box(
                    parameter.MsgBoxParams(
                        _("Failed to set the system timezone."),
                        _("Timezone configuration"),
                    ),
                    size=parameter.Size(height=10),
                )
            self._open_main_menu()
        elif self._is_cancel_or_esc(button_type, key):
            self._open_main_menu()

    # ------------------------------------------------------------------
    # Network interface configuration dialogs
    # ------------------------------------------------------------------

    _BOND_CREATE_SENTINEL = "__create_bond__"

    def _open_network_interface_select(self):
        """Show a list of interfaces plus a 'Create bond' entry."""
        self._reset_layout()
        self.print(_("Opening network configuration"))
        self.control.app_control.current_window = NETWORK_INTERFACE_SELECT
        ifaces = cui.network.list_interfaces()
        self._iface_choices = ifaces
        self._iface_radiogroup = []
        rows = []
        first = True
        for name in ifaces:
            state = cui.network.current_runtime_state(name)
            kind = state.get("kind", "ethernet")
            v4 = ", ".join(state.get("addresses_v4", []) or [_("no IPv4")])
            label = f"{name} [{kind}]  {v4}"
            rb = urwid.RadioButton(self._iface_radiogroup, label, state=first)
            rows.append(urwid.AttrMap(rb, "selectable", "focus"))
            first = False
        # Last entry: create a new bond device.
        bond_label = self._BOND_CREATE_SENTINEL + "  " + _("[ Create new bond device... ]")
        rb_new = urwid.RadioButton(self._iface_radiogroup, bond_label, state=not ifaces)
        rows.append(urwid.AttrMap(rb_new, "selectable", "focus"))
        backend = cui.network.get_backend()
        header = GText(
            _("Active backend: %s. Choose an interface and press Edit, "
              "or pick 'Create new bond device' to set one up.") % backend,
            urwid.CENTER,
        )
        body = urwid.Pile([
            (2, urwid.Filler(header)),
            urwid.AttrMap(cui.classes.scroll.ScrollBar(
                cui.classes.scroll.Scrollable(urwid.Pile(rows))
            ), "body"),
        ])
        footer = urwid.AttrMap(
            urwid.Columns([
                self.view.button_store.edit_button,
                self.view.button_store.cancel_button,
            ]),
            "buttonbar",
        )
        frame = parameter.Frame(
            body=body,
            footer=footer,
            focus_part="body",
        )
        self.dialog(
            frame,
            alignment=parameter.Alignment(urwid.CENTER, urwid.MIDDLE),
            size=parameter.Size(width=78, height=20),
            title=_("Network interfaces"),
        )

    def _key_ev_network_iface_select(self, key: str):
        self._handle_standard_tab_behaviour(key)
        button_type = util.get_button_type(
            key, self._open_main_menu, None, None,
            size=parameter.Size(height=10),
        )
        if self._is_edit_or_ok(button_type):
            selected = next(
                (rb.label.split()[0] for rb in self._iface_radiogroup if rb.state),
                "",
            )
            if selected == self._BOND_CREATE_SENTINEL:
                self._open_network_bond_create()
            elif selected:
                self._open_network_interface_edit(selected)
        elif self._is_cancel_or_esc(button_type, key):
            self._open_main_menu()

    # ------------------------------------------------------------------
    # Interface editor: addresses, routes, DNS, and bond-specific fields.
    # ------------------------------------------------------------------

    def _open_network_interface_edit(self, iface: str):
        self._reset_layout()
        self.control.app_control.current_window = NETWORK_INTERFACE_EDIT
        cfg = cui.network.load_interface_config(iface)
        self._iface_editing = iface
        self._iface_kind = cfg.kind
        self._iface_dhcp4_cb = urwid.CheckBox(_("DHCPv4"), state=cfg.dhcp4)
        self._iface_dhcp6_cb = urwid.CheckBox(_("DHCPv6"), state=cfg.dhcp6)
        self._iface_edit_addrs = cui.classes.gwidgets.GEdit(
            (18, _("Addresses: ")),
            edit_text="\n".join(cfg.addresses),
            multiline=True,
        )
        self._iface_edit_gw4 = cui.classes.gwidgets.GEdit(
            (18, _("Default gw v4: ")), edit_text=cfg.gateway4,
        )
        self._iface_edit_gw6 = cui.classes.gwidgets.GEdit(
            (18, _("Default gw v6: ")), edit_text=cfg.gateway6,
        )
        self._iface_edit_routes = cui.classes.gwidgets.GEdit(
            (18, _("Static routes: ")),
            edit_text="\n".join(
                f"{d} via {g}" if g else d for d, g in cfg.routes
            ),
            multiline=True,
        )
        self._iface_edit_dns = cui.classes.gwidgets.GEdit(
            (18, _("DNS servers: ")),
            edit_text="\n".join(cfg.dns),
            multiline=True,
        )
        pile_items = [
            GText(_("Interface: %(name)s (%(kind)s)") %
                  {"name": iface, "kind": cfg.kind}, urwid.CENTER),
            GText(_("One value per line. CIDR for addresses; "
                    "'<dest> via <gw>' for routes."), urwid.CENTER),
            urwid.Divider(),
            urwid.AttrMap(self._iface_dhcp4_cb, "selectable", "focus"),
            urwid.AttrMap(self._iface_dhcp6_cb, "selectable", "focus"),
            urwid.Divider(),
            self._iface_edit_addrs,
            self._iface_edit_gw4,
            self._iface_edit_gw6,
            self._iface_edit_routes,
            self._iface_edit_dns,
        ]
        if cfg.kind == "bond":
            pile_items.append(urwid.Divider())
            pile_items.append(
                GText(_("Bond mode: %(mode)s   MIIMON: %(miimon)d ms   "
                        "Members: %(members)s") %
                      {"mode": cfg.bond_mode,
                       "miimon": cfg.bond_miimon,
                       "members": ", ".join(cfg.bond_members) or _("(none)")},
                      urwid.CENTER))
        body = urwid.Padding(urwid.Filler(urwid.Pile(pile_items), urwid.TOP))
        footer = urwid.AttrMap(
            urwid.Columns([
                self.view.button_store.save_button,
                self.view.button_store.cancel_button,
            ]),
            "buttonbar",
        )
        frame = parameter.Frame(
            body=urwid.AttrMap(body, "body"),
            footer=footer,
            focus_part="body",
        )
        self.dialog(
            frame,
            alignment=parameter.Alignment(urwid.CENTER, urwid.MIDDLE),
            size=parameter.Size(width=80, height=24),
            title=_("Edit interface %s") % iface,
        )

    def _key_ev_network_iface_edit(self, key: str):
        self._handle_standard_tab_behaviour(key)
        button_type = util.get_button_type(
            key, self._open_network_interface_select, None, None,
            size=parameter.Size(height=10),
        )
        if self._is_save_or_ok(button_type):
            err = self._save_iface_from_form()
            if err:
                self.message_box(
                    parameter.MsgBoxParams(err, _("Network configuration")),
                    size=parameter.Size(height=10),
                )
                return
            self._open_main_menu()
        elif self._is_cancel_or_esc(button_type, key):
            self._open_network_interface_select()

    def _save_iface_from_form(self) -> str:
        """Validate the form and write the new config; return error or ''."""
        iface = getattr(self, "_iface_editing", None)
        if not iface:
            return _("No interface selected.")
        dhcp4 = self._iface_dhcp4_cb.state
        dhcp6 = self._iface_dhcp6_cb.state
        addrs = [a.strip() for a in self._iface_edit_addrs.edit_text.splitlines()
                 if a.strip()]
        gw4 = self._iface_edit_gw4.edit_text.strip()
        gw6 = self._iface_edit_gw6.edit_text.strip()
        dns = [d.strip() for d in self._iface_edit_dns.edit_text.splitlines()
               if d.strip()]
        route_lines = [r.strip() for r in self._iface_edit_routes.edit_text.splitlines()
                       if r.strip()]
        routes = []
        for line in route_lines:
            rerr = cui.network.validate_route(line)
            if rerr:
                return _("Invalid route '%(line)s': %(err)s") % {
                    "line": line, "err": rerr,
                }
            parsed = cui.network.parse_route_line(line)
            if parsed:
                routes.append(parsed)
        for addr in addrs:
            aerr = cui.network.validate_cidr(addr)
            if aerr:
                return _("Invalid address '%(addr)s': %(err)s") % {
                    "addr": addr, "err": aerr,
                }
        for label, gw in (("gateway v4", gw4), ("gateway v6", gw6)):
            if gw:
                gwerr = cui.network.validate_ip(gw)
                if gwerr:
                    return _("Invalid %(label)s '%(gw)s': %(err)s") % {
                        "label": label, "gw": gw, "err": gwerr,
                    }
        for d in dns:
            derr = cui.network.validate_ip(d)
            if derr:
                return _("Invalid DNS server '%(d)s': %(err)s") % {
                    "d": d, "err": derr,
                }
        # Preserve any bond-specific fields the user didn't touch in this dialog.
        existing = cui.network.load_interface_config(iface)
        cfg = cui.network.InterfaceConfig(
            name=iface,
            kind=existing.kind,
            dhcp4=dhcp4,
            dhcp6=dhcp6,
            addresses=addrs,
            gateway4=gw4,
            gateway6=gw6,
            dns=dns,
            routes=routes,
            bond_mode=existing.bond_mode,
            bond_miimon=existing.bond_miimon,
            bond_members=existing.bond_members,
            bond_master=existing.bond_master,
        )
        ok = cui.network.save_interface_config(cfg)
        if not ok:
            return _("Failed to write the interface configuration.")
        self.message_box(
            parameter.MsgBoxParams(
                _("Interface %(iface)s saved.") % {"iface": iface},
                _("Network configuration"),
            ),
            size=parameter.Size(height=10),
        )
        return ""

    # ------------------------------------------------------------------
    # Bond creation dialog.
    # ------------------------------------------------------------------

    def _open_network_bond_create(self):
        """Dialog to create a new bond device with member selection."""
        self._reset_layout()
        self.control.app_control.current_window = NETWORK_BOND_CREATE
        candidates = cui.network.list_bondable_interfaces()
        if not candidates:
            self.message_box(
                parameter.MsgBoxParams(
                    _("No physical interfaces available for bonding."),
                    _("Bond creation"),
                ),
                size=parameter.Size(height=10),
            )
            self._open_network_interface_select()
            return
        # Suggest the next free bondN name.
        existing = {n for n in cui.network.list_interfaces()
                    if n.startswith("bond")}
        suggested = next(
            (f"bond{i}" for i in range(0, 16) if f"bond{i}" not in existing),
            "bond0",
        )
        self._bond_name_edit = cui.classes.gwidgets.GEdit(
            (18, _("Bond name: ")), edit_text=suggested,
        )
        self._bond_miimon_edit = cui.classes.gwidgets.GEdit(
            (18, _("MIIMON (ms): ")), edit_text="100",
        )
        self._bond_mode_rb_group = []
        mode_items = []
        for mode in cui.network.BOND_MODES:
            rb = urwid.RadioButton(self._bond_mode_rb_group, mode,
                                   state=(mode == "active-backup"))
            mode_items.append(urwid.AttrMap(rb, "selectable", "focus"))
        self._bond_member_checks = []
        member_items = []
        for name in candidates:
            cb = urwid.CheckBox(name, state=False)
            self._bond_member_checks.append((name, cb))
            member_items.append(urwid.AttrMap(cb, "selectable", "focus"))
        pile_items = [
            GText(_("Create a new bond device. Pick the mode, the MIIMON "
                    "interval and at least one physical member."),
                  urwid.CENTER),
            urwid.Divider(),
            self._bond_name_edit,
            self._bond_miimon_edit,
            urwid.Divider(),
            GText(_("Mode:"), urwid.LEFT),
            urwid.Pile(mode_items),
            urwid.Divider(),
            GText(_("Members:"), urwid.LEFT),
            urwid.Pile(member_items),
        ]
        body = urwid.Padding(urwid.Filler(urwid.Pile(pile_items), urwid.TOP))
        footer = urwid.AttrMap(
            urwid.Columns([
                self.view.button_store.save_button,
                self.view.button_store.cancel_button,
            ]),
            "buttonbar",
        )
        frame = parameter.Frame(
            body=urwid.AttrMap(body, "body"),
            footer=footer,
            focus_part="body",
        )
        self.dialog(
            frame,
            alignment=parameter.Alignment(urwid.CENTER, urwid.MIDDLE),
            size=parameter.Size(width=72, height=22),
            title=_("Create bond device"),
        )

    def _key_ev_network_bond_create(self, key: str):
        self._handle_standard_tab_behaviour(key)
        button_type = util.get_button_type(
            key, self._open_network_interface_select, None, None,
            size=parameter.Size(height=10),
        )
        if self._is_save_or_ok(button_type):
            err = self._create_bond_from_form()
            if err:
                self.message_box(
                    parameter.MsgBoxParams(err, _("Bond creation")),
                    size=parameter.Size(height=10),
                )
                return
            self._open_main_menu()
        elif self._is_cancel_or_esc(button_type, key):
            self._open_network_interface_select()

    def _create_bond_from_form(self) -> str:
        name = self._bond_name_edit.edit_text.strip()
        if not name or not name.isidentifier() and not name.startswith("bond"):
            return _("Bond name must look like 'bond0', 'bond1', ...")
        try:
            miimon = int(self._bond_miimon_edit.edit_text.strip() or "100")
        except ValueError:
            return _("MIIMON must be a positive integer (milliseconds).")
        if miimon <= 0:
            return _("MIIMON must be a positive integer (milliseconds).")
        mode = next((rb.label for rb in self._bond_mode_rb_group if rb.state),
                    "active-backup")
        members = [n for n, cb in self._bond_member_checks if cb.state]
        if not members:
            return _("Select at least one physical member.")
        cfg = cui.network.InterfaceConfig(
            name=name,
            kind="bond",
            bond_mode=mode,
            bond_miimon=miimon,
            bond_members=members,
            dhcp4=True,
        )
        ok = cui.network.create_bond(cfg)
        if not ok:
            return _("Failed to create the bond device.")
        self.message_box(
            parameter.MsgBoxParams(
                _("Bond %(name)s created with %(count)d members.") % {
                    "name": name, "count": len(members),
                },
                _("Bond creation"),
            ),
            size=parameter.Size(height=10),
        )
        return ""
