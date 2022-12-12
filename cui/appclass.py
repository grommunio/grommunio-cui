# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2022 grommunio GmbH
"""In this module all application classes are hold."""
from typing import Optional, List, Union

import urwid

import cui
import cui.scroll
from cui.interface import ApplicationHandler

T_ = cui.util.init_localization()


class Header:
    """The Header class holds all header information and widgets"""
    class TextBlock:
        """TextBlock containing all tb widgets."""
        tb_sysinfo_top: Optional[cui.gwidgets.GText]
        tb_sysinfo_bottom: Optional[cui.gwidgets.GText]
        tb_intro: Optional[cui.gwidgets.GText]
        tb_header: cui.gwidgets.GText

    class Info:
        """The Info class contains additional information"""
        text_header: List[Union[str, tuple]]
        header: cui.gwidgets.GText
        app: ApplicationHandler
        authorized_options: str = ""
        kbdlayout: str = cui.util.get_current_kbdlayout()
        # The default color palette
        colormode: str = "light"

    info: Info = Info()
    tb: TextBlock = TextBlock()

    def __init__(
            self,
            colormode: str = None,
            kbd_layout: str = None,
            application: ApplicationHandler = None
    ):
        if colormode:
            self.info.colormode = colormode
        if kbd_layout:
            self.info.kbdlayout = kbd_layout
        if application:
            self.info.app = application
        self.info.text_header = [T_("grommunio console user interface")]
        self.info.text_header += ["\n"]
        self.info.text_header += [
            T_("Active keyboard layout: {kbd}; color set: {colormode}.")
        ]
        self.info.authorized_options = ""
        text_intro = [
            "\n",
            T_("If you need help, press the 'L' key to view logs."),
            "\n",
        ]
        self.tb.tb_intro = cui.gwidgets.GText(
            text_intro, align=urwid.CENTER, wrap=urwid.SPACE
        )
        text_sysinfo_top = cui.util.get_system_info("top")
        self.tb.tb_sysinfo_top = cui.gwidgets.GText(
            text_sysinfo_top, align=urwid.LEFT, wrap=urwid.SPACE
        )
        text_sysinfo_bottom = cui.util.get_system_info("bottom")
        self.tb.tb_sysinfo_bottom = cui.gwidgets.GText(
            text_sysinfo_bottom, align=urwid.LEFT, wrap=urwid.SPACE
        )
        self.tb.tb_header = cui.gwidgets.GText(
            "".join(self.info.text_header).format(
                colormode=self.info.colormode,
                kbd=self.info.kbdlayout,
                authorized_options="",
            ),
            align=urwid.CENTER,
            wrap=urwid.SPACE,
        )

    def set_app(self, application: ApplicationHandler):
        """Set the main app"""
        self.info.app = application

    def setkbdlayout(self, kbdlayout):
        """Set the keyboard layout"""
        self.info.kbdlayout = kbdlayout

    def getkbdlayout(self):
        """Return the current keyboard layout"""
        return self.info.kbdlayout

    def set_colormode(self, colormode):
        """Set the color mode"""
        self.info.colormode = colormode

    def get_colormode(self):
        """return the mode of color"""
        return self.info.colormode

    def set_authorized_options(self, options):
        """Set the authorized options"""
        self.info.authorized_options = options

    def get_authorized_options(self):
        """Return the authorized options"""
        return self.info.authorized_options

    def refresh_header(self):
        """Refresh header"""
        self.refresh_head_text()
        self.info.header = urwid.AttrMap(
            urwid.Padding(self.tb.tb_header, align=urwid.CENTER), "header"
        )
        if getattr(self.info, "app", None):
            if getattr(self.info.app, "footer", None):
                self.info.app.refresh_main_menu()

    def refresh_head_text(self):
        """Refresh head text."""
        self.tb.tb_header.set_text(
            "".join(self.info.text_header).format(
                colormode=self.info.colormode,
                kbd=self.info.kbdlayout,
                authorized_options=self.info.authorized_options,
            )
        )


class MainFrame:
    """The MainFrame class holds all mainframe widgets"""
    mainframe: Optional[urwid.Frame]
    vsplitbox: Optional[urwid.Pile]
    main_top: Optional[cui.scroll.ScrollBar]
    main_bottom: Optional[cui.scroll.ScrollBar]
    app: ApplicationHandler

    def __init__(self, application: ApplicationHandler):
        self.app = application
        self.main_top = cui.scroll.ScrollBar(
            cui.scroll.Scrollable(
                urwid.Pile(
                    [
                        urwid.Padding(self.app.header.tb.tb_intro, left=2, right=2, min_width=20),
                        urwid.Padding(
                            self.app.header.tb.tb_sysinfo_top,
                            align=urwid.LEFT,
                            left=6,
                            width=("relative", 80),
                        ),
                    ]
                )
            )
        )
        self.main_bottom = cui.scroll.ScrollBar(
            cui.scroll.Scrollable(
                urwid.Pile(
                    [
                        urwid.AttrMap(
                            urwid.Padding(
                                self.app.header.tb.tb_sysinfo_bottom,
                                align=urwid.LEFT,
                                left=6,
                                width=("relative", 80),
                            ),
                            "reverse",
                        )
                    ]
                )
            )
        )
