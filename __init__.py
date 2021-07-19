"""The console user interface (cui) is a console utility for configuring grommunio"""
from cui import Application
import cui

if __name__ == '__main__':
    app = cui.create_application()
    app.start()
