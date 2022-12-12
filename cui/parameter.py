# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH
"""Module containing different parameter classes to reduce needed parameter per call."""

import collections
from typing import Type
import urwid


def namedtuple_defaults(typename, field_names, default_values=()) -> Type[tuple]:
    """Creates a namedtuple but with default values.

    @param typename: The class name of the named tuple.
    @param field_names: The field names of the named tuple class.
    @param default_values: The default values of the named tuple object.
    @return: A namedtuple
    """
    _namedtuple = collections.namedtuple(typename, field_names)
    _namedtuple.__new__.__defaults__ = (None, ) * len(_namedtuple._fields)
    if isinstance(default_values, collections.Mapping):
        proto = _namedtuple(**default_values)
    else:
        proto = _namedtuple(*default_values)
    _namedtuple.__new__.__defaults__ = tuple(proto)
    return _namedtuple


alignment_params = ["align", "valign"]
alignment_defaults = (urwid.CENTER, urwid.MIDDLE)
Alignment = namedtuple_defaults("Alignment", alignment_params, alignment_defaults)

size_params = ["width", "height"]
size_defaults = (40, 10)
Size = namedtuple_defaults("Size", size_params, size_defaults)

frame_params = ["body", "header", "footer", "focus_part"]
frame_defaults = (None, None, None, None)
Frame = namedtuple_defaults("Frame", frame_params, frame_defaults)

view_ok_cancel_params = ["view_ok", "view_cancel"]
view_ok_cancel_defaults = (True, False)
ViewOkCancel = namedtuple_defaults("ViewOkCancel", view_ok_cancel_params, view_ok_cancel_defaults)

msgbox_params = ["msg", "title", "modal"]
msgbox_defaults = (None, None, True)
MsgBoxParams = namedtuple_defaults("MsgBoxParams", msgbox_params, msgbox_defaults)

inputbox_params = ["msg", "title", "modal"]
inputbox_defaults = (None, None, True)
InputBoxParams = namedtuple_defaults("InputBoxParams", inputbox_params, inputbox_defaults)
