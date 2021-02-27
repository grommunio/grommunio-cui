# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

from typing import Any
from urwid import ListBox, WidgetWrap


class ApplicationHandler(object):
    """
    Interface for accessing the Application object.
    """
    current_menu_focus: int = -1
    last_menu_focus: int = -2
    current_menu_state: int = -1
    maybe_menu_state: int = -1
    
    def handle_event(self, event: Any):
        """

        Handles user input to the console UI. The method in this handler is not implemented, so subclasses have to
        overwrite this method.

            :param event: A mouse or keyboard input sequence. While the mouse event has the form ('mouse press or
                release', button, column, line), the key stroke is represented as is a single key or even the
                represented value like 'enter', 'up', 'down', etc.
            :type: Any
        """
        raise NotImplementedError(f"{self.__class__}.handle_event() must not be called directly in {self.__name__} "
                                  f"and has to be implemented in sub classes!")
    
    def get_focused_menu(self, menu: ListBox, event: Any) -> int:
        """
        Returns id of focused menu item. Returns current id on enter or 1-9 or click, and returns the next id if
        key is up or down.

        - **Parameters**:

            The menu as a ListBox combined with any event to resolve the current id.

            :param menu: The menu from which you want to know the id.
            :type: ListBox
            :param event: The event passed to the menu. The event can be a keystroke also as a mouse click.
            :type: Any
            :returns: The id of the selected menu item. (>=1)
            :rtype: int

        """
        self.last_menu_focus: int = menu.focus_position + 1
        self.current_menu_focus: int = self.last_menu_focus
        item_count: int = len(menu.body)
        if type(event) is str:
            key: str = str(event)
            if key.endswith('enter') or key in [' ']:
                self.current_menu_focus = self.last_menu_focus
            elif len(key) == 1 and ord('1') <= ord(key) <= ord('9'):
                self.current_menu_focus = ord(str(key)) - ord('1')
            elif key == 'up':
                self.current_menu_focus = menu.focus_position if menu.focus_position > 0 else 1
            elif key == 'down':
                self.current_menu_focus = self.last_menu_focus + 1 if menu.focus_position < item_count - 1 \
                    else item_count
        return self.current_menu_focus
    
    def print(self, string='', align='left'):
        """
        Prints a string to the console UI

        Args:
            string (str): The string to print
            align (str): The alignment of the printed text
        """
        raise NotImplementedError(f"{self.__class__}.print(string, align) must'nt be called directly in {self.__name__}"
                                  f"and has to be implemented in sub classes!")


class WidgetDrawer(WidgetWrap):
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
        raise NotImplementedError(f"{self.__class__}.mark_as_dirty() must not be called directly in {self.__name__} "
                                  f"and has to be implemented in sub classes!")
    
    def refresh_content(self, event: Any = None):
        """
        Triggers the refreshing of dirty content.
        This method is not implemented here and must be done in sub classes.
        """
        raise NotImplementedError(f"{self.__class__}.refresh_content() must not be called directly in {self.__name__} "
                                  f"and has to be implemented in sub classes!")
    
    def render(self, size, focus=False):
        return super(WidgetDrawer, self).render(size, focus)
