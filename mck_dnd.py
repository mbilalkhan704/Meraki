"""
Meraki - drag-and-drop setup module.

Native drag-and-drop for the app's upload screens, via tkinterdnd2.

An earlier version of this hooked Windows' WM_DROPFILES directly via
ctypes (subclassing the app's own live window procedure) specifically to
avoid adding a pip dependency. That turned out to be unsafe in practice:
subclassing a live Tk toplevel's WNDPROC at the Win32 level is fragile,
and if anything goes even slightly wrong inside that raw callback, it
doesn't produce a Python traceback - ctypes callbacks can't safely
propagate a Python exception back through native code, so Windows
receives an unhandled native fault and kills the ENTIRE process instantly
on drop, with no dialog and no traceback. tkinterdnd2 is the standard,
well-tested library for exactly this, implemented properly in C rather
than by patching a running toolkit's message loop from Python - it does
not have this failure mode.

Requires: pip install tkinterdnd2
(For a PyInstaller build, its data files usually need to be included -
see the packaging note wherever this file's README covers building the
.exe.) If the package isn't installed, this degrades to browse-only
silently - nothing here is allowed to crash the app either way.
"""

import tkinter as tk

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES # type: ignore
    DND_AVAILABLE = True
except Exception:
    TkinterDnD = None
    DND_FILES = None
    DND_AVAILABLE = False

# The class every mixin/the main app inherits from: TkinterDnD.Tk when the
# package is available (so drop_target_register works on any widget under
# it), otherwise a plain tk.Tk.
AppBase = TkinterDnD.Tk if DND_AVAILABLE else tk.Tk
