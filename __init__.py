#!/usr/bin/env python3
"""The console user interface (cui) is a console utility for configuring grommunio"""
import cui

if __name__ == "__main__":
    app = cui.create_application()
    app.start()
    print("\n\x1b[J")
