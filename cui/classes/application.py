# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2022 grommunio GmbH
"""In this module all application classes are hold."""
import os
import subprocess
from typing import Optional, List, Union, Tuple, Any, Dict

import urwid

import cui
import cui.classes
import cui.classes.gwidgets
import cui.classes.scroll
import cui.classes.button
import cui.classes.menu
import cui.symbol
import cui.util
from cui.classes.interface import BaseApplication
from cui.classes.gwidgets import GText, GEdit
from cui.classes.scroll import ScrollBar
from cui.classes.menu import MenuItem
from cui.classes.button import GBoxButton

_ = cui.util.init_localization()

ADMIN_DEPENDENT_MENU_CAPTIONS = [
    _('Change admin-web password')
]


class SetupState:
    """Stores states of setup and returns a combined binary number"""
    is_system_pw_upset: bool = False
    is_network_upset: bool = False
    is_grommunio_upset: bool = False
    is_tymsyncd_upset: bool = False
    is_nginx_upset: bool = False
    is_grommunio_admin_installed: bool = False

    def check_network_config(self):
        return cui.util.check_socket("127.0.0.1", 22)

    def check_grommunio_setup(self):
        # return os.path.isfile('/etc/grommunio/setup_done')
        return os.path.isfile("/etc/grammm/setup_done") or os.path.isfile(
            "/etc/grommunio-common/setup_done"
        )

    def check_timesyncd_config(self):
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

    def check_nginx_config(self):
        return cui.util.check_socket("127.0.0.1", 8080)

    def set_setup_states(self):
        # check if pw is set
        self.is_system_pw_upset = cui.util.check_if_password_is_set("root")
        # check network config (2)
        self.is_network_upset = self.check_network_config()
        # check grommunio-setup config (4)
        self.is_grommunio_upset = self.check_grommunio_setup()
        # check timesyncd config (8)
        self.is_tymsyncd_upset = self.check_timesyncd_config()
            # give 0 error points cause timesyncd configuration is not necessarily
            # needed.
        # check nginx config (16)
        self.is_nginx_upset = self.check_nginx_config()
        self.is_grommunio_admin_installed = cui.util.check_if_gradmin_exists()

    def check_setup_state(self):
        ret_val = 0
        # check if pw is set
        if not self.is_system_pw_upset:
            ret_val += 1
        # check network config (2)
        if not self.is_network_upset:
            ret_val += 2
        # check grommunio-setup config (4)
        if not self.is_grommunio_upset:
            ret_val += 4
        # check timesyncd config (8)
        if not self.is_tymsyncd_upset:
            # give 0 error points cause timesyncd configuration is not necessarily
            # needed.
            ret_val += 0
        # check nginx config (16)
        if not self.is_nginx_upset:
            ret_val += 16
        # check grommunio-admin installed (32)
        if not self.is_grommunio_admin_installed:
            ret_val += 32
        return ret_val


setup_state: SetupState = SetupState()


