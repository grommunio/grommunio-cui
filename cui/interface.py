# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from typing import Any
import urwid


class ApplicationHandler(object):
    """
    Interface for accessing the Application object.
    """

    _view: Any
    _control: Any

    @property
    def view(self):
        return self._view

    @view.setter
    def view(self, val):
        self._view = val

    @property
    def control(self):
        return self._control

    @control.setter
    def control(self, val):
        self._control = val

    def handle_event(self, event: Any):
        """

        Handles user input to the console UI. The method in this handler is not implemented, so subclasses have to
        overwrite this method.

            :param event: A mouse or keyboard input sequence. While the mouse event has the form ('mouse press or
                release', button, column, line), the key stroke is represented as is a single key or even the
                represented value like 'enter', 'up', 'down', etc.
            :type: Any
        """
        raise NotImplementedError(
            f"{self.__class__}.handle_event() must not be called directly in {self.__name__} "
            f"and has to be implemented in sub classes."
        )

    def print(self, string="", align="left"):
        """
        Prints a string to the console UI

        Args:
            string (str): The string to print
            align (str): The alignment of the printed text
        """
        raise NotImplementedError(
            f"{self.__class__}.print(string, align) must'nt be called directly in {self.__name__}"
            f"and has to be implemented in sub classes."
        )


class WidgetDrawer(urwid.WidgetWrap):
    """
    Super class for custom wrapped widgets to simplify redraw issues.
    """

    _label: str

    @property
    def label(self) -> str:
        return self._label

    @label.setter
    def label(self, label: str):
        self._label = label

    def mark_as_dirty(self):
        """
        This method must be called if you want to mark that widget for redrawing.
        This method is not implemented here and must be done in sub classes.
        """
        raise NotImplementedError(
            f"{self.__class__}.mark_as_dirty() must not be called directly in {self.__name__} "
            f"and has to be implemented in sub classes."
        )

    def refresh_content(self, event: Any = None):
        """
        Triggers the refreshing of dirty content.
        This method is not implemented here and must be done in sub classes.
        """
        raise NotImplementedError(
            f"{self.__class__}.refresh_content() must not be called directly in {self.__name__} "
            f"and has to be implemented in sub classes."
        )

    def render(self, size, focus=False):
        return super(WidgetDrawer, self).render(size, focus)
