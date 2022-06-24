# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH
from typing import Any, Union, Tuple

import urwid


class GText(urwid.WidgetWrap):
    def __init__(
            self,
            markup,
            align=urwid.LEFT,
            wrap=urwid.SPACE,
            layout=None,
            left=2,
            right=2):
        self._t = urwid.Text(markup, align, wrap, layout)
        self._p = urwid.Padding(self._t, left=left, right=right)
        super(GText, self).__init__(self._p)
        # self._w = t

    def set_text(self, text):
        self._wrapped_widget.base_widget.set_text(text)

    def get_text(self):
        return self._wrapped_widget.base_widget.text

    @property
    def text(self):
        return self.get_text()

    @text.setter
    def text(self, text):
        self.set_text(text)

    @property
    def view(self):
        return f"{' ' * self._p.left}{self.get_text()}{' ' * self._p.right}"

    def __len__(self):
        return len(self._t.text) + self._p.left + self._p.right


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
        if isinstance(caption_object, tuple):
            t = urwid.Text(caption_object[len(
                caption_object) - 1], align, wrap=urwid.widget.CLIP, layout=layout)
        else:
            t = urwid.Text(
                caption_object,
                align,
                wrap=urwid.widget.CLIP,
                layout=layout)
        e = urwid.Edit(
            "",
            edit_text,
            multiline,
            align,
            wrap,
            allow_tab,
            edit_pos,
            layout,
            mask)
        a = urwid.AttrMap(e, 'selectable', 'focus')
        s = urwid.Text('')
        p_t = urwid.Padding(t, left=2)
        p_a = urwid.Padding(a, right=2)
        c: urwid.Columns
        if isinstance(caption_object, tuple):
            if len(caption_object) == 3:
                t_crossing = (caption_object[0], caption_object[1], p_t)
                a_crossing = (caption_object[0], 100 - caption_object[1], p_a)
            elif len(caption_object) == 2:
                t_crossing = (caption_object[0], p_t)
                a_crossing = p_a
            elif len(caption_object) == 1:
                t_crossing = (len(p_t.original_widget.text) +
                              p_t.left + p_t.right, p_t)
                a_crossing = ('weight', 1, p_a)
            else:
                raise Exception(
                    'Out of bounds Exception. Tuple must be of size 1, 2 or 3!')
        else:
            # t_crossing = ('pack', p_t)
            # a_crossing = ('pack', p_a)
            # t_crossing = ('weight', 0, p_t)
            t_crossing = (len(p_t.original_widget.text) +
                          p_t.left + p_t.right, p_t)
            a_crossing = ('weight', 1, p_a)
        # c = urwid.Columns([t_crossing, a_crossing])
        space_crossing = (1, s)
        c = urwid.Columns(
            [t_crossing, urwid.Columns([space_crossing, a_crossing])])
        # p = urwid.Padding(c, left=2, right=2)
        super(GEdit, self).__init__(c)
        self.edit_widget = e
        # self._w = t

    def set_text(self, text):
        # self._wrapped_widget.base_widget.base_widget.set_text(text)
        self.edit_widget.set_text(text)

    def get_edit_text(self):
        return self.edit_widget.get_edit_text()

    def set_edit_text(self, text):
        self.edit_widget.edit_text = text

    @property
    def edit_text(self):
        # return self._wrapped_widget.base_widget.base_widget.edit_text
        return self.edit_widget.edit_text

    @edit_text.setter
    def edit_text(self, text):
        # self._wrapped_widget.base_widget.base_widget.edit_text = text
        self.edit_widget.edit_text = text
