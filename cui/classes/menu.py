# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from typing import Any, List, Dict
import urwid
from cui.classes.interface import BaseApplication, WidgetDrawer
from cui.classes.gwidgets import GText


class MenuItem(GText):
    """
    Standard MenuItem enhances Text urwid.Widget by signal 'activate'
    """

    application: BaseApplication = None

    def __init__(
        self,
        menu_id,
        caption,
        description: Any = None,
        app: BaseApplication = None,
    ):
        GText.__init__(self, caption)
        self.id = menu_id
        self.description = description
        urwid.register_signal(self.__class__, ["activate"])
        self.application = app

    def keypress(self, _, key: str = "") -> str:
        if key == "enter":
            urwid.emit_signal(self, "activate", key)
        else:
            if self.application is not None:
                if key not in ["c", "f1", "f5", "esc"]:
                    self.application.handle_event(key)
            return key

    def get_id(self) -> int:
        return self.id

    def get_description(self) -> str:
        return self.description

    def selectable(self):
        return True
