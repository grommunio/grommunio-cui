#!/usr/bin/env python3
#
#  Copyright (c) 2020 by grammm GmbH.
#
import sys
from asyncio.events import AbstractEventLoop
from pathlib import Path
from typing import Any, List, Tuple, Dict
import psutil
import os
import time
from ordered_set import OrderedSet
from psutil._common import snicstats, snicaddr
from getpass import getuser
from scroll import ScrollBar, Scrollable
from button import GButton, GBoxButton
from menu import MenuItem, MultiMenuItem
from interface import ApplicationHandler, WidgetDrawer
from common import DeviceInfo, DNSInfo, ifcfginfo
from util import authenticate_user, get_clockstring, get_palette, get_system_info, get_next_palette_name, fast_tail
from urwid import AttrWrap, ExitMainLoop, Padding, Columns, Text, ListBox, Frame, LineBox, SimpleListWalker, MainLoop, \
    LEFT, CENTER, SPACE, Filler, Pile, Edit, Button, connect_signal, AttrMap, GridFlow, Overlay, Widget, Terminal, \
    SimpleFocusListWalker, set_encoding, MIDDLE, TOP, RadioButton, ListWalker, raw_display


# print(sys.path)
try:
    import asyncio
except ImportError:
    import trollius as asyncio

_PRODUCTIVE: bool = True
loop: AbstractEventLoop
_MAIN: str = 'MAIN'
_MAIN_MENU: str = 'MAIN-MENU'
_TERMINAL: str = 'TERMINAL'
_LOGIN: str = 'LOGIN'
_LOGOUT: str = 'LOGOUT'
_NETWORK_CONFIG_MENU: str = 'NETWORK-CONFIG-MENU'
_UNSUPPORTED: str = 'UNSUPPORTED'
_PASSWORD: str = 'PASSWORD'
_DEVICE_CONFIG: str = 'DEVICE-CONFIG'
_IP_CONFIG: str = 'IP-CONFIG'
_IP_ADDRESS_CONFIG: str = 'IP-ADDRESS-CONFIG'
_DNS_CONFIG: str = 'DNS-CONFIG'
_MESSAGE_BOX: str = 'MESSAGE-BOX'
_LOG_VIEWER: str = 'LOG-VIEWER'


