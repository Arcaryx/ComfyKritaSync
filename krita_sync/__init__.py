import sys

if 'krita' in sys.modules:
    from .krita_sync import *
