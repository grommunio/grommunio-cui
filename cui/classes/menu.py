# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH
"""The module contains classes which objects are used in menus"""
from typing import Any
import urwid
from cui.classes.interface import BaseApplication
from cui.classes.gwidgets import GText


class MenuItem(GText):
    """
    Standard MenuItem enhances Text urwid.Widget by signal 'activate'
    """

    application: BaseApplication = None
    _selectable = True

    def __init__(
        self,
        menu_id,
        caption,
        description: Any = None,
        app: BaseApplication = None,
    ):
        GText.__init__(self, caption)
        self.idx = menu_id
        self.description = description
        urwid.register_signal(self.__class__, ["activate"])
        self.application = app

    def keypress(self, _, key: str = "") -> str:
        """Handles the pressed key"""
        if key == "enter":
            urwid.emit_signal(self, "activate", key)
        else:
            if self.application is not None:
                if key not in ["c", "f1", "f5", "esc"]:
                    self.application.handle_event(key)
            return key
        return None

    def get_id(self) -> int:
        """Return the current idx"""
        return self.idx

    def get_description(self) -> str:
        """Return the current description"""
        return self.description

    def disable(self):
        self._selectable = False

    def enable(self):
        self._selectable = True

    def selectable(self):
        """Return if the widget is selectable"""
        return self._selectable
