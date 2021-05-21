# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

import urwid


class GText(urwid.WidgetWrap):
    def __init__(self, markup, align=urwid.LEFT, wrap=urwid.SPACE, layout=None):
        t = urwid.Text(markup, align, wrap, layout)
        if t.align == urwid.LEFT:
            p = urwid.Padding(t, left=2, right=2)
        else:
            p = urwid.Padding(t, left=0, right=0)
        super(GText, self).__init__(p)
        # self._w = t

    def set_text(self, text):
        self._wrapped_widget.base_widget.set_text(text)



