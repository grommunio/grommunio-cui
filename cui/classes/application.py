# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2022 grommunio GmbH
"""In this module all application classes are hold."""
import os
from typing import Optional, List, Union, Tuple, Any, Dict

import urwid

import cui
import cui.scroll
import cui.button
import cui.menu
import cui.symbol
from cui.classes.interface import BaseApplication

T_ = cui.util.init_localization()


class Header:
    """The Header class holds all header information and widgets"""
    class TextBlock:
        """TextBlock containing all tb widgets."""
        tb_sysinfo_top: Optional[cui.gwidgets.GText]
        tb_sysinfo_bottom: Optional[cui.gwidgets.GText]
        tb_intro: Optional[cui.gwidgets.GText]
        tb_header: cui.gwidgets.GText

    class Info:
        """The Info class contains additional information"""
        text_header: List[Union[str, tuple]]
        header: cui.gwidgets.GText
        app: BaseApplication
        authorized_options: str = ""
        kbdlayout: str = cui.util.get_current_kbdlayout()
        # The default color palette
        colormode: str = "light"

    info: Info = Info()
    tb: TextBlock = TextBlock()

    def __init__(
            self,
            colormode: str = None,
            kbd_layout: str = None,
            application: BaseApplication = None
    ):
        if colormode:
            self.info.colormode = colormode
        if kbd_layout:
            self.info.kbdlayout = kbd_layout
        if application:
            self.info.app = application
        self.info.text_header = [T_("grommunio console user interface")]
        self.info.text_header += ["\n"]
        self.info.text_header += [
            T_("Active keyboard layout: {kbd}; color set: {colormode}.")
        ]
        self.info.authorized_options = ""
        text_intro = [
            "\n",
            T_("If you need help, press the 'L' key to view logs."),
            "\n",
        ]
        self.tb.tb_intro = cui.gwidgets.GText(
            text_intro, align=urwid.CENTER, wrap=urwid.SPACE
        )
        text_sysinfo_top = cui.util.get_system_info("top")
        self.tb.tb_sysinfo_top = cui.gwidgets.GText(
            text_sysinfo_top, align=urwid.LEFT, wrap=urwid.SPACE
        )
        text_sysinfo_bottom = cui.util.get_system_info("bottom")
        self.tb.tb_sysinfo_bottom = cui.gwidgets.GText(
            text_sysinfo_bottom, align=urwid.LEFT, wrap=urwid.SPACE
        )
        self.tb.tb_header = cui.gwidgets.GText(
            "".join(self.info.text_header).format(
                colormode=self.info.colormode,
                kbd=self.info.kbdlayout,
                authorized_options="",
            ),
            align=urwid.CENTER,
            wrap=urwid.SPACE,
        )

    def set_app(self, application: BaseApplication):
        """Set the main app"""
        self.info.app = application

    def set_kbdlayout(self, kbdlayout):
        """Set the keyboard layout"""
        self.info.kbdlayout = kbdlayout

    def get_kbdlayout(self):
        """Return the current keyboard layout"""
        return self.info.kbdlayout

    def set_colormode(self, colormode):
        """Set the color mode"""
        self.info.colormode = colormode

    def get_colormode(self):
        """return the mode of color"""
        return self.info.colormode

    def set_authorized_options(self, options):
        """Set the authorized options"""
        self.info.authorized_options = options

    def get_authorized_options(self):
        """Return the authorized options"""
        return self.info.authorized_options

    def refresh_header(self):
        """Refresh header"""
        self.refresh_head_text()
        self.info.header = urwid.AttrMap(
            urwid.Padding(self.tb.tb_header, align=urwid.CENTER), "header"
        )
        if getattr(self.info, "app", None):
            if getattr(self.info.app, "footer", None):
                self.info.app.view.top_main_menu.refresh_main_menu()

    def refresh_head_text(self):
        """Refresh head text."""
        self.tb.tb_header.set_text(
            "".join(self.info.text_header).format(
                colormode=self.info.colormode,
                kbd=self.info.kbdlayout,
                authorized_options=self.info.authorized_options,
            )
        )


