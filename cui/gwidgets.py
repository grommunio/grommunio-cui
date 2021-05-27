# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH
from typing import Any, Union, Tuple

import urwid


class GText(urwid.WidgetWrap):
    def __init__(self, markup, align=urwid.LEFT, wrap=urwid.SPACE, layout=None):
        t = urwid.Text(markup, align, wrap, layout)
        p = urwid.Padding(t, left=2, right=2)
        super(GText, self).__init__(p)
        # self._w = t

    def set_text(self, text):
        self._wrapped_widget.base_widget.set_text(text)


class GEdit(urwid.WidgetWrap):
    def __init__(self,
                 caption: Any = u"",
                 edit_text: Union[bytes, str] = u"",
                 multiline: bool = False,
                 align: Any = urwid.widget.LEFT,
                 wrap: Any = urwid.widget.SPACE,
                 allow_tab: bool = False,
                 edit_pos: int = None,
                 layout: Any = None,
                 mask: Union[bytes, str] = None):
        caption_object: Tuple[Any, ...]
        if len(caption) == 0:
            caption_object = (caption, )
        else:
            caption_object = caption
        if type(caption_object) is tuple:
            t = urwid.Text(caption_object[len(caption_object) - 1])
        else:
            t = urwid.Text(caption_object)
        e = urwid.Edit("", edit_text, multiline, align, wrap, allow_tab, edit_pos, layout, mask)
        a = urwid.AttrMap(e, 'selectable', 'focus')
        p_t = urwid.Padding(t, left=2)
        p_a = urwid.Padding(a, right=2)
        c: urwid.Columns
        if type(caption_object) is tuple:
            if len(caption_object) == 3:
                t_crossing = (caption_object[0], caption_object[1], p_t)
                a_crossing = (caption_object[0], 100 - caption_object[1], p_a)
            elif len(caption_object) == 2:
                t_crossing = (caption_object[0], p_t)
                a_crossing = p_a
            elif len(caption_object) == 1:
                t_crossing = ('weight', 0, p_t)
                a_crossing = ('weight', 1, p_a)
            else:
                raise Exception('Out of bounds Exception. Tuple must be of size 1, 2 or 3!')
        else:
            t_crossing = ('pack', p_t)
            a_crossing = p_a
        c = urwid.Columns([t_crossing, a_crossing])
        # p = urwid.Padding(c, left=2, right=2)
        super(GEdit, self).__init__(c)
        self.edit_widget = e
        # self._w = t

    def set_text(self, text):
        # self._wrapped_widget.base_widget.base_widget.set_text(text)
        self.edit_widget.set_text(text)

    @property
    def edit_text(self):
        # return self._wrapped_widget.base_widget.base_widget.edit_text
        return self.edit_widget.edit_text

    @edit_text.setter
    def edit_text(self, text):
        # self._wrapped_widget.base_widget.base_widget.edit_text = text
        self.edit_widget.edit_text = text


