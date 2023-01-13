#!/usr/bin/python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2022 grommunio GmbH
"""The console user interface (cui) is a console utility for configuring grommunio"""
# Disable pylint warning about module name not being in snake_case naming style.
# pylint: disable=invalid-name
import cui

if __name__ == "__main__":
    app = cui.create_application()[0]
    app.start()
    print("\n\x1b[J")
