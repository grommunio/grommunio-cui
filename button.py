# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

from typing import Any
from urwid import AttrMap, Button, Padding, Pile, Text, WidgetWrap, connect_signal, register_signal
from interface import ApplicationHandler, WidgetDrawer


class GButton(Button):
    """
    Extended Button class with custom left and right sign.
    """
    application: ApplicationHandler = None
    
    def __init__(self, label: Any, on_press: Any = None, user_data: Any = None, left_end: str = '<',
                 right_end: str = '>'):
        self.button_left = Text(left_end)
        self.button_right = Text(right_end)
        super(GButton, self).__init__(label, on_press, user_data)
    
    def wrap(self, left_pad: int = 4, right_pad: int = 4) -> Padding:
        button = AttrMap(self, 'buttn', 'buttnf')
        button = Padding(button, left=left_pad, right=right_pad)
        return button
    
    def set_application(self, app: ApplicationHandler):
        self.application = app


class GBoxButton(WidgetDrawer):
    """
    Extended Button class with surrounding lines. Drawing by unicode chars.
    """
    _top_left_char: str = u'┌'
    _top_right_char: str = u'┐'
    _vertical_border_char: str = u'│'
    _horizontal_border_char: str = u'─'
    _bottom_left_char: str = u'└'
    _bottom_right_char: str = u'┘'
    
    def __init__(self, label, on_press=None, user_data=None):
        padding_size = 2
        border = self._horizontal_border_char * (len(label) + padding_size * 2)
        # cursor_position = len(border) + padding_size
        
        self.top: str = f"{self._top_left_char}{border}{self._top_right_char}"
        self.middle: str = f"{self._vertical_border_char}  {label}  {self._vertical_border_char}"
        self.bottom: str = f"{self._bottom_left_char}{border}{self._bottom_right_char}"
        
        self.widget = Pile([
            Text(self.top),
            Text(self.middle),
            Text(self.bottom),
        ])
        self._label = label
        self.label = label
        self.widget = AttrMap(self.widget, 'buttn', 'buttnf')
        self._hidden_button: GButton = GButton('hidden %s' % label, on_press, user_data)
        super(GBoxButton, self).__init__(self.widget)
        register_signal(self.__class__, ['click'])
        connect_signal(self, 'click', on_press)
    
    def selectable(self):
        return True
    
    def keypress(self, *args, **kw):
        return self._hidden_button.keypress(*args, **kw)
    
    def mouse_event(self, size, event, button, x, y, focus):
        if self._hidden_button.application is not None:
            self._hidden_button.application.print(f"GBoxButton({self._label}).mouse_event(size={size}, event={event}, "
                                                  f"button={button}, x={x}, y={y}, focus={focus})")
            if event == 'mouse press':
                self._hidden_button.application.handle_event(f'button <{self._label}> enter')
        rv = True
        # rv = self._hidden_button.mouse_event(size, event, button, x, y, focus)
        return rv
    
    def set_application(self, app: ApplicationHandler):
        self._hidden_button.set_application(app)
