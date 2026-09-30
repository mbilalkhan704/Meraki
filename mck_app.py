"""
Meraki - Bulk Certificate Generator
===========================
A standalone desktop app (similar to Canva's "Bulk Create") that:
  1. Loads a CSV or Excel file and lets you pick which column holds the name.
  2. Loads a certificate template image (any size, tuned for ~2000x1414).
  3. Lets you drag-position the name directly on a live preview, or type
     exact pixel coordinates.
  4. Lets you pick any font from Google Fonts (fetched live, with "Great
     Vibes" selected by default and a bundled .ttf as an offline backup).
  5. Lets you toggle Bold / Italic / Underline on the name text.
  6. Generates one file per row (PDF, PNG, or JPG) saved into a
     "certificates" subfolder, named after the person.

This is the entry point: it assembles the CertificateApp class out of the
feature mixins below and starts the app. Each mixin lives in its own file,
grouped by feature, so no single file holds the whole application:

    mck_constants.py       - paths, settings location, themes, palette data
    mck_utils.py           - standalone helpers (networking, file I/O,
                              text rendering, color math) - no app state
    mck_dnd.py             - drag-and-drop setup (tkinterdnd2) and AppBase
    mck_core.py            - init, splash screen, settings persistence
    mck_font_picker.py     - the Word-style font autocomplete boxes
    mck_dialogs.py         - icons, Settings dialog, API key prompt, themes
    mck_build_ui.py        - constructs the whole main window
    mck_upload_screen.py   - the "Upload Source File" gate screen + tabs
    mck_source_view.py     - the CSV/Excel grid and row-selection system
    mck_widgets_certid.py  - reusable widget builders + Certificate ID logic
    mck_cert_image.py      - loading source files/certificate images
    mck_color_picker.py    - the advanced color-choosing dialog
    mck_generation.py      - preview canvas + the actual bulk-generation run

Run directly with:  python mck_app.py
See README.md in this folder for how to bundle it into a single .exe.
"""

import sys

from mck_dnd import AppBase
from mck_core import CoreMixin
from mck_font_picker import FontPickerMixin
from mck_dialogs import DialogsMixin
from mck_build_ui import BuildUiMixin
from mck_upload_screen import UploadScreenMixin
from mck_source_view import SourceViewMixin
from mck_widgets_certid import WidgetsCertIdMixin
from mck_cert_image import CertImageMixin
from mck_color_picker import ColorPickerMixin
from mck_generation import PreviewGenerationMixin


# ---------------------------------------------------------------------------
# Main application - assembled from the feature mixins above. None of the
# mixins override each other's methods (every method name is unique across
# all of them), so their relative order doesn't matter EXCEPT for one
# thing: CoreMixin (which defines __init__) must come BEFORE AppBase
# (tk.Tk). Tkinter's own classes don't call super().__init__() - they are
# not written to cooperate with Python's multiple-inheritance chain - so
# if AppBase came first, Python would find tk.Tk.__init__ first, run it,
# and stop there without ever reaching CoreMixin.__init__ at all (no
# title, no splash screen, no _build_ui() call - just a bare default Tk
# window). Putting CoreMixin first means Python calls CoreMixin.__init__
# first, and its own super().__init__() call correctly continues the
# chain into tk.Tk.__init__ from there.
# ---------------------------------------------------------------------------
class CertificateApp(
    CoreMixin,
    AppBase,
    FontPickerMixin,
    DialogsMixin,
    BuildUiMixin,
    UploadScreenMixin,
    SourceViewMixin,
    WidgetsCertIdMixin,
    CertImageMixin,
    ColorPickerMixin,
    PreviewGenerationMixin,
):
    pass


if __name__ == "__main__":
    # Prevent Windows from falling back to the default Python "snake" icon on taskbar
    if sys.platform.startswith("win"):
        import ctypes
        myappid = "oric.merakicert.bulkgenerator.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = CertificateApp()
    app.mainloop()