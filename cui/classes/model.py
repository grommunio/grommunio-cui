import datetime
import os
import re
import subprocess
import time
from getpass import getuser
from pathlib import Path
from typing import Dict, Any, List, Tuple, Set

import requests
import urwid
import yaml
from requests import Response
from systemd import journal
from yaml import SafeLoader

import cui.classes
from cui.symbol import LOG_VIEWER, MAIN, MESSAGE_BOX, INPUT_BOX, PASSWORD, LOGIN, REBOOT, \
    SHUTDOWN, MAIN_MENU, ADMIN_WEB_PW, TIMESYNCD, REPO_SELECTION, KEYBOARD_SWITCH
from cui import util, parameter
from cui.util import _
from cui.classes.interface import BaseApplication, WidgetDrawer
from cui.classes.menu import MenuItem
from cui.classes.button import GButton, GBoxButton
from cui.classes.application import Header, MainFrame
from cui.classes.gwidgets import GText, GEdit
from cui.classes.scroll import ScrollBar, Scrollable


class ApplicationModel(BaseApplication):
    """
    The console UI. Main application class.
    """
    admin_api_config: Dict[str, Any]
    view: cui.classes.application.View
    control: cui.classes.application.Control

    def __init__(self):
        self.admin_api_config = {}
        self.view = cui.classes.application.View(self)
        self.control = cui.classes.application.Control(MAIN)
        # MAIN Page
        self.control.app_control.loop = util.create_main_loop(self)
        self.control.app_control.loop.set_alarm_in(1, self._update_clock)

        util.create_application_buttons(self)

        self.view.top_main_menu.refresh_main_menu()

        # Password Dialog
        self._prepare_password_dialog()

        # Read in logging units
        self._load_journal_units()

        # Log file viewer
        self.log_file_content: List[str] = [
            _("If this is not that what you expected to see, you probably have insufficient "
               "permissions."),
        ]
        self._prepare_log_viewer("NetworkManager", self.control.log_control.log_line_count)

        self._prepare_timesyncd_config()

        # some settings
        GButton.application = self

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
        self.control.app_control.body = self.view.main_frame.mainframe
        # self.print(_("Idle"))

    def handle_event(self, event: Any):
        super().handle_event(event)

    def _process_changed_repo_config(self, height, repo_res):
        header = GText(_("One moment, please ..."))
        footer = GText(_('Fetching GPG-KEY file and refreshing '
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
            _('Software repository selection has been canceled.'),
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
                _(f"Timesyncd configuration change {success_msg}!"),
                _("Timesyncd Configuration"),
            ),
            size=parameter.Size(height=10)
        )
        success_msg = _("NOTHING")
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

    def _return_to(self):
        """Return to mainframe or mainmenu depending on situation and state."""
        if self.control.app_control.last_current_window in [MAIN_MENU]:
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

    def _open_change_password(self):
        """
        Opens password changing dialog.
        """
        self._reset_layout()
        self.print(_("Changing system password"))
        self._open_change_system_pw_dialog()

    def _open_change_system_pw_dialog(self):
        """Open the change system password Dialog."""
        title = _("System Password Change")
        msg = _("Enter the new system password:")
        self._create_password_dialog(msg, title, PASSWORD)

    def _create_password_dialog(self, msg, title, current_window):
        width = 60
        input_text = ""
        height = 14
        mask = "*"
        self.control.app_control.input_box_caller = self.control.app_control.current_window
        self.control.app_control.input_box_caller_body = self.control.app_control.loop.widget
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
            _("Use the arrow keys to switch between logfiles. <urwid.LEFT> and <RIGHT> switch the logfile, while <+> and <-> changes the line count to view. (%s)") % self.control.log_control.log_line_count
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
        if self.control.app_control.current_window != LOG_VIEWER:
            self.control.app_control.log_file_caller = self.control.app_control.current_window
            self.control.app_control.log_file_caller_body = self.control.app_control.body
            self.control.app_control.current_window = LOG_VIEWER
        self.print(_("Log file viewer has to open file {%s} ...") % unit)
        self._prepare_log_viewer(unit, lines)
        self.control.app_control.body = self.control.log_control.log_viewer
        self.control.app_control.loop.widget = self.control.app_control.body

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

    def _open_reset_aapi_pw(self):
        """Open reset admin-API password."""
        title = _("admin-web Password Change")
        msg = _("Enter the new admin-web password:")
        self._create_password_dialog(msg, title, ADMIN_WEB_PW)

    def _open_timesyncd_conf(self):
        """Open timesyncd configuration form."""
        self._reset_layout()
        self.print(_("Opening timesyncd configuration"))
        self.control.app_control.current_window = TIMESYNCD
        header = urwid.AttrMap(GText(_("Timesyncd Configuration"), urwid.CENTER), "header")
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
        text = _("Insert the NTP servers separated by <urwid.SPACE> char.")
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
        self.print(_("Opening repository selection"))
        self.control.app_control.current_window = REPO_SELECTION
        header = urwid.AttrMap(GText(_("Software repository selection"), urwid.CENTER), "header")
        self._prepare_repo_config()
        self._open_conf_dialog(self.control.menu_control.repo_selection_body, header, [self.view.button_store.save_button, self.view.button_store.cancel_button])

    def _prepare_repo_config(self):
        """Prepare repository configuration form."""
        baseurl = 'https://download.grommunio.com/community/openSUSE_Leap_' \
                  '15.3/?ssl_verify=no'
        repofile = '/etc/zypp/repos.d/grommunio.repo'
        config = cui.classes.parser.ConfigParser(infile=repofile)
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
                rbg, _('Use "community" repository'), state=is_community
            ),
            blank,
            urwid.RadioButton(
                rbg, _('Use "supported" repository'), state=is_supported
            ),
            urwid.Columns([
                vblank, GEdit(_('Username: '), edit_text=default_user), vblank
            ]),
            urwid.Columns([
                vblank, GEdit(_('Password: '), edit_text=default_pw), vblank
            ])
        ]
        self.control.menu_control.repo_selection_body = urwid.LineBox(urwid.Padding(urwid.Filler(urwid.Pile(body_content), urwid.TOP)))

    def _open_setup_wizard(self):
        """Open grommunio setup wizard."""
        self.control.app_control.loop.stop()
        self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.old_termios)
        if Path("/usr/sbin/grommunio-setup").exists():
            os.system("/usr/sbin/grommunio-setup")
        else:
            os.system("/usr/sbin/grammm-setup")
        self.view.gscreen.screen.tty_signal_keys(*self.view.gscreen.blank_termios)
        self.control.app_control.loop.start()

    def _open_main_menu(self):
        """
        Opens amin menu,
        """
        self._reset_layout()
        self.print(_("Login successful"))
        self.control.app_control.current_window = MAIN_MENU
        self.view.header.set_authorized_options(_(", <F4> for Main-Menu"))
        self.prepare_mainscreen()
        self.control.app_control.body = self.view.top_main_menu.main_menu
        self.control.app_control.loop.widget = self.control.app_control.body

    def _open_mainframe(self):
        """
        Opens main window. (Welcome screen)
        """
        self._reset_layout()
        self.print(_("Returning to main screen."))
        self.control.app_control.current_window = MAIN
        self.prepare_mainscreen()
        self.control.app_control.loop.widget = self.control.app_control.body

    def _check_login(self):
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
            if util.authenticate_user(
                self.view.button_store.user_edit.get_edit_text(), self.view.button_store.pass_edit.get_edit_text()
            ):
                self.view.button_store.pass_edit.set_edit_text("")
                self._open_main_menu()
            else:
                self.message_box(
                    parameter.MsgBoxParams(
                        _("Incorrect credentials. Access denied!"),
                        _("Password verification"),
                    )
                )
                self.print(_("Login wrong! (%s)") % msg)

    def _press_button(self, button: urwid.Widget, *args, **kwargs):
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
        self.print(_("Opening keyboard configuration"))
        self.control.app_control.last_current_window = self.control.app_control.current_window
        self.control.app_control.current_window = KEYBOARD_SWITCH
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
        if getattr(self.control.app_control, "loop", None):
            if self.control.app_control.loop:
                self.control.app_control.loop.draw_screen()

    def _reset_layout(self):
        """
        Resets the console UI to the default layout
        """

        if getattr(self.control.app_control, "loop", None):
            self.control.app_control.loop.widget = self.control.app_control.body
            self.control.app_control.loop.draw_screen()

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
        swap_widget = getattr(self.control.app_control, "body", None)
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
        self.control.app_control.loop.draw_screen()

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

            elif self.control.app_control.current_window == MESSAGE_BOX:
                if key.endswith('enter') or key == 'esc':
                    self.control.app_control.current_window = self.control.app_control.message_box_caller
                    self.control.app_control.body = self.control.app_control.message_box_caller_body
                    self.reset_layout()

        Args:
            @param mb_params: Messagebox parameters like msg, title and modal.
            @param alignment: The alignment in align and valign.
            @param size: The size in width and height.
            @param view_buttons: The viewed buttons ok or cancel.
        """
        if self.control.app_control.current_window != MESSAGE_BOX:
            self.control.app_control.message_box_caller = self.control.app_control.current_window
            self.control.app_control.message_box_caller_body = self.control.app_control.loop.widget
            self.control.app_control.current_window = MESSAGE_BOX
        body = urwid.LineBox(urwid.Padding(urwid.Filler(urwid.Pile([GText(mb_params.msg, urwid.CENTER)]), urwid.TOP)))
        footer = self._create_footer(view_buttons.view_ok, view_buttons.view_cancel)

        if mb_params.title is None:
            title = _("Message")
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
        self.control.app_control.input_box_caller_body = self.control.app_control.loop.widget
        self.control.app_control.current_window = INPUT_BOX
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
            title = _("Input expected")
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
        self.control.app_control.loop.run()
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
            body = GText(_("No body"), align="center")
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

        # self.control.app_control.body = body

        widget = urwid.Overlay(
            urwid.LineBox(self.view.gscreen.layout),
            self.control.app_control.body,
            align=alignment.align,
            width=size.width,
            valign=alignment.valign,
            height=size.height,
        )

        if getattr(self.control.app_control, "loop", None):
            self.control.app_control.loop.widget = widget
            if not modal:
                self.control.app_control.loop.draw_screen()