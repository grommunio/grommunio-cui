# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2022 grommunio GmbH
"""In this module all application classes are hold."""
from typing import Optional, List, Union

import urwid

import cui

T_ = cui.util.init_localization()


class Header(object):
    tb_sysinfo_top: Optional[cui.gwidgets.GText]
    tb_sysinfo_bottom: Optional[cui.gwidgets.GText]
    tb_intro: Optional[cui.gwidgets.GText]
    text_header: List[Union[str, tuple]]
    authorized_options: str

    def __init__(self):
        self.text_header = [T_("grommunio console user interface")]
        self.text_header += ["\n"]
        self.text_header += [
            T_("Active keyboard layout: {kbd}; color set: {colormode}.")
        ]
        self.authorized_options = ""
        text_intro = [
            "\n",
            T_("If you need help, press the 'L' key to view logs."),
            "\n",
        ]
        self.tb_intro = cui.gwidgets.GText(text_intro, align=urwid.CENTER, wrap=urwid.SPACE)
        text_sysinfo_top = cui.util.get_system_info("top")
        self.tb_sysinfo_top = cui.gwidgets.GText(text_sysinfo_top, align=urwid.LEFT, wrap=urwid.SPACE)
        text_sysinfo_bottom = cui.util.get_system_info("bottom")
        self.tb_sysinfo_bottom = cui.gwidgets.GText(
            text_sysinfo_bottom, align=urwid.LEFT, wrap=urwid.SPACE
        )


class Test(object):
    pass
