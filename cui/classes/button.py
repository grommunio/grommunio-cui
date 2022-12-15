# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from typing import Any
import urwid
from cui.classes.interface import BaseApplication, WidgetDrawer


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
        left_end: str = "<",
        right_end: str = ">",
    ):
        self.button_left = urwid.Text(left_end)
        self.button_right = urwid.Text(right_end)
        super(GButton, self).__init__(label, on_press, user_data)

    def wrap(self, left_pad: int = 4, right_pad: int = 4) -> urwid.Padding:
        button = urwid.AttrMap(self, "buttn", "buttnf")
        button = urwid.Padding(button, left=left_pad, right=right_pad)
        return button

    def set_application(self, app: BaseApplication):
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
        self._hidden_button: GButton = GButton(
            "hidden %s" % label, on_press, user_data
        )
        super(GBoxButton, self).__init__(self.widget)
        urwid.register_signal(self.__class__, ["click"])
        urwid.connect_signal(self, "click", on_press)

    def selectable(self):
        return True

    def keypress(self, *args, **kw):
        return self._hidden_button.keypress(*args, **kw)

    def mouse_event(self, size, event, button, x, y, focus):
        if self._hidden_button.application is not None:
            self._hidden_button.application.print(
                f"GBoxButton({self._label}).mouse_event(size={size}, event={event}, "
                f"button={button}, x={x}, y={y}, focus={focus})"
            )
            if event == "mouse press":
                self._hidden_button.application.handle_event(
                    f"button <{self._label}> enter"
                )
        rv = True
        # rv = self._hidden_button.mouse_event(size, event, button, x, y, focus)
        return rv

    def set_application(self, app: BaseApplication):
        self._hidden_button.set_application(app)

    def refresh_content(self, event: Any = None):
        pass

    def mark_as_dirty(self):
        pass