class MainFrame:
    """The MainFrame class holds all mainframe widgets"""
    mainframe: Optional[urwid.Frame]
    vsplitbox: Optional[urwid.Pile]
    main_top: Optional[cui.scroll.ScrollBar]
    main_bottom: Optional[cui.scroll.ScrollBar]
    app: BaseApplication

    def __init__(self, application: BaseApplication):
        self.app = application
        self.main_top = cui.scroll.ScrollBar(
            cui.scroll.Scrollable(
                urwid.Pile(
                    [
                        urwid.Padding(self.app.view.header.tb.tb_intro, left=2, right=2, min_width=20),
                        urwid.Padding(
                            self.app.view.header.tb.tb_sysinfo_top,
                            align=urwid.LEFT,
                            left=6,
                            width=("relative", 80),
                        ),
                    ]
                )
            )
        )
        self.main_bottom = cui.scroll.ScrollBar(
            cui.scroll.Scrollable(
                urwid.Pile(
                    [
                        urwid.AttrMap(
                            urwid.Padding(
                                self.app.view.header.tb.tb_sysinfo_bottom,
                                align=urwid.LEFT,
                                left=6,
                                width=("relative", 80),
                            ),
                            "reverse",
                        )
                    ]
                )
            )
        )


class MainMenu:
    current_menu_state: int = -1
    maybe_menu_state: int = -1
    current_menu_focus: int = -1
    last_menu_focus: int = -2
    menu_description: urwid.Widget
    main_menu: urwid.Frame
    main_menu_list: urwid.ListBox
    app: BaseApplication

    def __init__(self, application: BaseApplication):
        self.app = application
        
    def get_focused_menu(self, menu: urwid.ListBox, event: Any) -> int:
        """
        Returns id of focused menu item. Returns current id on enter or 1-9 or click, and returns the next id if
        key is up or down.

        - **Parameters**:

            The menu as a urwid.ListBox combined with any event to resolve the current id.

            :param menu: The menu from which you want to know the id.
            :type: urwid.ListBox
            :param event: The event passed to the menu. The event can be a keystroke also as a mouse click.
            :type: Any
            :returns: The id of the selected menu item. (>=1)
            :rtype: int

        """
        item_count: int
        if isinstance(menu, cui.ScrollBar):
            tmp_menu = menu.base_widget
            item_count = len(tmp_menu.contents)
        else:
            tmp_menu = menu
            item_count = len(tmp_menu.body)
        self.last_menu_focus: int = tmp_menu.focus_position + 1
        self.current_menu_focus: int = self.last_menu_focus
        if type(event) is str:
            key: str = str(event)
            if key.endswith("enter") or key in [" "]:
                self.current_menu_focus = self.last_menu_focus
            elif len(key) == 1 and ord("1") <= ord(key) <= ord("9"):
                self.current_menu_focus = ord(str(key)) - ord("1")
            elif key == "up":
                self.current_menu_focus = (
                    tmp_menu.focus_position if tmp_menu.focus_position > 0 else 1
                )
            elif key == "down":
                self.current_menu_focus = (
                    self.last_menu_focus + 1
                    if tmp_menu.focus_position < item_count - 1
                    else item_count
                )
        return self.current_menu_focus

    def refresh_main_menu(self):
        """Refresh main menu."""
        def create_menu_description(description, description_title):
            item: urwid.Pile = urwid.Pile([
                cui.gwidgets.GText(description_title, urwid.CENTER)
                if not isinstance(description_title, cui.gwidgets.GText)
                else description_title,
                cui.gwidgets.GText(""),
                cui.gwidgets.GText(description, urwid.LEFT)
                if not isinstance(description, cui.gwidgets.GText)
                else description,
            ])
            return item

        self.app.view.top_main_menu.menu_description = create_menu_description(
            T_("Main Menu"),
            T_("Here you can do the main actions"),
        )
        # Main Menu
        items = {
            T_("Language configuration"): create_menu_description(
                T_("Language"),
                T_("Opens the yast2 configurator for setting language settings.")
            ),
            T_("Change system password"): create_menu_description(
                T_("Password change"),
                T_("Opens a dialog for changing the password of the system root user. When a password is set, you can login via ssh and rerun grommunio-cui."),
            ),
            T_("Network interface configuration"): create_menu_description(
                T_("Configuration of network"),
                T_("Opens the yast2 configurator for setting up devices, interfaces, IP addresses, DNS and more.")
            ),
            T_("Timezone configuration"): create_menu_description(
                T_("Timezone"),
                T_("Opens the yast2 configurator for setting country and timezone settings.")
            ),
            T_("timesyncd configuration"): create_menu_description(
                T_("timesyncd"),
                T_("Opens a simple configurator for configuring systemd-timesyncd as a lightweight NTP client for time synchronization.")
            ),
            T_("Select software repositories"): create_menu_description(
                T_("Software repositories selection"),
                T_("Opens dialog for choosing software repositories."),
            ),
            T_("Update the system"): create_menu_description(
                T_("System update"),
                T_("Executes the system package manager for the installation of newer component versions."),
            ),
            T_("grommunio setup wizard"): create_menu_description(
                T_("Setup wizard"),
                T_("Executes the grommunio-setup script for the initial configuration of grommunio databases, TLS certificates, services and the administration web user interface.")
            ),
            T_("Change admin-web password"): create_menu_description(
                T_("Password change"),
                T_("Opens a dialog for changing the password used by the administration web interface.")
            ),
            T_("Terminal"): create_menu_description(
                T_("Terminal"),
                T_("Starts terminal for advanced system configuration.")
            ),
            T_("Reboot"): create_menu_description(T_("Reboot system."), cui.gwidgets.GText("")),
            T_("Shutdown"): create_menu_description(
                T_("Shutdown system."),
                T_("Shuts down the system and powers off."),
            ),
        }
        if os.getppid() != 1:
            items["Exit"] = urwid.Pile([cui.gwidgets.GText(T_("Exit CUI"), urwid.CENTER)])
        self.app.view.top_main_menu.main_menu_list = self._prepare_menu_list(items)
        if self.app.control.app_control.current_window == cui.symbol.MAIN_MENU and self.app.view.top_main_menu.current_menu_focus > 0:
            off: int = 1
            if self.app.control.app_control.last_current_window == cui.symbol.MAIN_MENU:
                off = 1
            self.app.view.top_main_menu.main_menu_list.focus_position = self.app.view.top_main_menu.current_menu_focus - off
        self.app.view.top_main_menu.main_menu = self._menu_to_frame(self.app.view.top_main_menu.main_menu_list)
        if self.app.control.app_control.current_window == cui.symbol.MAIN_MENU:
            self.app.control.app_control.loop.widget = self.app.view.top_main_menu.main_menu
            self.app.control.app_control.body = self.app.view.top_main_menu.main_menu

    def _prepare_menu_list(self, items: Dict[str, urwid.Widget]) -> urwid.ListBox:
        """
        Prepare general menu list.

        :param items: A dictionary of widgets representing the menu items.
        :return: urwid.ListBox containing menu items.
        """
        menu_items: List[cui.menu.MenuItem] = self._create_menu_items(items)
        return urwid.ListBox(urwid.SimpleFocusListWalker(menu_items))

    def _menu_to_frame(self, listbox: urwid.ListBox):
        """Put menu(urwid.ListBox) into a urwid.Frame."""
        fopos: int = listbox.focus_position
        menu = urwid.Columns([
            urwid.AttrMap(listbox, "body"), urwid.AttrMap(urwid.ListBox(urwid.SimpleListWalker([
                listbox.body[fopos].original_widget.get_description()
            ])), "reverse",),
        ])
        return urwid.Frame(menu, header=self.app.view.header.info.header, footer=self.app.view.main_footer.footer)

    def _create_menu_items(self, items: Dict[str, urwid.Widget]) -> List[cui.menu.MenuItem]:
        """
        Takes a dictionary with menu labels as keys and widget(lists) as
        content and creates a list of menu items.

        :param items: Dictionary in the form {'label': urwid.Widget}.
        :return: List of MenuItems.
        """
        menu_items: List[cui.menu.MenuItem] = []
        for idx, caption in enumerate(items.keys(), 1):
            if getattr(self, "app", None):
                item = cui.menu.MenuItem(idx, caption, items.get(caption), self.app)
                urwid.connect_signal(item, "activate", self.app.handle_event)
                menu_items.append(urwid.AttrMap(item, "selectable", "focus"))
        return menu_items


