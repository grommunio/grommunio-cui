# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2022 grommunio GmbH
"""The module contains the application model of the grommunio-cui"""
import datetime
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple, Set

import urwid
import yaml
from systemd import journal

import cui.classes
import cui.classes.button
from cui.symbol import LOG_VIEWER, MAIN, MESSAGE_BOX, INPUT_BOX, PASSWORD, \
    MAIN_MENU, ADMIN_WEB_PW, TIMESYNCD, REPO_SELECTION, KEYBOARD_SWITCH
from cui import util, parameter
from cui.util import _
from cui.classes.interface import BaseApplication
from cui.classes.button import GButton, GBoxButton
from cui.classes.application import MainFrame, setup_state
from cui.classes.gwidgets import GText, GEdit
from cui.classes.scroll import ScrollBar, Scrollable

_ = cui.util.init_localization()


class ApplicationModel(BaseApplication):
    """
    The console UI. Main application class.
    """
    admin_api_config: Dict[str, Any]
    view: cui.classes.application.View
    control: cui.classes.application.Control

    def __init__(self):
        setup_state.set_setup_states()
        self.admin_api_config = {}
        self.view = cui.classes.application.View(self)
        self.control = cui.classes.application.Control(MAIN)
        # MAIN Page
        self.control.app_control.loop = util.create_main_loop(self)
        self.control.app_control.loop.set_alarm_in(1, self._update_clock)

        cui.classes.button.create_application_buttons(self)

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
        # self.view.header = Header()
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
        self.print(event)
        super().handle_event(event)

    def _return_to(self):
        """Return to mainframe or mainmenu depending on situation and state."""
        if self.control.app_control.last_current_window in [MAIN_MENU]:
            self._open_main_menu()
        else:
            self._open_mainframe()

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
            self.admin_api_config = yaml.load(out, Loader=yaml.SafeLoader)
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
            _("Use the arrow keys to switch between logfiles. <urwid.LEFT> and <RIGHT> "
              "switch the logfile, while <+> and <-> changes the line count to view. "
              "(%s)") % self.control.log_control.log_line_count
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
        self._open_conf_dialog(self.timesyncd_body, header, [
            self.view.button_store.ok_button, self.view.button_store.cancel_button
        ])

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
        self._open_conf_dialog(self.control.menu_control.repo_selection_body, header, [
            self.view.button_store.save_button, self.view.button_store.cancel_button
        ])

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
        self.control.menu_control.repo_selection_body = urwid.LineBox(
            urwid.Padding(urwid.Filler(urwid.Pile(body_content), urwid.TOP))
        )

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
        self.prepare_mainscreen()
        self.control.app_control.body = self.view.top_main_menu.main_menu
        self.control.app_control.loop.widget = self.control.app_control.body
        self.redraw()

    def _open_mainframe(self):
        """
        Opens main window. (Welcome screen)
        """
        self._reset_layout()
        self.print(_("Returning to main screen."))
        self.control.app_control.current_window = MAIN
        self.prepare_mainscreen()
        self.control.app_control.loop.widget = self.control.app_control.body

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
        self.control.menu_control.keyboard_list = ScrollBar(Scrollable(
            urwid.Pile(self.control.menu_control.keyboard_content)
        ))
        self.control.menu_control.keyboard_switch_body = self.control.menu_control.keyboard_list

    def redraw(self):
        """
        Redraws screen.
        """
        if getattr(self.control.app_control, "loop", None):
            if self.control.app_control.loop:
                self.control.app_control.loop.draw_screen()
        if getattr(self, "view", None):
            if getattr(self.view, "header", None):
                self.view.header.refresh_header()

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
        self.view.main_footer.footer = urwid.AttrMap(
            urwid.Pile(self.view.main_footer.footer_content),
            "footer"
        )
        swap_widget = getattr(self.control.app_control, "body", None)
        if swap_widget:
            swap_widget.footer = self.view.main_footer.footer
            self.redraw()
        self.control.app_control.current_bottom_info = string

    def _create_progress_bar(self, max_progress=100):
        """Create progressbar"""
        self.control.app_control.progressbar = urwid.ProgressBar(
            'PB.normal', 'PB.complete', 0, max_progress, 'PB.satt'
        )
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
                    self.control.app_control.current_window =
                            self.control.app_control.message_box_caller
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
        body = urwid.LineBox(urwid.Padding(
            urwid.Filler(urwid.Pile([GText(mb_params.msg, urwid.CENTER)]), urwid.TOP)
        ))
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
            ib_params: parameter.InputBoxParams = parameter.InputBoxParams(
                None, None, "", False, None, True
            ),
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

            self.control.app_control.app_control.current_window_input_box =
                    _ANY_OF_YOUR_CURRENT_WINDOWS
            self.input_box('Y/n', 'Question', 'yes')

            # and later on event handling
            elif self.control.app_control.current_window == _ANY_OF_YOUR_CURRENT_WINDOWS:
                if key.endswith('enter') or key == 'esc':
                    self.control.app_control.current_window =
                            self.control.app_control.input_box_caller  # here you
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
                                "",
                                ib_params.input_text,
                                ib_params.multiline,
                                urwid.CENTER,
                                mask=ib_params.mask
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

    def start(self, immediate_restart: bool = False):
        """
        Starts the console UI
        """
        # set_trace(term_size=(129, 18))
        # set_trace()
        if immediate_restart:
            raise urwid.ExitMainLoop()
        self.prepare_mainscreen()
        self.control.app_control.loop.widget = self.control.app_control.body
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
