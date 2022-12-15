import os
from getpass import getuser
from typing import Any

import urwid

import cui.classes
from cui.symbol import LOG_VIEWER, MAIN, MESSAGE_BOX, INPUT_BOX, TERMINAL, PASSWORD, LOGIN, REBOOT, SHUTDOWN, \
    MAIN_MENU, UNSUPPORTED, ADMIN_WEB_PW, TIMESYNCD, REPO_SELECTION, KEYBOARD_SWITCH, PRODUCTION
from cui import util, parameter
from cui.classes.model import ApplicationModel
from cui.util import T_


class ApplicationHandler(ApplicationModel):
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
        if self.control.log_control.log_finished and self.control.app_control.current_window != LOG_VIEWER:
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
                    body=urwid.LineBox(urwid.Padding(urwid.Filler(self.view.login_window.login_body))),
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
            if self.control.app_control.message_box_caller not in (self.control.app_control.current_window, MESSAGE_BOX):
                self.control.app_control.current_window = self.control.app_control.message_box_caller
                self.control.app_control.body = self.control.app_control.message_box_caller_body
            if self.view.gscreen.old_layout:
                self.view.gscreen.layout = self.view.gscreen.old_layout
            self._reset_layout()
            if self.control.app_control.current_window not in [
                LOGIN, MAIN_MENU, TIMESYNCD, REPO_SELECTION
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
                    self.control.app_control.loop.widget.top_w.base_widget.body.base_widget[
                        1
                    ].edit_text
                )
            else:
                self.control.app_control.last_input_box_value = ""
            self.control.app_control.current_window = self.control.app_control.current_window_input_box
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
        success_msg = T_("NOTHING")
        if key.lower().endswith("enter"):
            if key.lower().startswith("hidden"):
                button_type = key.lower().split(" ")[1]
            else:
                button_type = "ok"
            if button_type == "ok":
                success_msg = T_("was successful")
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
                util.T_ = util.restart_gui()

        def exit_main_loop():
            raise urwid.ExitMainLoop()

        menu_selected: int = self._handle_standard_menu_behaviour(
            self.view.top_main_menu.main_menu_list, key, self.view.top_main_menu.main_menu.base_widget.body[1]
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
            self.control.log_control.log_line_count = max(min(self.control.log_control.log_line_count, 10000), 200)
            self.control.log_control.current_log_unit = max(min(self.control.log_control.current_log_unit, len(self.control.log_control.log_units) - 1), 0)
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
        success_msg = T_("NOTHING")
        if key.lower().endswith("enter"):
            if key.lower().startswith("hidden"):
                button_type = key.lower().split(" ")[1]
            else:
                button_type = "ok"
            if button_type == "ok":
                success_msg = T_("was successful")
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
                config2 = cui.classes.parser.ConfigParser(infile=repo_res.get("repofile", None))
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