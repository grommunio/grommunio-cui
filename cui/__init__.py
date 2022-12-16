#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH
"""The main module of grommunio-cui."""
import sys
from typing import Tuple, Union
# from pudb.remote import set_trace
import urwid
from cui import classes
from cui.classes.gwidgets import GText, GEdit
from cui import util, parameter
import cui.classes.parser
from cui.classes.application import Header, MainFrame, GScreen, ButtonStore
from cui.classes.handler import ApplicationHandler
from cui.classes.scroll import ScrollBar, Scrollable
from cui.classes.button import GButton, GBoxButton
from cui.classes.interface import BaseApplication, WidgetDrawer
from cui.symbol import PRODUCTION, MAIN, MAIN_MENU, TERMINAL, LOGIN, REBOOT, SHUTDOWN, \
    UNSUPPORTED, PASSWORD, MESSAGE_BOX, INPUT_BOX, LOG_VIEWER, ADMIN_WEB_PW, TIMESYNCD, \
    KEYBOARD_SWITCH, REPO_SELECTION

try:
    import asyncio
except ImportError:
    import trollius as asyncio

_ = util.init_localization()


class Application(ApplicationHandler):
    """Placeholder class for future extensions"""


def create_application() -> Tuple[Union[Application, None], bool]:
    """Creates and returns the main application"""
    urwid.set_encoding("utf-8")
    production = True
    if "--help" in sys.argv:
        print(_("Usage: {%s} [OPTIONS]") % sys.argv[0])
        print(_("\tOPTIONS:"))
        print(_("\t\t--help: Show this message."))
        print(_("\t\t-v/--debug: Verbose/Debugging mode."))
        return None, PRODUCTION
    app = Application()
    if "-v" in sys.argv:
        app.set_debug(True)
    else:
        app.set_debug(False)

    app.view.gscreen.quiet = True

    if "--hidden-login" in sys.argv:
        production = False

    return app, production


def main_app():
    """Starts main application."""
    # application, PRODUCTION = create_application()
    application = create_application()[0]
    # application.set_debug(True)
    # application.gscreen.quiet = False
    # # PRODUCTION = False
    application.start()
    print("\n\x1b[J")


if __name__ == "__main__":
    main_app()
