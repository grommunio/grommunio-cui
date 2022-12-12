#!/usr/bin/env python3
"""The console user interface (cui) is a console utility for configuring grommunio"""
# Disable pylint warning about module name not being in snake_case naming style.
# pylint: disable=invalid-name
import cui

if __name__ == "__main__":
    app = cui.create_application()[0]
    app.start()
    print("\n\x1b[J")
