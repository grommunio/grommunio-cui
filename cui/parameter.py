# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

import collections

import urwid


def namedtuple_defaults(typename, field_names, default_values=()):
    T = collections.namedtuple(typename, field_names)
    T.__new__.__defaults__ = (None, ) * len(T._fields)
    if isinstance(default_values, collections.Mapping):
        proto = T(**default_values)
    else:
        proto = T(*default_values)
    T.__new__.__defaults__ = tuple(proto)
    return T


alignment_params = ["align", "valign"]
alignment_defaults = (urwid.CENTER, urwid.MIDDLE)
Alignment = namedtuple_defaults("Alignment", alignment_params, alignment_defaults)

size_params = ["width", "height"]
size_defaults = (40, 10)
Size = namedtuple_defaults("Size", size_params, size_defaults)

frame_params = ["body", "header", "footer", "focus_part"]
frame_defaults = (None, None, None, None)
Frame = namedtuple_defaults("Frame", frame_params, frame_defaults)