class Application(ApplicationHandler):
    """
    The console UI. Main application class.
    """
    current_window: str = _MAIN
    message_box_caller: str = ''
    _message_box_caller_body: Widget = None
    log_file_caller: str = ''
    _log_file_caller_body: Widget = None
    current_event = None
    current_bottom_info = 'Idle'
    menu_items: List[str] = []
    layout: Frame
    debug: bool = False
    current_menu_state: int = -1
    maybe_menu_state: int = -1
    active_device: str = 'lo'
    active_ips: Dict[str, List[Tuple[str, str, str, str]]] = {}

    # The default color palette
    _current_colormode: str = 'light'

    # The hidden input string
    _hidden_input: str = ""
    _hidden_pos: int = 0

    def __init__(self):
        # MAIN Page
        set_encoding('utf-8')
        self.screen = raw_display.Screen()
        undefined5 = ['undefined' for bla in range(0, 5)]
        self.screen.tty_signal_keys(*undefined5)
        self.text_header = (
            u"Welcome to grammm console user interface! UP / DOWN / PAGE UP / PAGE DOWN are scrolling.\n"
            u"<F1> switch to colormode '{colormode}', <F2> for Login{authorized_options} and <F12> for "
            u"exit/reboot.")
        self.authorized_options = ''
        text_intro = [u"Here is the ", ('HL.body', u"grammm"), u" terminal console user interface", u"\n",
                      u"   From here you can configure your system"]
        self.tb_intro = Text(text_intro, align=CENTER, wrap=SPACE)
        text_sysinfo_top = get_system_info("grammm_top")
        self.tb_sysinfo_top = Text(text_sysinfo_top, align=LEFT, wrap=SPACE)
        text_sysinfo_bottom = get_system_info("grammm_bottom")
        self.tb_sysinfo_bottom = Text(text_sysinfo_bottom, align=LEFT, wrap=SPACE)
        self.main_top = ScrollBar(Scrollable(
            Pile([
                Padding(self.tb_intro, left=2, right=2, min_width=20),
                Padding(self.tb_sysinfo_top, align=LEFT, left=6, width=('relative', 80))
            ])
        ))
        self.main_bottom = ScrollBar(Scrollable(
            Pile([AttrWrap(Padding(self.tb_sysinfo_bottom, align=LEFT, left=6, width=('relative', 80)), 'reverse')])
        ))
        colormode: str = "light" if self._current_colormode == 'dark' else 'dark'
        self.tb_header = Text(self.text_header.format(colormode=colormode, authorized_options=''), align=CENTER,
                              wrap=SPACE)
        self.header = AttrMap(Padding(self.tb_header, align=CENTER), 'header')
        self.vsplitbox = Pile([("weight", 50, AttrMap(self.main_top, "body")), ("weight", 50, self.main_bottom)])
        self.footer_text = Text('heute')
        self.print("Idle")
        self.footer = AttrMap(self.footer_text, 'footer')
        # frame = Frame(AttrMap(self.vsplitbox, 'body'), header=self.header, footer=self.footer)
        frame = Frame(AttrMap(self.vsplitbox, 'reverse'), header=self.header, footer=self.footer)
        self.mainframe = LineBox(frame)
        self._body = self.mainframe

        # Loop
        self._loop = MainLoop(
            self._body,
            get_palette(self._current_colormode),
            unhandled_input=self.handle_event
        )
        self._loop.set_alarm_in(1, self.update_clock)
        self._loop.screen.set_terminal_properties(colors=256)

        # Login Dialog
        self.login_header = AttrMap(Text(('header', 'Please Login'), align='center'), 'header')
        self.user_edit = Edit("Username: ", edit_text=getuser(), edit_pos=0)
        self.pass_edit = Edit("Password: ", edit_text="", edit_pos=0, mask='*')
        self.login_body = Pile([
            AttrMap(self.user_edit, 'selectable', 'focus'),
            self.pass_edit,
        ])
        login_button = GBoxButton("Login", self.check_login)
        connect_signal(login_button, 'click', lambda button: self.handle_event('login enter'))
        # self.login_footer = GridFlow([login_button], 10, 1, 1, 'center')
        self.login_footer = AttrMap(Columns([Text(""), login_button, Text("")]), 'buttonbar')

        # Common OK Button
        # self.ok_button = GButton("OK", self.press_button, left_end='[', right_end=']')
        self.ok_button = GBoxButton("OK", self.press_button)
        connect_signal(self.ok_button, 'click', lambda button: self.handle_event('ok enter'))
        self.ok_button = (8, self.ok_button)
        self.ok_button_footer = AttrMap(Columns([
            ('weight', 1, Text('')),
            ('weight', 1, Columns([('weight', 1, Text('')), self.ok_button, ('weight', 1, Text(''))])),
            ('weight', 1, Text(''))
        ]), 'buttonbar')

        # Common Cancel Button
        self.cancel_button = GBoxButton("Cancel", self.press_button)
        connect_signal(self.cancel_button, 'click', lambda button: self.handle_event('cancel enter'))
        self.cancel_button = (12, self.cancel_button)
        self.cancel_button_footer = GridFlow([self.cancel_button[1]], 10, 1, 1, 'center')

        # Common Close Button
        self.close_button = GBoxButton("Close", self.press_button)
        connect_signal(self.close_button, 'click', lambda button: self.handle_event('close enter'))
        self.close_button = (11, self.close_button)
        # self.close_button_footer = GridFlow([self.close_button], 10, 1, 1, 'center')
        self.close_button_footer = AttrMap(Columns([
            ('weight', 1, Text('')),
            ('weight', 1, Columns([('weight', 1, Text('')), self.close_button, ('weight', 1, Text(''))])),
            ('weight', 1, Text(''))
        ]), 'buttonbar')

        # Common Add Button
        self.add_button = GBoxButton("Add", self.press_button)
        connect_signal(self.add_button, 'click', lambda button: self.handle_event('add enter'))
        self.add_button = (9, self.add_button)
        self.add_button_footer = GridFlow([self.add_button[1]], 10, 1, 1, 'center')

        # Common Edit Button
        self.edit_button = GBoxButton("Edit", self.press_button)
        connect_signal(self.edit_button, 'click', lambda button: self.handle_event('edit enter'))
        self.edit_button = (10, self.edit_button)
        self.edit_button_footer = GridFlow([self.edit_button[1]], 10, 1, 1, 'center')

        # Common Details Button
        self.details_button = GBoxButton("Details", self.press_button)
        connect_signal(self.details_button, 'click', lambda button: self.handle_event('details enter'))
        self.details_button = (13, self.details_button)
        self.details_button_footer = GridFlow([self.details_button[1]], 10, 1, 1, 'center')

        # Common Toggle Button
        self.toggle_button = GBoxButton("Space to toggle", self.press_button)
        self.toggle_button._selectable = False
        self.toggle_button = (21, self.toggle_button)
        self.toggle_button_footer = GridFlow([self.toggle_button[1]], 10, 1, 1, 'center')

        # Common Apply Button
        self.apply_button = GBoxButton("Apply", self.press_button)
        connect_signal(self.apply_button, 'click', lambda button: self.handle_event('apply enter'))
        self.apply_button = (12, self.apply_button)
        self.apply_button_footer = GridFlow([self.apply_button[1]], 10, 1, 1, 'center')

        # Common Save Button
        self.save_button = GBoxButton("Save", self.press_button)
        connect_signal(self.save_button, 'click', lambda button: self.handle_event('save enter'))
        self.save_button = (10, self.save_button)
        self.save_button_footer = GridFlow([self.save_button[1]], 10, 1, 1, 'center')

        # The common menu description column
        self.menu_description = Pile([Text('Main Menu', CENTER), Text('Here you can do the main actions', LEFT)])

        # Main Menu
        items = {
            '1) Change Password': Pile([
                Text('Changing Password', CENTER), Text(""),
                Text(f'Use this for changing your password of user {getuser()}.')
            ]),
            '2) Network Configuration': Pile([
                Text('Network Configuration', CENTER), Text(""),
                Text('Here you can configure the Network. Set up the active device, configure IP address and DNS.')
            ]),
            '3) Terminal': Pile([
                Text('Terminal', CENTER), Text(""),
                # Text('Starts Terminal and closes everything else.'),
                Text('Starts Terminal in a sub window.')
            ]),
        }
        self.main_menu_list = self.prepare_menu_list(items)
        self.main_menu = self.wrap_menu(self.main_menu_list)

        # Network Config Menu
        items = {
            '1) Device Configuration': Pile([
                Text('Device Configuration', CENTER), Text(""),
                Text('Here you can select your active device.')
            ]),
            '2) IP Configuration': Pile([
                Text('IP Configuration', CENTER), Text(""),
                Text('Here you can configure the IP Addresses etc. for the Network.')
            ]),
            '3) DNS Configuration': Pile([
                Text('DNS Configuration', CENTER), Text(""),
                Text('Configure Domain Name Server.')
            ]),
        }
        self.network_menu_list = self.prepare_menu_list(items)
        self.network_menu = self.wrap_menu(self.network_menu_list)

        # Terminal Dialog
        # self.terminal_footer = GridFlow([self.close_button], 10, 1, 1, 'center')
        self.terminal_footer = self.close_button_footer
        self.term = Terminal(None)
        self.terminal_frame = LineBox(
            Pile([
                ('weight', 70, self.term),
            ]),
        )

        # Password Dialog
        self.password = Terminal(["passwd"])
        self.password_frame = LineBox(
            Pile([
                ('weight', 70, self.password),
            ]),
        )

        # Device Config Menu
        self.prepare_device_config()

        # IP Config Menu
        self.prepare_ip_config()

        # DNS Config Menu
        self.prepare_dns_config()

        # Log file viewer
        self.log_file_content: List[str] = [
            "If this is not that what you expected to see,",
            "You probably have insufficient permissions!?"
        ]
        self.prepare_log_viewer('syslog', 200)

        # UNSUPPORTED shell
        self.unsupported_term = Terminal(None, encoding='utf-8')
        for w in self.unsupported_term.signals:
            connect_signal(self.unsupported_term, w, lambda widget: self.listen_unsupported(w, widget))
        self.unsupported_frame = LineBox(Pile([self.unsupported_term]))

        # some settings
        MultiMenuItem.application = self
        GButton.application = self

    def listen_unsupported(self, what: str, key: Any):
        self.print(f"What is {what}.")
        if key in ['ctrl a', 'A']:
            return key

    def handle_event(self, event: Any):
        """
        Handles user input to the console UI.

            :param event: A mouse or keyboard input sequence. While the mouse event has the form ('mouse press or
                release', button, column, line), the key stroke is represented as is a single key or even the
                represented value like 'enter', 'up', 'down', etc.
            :type: Any
        """
        log_finished: bool = False
        self.current_event = event
        if type(event) == str:
            # event was a key stroke
            key: str = str(event)
            if self.current_window == _MAIN:
                if len(self.authorized_options) > 0:
                    # user has successfully logged in
                    if key == 'f4':
                        self.open_main_menu()
                if key in ['f2', 'f12', 'S' if self.debug else 'f12']:
                    self.login_body.focus_position = 0 if getuser() == '' else 1  # focus on passwd if user detected
                    if key != 'f2':
                        self.user_edit.edit_text = "root"  # need to be superuser for shutdown
                    self.dialog(body=LineBox(Padding(Filler(self.login_body))), header=self.login_header,
                                footer=self.login_footer, focus_part='body', align='center', valign='middle',
                                width=40, height=10)
                    if key == 'f2':
                        self.current_window = _LOGIN
                    elif key in ['S', 'f12']:
                        self.current_window = _LOGOUT
                elif key == 'l' and not _PRODUCTIVE:
                    self.open_main_menu()
                elif key == 'tab':
                    self.vsplitbox.focus_position = 0 if self.vsplitbox.focus_position == 1 else 1

            elif self.current_window == _MESSAGE_BOX:
                if key.endswith('enter') or key == 'esc':
                    self.current_window = self.message_box_caller
                    self._body = self._message_box_caller_body
                    self.reset_layout()

            elif self.current_window == _TERMINAL:
                self.handle_standard_tab_behaviour(key)
                if key == 'f10':
                    raise ExitMainLoop()
                elif key.endswith('enter') or key == 'esc':
                    self.open_main_menu()

            elif self.current_window == _PASSWORD:
                self.handle_standard_tab_behaviour(key)
                if key == 'close enter' or key == 'esc':
                    self.open_main_menu()

            elif self.current_window in [_LOGIN, _LOGOUT]:
                self.handle_standard_tab_behaviour(key)
                if key.endswith('enter'):
                    self.check_login()
                elif key == 'esc':
                    self.open_mainframe()

            elif self.current_window == _MAIN_MENU:
                menu_selected: int = self.handle_standard_menu_behaviour(self.main_menu_list, key,
                                                                         self.main_menu.base_widget.body[1])
                if key.endswith('enter') or key in range(ord('1'), ord('9') + 1):
                    if menu_selected == 1:
                        self.open_change_password()
                    elif menu_selected == 2:
                        self.open_network_config()
                    elif menu_selected == 3:
                        self.open_terminal()
                elif key == 'esc':
                    self.open_mainframe()

            elif self.current_window == _NETWORK_CONFIG_MENU:
                menu_selected: int = self.handle_standard_menu_behaviour(self.network_menu_list, key,
                                                                         self.network_menu.base_widget.body[1])
                if key.endswith('enter') or key in range(ord('1'), ord('9') + 1):
                    if menu_selected == 1:
                        self.open_device_config(self.active_device)
                    elif menu_selected == 2:
                        self.open_ip_config()
                    elif menu_selected == 3:
                        self.open_dns_config()
                elif key == 'esc':
                    self.open_main_menu()

            elif self.current_window == _DEVICE_CONFIG:
                self.handle_standard_tab_behaviour(key)
                menu_selected = 0
                if key.endswith('enter') or key in range(ord('1'), ord('9') + 1):
                    if key.lower().find('cancel') > 0:
                        self.open_network_config()
                    elif key.lower().find('ok') > 0:
                        self.active_device = self.get_pure_menu_name(
                            self.device_config_menu_list[0].get_selected().label)
                        self.open_network_config()
                    elif key.lower().find('details') > 0:
                        self.active_device = self.get_pure_menu_name(
                            self.device_config_menu_list[0].get_selected().label)
                        self.open_ip_config()
                elif key == "multimenuitem  ":
                    # self.maybe_menu_state = self.device_config_menu_list[0].get_selected_id()
                    pass
                elif key == 'esc':
                    self.open_network_config()

            elif self.current_window == _IP_CONFIG:
                self.handle_standard_tab_behaviour(key)
                menu_selected = 0
                if key.endswith('enter') or key in range(ord('1'), ord('9') + 1):
                    if key.lower().find('cancel') > 0:
                        self.open_device_config(self.active_device)
                    elif key.lower().find('apply') > 0:
                        self.write_ip_config()
                    elif key.lower().find('ok') > 0:
                        self.write_ip_config()
                        self.open_device_config(self.active_device)
                elif key == 'esc':
                    self.open_device_config(self.active_device)

            elif self.current_window == _DNS_CONFIG:
                self.handle_standard_tab_behaviour(key)
                menu_selected = 0
                if key.endswith('enter') or key in range(ord('1'), ord('9') + 1):
                    if key.lower().find('cancel') > 0:
                        self.open_network_config()
                    elif key.lower().find('apply') > 0:
                        self.write_dns_config()
                    elif key.lower().find('ok') > 0:
                        self.write_dns_config()
                        self.open_network_config()
                elif key == 'esc':
                    self.open_network_config()

            elif self.current_window == _LOG_VIEWER:
                if key in ['meta f1', 'H']:
                    self.current_window = self.log_file_caller
                    self._body = self._log_file_caller_body
                    self.reset_layout()
                    log_finished = True
                elif self._hidden_pos < len(_UNSUPPORTED) and key == _UNSUPPORTED.lower()[self._hidden_pos]:
                    self._hidden_input += key
                    self._hidden_pos += 1
                    if self._hidden_input == _UNSUPPORTED.lower():
                        self.open_unsupported()
                        # raise ExitMainLoop()
                else:
                    self._hidden_input = ""
                    self._hidden_pos = 0

            elif self.current_window == _UNSUPPORTED:
                if key in ['ctrl d', 'esc', 'meta f1']:
                    self.current_window = self.log_file_caller
                    self._body = self._log_file_caller_body
                    self.reset_layout()

            if key in ['f10', 'Q']:
                raise ExitMainLoop()
            elif key == 'f4' and len(self.authorized_options) > 0:
                self.open_mainframe()
            elif key == 'f1' or key == 'c':
                # self.change_colormode('dark' if self._current_colormode == 'light' else 'light')
                self.switch_next_colormode()
            elif key in ['meta f1', 'H'] and self.current_window != _LOG_VIEWER and not log_finished:
                # self.open_log_viewer('test', 10)
                self.open_log_viewer('syslog', 200)

        elif type(event) == tuple:
            # event is a mouse event in the form ('mouse press or release', button, column, line)
            event: Tuple[str, float, int, int] = tuple(event)
            if event[0] == 'mouse press' and event[1] == 1:
                # self.handle_event('mouseclick left enter')
                self.handle_event('my mouseclick left button')

        self.print(self.current_bottom_info)

    @staticmethod
    def get_pure_menu_name(label: str) -> str:
        """
        Reduces label with id to original label-only form.

        :param label: The label in form "ID) LABEL" or "LABEL".
        :return: Only LABEL without "ID) ".
        """
        if label.find(') ') > 0:
            parts = label.split(') ')
            if len(parts) < 2:
                return label
            else:
                return parts[1]
        else:
            return label

    def handle_click(self, creator: Widget, option: bool = False):
        """
        Handles RadioButton clicks.

        :param creator: The widget creating calling the function.
        :param option: On if True, of otherwise.
        """
        self.print(f"Creator ({creator}) clicked {option}.")

    def handle_menu_changed(self, *args, **kwargs):
        """
        Is called additionally if item is chnaged (???).
        TODO Check what this does exactly.  or when it is called

        :param args: Optional user_args.
        :param kwargs: Optional keyword args
        """
        self.print(f"Called handle_menu_changed() with args({args}) und kwargs({kwargs})")

    def handle_menu_activated(self, *args, **kwargs):
        """
        Is called additionally if menu is activated.
        (Maybe obsolete!)

        :param args: Optional user_args.
        :param kwargs: Optional keyword args
        """
        self.print(f"Called handle_menu_activated() with args({args}) und kwargs({kwargs})")

    def open_terminal(self):
        """
        Opens terminal dialog.
        """
        self.reset_layout()
        self.current_window = _TERMINAL
        self.dialog(
            header=Text(f"Terminal for user {getuser()}", align='center'),
            body=self.terminal_frame, footer=self.terminal_footer, focus_part='body',
            align='center', valign='middle', width=80, height=25
        )
        self.term.main_loop = self._loop

    def open_unsupported(self):
        """
        Opens terminal dialog.
        """
        self.reset_layout()
        self.current_window = _UNSUPPORTED
        self._body = self.unsupported_frame
        self._loop.widget = self._body

    def open_change_password(self):
        """
        Opens password changing dialog.
        """
        self.reset_layout()
        self.current_window = _PASSWORD
        self.print('Opening change password dialog.')
        self.dialog(
            header=Text(f"Change password for user {getuser()}", align='center'),
            body=self.password_frame, footer=self.close_button_footer, focus_part='body',
            align=CENTER, valign='middle', width=80, height=25
        )

    def prepare_device_config(self, selected: str = None):
        """
        Prepares the device config dialog with selected device.

        :param selected: The device to be selected.
        """
        th: Columns
        th, items = self.get_device_config_info()
        table_header = AttrMap(Filler(th, TOP), 'reverse')
        self.device_config_menu_list: List[MultiMenuItem] = self.create_multi_menu_items(items, selected)
        self.device_config_menu_listbox: ListBox[ListWalker] = self.create_multi_menu_listbox(
            self.device_config_menu_list)
        self.device_config_menu: LineBox = self.wrap_multi_menu_listbox(self.device_config_menu_listbox, table_header,
                                                                        'Device Config Menu')

    def open_device_config(self, selected: str = None):
        """
        Opens device config dialog with selected device.

        :param selected: The device to be selected.
        """
        self.reset_layout()
        self.current_window = _DEVICE_CONFIG
        self.print("Device Config has to open ...")
        self.prepare_device_config(selected)
        self.dialog(
            body=self.device_config_menu, footer=AttrMap(Columns([
                ('weight', 50, Columns([self.toggle_button, self.details_button])),
                ('weight', 30, Columns([self.ok_button, self.cancel_button])),
            ]), 'buttonbar'), focus_part='body',
            align=CENTER, valign=MIDDLE, width=130, height=15
        )
        self.current_menu_state = self.device_config_menu_list[0].get_selected_id()

    def prepare_ip_config(self, dhcp_state: bool = None):
        """
        Prepares ip config dialog with dhcp or static set.

        :param dhcp_state: DHCP is on if True, STATIC if false
        """
        device: str = self.active_device
        if self.active_device == 'None':
            device = 'lo'
        grp = []
        th = Text(f"IP configuration of {device}")
        di = DeviceInfo(device)
        if dhcp_state is None:
            dhcp_state = True
            if di.dhcp.lower().find('dhcp') < 0:
                dhcp_state = False
        dhcp = RadioButton(grp, "Configure IP Address automatically (DHCP)", dhcp_state, self.check_ip_config)
        static = RadioButton(grp, "Configure IP Address manually (STATIC)", not dhcp_state, self.check_ip_config)
        table_header = AttrMap(Filler(th, TOP), 'reverse')
        # self.ip_config_menu_list: List[RadioButton] = grp
        self.ip_config_menu_list: List[RadioButton] = [
            AttrMap(dhcp, 'MMI.selectable', 'MMI.focus'), AttrMap(static, 'MMI.selectable', 'MMI.focus')
        ]
        self.ip_config_menu_listbox: ListBox[ListWalker] = ListBox(SimpleFocusListWalker(self.ip_config_menu_list))
        self.ip_config_menu_content = self.get_ip_config_info(dhcp_state)
        self.ip_config_menu: LineBox = LineBox(Pile([
            (3, AttrMap(Filler(Text('IP Config Menu', CENTER), TOP), 'body')),
            (1, table_header),
            AttrMap(Columns([self.ip_config_menu_listbox]), 'MMI.selectable'),
            AttrMap(Filler(self.ip_config_menu_content, TOP), 'MMI.selectable'),
        ]))
        self.ip_config_menu.base_widget.focus_position = 2 if dhcp_state else 3

    def check_ip_config(self, rb: RadioButton, state: bool):
        """
        Checks currently selected menu item and reopens ip config dialog.
        This method is always called if state is switching between dhcp and static.

        :param rb: The RadioButton that is calling.
        :param state: If rb is set or unset.
        """
        if state:
            dhcp: bool
            if str(rb.label).lower().find('dhcp') < 0:
                dhcp = False
            else:
                dhcp = True
            self.open_ip_config(dhcp)

    def open_ip_config(self, dhcp_state: bool = None):
        """
        Opens ip config dialog with dhcp or static set.

        :param dhcp_state: DHCP is on if True, STATIC if false
        """
        self.reset_layout()
        self.current_window = _IP_CONFIG
        self.print("IP Config has to open ...")
        self.prepare_ip_config(dhcp_state)
        self.dialog(
            body=self.ip_config_menu, footer=AttrMap(Columns([
                ('weight', 50, Columns([self.toggle_button, self.apply_button])),
                ('weight', 30, Columns([self.ok_button, self.cancel_button]))
            ]), 'buttonbar'), focus_part='body',
            align=CENTER, valign=MIDDLE, width=80, height=15
        )
        # self.current_menu_state = self.ip_config_menu_list[0].get_selected_id()

    def prepare_dns_config(self, dns_state: bool = None):
        """
        Prepares DNS config dialog with auto or manually set.

        :param dns_state: DNS auto is on if True, off if false
        """
        grp = []
        th = Text("DNS configuration")
        di = DNSInfo()
        if dns_state is None:
            dns_state = True
            if not di.auto:
                dns_state = False
        auto = RadioButton(grp, "Obtain DNS IP Address and hostname automatically, ", dns_state, self.check_dns_config)
        dns = RadioButton(grp, "or use following DNS and host informations.", not dns_state, self.check_dns_config)
        table_header = AttrMap(Filler(th, TOP), 'reverse')
        # self.dns_config_menu_list: List[RadioButton] = grp
        self.dns_config_menu_list: List[RadioButton] = [
            AttrMap(auto, 'MMI.selectable', 'MMI.focus'), AttrMap(dns, 'MMI.selectable', 'MMI.focus')
        ]
        self.dns_config_menu_listbox: ListBox[ListWalker] = ListBox(SimpleFocusListWalker(self.dns_config_menu_list))
        self.dns_config_menu_content = self.get_dns_config_info(dns_state)
        self.dns_config_menu: LineBox = LineBox(Pile([
            (3, AttrMap(Filler(Text('DNS Config Menu', CENTER), TOP), 'body')),
            (1, table_header),
            AttrMap(Columns([self.dns_config_menu_listbox]), 'MMI.selectable'),
            AttrMap(Filler(self.dns_config_menu_content, TOP), 'MMI.selectable'),
        ]))
        self.dns_config_menu.base_widget.focus_position = 2 if dns_state else 3

    def prepare_log_viewer(self, logfile: str = 'syslog', lines: int = 0):
        """
Prepares log file viewer widget and fills last lines of file content.

:param logfile: The logfile to be viewed.
        """
        filename: str = '/var/log/messages'
        if logfile == 'syslog':
            filename = '/var/log/messages'
        elif logfile == 'test':
            filename = '../README.md'

        log: Path = Path(filename)

        if log.exists():
            # self.log_file_content = log.read_text('utf-8')[:lines * -1]
            if os.access(str(log), os.R_OK):
                self.log_file_content = fast_tail(str(log.absolute()), lines)

        self.log_viewer = LineBox(Pile([ScrollBar(Scrollable(Pile([Text(line) for line in self.log_file_content])))]))

    def check_dns_config(self, rb: RadioButton, state: bool):
        """
        Checks currently selected menu item and reopens dns config dialog.
        This method is always called if state is switching between DNS auto and manually.

        :param rb: The RadioButton that is calling.
        :param state: If rb is set or unset.
        """
        if state:
            dns: bool
            if str(rb.label).lower().find('auto') < 0:
                dns = False
            else:
                dns = True
            self.open_dns_config(dns)

    def open_log_viewer(self, logfile: str, lines: int = 0):
        """
        Opens log file viewer.
        """
        self.log_file_caller = self.current_window
        self._log_file_caller_body = self._body
        self.current_window = _LOG_VIEWER
        self.print(f"Log file viewer has to open file {logfile} ...")
        self.prepare_log_viewer(logfile, lines)
        self._body = self.log_viewer
        self._loop.widget = self._body

    def open_dns_config(self, dns_state: bool = None):
        """
        Opens DNS config dialog.
        """
        self.reset_layout()
        self.current_window = _DNS_CONFIG
        self.print("DNS Config has to open ...")
        self.prepare_dns_config(dns_state)
        self.dialog(
            body=self.dns_config_menu, footer=AttrMap(Columns([
                ('weight', 50, Columns([self.toggle_button, self.apply_button])),
                ('weight', 30, Columns([self.ok_button, self.cancel_button]))
            ]), 'buttonbar'), focus_part='body',
            align=CENTER, valign=MIDDLE, width=80, height=15
        )

    def open_network_config(self):
        """
        Opens network config menu.
        """
        self.reset_layout()
        self.print("Enter network config!")
        self.current_window = _NETWORK_CONFIG_MENU
        self._body = self.network_menu
        self._loop.widget = self._body

    def open_main_menu(self):
        """
        Opens amin menu,
        """
        self.reset_layout()
        self.print("Login successfully!")
        self.current_window = _MAIN_MENU
        self.authorized_options = ', <F4> for Main-Menu'
        colormode: str = "light" if self._current_colormode == 'dark' else 'dark'
        self.tb_header.set_text(self.text_header.format(colormode=colormode,
                                                        authorized_options=self.authorized_options))
        self._body = self.main_menu
        self._loop.widget = self._body

    def open_mainframe(self):
        """
        Opens main window. (Welcome screen)
        """
        self.reset_layout()
        self.print("Returning to main screen!")
        self.current_window = _MAIN
        self._body = self.mainframe
        self._loop.widget = self._body

    def check_login(self, w: Widget = None):
        """
        Checks login data and switch to authenticate on if successful.
        """
        msg = f"checking user {self.user_edit.get_edit_text()} with pass {self.pass_edit.get_edit_text()} ..."
        msg += f"activated by {w}!"
        if self.current_window == _LOGIN:
            if authenticate_user(self.user_edit.get_edit_text(), self.pass_edit.get_edit_text()):
                self.open_main_menu()
            else:
                self.message_box(f'You have taken a wrong password, {self.user_edit.get_edit_text()}!')
                self.print(f"Login wrong! ({msg})")
        elif self.current_window == _LOGOUT:
            if self.user_edit.get_edit_text() != 'root':
                self.message_box('You need to be superuser!')
                self.user_edit.edit_text = 'root'
            elif authenticate_user(self.user_edit.get_edit_text(), self.pass_edit.get_edit_text()):
                self.message_box('After pressing OK, the system will be shut down!\nBe sure to leave nothing undone.')
                os.system('/sbin/shutdown -h now')
            else:
                self.print(f"Login wrong! ({msg})")
                self.message_box(f'You have taken a wrong password, {self.user_edit.get_edit_text()}!')

    def press_button(self, button: Widget, *args, **kwargs):
        """
        Handles general events if a button is pressed.

        :param button: The button been clicked.
        """
        label: str = "UNKNOWN LABEL"
        if isinstance(button, Button) or isinstance(button, WidgetDrawer):
            label = button.label
        if not self.current_window == _MAIN:
            self.print(f"{self.__class__}.press_button(button={button}, *args={args}, kwargs={kwargs})")
            self.handle_event(f"{label} enter")

    def prepare_menu_list(self, items: Dict[str, Widget]) -> ListBox:
        """
        Prepare general menu list.

        :param items: A dictionary of widgets representing the menu items.
        :return: ListBox containig menu items.
        """
        menu_items: List[MenuItem] = self.create_menu_items(items)
        return ListBox(SimpleFocusListWalker(menu_items))

    def wrap_menu(self, listbox: ListBox) -> LineBox:
        """
        Wraps menu ListBox with LineBox.

        :param listbox:  The ListBox to be wrapped.
        :return: The LineBox wrapping ListBox.
        """
        menu = Columns([
            AttrMap(listbox, 'body'),
            AttrMap(ListBox(SimpleListWalker([self.menu_description])), 'reverse'),
        ])
        menu[1]._selectable = False
        return LineBox(Frame(menu, header=self.header, footer=self.footer))

    def prepare_radio_list(self, items: Dict[str, Widget]) -> Tuple[ListBox, ListBox]:
        """
        Prepares general radio list containing RadioButtons and content.

        :param items: A dictionary of widgets representing the menu items.
        :return: Tuple of one ListBox containing menu items and one containing the content.
        """
        radio_items: List[RadioButton]
        radio_content: List[Widget]
        radio_items, radio_content = self.create_radiobutton_items(items)
        radio_walker: ListWalker = SimpleListWalker(radio_items)
        content_walker: ListWalker = SimpleListWalker(radio_content)
        if len(radio_items) > 0:
            connect_signal(radio_walker, 'modified', self.handle_event, user_args=[radio_walker, radio_items])
        return ListBox(radio_walker), ListBox(content_walker)

    def wrap_radio(self, master: ListBox, slave: ListBox, header: Widget, title: str = None) -> LineBox:
        """
        Wraps the two ListBoxes returned by ::self::.prepare_radio_list() as master (RadioButton) and slave (content)
        with menues header and an optional title.

        :param master: The leading RadioButtons.
        :param slave: The following content widgets.
        :param header: The menu header.
        :param title: The optional title.
        :return: The wrapped LineBox.
        """
        title = 'Menu' if title is None else title
        return LineBox(Pile([
            (3, AttrMap(Filler(Text(title, CENTER), TOP), 'body')),
            (1, header),
            AttrMap(Columns([
                ('weight', 1, AttrMap(master, 'MMI.selectable', 'MMI.focus')),
                ('weight', 4, AttrMap(slave, 'MMI.selectable', 'MMI.focus')),
            ]), 'reverse'),
        ]))

    def change_colormode(self, mode: str):
        p = get_palette(mode)
        self._current_colormode = mode
        colormode: str = "light" if self._current_colormode == 'dark' else 'dark'
        self.tb_header.set_text(self.text_header.format(colormode=colormode,
                                                        authorized_options=self.authorized_options))
        self._loop.screen.register_palette(p)
        self._loop.screen.clear()

    def switch_next_colormode(self):
        o = self._current_colormode
        n = get_next_palette_name(o)
        p = get_palette(n)
        self.tb_header.set_text(self.text_header.format(colormode=get_next_palette_name(n),
                                                        authorized_options=self.authorized_options))
        self._loop.screen.register_palette(p)
        self._loop.screen.clear()
        self._current_colormode = n

    def redraw(self):
        """
        Redraws screen.
        """
        self._loop.draw_screen()

    def reset_layout(self):
        """
        Resets the console UI to the default layout
        """

        self._loop.widget = self._body
        self._loop.draw_screen()

    def create_menu_items(self, items: Dict[str, Widget]) -> List[MenuItem]:
        """
        Takes a dictionary with menu labels as keys and widget(lists) as content and creates a list of menu items.

        :param items: Dictionary in the form {'label': Widget}.
        :return: List of MenuItems.
        """
        menu_items: List[MenuItem] = []
        for id, caption in enumerate(items.keys(), 1):
            item = MenuItem(id, caption, items.get(caption), self)
            connect_signal(item, 'activate', self.handle_event)
            menu_items.append(AttrMap(item, 'selectable', 'focus'))
        return menu_items

    def create_radiobutton_items(self, items: Dict[str, Widget]) -> Tuple[List[RadioButton], List[Widget]]:
        """
        Takes a dictionary with menu labels as keys and widget(lists) as content and creates a tuple of two lists.
        One list of leading RadioButtons and the second list contains the following widget..

        :param items: Dictionary in the form {'label': Widget}.
        :return: Tuple with two lists. One List of MenuItems representing the leading radio buttons and one the content
                 widget.
        """
        menu_items: List[RadioButton] = []
        my_items: List[RadioButton] = []
        my_items_content: List[Widget] = []
        for id, caption in enumerate(items.keys(), 1):
            item = RadioButton(menu_items, caption, on_state_change=self.handle_click)
            my_items.append(AttrMap(item, 'MMI-selectable', 'MMI.focus'))
            my_items_content.append(AttrMap(items.get(caption), 'MMI-selectable', 'MMI.focus'))
        return my_items, my_items_content

    def create_multi_menu_items(self, items: Dict[str, Widget], selected: str = None) -> List[MultiMenuItem]:
        """
        Takes a dictionary with menu labels as keys and widget(lists) as content and creates a list of multi menu items
        with being one selected..

        :param items: Dictionary in the form {'label': Widget}.
        :param selected: The label of the selected multi menu item.
        :return: List of MultiMenuItems.
        """
        menu_items: List[MultiMenuItem] = []
        my_items: List[MultiMenuItem] = []
        for id, caption in enumerate(items.keys(), 1):
            caption_wo_no: str = self.get_pure_menu_name(caption)
            state: Any
            if selected is not None:
                if selected == caption_wo_no:
                    state = True
                else:
                    state = False
            else:
                state = 'first True'
            item = MultiMenuItem(menu_items, id, caption_wo_no, items.get(caption), state=state,
                                 on_state_change=MultiMenuItem.handle_menu_changed, app=self)
            my_items.append(item)
            # connect_signal(item, 'activate', self.handle_event)
            # menu_items.append(AttrMap(item, 'selectable', 'focus'))
        return my_items

    def create_multi_menu_listbox(self, menu_list: List[MultiMenuItem]) -> ListBox:
        """
        Creates general listbox of multi menu items from list of multi menu items.

        :param menu_list: list of MultiMenuItems
        :return: The ListBox.
        """
        listbox: ListBox[ListWalker] = ListBox(SimpleListWalker(menu_list))
        item: MultiMenuItem
        for item in menu_list:
            item.set_parent_listbox(listbox)
        return listbox

    def wrap_multi_menu_listbox(self, listbox: ListBox, header: Widget = None, title: str = None) -> LineBox:
        """
        Wraps general listbox of multi menu items with a linebox.

        :param listbox: ListBox to be wrapped.
        :param header: Optional ListBox header.
        :param title: Optional title. "Menu" is used if title is None.
        :return: The wrapping LineBox around the ListBox.
        """
        title = 'Menu' if title is None else title
        return LineBox(Pile([
            (3, AttrMap(Filler(Text(title, CENTER), TOP), 'body')),
            (1, header) if header is not None else (),
            AttrMap(Columns([listbox]), 'MMI.selectable'),
        ]))

    def get_ip_config_info(self, readonly: bool = True) -> Pile:
        """
        Returns pile filled with ip config info area. The area containing IP-address, Netmask and Gateway.
        The Fields are readonly by default, usually dhcp mode. In the other case editable Edit fields will be returned
        instead.

        :param readonly: The mode the area will be displayed.
        :return: Pile with 3 Lines of Columns([Text("..."), Text(value)]) on readonly
                 or 3 Lines of Columns([Text("..."), Edit(""]) (with .edit_text = value set) if not readonly.
        """
        di = DeviceInfo(self.active_device if not self.active_device == 'None' else 'lo')
        ip = Columns([
            AttrMap(Text('IP-Address'), 'MMI.selectable', 'MMI.focus'),
            AttrMap(Text(di.ipaddr), 'MMI.selectable', 'MMI.focus')
            if readonly else AttrMap(Edit(''), 'MMI.selectable', 'MMI.focus')
        ])
        nm = Columns([
            AttrMap(Text('Netmask'), 'MMI.selectable', 'MMI.focus'),
            AttrMap(Text(di.netmask), 'MMI.selectable', 'MMI.focus')
            if readonly else AttrMap(Edit(''), 'MMI.selectable', 'MMI.focus')
        ])
        gw = Columns([
            AttrMap(Text('Gateway'), 'MMI.selectable', 'MMI.focus'),
            AttrMap(Text(di.gateway), 'MMI.selectable', 'MMI.focus')
            if readonly else AttrMap(Edit(''), 'MMI.selectable', 'MMI.focus')
        ])
        if not readonly:
            ip[1].edit_text = di.ipaddr
            nm[1].edit_text = di.netmask
            gw[1].edit_text = di.gateway
        return Pile([ip, nm, gw])

    @staticmethod
    def get_dns_config_info(readonly: bool = True) -> Pile:
        """
        Returns pile filled with dns config info area. The area containing primary and secondary nameservers, gateway
        and DNS suffixes. The fields are readonly by default, usually auto mode. In the other case editable Edit
        fields will be returned instead.

        :param readonly: The mode the area will be displayed.
        :return: Pile with 4 Lines of Columns([Text("..."), Text(value)]) on readonly
                 or 4 Lines of Columns([Text("..."), Edit(""]) (with .edit_text = value set) if not readonly.
        """
        di = DNSInfo()
        prim = Columns([
            AttrMap(Text('Primary Nameserver'), 'MMI.selectable', 'MMI.focus'),
            AttrMap(Text(di.primary), 'MMI.selectable', 'MMI.focus')
            if readonly else AttrMap(Edit(''), 'MMI.selectable', 'MMI.focus')
        ])
        sec = Columns([
            AttrMap(Text('Secondary Nameserver'), 'MMI.selectable', 'MMI.focus'),
            AttrMap(Text(di.secondary), 'MMI.selectable', 'MMI.focus')
            if readonly else AttrMap(Edit(''), 'MMI.selectable', 'MMI.focus')
        ])
        host = Columns([
            AttrMap(Text('Hostname'), 'MMI.selectable', 'MMI.focus'),
            AttrMap(Text(di.hostname), 'MMI.selectable', 'MMI.focus')
            if readonly else AttrMap(Edit(''), 'MMI.selectable', 'MMI.focus')
        ])
        search = Columns([
            AttrMap(Text('Searchlist'), 'MMI.selectable', 'MMI.focus'),
            AttrMap(Text(di.search), 'MMI.selectable', 'MMI.focus')
            if readonly else AttrMap(Edit(''), 'MMI.selectable', 'MMI.focus')
        ])
        if not readonly:
            prim[1].edit_text = di.primary
            sec[1].edit_text = di.secondary
            host[1].edit_text = di.hostname
            host[1].edit_text = di.search
        return Pile([prim, sec, host, search])

    def get_device_config_info_dynamic(self) -> Tuple[Columns, Dict[str, Columns]]:
        """TODO: The formatting is still completely wrong. Solve!"""
        items = {}
        id: int = 0
        if_info: ifcfginfo
        if_stat: snicstats
        if_stats = psutil.net_if_stats()
        self.devices: List[str] = if_stats.keys()
        header_fields: OrderedSet[str] = OrderedSet(['bootproto', 'ipaddr', 'netmask', 'gateway'])
        fieldsizes: Dict[str, int] = {'bootproto': 1, 'ipaddr': 1, 'netmask': 1, 'gateway': 1}
        for dev in self.devices:
            di = DeviceInfo(dev)
            if_stat = di.get_if_stats()
            for f in if_stat._fields:
                header_fields.add(f)
        for dev in self.devices:
            id += 1
            di = DeviceInfo(dev)
            if_info = di.get_if_stats()
            cols = []
            for f in header_fields:
                v = f"{getattr(if_info, f, '')}"
                item = Text(v)
                size = len(v)
                fieldsizes[f] = size if fieldsizes.get(f, 0) <= size else fieldsizes.get(f, 0)
                cols.append(('weight', size, item))
            items[f"{id}) {dev}"] = Columns(cols)
        table_header = Columns([
            ('weight', 1, Text('Device')),
            ('weight', len(header_fields),
            Columns([('weight', fieldsizes.get(t, 1), Text(t.title())) for t in header_fields])),
            # ('weight', 4, Columns([Text('Uplink'), Text('Duplex'), Text('Speed'), Text('MTU')])),
        ])
        return table_header, items

    def get_device_config_info(self) -> Tuple[Columns, Dict[str, Columns]]:
        """
        Returns a tuple of first columns as table_header and second a dictionary with labels as keys and the content
        columns as values.

        :return: The tuple containing first the table header and second the items as Dict.
        """
        items = {}
        id: int = 0
        if_info: ifcfginfo
        if_stat: snicstats
        if_addr: snicaddr
        if_stats = psutil.net_if_stats()
        self.devices: List[str] = if_stats.keys()
        table_header = Columns([
            ('weight', 1, Text('Device')),
            ('weight', 4, Columns([Text('DHCP'), Text('IP-Address'), Text('Netmask'), Text('Gateway')])),
        ])
        if_name: str
        for if_name in self.devices:
            id += 1
            di = DeviceInfo(if_name)
            if_info = di.get_ifcfg_info()
            if_stat = di.get_if_stats()
            if_addr = di.get_if_addr()
            if str(if_info.bootproto).lower() == 'static':
                dhcp = f"{if_info.bootproto}"
                ipaddr = f"{str(if_info.ipaddr).split('/')[0]}"
                netmask = f"{if_info.netmask}"
                gateway = f"{if_info.gateway}"
            else:
                dhcp = f"{if_info.bootproto}"
                ipaddr = f"{str(if_addr.address).split('/')[0]}"
                netmask = f"{if_addr.netmask}"
                gateway = f"{if_info.gateway}"
            items[f'{id}) {if_name}'] = Columns([
                Text(str(dhcp)), Text(str(ipaddr)), Text(str(netmask)), Text(str(gateway)),
            ])
        return table_header, items

    def print(self, string='', align='left'):
        """
        Prints a string to the console UI

        Args:
            string (str): The string to print
            align (str): The alignment of the printed text
        """
        text = [('clock', f"{get_clockstring()}: "), ('footer', string)]
        if self.debug:
            text += ['\n', ('', f"({self.current_event})"), ('', f" on {self.current_window}")]
        self.footer_text.set_text([text])
        self.current_bottom_info = string

    def message_box(self, msg: Any, title: str = None, align: str = CENTER, width: int = 45,
                    valign: str = MIDDLE, height: int = 9):
        """
        Creates a message box dialog with an optional title. The message also can be a list of urwid formatted tuples.

        To use the box as standard message box always returning to it's parent, then ou have to implement something like
        this in your event handler: (f.e. **self**.handle_event)

            elif self.current_window == _MESSAGE_BOX:
                if key.endswith('enter') or key == 'esc':
                    self.current_window = self.message_box_caller
                    self._body = self._message_box_caller_body
                    self.reset_layout()

        :param msg: List or one element of urwid formatted tuple containing the message content.
        :type: Any
        :param title: Optional title as simple string.
        :param align: Horizontal align.
        :param width: The width of the box.
        :param valign: Vertical align.
        :param height: The height of the box.
        """
        self.message_box_caller = self.current_window
        self._message_box_caller_body = self._loop.widget
        self.current_window = _MESSAGE_BOX
        body = LineBox(Padding(Filler(Pile([Text(msg, CENTER)]), TOP)))
        if title is None:
            title = 'Message'
        self.dialog(
            body=body, header=Text(title, CENTER),
            footer=self.ok_button_footer, focus_part='footer',
            align=align, width=width, valign=valign, height=height
        )

    def printf(self, *strings):
        """
        Prints multiple strings with different alignment
        TODO implemnt a similar method

        Args:
            strings (tuple): A string, alignment pair
        """

        self._body_walker.append(
            Columns(
                [
                    Text(string, align=align)
                    for string, align in strings
                ]
            )
        )

    def get_focused_menu(self, menu: ListBox, event: Any) -> int:
        """
        Returns id of focused menu item. Returns current id on enter or 1-9 or click, and returns the next id if
        key is up or down.

        :param menu: The menu from which you want to know the id.
        :type: ListBox
        :param event: The event passed to the menu.
        :type: Any
        :returns: The id of the selected menu item. (>=1)
        :rtype: int
        """
        self.current_menu_focus = super(Application, self).get_focused_menu(menu, event)
        if not self.last_menu_focus == self.current_menu_focus:
            cid: int = self.last_menu_focus - 1
            nid: int = self.current_menu_focus - 1
            cw: Widget = menu.body[cid].base_widget
            nw: Widget = menu.body[nid].base_widget
            if isinstance(cw, MultiMenuItem) and isinstance(nw, MultiMenuItem):
                cmmi: MultiMenuItem = cw
                nmmi: MultiMenuItem = nw
                cmmi.mark_as_dirty()
                nmmi.mark_as_dirty()
                nmmi.set_focus()
                cmmi.refresh_content()
        return self.current_menu_focus

    def handle_standard_menu_behaviour(self, menu: ListBox, event: Any, description_box: ListBox = None) -> int:
        """
        Handles standard menu behaviour and returns the focused id, if any.

        :param menu: The menu to be handled.
        :param event: The event to be handled.
        :param description_box: The ListBox containing the menu content that may be refreshed with the next description.
        :return: The id of the menu having the focus (1+)
        """
        id: int = self.get_focused_menu(menu, event)
        if str(event) not in ['up', 'down']:
            return id
        if description_box is not None:
            focused_item: MenuItem = menu.body[id - 1].base_widget
            description_box.body[0] = focused_item.get_description()
        return id

    def handle_standard_tab_behaviour(self, key: str = 'tab'):
        """
        Handles standard tabulator bahaviour in dialogs. Switching from body to footer and vice versa.

        :param key: The key to be handled.
        """
        if key == 'tab':
            if self.layout.focus_position == 'body':
                self.layout.focus_position = 'footer'
            elif self.layout.focus_position == 'footer':
                self.layout.focus_position = 'body'

    def set_debug(self, on: bool):
        """
        Sets debug mode on or off.

        :param on: True for on and False for off.
        """
        self.debug = on

    def update_clock(self, loop: MainLoop, data: Any = None):
        """
        Updates taskbar every second.

        :param loop: The event loop calling next update_clock()
        """
        self.print(self.current_bottom_info)
        loop.set_alarm_in(1, self.update_clock)

    def start(self):
        """
        Starts the console UI
        """
        self._loop.run()

    def dialog(self, body: Widget = None, header: Widget = None, footer: Widget = None, focus_part: str = None,
               align: str = CENTER, width: int = 40, valign: str = MIDDLE, height: int = 10):
        """
        Overlays a dialog box on top of the console UI

        Args:
            body (Widget): The center widget.
            header (Widget): The header widget.
            footer (Widget): The footer widget.
            focus_part (str): The part getting the focus. ('header', 'body' or 'footer')
            align (str): Horizontal align.
            width (int): The width of the box.
            valign (str): Vertical align.
            height (int): The height of the box.
        """
        # Body
        if body is None:
            body_text = Text('No body', align='center')
            body_filler = Filler(body_text, valign='top')
            body_padding = Padding(
                body_filler,
                left=1,
                right=1
            )
            body = LineBox(body_padding)

        # Footer
        if footer is None:
            footer = GBoxButton('Okay', self.reset_layout())
            footer = AttrWrap(footer, 'selectable', 'focus')
            footer = GridFlow([footer], 8, 1, 1, 'center')

        # Focus
        if focus_part is None:
            focus_part = 'footer'

        # Layout
        self.layout = Frame(
            body,
            header=header,
            footer=footer,
            focus_part=focus_part
        )

        w = Overlay(
            LineBox(self.layout),
            self._body,
            align=align,
            width=width,
            valign=valign,
            height=height
        )

        self._loop.widget = w

    def write_ip_config(self):
        """
        Writes down ip config if apply or ok is being done.
        """
        di = DeviceInfo(self.active_device)
        if self.ip_config_menu.base_widget[2][0].body[0].state:
            di.dhcp = "'dhcp'"
            di.ipaddr = self.ip_config_menu.base_widget[3][0][1].get_text()
            di.netmask = self.ip_config_menu.base_widget[3][1][1].get_text()
            di.gateway = self.ip_config_menu.base_widget[3][2][1].get_text()
        else:
            di.dhcp = 'static'
            di.ipaddr = self.ip_config_menu.base_widget[3][0][1].edit_text
            di.netmask = self.ip_config_menu.base_widget[3][1][1].edit_text
            di.gateway = self.ip_config_menu.base_widget[3][2][1].edit_text
        self.message_box(["Config written", (' ' if di.write_config() else ('important', ' not ')), "successfully."])

    def write_dns_config(self):
        """
        Writes down dns config if apply or ok is being done.
        """
        di = DNSInfo()
        if self.dns_config_menu.base_widget[2][0].body[0].state:
            di.auto = True
            di.primary = self.dns_config_menu.base_widget[3][0][1].get_text()
            di.secondary = self.dns_config_menu.base_widget[3][1][1].get_text()
            di.hostname = self.dns_config_menu.base_widget[3][2][1].get_text()
        else:
            di.auto = False
            di.primary = self.dns_config_menu.base_widget[3][0][1].edit_text
            di.secondary = self.dns_config_menu.base_widget[3][1][1].edit_text
            di.hostname = self.dns_config_menu.base_widget[3][2][1].edit_text
        self.message_box(["Config written", (' ' if di.write_config() else ('important', ' not ')), "successfully."])


if __name__ == '__main__':
    set_encoding('utf-8')
    # print(sys.argv)
    time.sleep(2)
    if "--help" in sys.argv:
        print(f"Usage: {sys.argv[0]} [OPTIONS]")
        print(f"\tOPTIONS:")
        print(f"\t\t--help: Show this message.")
        print(f"\t\t-v/--debug: Verbose/Debugging mode.")
    else:
        app = Application()
        if "-v" in sys.argv:
            app.set_debug(True)
        else:
            app.set_debug(False)
        app.start()
