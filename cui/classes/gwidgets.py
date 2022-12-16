# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH
"""The gwidgets module contains all grommunio widgets"""
from typing import Any, Tuple

import urwid


class GText(urwid.WidgetWrap):
    """The grommunio Text field widget"""
    _selectable = False

    def __init__(self, markup, *args, **kwargs):
        # Set variables
        params = {
            "align": urwid.LEFT,
            "wrap": urwid.SPACE,
            "layout": None,
            "left": 2,
            "right": 2,
        }
        for (i, key) in enumerate(params.keys()):
            params[key] = kwargs.get(key, args[i] if len(args) > i else params.get(key))
        self._t = urwid.Text(markup, params["align"], params["wrap"], params["layout"])
        self._p = urwid.Padding(self._t, left=params["left"], right=params["right"])
        super().__init__(self._p)
        # self._w = t

    def set_text(self, text):
        """Set the text of the GText widget."""
        self._wrapped_widget.base_widget.set_text(text)

    def get_text(self):
        """Get the text of the GText widget."""
        return self._wrapped_widget.base_widget.text

    @property
    def text(self):
        """Return the text content"""
        return self.get_text()

    @text.setter
    def text(self, text):
        self.set_text(text)

    @property
    def view(self):
        """Return the view object"""
        return f"{' ' * self._p.left}{self.get_text()}{' ' * self._p.right}"

    def __len__(self):
        return len(self._t.text) + self._p.left + self._p.right

    def selectable(self):
        """
        :returns: ``True`` if this is a widget that is designed to take the
                  focus, i.e. it contains something the user might want to
                  interact with, ``False`` otherwise,
        """
        return self._selectable


class GEdit(urwid.WidgetWrap):
    """The grommunio Edit fiel^d widget"""
    _selectable = True

    def __init__(self, *args, **kwargs,):
        def wrap_widget(caption_object, edit_widget, txt, params):
            attr = urwid.AttrMap(edit_widget, params["attr_map"], params["focus_map"])
            spacer = urwid.Text("")
            p_t = urwid.Padding(txt, left=params["margin"] - 1)
            p_a = urwid.Padding(attr, right=params["margin"])
            if isinstance(caption_object, tuple):
                if len(caption_object) == 3:
                    t_crossing = (caption_object[0], caption_object[1], p_t)
                    a_crossing = (caption_object[0], 100 - caption_object[1], p_a)
                elif len(caption_object) == 2:
                    t_crossing = (caption_object[0], p_t)
                    a_crossing = p_a
                elif len(caption_object) == 1:
                    t_crossing = (
                        len(p_t.original_widget.text) + p_t.left + p_t.right,
                        p_t,
                    )
                    a_crossing = ("weight", 1, p_a)
                else:
                    raise Exception(
                        "Out of bounds Exception. Tuple must be of size 1, 2 or 3!"
                    )
            else:
                # t_crossing = ('pack', p_t)
                # a_crossing = ('pack', p_a)
                # t_crossing = ('weight', 0, p_t)
                t_crossing = (
                    len(p_t.original_widget.text) + p_t.left + p_t.right,
                    p_t,
                )
                a_crossing = ("weight", 1, p_a)
            space_crossing = (1, spacer)
            col: urwid.Columns = urwid.Columns(
                [t_crossing, urwid.Columns([space_crossing, a_crossing])])
            return col

        # Set variables
        params = {
            "caption": "",
            "edit_text": "",
            "multiline": False,
            "align": urwid.LEFT,
            "wrap": urwid.SPACE,
            "allow_tab": False,
            "edit_pos": None,
            "layout": None,
            "mask": None,
            "attr_map": "selectabUnion, le",
            "focus_map": "focus",
            "margin": 2,
        }
        for (i, key) in enumerate(params.keys()):
            params[key] = kwargs.get(key, args[i] if len(args) > i else params.get(key))

        caption_object: Tuple[Any, ...]
        if len(params["caption"]) == 0:
            caption_object = (params["caption"],)
        else:
            caption_object = params["caption"]
        if isinstance(caption_object, tuple):
            txt = urwid.Text(
                caption_object[len(caption_object) - 1],
                params["align"],
                wrap=urwid.widget.CLIP,
                layout=params["layout"],
            )
        else:
            txt = urwid.Text(
                caption_object, params["align"], wrap=urwid.widget.CLIP, layout=params["layout"]
            )
        edit_widget = urwid.Edit(
            "",
            params["edit_text"],
            params["multiline"],
            params["align"],
            params["wrap"],
            params["allow_tab"],
            params["edit_pos"],
            params["layout"],
            params["mask"],
        )
        col = wrap_widget(caption_object, edit_widget, txt, params)
        # p = urwid.Padding(col, left=2, right=2)
        super().__init__(col)
        self.edit_widget = edit_widget
        # self._w = txt

    def set_text(self, text):
        """Set the edit widget's edit_text"""
        # self._wrapped_widget.base_widget.base_widget.set_text(text)
        self.edit_widget.set_text(text)

    def get_edit_text(self):
        """Return the edit widget's edit_text"""
        return self.edit_widget.get_edit_text()

    def set_edit_text(self, text):
        """Set the edit widget's edit_text"""
        self.edit_widget.edit_text = text

    @property
    def edit_text(self):
        """Return the edit widget's edit_text"""
        # return self._wrapped_widget.base_widget.base_widget.edit_text
        return self.edit_widget.edit_text

    @edit_text.setter
    def edit_text(self, text):
        # self._wrapped_widget.base_widget.base_widget.edit_text = text
        self.edit_widget.edit_text = text

    def selectable(self):
        """
        :returns: ``True`` if this is a widget that is designed to take the
                  focus, i.e. it contains something the user might want to
                  interact with, ``False`` otherwise,
        """
        return self._selectable