class GScreen:
    old_termios: Optional[Tuple[Any, Any, Any, Any, Any]]
    blank_termios: Optional[Tuple[Any, Any, Any, Any, Any]]
    screen: Optional[urwid.raw_display.Screen]
    layout: urwid.Frame = None
    old_layout: urwid.Frame = None
    debug: bool = False
    quiet: bool = False


class ButtonStore:
    ok_button: Optional[cui.button.GBoxButton]
    add_button: Optional[cui.button.GBoxButton]
    edit_button: Optional[cui.button.GBoxButton]
    save_button: Optional[cui.button.GBoxButton]
    close_button: Optional[cui.button.GBoxButton]
    cancel_button: Optional[cui.button.GBoxButton]
    details_button: Optional[cui.button.GBoxButton]
    apply_button: Optional[cui.button.GBoxButton]
    ok_button_footer: urwid.Widget
    add_button_footer: urwid.Widget
    edit_button_footer: urwid.Widget
    save_button_footer: urwid.Widget
    close_button_footer: urwid.Widget
    cancel_button_footer: urwid.Widget
    details_button_footer: urwid.Widget
    apply_button_footer: urwid.Widget
    user_edit: Optional[cui.gwidgets.GEdit]
    pass_edit: Optional[cui.gwidgets.GEdit]


