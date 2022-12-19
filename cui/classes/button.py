# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH
"""This module contains the button classes"""
from getpass import getuser
from typing import Any, Tuple
import urwid

import cui
from cui.classes.interface import BaseApplication, WidgetDrawer
from cui.util import _

_ = cui.util.init_localization()


class GButton(urwid.Button):
    """
    Extended urwid.Button class with custom left and right sign.
    """

    _selectable = True
    application: BaseApplication = None

    def __init__(
        self,
        label: Any,
        on_press: Any = None,
        user_data: Any = None,
        margin_chars: (str, str) = ("<", ">"),
    ):
        self.button_left = urwid.Text(margin_chars[0])
        self.button_right = urwid.Text(margin_chars[1])
        super().__init__(label, on_press, user_data)

    def wrap(self, left_pad: int = 4, right_pad: int = 4) -> urwid.Padding:
        """Sets the application"""
        button = urwid.AttrMap(self, "buttn", "buttnf")
        button = urwid.Padding(button, left=left_pad, right=right_pad)
        return button

    def set_application(self, app: BaseApplication):
        """Sets the application"""
        self.application = app


class GBoxButton(WidgetDrawer):
    """
    Extended urwid.Button class with surrounding lines. Drawing by unicode chars.
    """

    _selectable = True

    _top_left_char: str = "┌"
    _top_right_char: str = "┐"
    _vertical_border_char: str = "│"
    _horizontal_border_char: str = "─"
    _bottom_left_char: str = "└"
    _bottom_right_char: str = "┘"

    def __init__(self, label, on_press=None, user_data=None):
        padding_size = 2
        border = self._horizontal_border_char * (len(label) + padding_size * 2)
        # cursor_position = len(border) + padding_size

        self.top: str = f"{self._top_left_char}{border}{self._top_right_char}"
        self.middle: str = f"{self._vertical_border_char}  {label}  {self._vertical_border_char}"
        self.bottom: str = (
            f"{self._bottom_left_char}{border}{self._bottom_right_char}"
        )

        self.widget = urwid.Pile(
            [
                urwid.Text(self.top),
                urwid.Text(self.middle),
                urwid.Text(self.bottom),
            ]
        )
        self._label = label
        self.label = label
        self.widget = urwid.AttrMap(self.widget, "buttn", "buttnf")
        self._hidden_button: GButton = GButton(f"hidden {label}", on_press, user_data)
        super().__init__(self.widget)
        urwid.register_signal(self.__class__, ["click"])
        urwid.connect_signal(self, "click", on_press)

    def selectable(self):
        """Return if selectable or not"""
        return True

    def keypress(self, *args, **kw):
        """Handle key event while event is NOT a mouse event in the
        form size, event"""
        return self._hidden_button.keypress(*args, **kw)

    # pylint: disable=too-many-arguments  ,
    # because mouse_event method on urwid is the same
    def mouse_event(self, size, event, button, col, row, focus):
        """Handle mouse event while event is a mouse event in the
        form size, event, button, col, row, focus"""
        if self._hidden_button.application is not None:
            self._hidden_button.application.print(
                f"GBoxButton({self._label}).mouse_event(size={size}, event={event}, "
                f"button={button}, col={col}, row={row}, focus={focus})"
            )
            if event == "mouse press":
                self._hidden_button.application.handle_event(
                    f"button <{self._label}> enter"
                )
        # rv = self._hidden_button.mouse_event(size, event, button, col, row, focus)
        return True

    def set_application(self, app: BaseApplication):
        """Set the application to app property."""
        self._hidden_button.set_application(app)


def create_application_buttons(app):
    """Create all application buttons"""

    def create_button(label, event, button_func, handle_event_func):
        res = cui.classes.button.GBoxButton(label, button_func)
        urwid.connect_signal(
            res,
            "click",
            lambda button: handle_event_func(event),
        )
        res = (len(res.label) + 6, res)
        return res

    def create_button_footer(button_ref: Any, which: str = "attrmap"):
        if not isinstance(button_ref, Tuple):
            button_ref = (len(button_ref.label) + 6, button_ref)
        res = urwid.AttrMap(urwid.Columns([
            ("weight", 1, cui.classes.gwidgets.GText("")),
            ("weight", 1, urwid.Columns([
                ("weight", 1, cui.classes.gwidgets.GText("")),
                button_ref,
                ("weight", 1, cui.classes.gwidgets.GText("")),
            ]),),
            ("weight", 1, cui.classes.gwidgets.GText("")),
        ]), "buttonbar", )
        if which.startswith("grid"):
            res = urwid.GridFlow([button_ref[1]], 10, 1, 1, "center")
        return res

    def create_both(label, event, which: str = "attr"):
        but = create_button(label, event, app.press_button, app.handle_event)
        return but, create_button_footer(but, which)

    # Login Dialog
    app.view.login_window.login_header = urwid.AttrMap(
        cui.classes.gwidgets.GText(("header", _("Login")), align="center"), "header"
    )
    app.view.button_store.user_edit = cui.classes.gwidgets.GEdit(
        (_("Username: "),), edit_text=getuser(), edit_pos=0
    )
    app.view.button_store.pass_edit = cui.classes.gwidgets.GEdit(
        _("Password: "), edit_text="", edit_pos=0, mask="*"
    )
    app.view.login_window.login_body = urwid.Pile(
        [
            app.view.button_store.user_edit,
            app.view.button_store.pass_edit,
        ]
    )
    login_button = cui.classes.button.GBoxButton(_("Login"), app.check_login)
    urwid.connect_signal(
        login_button,
        "click",
        lambda button: app.handle_event("login enter"),
    )
    app.view.login_window.login_footer = urwid.AttrMap(urwid.Columns([
        cui.classes.gwidgets.GText(""),
        login_button, cui.classes.gwidgets.GText("")
    ]), "buttonbar")
    # Common OK Button
    app.view.button_store.ok_button, app.view.button_store.ok_button_footer = create_both(
        _("OK"), "ok enter", "attr"
    )
    # Common Cancel Button
    app.view.button_store.cancel_button, app.view.button_store.cancel_button_footer = create_both(
        _("Cancel"), "cancel enter", "grid"
    )
    # Common close Button
    app.view.button_store.close_button, app.view.button_store.close_button_footer = create_both(
        _("Close"), "close enter", "attr"
    )
    # Common Add Button
    app.view.button_store.add_button, app.view.button_store.add_button_footer = create_both(
        _("Add"), "add enter", "grid"
    )
    # Common Edit Button
    app.view.button_store.edit_button, app.view.button_store.edit_button_footer = create_both(
        _("Edit"), "edit enter", "attr"
    )
    # Common Save Button
    app.view.button_store.save_button, app.view.button_store.save_button_footer = create_both(
        _("Save"), "save enter", "grid"
    )
    # Common Details Button
    app.view.button_store.details_button, app.view.button_store.details_button_footer = create_both(
        _("Details"), "details enter", "grid"
    )
    # Common Toggle Button
    app.view.button_store.toggle_button, app.view.button_store.toggle_button_footer = create_both(
        _("Toggle"), "toggle enter", "grid"
    )
    # Common Apply Button
    app.view.button_store.apply_button, app.view.button_store.apply_button_footer = create_both(
        _("Apply"), "apply enter", "grid"
    )