class Header:
    """The Header class holds all header information and widgets"""

    class Info:
        """The Info class contains additional information"""
        header: GText
        app: BaseApplication
        authorized_options: str = ""
        kbdlayout: str = cui.util.get_current_kbdlayout()
        # The default color palette
        colormode: str = "light"

        def debug_out(self, msg):
            """Prints all elements of the class. """
            for elem in dir(self):
                print(elem)
            print(msg)

        @property
        def user_is_authorized(self):
            """Return if user is authenticated"""
            return self.authorized_options != ""

    class TextBlock:
        """TextBlock containing all tb widgets."""
        text_header: List[Union[str, tuple]]
        tb_sysinfo_top: Optional[GText]
        tb_sysinfo_bottom: Optional[GText]
        tb_intro: Optional[GText]
        tb_header: GText

        def __init__(self, info):
            self.info_ref = info
            self.refresh_content()

        def refresh_content(self):
            """Refresh header'S textblock content and translate"""
            # from pudb.remote import set_trace;set_trace(term_size=(230, 60))
            self.text_header = [_("grommunio console user interface")]
            self.text_header += ["\n"]
            self.text_header += [
                _("Active keyboard layout: {kbd}; color set: {colormode}{authorized_options}.")
            ]
            text_intro = [
                "\n",
                _("If you need help, press the 'L' key to view logs."),
                "\n",
            ]
            self.tb_intro = GText(
                text_intro, align=urwid.CENTER, wrap=urwid.SPACE
            )
            text_sysinfo_top = cui.util.get_system_info("top")
            self.tb_sysinfo_top = GText(
                text_sysinfo_top, align=urwid.LEFT, wrap=urwid.SPACE
            )
            text_sysinfo_bottom = cui.util.get_system_info("bottom")
            self.tb_sysinfo_bottom = GText(
                text_sysinfo_bottom, align=urwid.LEFT, wrap=urwid.SPACE
            )
            self.tb_header = GText(self.text, align=urwid.CENTER, wrap=urwid.SPACE,)

        def debug_out(self, msg):
            """Prints all elements of the class. """
            for elem in dir(self):
                print(elem)
            print(msg)

        @property
        def text(self):
            """Returns the text as string. """
            return "".join(self.text_header).format(
                kbd=self.info_ref.kbdlayout,
                colormode=self.info_ref.colormode,
                authorized_options=self.info_ref.authorized_options,
            )

    info: Info = Info()
    tb: TextBlock = TextBlock(info)
    _app: BaseApplication

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
        self.info.authorized_options = ""
        self.refresh_content()

    def refresh_content(self):
        """Refresh header content and translate"""
        self.tb.refresh_content()

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
            if getattr(self.info.app, "view", None):
                self.info.app.view.top_main_menu.refresh_main_menu()
        self.refresh_content()

    def refresh_head_text(self):
        """Refresh head text."""
        self.tb.tb_header.set_text(self.tb.text)

    def debug_out(self, msg):
        """Prints all elements of the class. """
        for elem in dir(self):
            print(elem)
        print(msg)

    @property
    def app(self):
        """Returns the application property. """
        return self._app

    @app.setter
    def app(self, app):
        self._app = app

    def is_app_set(self):
        """Checks if app property is set."""
        return self.app is not None


