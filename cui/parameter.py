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


dialog_params = ["body", "header", "footer", "focus_part",
                 "align", "width", "valign", "height", "modal"]
dialog_defaults = (None, None, None, None, urwid.CENTER, 40, urwid.MIDDLE, 10, False)
DialogParams = namedtuple_defaults("DialogParams", dialog_params, dialog_defaults)