class LoginWindow:
    login_body: Optional[urwid.Widget]
    login_header: Optional[urwid.Widget]
    login_footer: Optional[urwid.Widget]


class ApplicationControl:
    current_window: str
    last_current_window: str = ""
    current_window_input_box: str = ""
    message_box_caller: str = ""
    message_box_caller_body: urwid.Widget = None
    last_pressed_button: str = ""
    input_box_caller: str = ""
    input_box_caller_body: urwid.Widget = None
    last_input_box_value: str = ""
    log_file_caller: str = ""
    log_file_caller_body: urwid.Widget = None
    current_event = ""
    current_bottom_info = T_("Idle")
    menu_items: List[str] = []
    body: urwid.Widget
    loop: urwid.MainLoop
    key_counter: Dict[str, int] = {}
    progressbar: urwid.ProgressBar

    def __init__(self, initial_window):
        self.current_window = initial_window


class MenuControl:
    repo_selection_body: urwid.LineBox
    timesyncd_vars: Dict[str, str] = {}
    keyboard_rb: List
    keyboard_content: List
    keyboard_list: cui.scroll.ScrollBar
    keyboard_switch_body: cui.scroll.ScrollBar


class LogControl:
    log_units: Dict[str, Dict[str, str]] = {}
    current_log_unit: int = 0
    log_line_count: int = 200
    log_finished: bool = False
    log_viewer: urwid.LineBox
    # The hidden input string
    hidden_input: str = ""
    hidden_pos: int = 0


class Control:
    app_control: ApplicationControl
    log_control: LogControl = LogControl()
    menu_control: MenuControl = MenuControl()

    def __init__(self, initial_window):
        self.app_control = ApplicationControl(initial_window)


class Footer:
    footer_content = []
    footer: urwid.Pile


class View:
    main_frame: MainFrame
    header: Header
    top_main_menu: MainMenu
    main_footer: Footer = Footer()
    gscreen: GScreen
    button_store: ButtonStore = ButtonStore()
    login_window: LoginWindow = LoginWindow()
    app: BaseApplication

    def __init__(self, application: BaseApplication):
        self.app = application
        self.top_main_menu = MainMenu(self.app)