class MainFrame:
    """The MainFrame class holds all mainframe widgets"""
    mainframe: Optional[urwid.Frame]
    vsplitbox: Optional[urwid.Pile]
    main_top: Optional[ScrollBar]
    main_bottom: Optional[ScrollBar]
    _app: BaseApplication

    def __init__(self, application: BaseApplication):
        self.app = application
        self.main_top = ScrollBar(
            cui.classes.scroll.Scrollable(
                urwid.Pile(
                    [
                        urwid.Padding(self.app.view.header.tb.tb_intro, left=2, right=2,
                                      min_width=20),
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
        self.main_bottom = ScrollBar(
            cui.classes.scroll.Scrollable(
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

    def debug_out(self, msg):
        """Prints all elements of the class. """
        for elem in dir(self):
            print(elem)
        print(msg)

    @property
    def app(self):
        """Returns the application property. """
        return self._app

    @app.setter
    def app(self, app):
        self._app = app

    def is_app_set(self):
        """Checks if app property is set."""
        return self.app is not None


class MainMenu:
    """The MainMenu class contains all main menu code."""
    current_menu_state: int = -1
    maybe_menu_state: int = -1
    current_menu_focus: int = -1
    last_menu_focus: int = -2
    menu_description: urwid.Widget
    main_menu: urwid.Frame
    main_menu_list: urwid.ListBox
    _app: BaseApplication

    def __init__(self, application: BaseApplication):
        self.app = application

    def get_focused_menu(self, menu: urwid.ListBox, event: Any) -> int:
        """
        Returns idx of focused menu item. Returns current idx on enter or 1-9 or click, and
            returns the next idx if key is up or down.

        - **Parameters**:

            The menu as a urwid.ListBox combined with any event to resolve the current idx.

            :param menu: The menu from which you want to know the idx.
            :type: urwid.ListBox
            :param event: The event passed to the menu. The event can be a keystroke also
                as a mouse click.
            :type: Any
            :returns: The idx of the selected menu item. (>=1)
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
        if isinstance(event, str):
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

        def create_menu_description(description_title, description):
            item: urwid.Pile = urwid.Pile([
                GText(description_title, urwid.CENTER)
                if not isinstance(description_title, GText)
                else description_title,
                GText(""),
                GText(description, urwid.LEFT)
                if not isinstance(description, GText)
                else description,
            ])
            return item

        self.app.view.top_main_menu.menu_description = create_menu_description(
            _("Main Menu"),
            _("Here you can do the main actions"),
        )
        # Main Menu
        items = {
            _("Language configuration"): create_menu_description(
                _("Language"),
                _("Opens the yast2 configurator for setting language settings.")
            ),
            _("Change system password"): create_menu_description(
                _("Password change"),
                _("Opens a dialog for changing the password of the system root user. "
                   "When a password is set, you can login via ssh and rerun grommunio-cui."),
            ),
            _("Network interface configuration"): create_menu_description(
                _("Configuration of network"),
                _("Opens the yast2 configurator for setting up devices, interfaces, "
                   "IP addresses, DNS and more.")
            ),
            _("Timezone configuration"): create_menu_description(
                _("Timezone"),
                _("Opens the yast2 configurator for setting country and timezone settings.")
            ),
            _("timesyncd configuration"): create_menu_description(
                _("timesyncd"),
                _("Opens a simple configurator for configuring systemd-timesyncd as a "
                   "lightweight NTP client for time synchronization.")
            ),
            _("Select software repositories"): create_menu_description(
                _("Software repositories selection"),
                _("Opens dialog for choosing software repositories."),
            ),
            _("Update the system"): create_menu_description(
                _("System update"),
                _("Executes the system package manager for the installation of newer "
                   "component versions."),
            ),
            _("grommunio setup wizard"): create_menu_description(
                _("Setup wizard"),
                _("Executes the grommunio-setup script for the initial configuration of "
                   "grommunio databases, TLS certificates, services and the administration "
                   "web user interface.")
            ),
            _("Change admin-web password"): create_menu_description(
                _("Password change"),
                _("Opens a dialog for changing the password used by the administration "
                   "web interface.")
            ),
            _("Terminal"): create_menu_description(
                _("Terminal"),
                _("Starts terminal for advanced system configuration.")
            ),
            _("Reboot"): create_menu_description(_("Reboot system."), GText("")),
            _("Shutdown"): create_menu_description(
                _("Shutdown system."),
                _("Shuts down the system and powers off."),
            ),
        }
        if os.getppid() != 1:
            items["Exit"] = urwid.Pile([GText(_("Exit CUI"), urwid.CENTER)])
        self.app.view.top_main_menu.main_menu_list = self._prepare_menu_list(items)
        if self.app.control.app_control.current_window == cui.symbol.MAIN_MENU \
                and self.app.view.top_main_menu.current_menu_focus > 0:
            off: int = 1
            if self.app.control.app_control.last_current_window == cui.symbol.MAIN_MENU:
                off = 1
            self.app.view.top_main_menu.main_menu_list.focus_position = \
                self.app.view.top_main_menu.current_menu_focus - off
        self.app.view.top_main_menu.main_menu = self._menu_to_frame(
            self.app.view.top_main_menu.main_menu_list)
        if self.app.control.app_control.current_window == cui.symbol.MAIN_MENU:
            self.app.control.app_control.loop.widget = self.app.view.top_main_menu.main_menu
            self.app.control.app_control.body = self.app.view.top_main_menu.main_menu

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
            ])), "reverse", ),
        ])
        return urwid.Frame(menu, header=self.app.view.header.info.header,
                           footer=self.app.view.main_footer.footer)

    def _create_menu_items(self, items: Dict[str, urwid.Widget]) -> List[MenuItem]:
        """
        Takes a dictionary with menu labels as keys and widget(lists) as
        content and creates a list of menu items.

        :param items: Dictionary in the form {'label': urwid.Widget}.
        :return: List of MenuItems.
        """
        menu_items: List[MenuItem] = []
        for idx, caption in enumerate(items.keys(), 1):
            if getattr(self, "app", None):
                item = MenuItem(idx, caption, items.get(caption), self.app)
                if not cui.util.check_if_gradmin_exists() and _(caption) in ADMIN_DEPENDENT_MENU_CAPTIONS:
                    urwid.connect_signal(item, "activate", self.app.handle_nothing)
                    attr = "disabled"
                    item.disable()
                else:
                    urwid.connect_signal(item, "activate", self.app.handle_event)
                    attr = "selectable"
                menu_items.append(urwid.AttrMap(item, attr, "focus"))
        return menu_items

    def debug_out(self, msg):
        """Prints all elements of the class. """
        for elem in dir(self):
            print(elem)
        print(msg)

    @property
    def app(self):
        """Returns the application property. """
        return self._app

    @app.setter
    def app(self, app):
        self._app = app

    def is_app_set(self):
        """Checks if app property is set."""
        return self.app is not None


class GScreen:
    """The GScreen class contains all screen code."""
    old_termios: Optional[Tuple[Any, Any, Any, Any, Any]]
    blank_termios: Optional[Tuple[Any, Any, Any, Any, Any]]
    screen: Optional[urwid.raw_display.Screen]
    layout: urwid.Frame = None
    old_layout: urwid.Frame = None
    debug: bool = False
    quiet: bool = False
    _app: BaseApplication

    def debug_out(self, msg):
        """Prints all elements of the class. """
        for elem in dir(self):
            print(elem)
        print(msg)

    @property
    def app(self):
        """Returns the application property. """
        return self._app

    @app.setter
    def app(self, app):
        self._app = app

    def is_app_set(self):
        """Checks if app property is set."""
        return self.app is not None


class ButtonStore:
    """The ButtonStore class contains all button classes."""
    ok_button: Optional[GBoxButton]
    add_button: Optional[GBoxButton]
    edit_button: Optional[GBoxButton]
    save_button: Optional[GBoxButton]
    close_button: Optional[GBoxButton]
    cancel_button: Optional[GBoxButton]
    details_button: Optional[GBoxButton]
    apply_button: Optional[GBoxButton]
    ok_button_footer: urwid.Widget
    add_button_footer: urwid.Widget
    edit_button_footer: urwid.Widget
    save_button_footer: urwid.Widget
    close_button_footer: urwid.Widget
    cancel_button_footer: urwid.Widget
    details_button_footer: urwid.Widget
    apply_button_footer: urwid.Widget
    user_edit: Optional[GEdit]
    pass_edit: Optional[GEdit]
    _app: BaseApplication

    def debug_out(self, msg):
        """Prints all elements of the class. """
        for elem in dir(self):
            print(elem)
        print(msg)

    @property
    def app(self):
        """Returns the application property. """
        return self._app

    @app.setter
    def app(self, app):
        self._app = app

    def is_app_set(self):
        """Checks if app property is set."""
        return self.app is not None


class LoginWindow:
    """The LoginControl class contains all login controlling code."""
    login_body: Optional[urwid.Widget]
    login_header: Optional[urwid.Widget]
    login_footer: Optional[urwid.Widget]
    _app: BaseApplication

    def debug_out(self, msg):
        """Prints all elements of the class. """
        for elem in dir(self):
            print(elem)
        print(msg)

    @property
    def app(self):
        """Returns the application property. """
        return self._app

    @app.setter
    def app(self, app):
        self._app = app

    def is_app_set(self):
        """Checks if app property is set."""
        return self.app is not None


class ApplicationControl:
    """The ApplicationControl class contains all application controlling code."""
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
    current_bottom_info = _("Idle")
    menu_items: List[str] = []
    body: urwid.Widget
    loop: urwid.MainLoop
    key_counter: Dict[str, int] = {}
    progressbar: urwid.ProgressBar
    _app: BaseApplication

    def __init__(self, initial_window):
        self.current_window = initial_window

    def debug_out(self, msg):
        """Prints all elements of the class. """
        for elem in dir(self):
            print(elem)
        print(msg)

    @property
    def app(self):
        """Returns the application property. """
        return self._app

    @app.setter
    def app(self, app):
        self._app = app

    def is_app_set(self):
        """Checks if app property is set."""
        return self.app is not None


class MenuControl:
    """The MenuControl class contains all menu controlling code."""
    repo_selection_body: urwid.LineBox
    timesyncd_vars: Dict[str, str] = {}
    keyboard_rb: List
    keyboard_content: List
    keyboard_list: ScrollBar
    keyboard_switch_body: ScrollBar
    _app: BaseApplication

    def debug_out(self, msg):
        """Prints all elements of the class. """
        for elem in dir(self):
            print(elem)
        print(msg)

    @property
    def app(self):
        """Returns the application property. """
        return self._app

    @app.setter
    def app(self, app):
        self._app = app

    def is_app_set(self):
        """Checks if app property is set."""
        return self.app is not None


class LogControl:
    """The LogControl class contains all log controlling code."""
    log_units: Dict[str, Dict[str, str]] = {}
    current_log_unit: int = 0
    log_line_count: int = 200
    log_finished: bool = False
    log_viewer: urwid.LineBox
    # The hidden input string
    hidden_input: str = ""
    hidden_pos: int = 0
    _app: BaseApplication

    def debug_out(self, msg):
        """Prints all elements of the class. """
        for elem in dir(self):
            print(elem)
        print(msg)

    @property
    def app(self):
        """Returns the application property. """
        return self._app

    @app.setter
    def app(self, app):
        self._app = app

    def is_app_set(self):
        """Checks if app property is set."""
        return self.app is not None


class Control:
    """The Control class contains all controlling code."""
    app_control: ApplicationControl
    log_control: LogControl = LogControl()
    menu_control: MenuControl = MenuControl()
    _app: BaseApplication

    def __init__(self, initial_window):
        self.app_control = ApplicationControl(initial_window)

    def debug_out(self, msg):
        """Prints all elements of the class. """
        for elem in dir(self):
            print(elem)
        print(msg)

    @property
    def app(self):
        """Returns the application property. """
        return self._app

    @app.setter
    def app(self, app):
        self._app = app

    def is_app_set(self):
        """Checks if app property is set."""
        return self.app is not None


class Footer:
    """The Footer class contains all footer elements."""
    footer_content = []
    footer: urwid.Pile
    _app: BaseApplication

    def debug_out(self, msg):
        """Prints all elements of the class. """
        for elem in dir(self):
            print(elem)
        print(msg)

    @property
    def app(self):
        """Returns the application property. """
        return self._app

    @app.setter
    def app(self, app):
        self._app = app

    def is_app_set(self):
        """Checks if app property is set."""
        return self.app is not None


class View:
    """The view class contains all view elements that are visible"""
    main_frame: MainFrame
    header: Header = Header()
    top_main_menu: MainMenu
    main_footer: Footer = Footer()
    gscreen: GScreen
    button_store: ButtonStore = ButtonStore()
    login_window: LoginWindow = LoginWindow()
    _app: BaseApplication

    def __init__(self, application: BaseApplication):
        self.app = application
        self.top_main_menu = MainMenu(self.app)

    def debug_out(self, msg):
        """Prints all elements of the class. """
        for elem in dir(self):
            print(elem)
        print(msg)

    @property
    def app(self):
        """Returns the application property. """
        return self._app

    @app.setter
    def app(self, app):
        self._app = app

    def is_app_set(self):
        """Checks if app property is set."""
        return self.app is not None
