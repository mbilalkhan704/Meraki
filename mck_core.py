"""Meraki - core mixin: app init, splash screen, settings persistence,
recent-item recording, the How to Use dialog content, and the
always-on left-panel scroll handler."""

import os
import sys
import math
import threading
import webbrowser
import json
import re
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk

from mck_constants import (
    SETTINGS_PATH, 
    DEFAULT_FONT_FAMILY,
    ORIC_LOGO_FILE, 
    APP_ICON_PNG, 
    APP_ICON_ICO, 
    SPLASH_BG, 
    SPLASH_PALETTE,
    SPLASH_DURATION_MS,
    GITHUB_ISSUES_URL,
    CERT_ID_DEFAULT_LENGTH,
    THEMES,
    DEFAULT_THEME,
    SPLASH_LOGO_SIZE
)

from mck_utils import fetch_google_fonts_catalog


class _FLASHWINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("hwnd", ctypes.c_void_p),
                ("dwFlags", ctypes.c_uint), ("uCount", ctypes.c_uint),
                ("dwTimeout", ctypes.c_uint)]
    
class CoreMixin:
    def __init__(self):
        super().__init__()
        # Hidden IMMEDIATELY, before any other setup - Tk briefly maps the
        # default-sized blank root window the instant it's created, and
        # every line before withdraw() (title, icon, minsize...) gives the
        # OS compositor another chance to actually paint that blank frame
        # on screen for a tick before we hide it. Withdrawing first, then
        # doing the rest of setup while still hidden, is the standard fix.
        self.withdraw()
        self.title("Meraki - Bulk Certificate Generator")
        
        # Load window icon
        if os.path.isfile(APP_ICON_ICO) and sys.platform.startswith("win"):
            self.iconbitmap(APP_ICON_ICO)
        elif os.path.isfile(APP_ICON_PNG):
            icon_img = ImageTk.PhotoImage(file=APP_ICON_PNG)
            self.iconphoto(True, icon_img)
        self.minsize(1150, 660)

        # ---- state -----------------------------------------------------
        self.csv_path = None
        self.csv_headers = []
        self.csv_rows = []

        self.cert_image = None          # full-resolution PIL.Image (RGBA)
        self.preview_base = None        # scaled-down PIL.Image for canvas
        self.preview_scale = 1.0
        self.tk_preview_img = None      # keep a reference (avoid GC)

        self.available_fonts = {}       # family name -> filepath (str) OR raw bytes
        self.google_catalog = None      # dict {family: ttf_url} once fetched via official API
        self._font_pickers = {}         # "name" / "cert_id" -> widgets+vars, see _register_font_picker

        self.name_col = tk.StringVar()
        self.pos_x = tk.IntVar(value=1000)
        self.pos_y = tk.IntVar(value=700)
        self.center_name_x = tk.BooleanVar(value=False)
        self.center_name_y = tk.BooleanVar(value=False)
        self.font_size = tk.IntVar(value=90)
        self.font_color = "#1a1a1a"
        self.align_var = tk.StringVar(value="center")
        self.font_choice = tk.StringVar(value=DEFAULT_FONT_FAMILY)
        self.bold_var = tk.BooleanVar(value=False)
        self.italic_var = tk.BooleanVar(value=False)
        self.underline_var = tk.BooleanVar(value=False)
        self.name_casing = tk.StringVar(value="As in file")
        self.output_dir = None
        self.output_subfolder_name = tk.StringVar(value="certificates")
        self.output_format = tk.StringVar(value="PDF")

        # Certificate ID: always generated into the data file + filename;
        # drawing it on the certificate image itself is optional. It has
        # its own font choice, independent of the Name's, but shares the
        # Name's size/color/alignment/bold-italic-underline settings.
        self.cert_id_enabled = tk.BooleanVar(value=False)
        self.cert_id_length = tk.IntVar(value=CERT_ID_DEFAULT_LENGTH)
        self.cert_id_use_digits = tk.BooleanVar(value=True)
        self.cert_id_use_upper = tk.BooleanVar(value=True)
        self.cert_id_use_lower = tk.BooleanVar(value=False)
        self.cert_id_pos_x = tk.IntVar(value=1000)
        self.cert_id_pos_y = tk.IntVar(value=900)
        self.center_id_x = tk.BooleanVar(value=False)
        self.center_id_y = tk.BooleanVar(value=False)
        self.cert_id_font_choice = tk.StringVar(value=DEFAULT_FONT_FAMILY)
        self.cert_id_bold_var = tk.BooleanVar(value=False)
        self.cert_id_italic_var = tk.BooleanVar(value=False)
        self.cert_id_underline_var = tk.BooleanVar(value=False)
        self.cert_id_font_size = tk.IntVar(value=90)
        self.cert_id_font_color = "#1a1a1a"
        self.cert_id_align_var = tk.StringVar(value="center")
        self._cert_id_format_sample = ""
        self._cert_id_preview_override = False

        # Row-selection state for the new CSV View tab: which rows the
        # user wants processed on the next "Generate" click.
        self.row_selection_mode = tk.StringVar(value="all")
        self.row_selection_text = tk.StringVar(value="")
        self.row_selection_locked_chips = []  # [{"indices": frozenset, "label": str}, ...]
        self._row_selection_syncing = False
        self.current_view = "csv"

        self.pos_x.trace_add("write", lambda *_a: self._on_position_changed("name", "x"))
        self.pos_y.trace_add("write", lambda *_a: self._on_position_changed("name", "y"))
        self.cert_id_pos_x.trace_add("write", lambda *_a: self._on_position_changed("cert_id", "x"))
        self.cert_id_pos_y.trace_add("write", lambda *_a: self._on_position_changed("cert_id", "y"))

        self.google_api_key = tk.StringVar()
        self.theme = tk.StringVar(value=DEFAULT_THEME)
        self._current_theme_colors = THEMES[DEFAULT_THEME]
        self.recent_colors = []   # loaded from settings.json in _load_settings
        self.recent_files = []    # loaded from settings.json in _load_settings
        self.recent_cert_images = []  # loaded from settings.json in _load_settings

        self._dragging = False
        self._toggle_redraws = []
        self._active_modal_dialogs = []

        # Clicking the window's X asks for confirmation first, instead of
        # closing instantly - see _on_close_request.
        self.protocol("WM_DELETE_WINDOW", self._on_close_request)
        # Modal-dialog attention (flash/shake if a dialog loses focus to
        # the main window while it holds the grab) is driven by a polling
        # loop instead of an event binding - see _register_modal_dialog.
        self._modal_focus_poll_running = False

        self._show_splash()

        self._load_settings()
        self._build_ui()
        self._apply_theme(self.theme.get())
        self._refresh_all_font_dropdowns()
        self._refresh_cert_id_sample()
        self._update_cert_id_controls_state()
        self._update_output_path_preview()
        self._init_default_font()
        self._bootstrap_catalog()

    # ------------------------------------------------------------------
    # Modal-dialog attention: several of this app's dialogs (Settings,
    # How to Use, Choose Color, ...) hold a Tk input grab, which leaves the
    # main window unresponsive - and if the dialog is hidden behind other
    # windows, or the user just didn't notice it, the app looks frozen
    # with no hint why. So while a dialog is open, this periodically
    # checks where keyboard focus ACTUALLY is; if it's drifted away from
    # the dialog (e.g. clicking the main window brought it to the front,
    # even though Tk's grab then stops it from doing anything useful),
    # the dialog gets flashed/shaken, the system alert sound plays, and
    # its taskbar entry flashes on Windows.
    #
    # This intentionally does NOT rely on catching a specific Tk event
    # (like <FocusIn> on the main window) to detect the "user is stuck"
    # moment - a local grab_set() specifically prevents focus from ever
    # transferring into the main window's widgets while a dialog holds
    # it, so that event never reliably fires for the scenario it needs
    # to catch. Directly polling the real current focus state sidesteps
    # that entirely.
    # ------------------------------------------------------------------
    def _hwnd(self, widget):
        """Real top-level window handle (Tk's winfo_id is the inner child)."""
        h = widget.winfo_id()
        return ctypes.windll.user32.GetParent(h) or h

    def _user_is_off_dialog(self, target):
        """True when the user has clicked the main window while a dialog is open."""
        if sys.platform.startswith("win"):
            try:
                return ctypes.windll.user32.GetForegroundWindow() == self._hwnd(self)
            except Exception:
                return False
        try:
            f = self.focus_get()
        except Exception:
            return False
        if f is None:          # app not focused at all: not "stuck"
            return False
        s, t = str(f), str(target)
        return not (s == t or s.startswith(t + "."))
    
    def _register_modal_dialog(self, dialog):
        """Track an open modal dialog so attention feedback can target it,
        stop tracking it automatically once it's destroyed, and start the
        focus-polling loop (idempotent - safe to call while it's already
        running for an earlier dialog)."""
        self._active_modal_dialogs.append(dialog)

        def _on_destroyed(event, d=dialog):
            if event.widget is d and d in self._active_modal_dialogs:
                self._active_modal_dialogs.remove(d)

        dialog.bind("<Destroy>", _on_destroyed, add="+")

        # Explicitly focus the dialog itself now, so the very first poll
        # tick doesn't see "nothing focused yet" and mistake that for the
        # user being stuck on the main window. Any dialog that focuses a
        # more specific widget of its own (e.g. an entry) later in its own
        # setup will correctly override this afterward.
        try:
            dialog.focus_set()
        except Exception:
            pass

        if not getattr(self, "_modal_focus_poll_running", False):
            self._modal_focus_poll_running = True
            self.after(400, self._poll_modal_focus)

    def _poll_modal_focus(self):
        alive = [d for d in self._active_modal_dialogs if d.winfo_exists()]
        if not alive:
            self._modal_focus_poll_running = False
            return  # nothing open - stop polling; _register_modal_dialog restarts it later

        target = alive[-1]
        if self._user_is_off_dialog(target) and not getattr(target, "_attn_cooldown", False):
            self._flash_dialog_attention(target)
            target._attn_cooldown = True
            self.after(1200, lambda: setattr(target, "_attn_cooldown", False))

        self.after(300, self._poll_modal_focus)

    def _flash_dialog_attention(self, dialog):
        if not dialog.winfo_exists():
            return
        hook = getattr(dialog, "_on_attention", None)   # e.g. color picker closes its flyout
        if hook:
            try:
                hook()
            except Exception:
                pass
        try:
            if sys.platform.startswith("win"):
                import winsound
                winsound.MessageBeep()
            else:
                self.bell()
        except Exception:
            pass
        if sys.platform.startswith("win"):
            try:
                for w in (dialog, self):   # dialog is transient, so the taskbar button belongs to the main window
                    info = _FLASHWINFO(ctypes.sizeof(_FLASHWINFO), self._hwnd(w), 3, 3, 0)  # caption + tray, 3 times
                    ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
            except Exception:
                pass
        try:
            dialog.deiconify()
            dialog.lift()
            dialog.focus_force()
            dialog.grab_set()
        except Exception:
            pass
        self._pulse_dialog(dialog)

    def _install_close_hook(self):
        """Windows only: intercept the title-bar X (WM_CLOSE / SC_CLOSE) at the
        OS level, so it still reaches us while a dialog holds a Tk grab."""
        if not sys.platform.startswith("win"):
            return
        WM_CLOSE, WM_SYSCOMMAND, SC_CLOSE, SC_MINIMIZE, GWLP_WNDPROC = 0x0010, 0x0112, 0xF060, 0xF020, -4
        user32 = ctypes.windll.user32
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, ctypes.c_uint,
                                    wintypes.WPARAM, wintypes.LPARAM)
        user32.SetWindowLongPtrW.restype = ctypes.c_void_p
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        user32.CallWindowProcW.restype = LRESULT
        user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, ctypes.c_uint,
                                        wintypes.WPARAM, wintypes.LPARAM]

        def proc(hwnd, msg, wparam, lparam):
            cmd = wparam & 0xFFF0
            if msg == WM_CLOSE or (msg == WM_SYSCOMMAND and cmd in (SC_CLOSE, SC_MINIMIZE)):
                alive = [d for d in self._active_modal_dialogs if d.winfo_exists()]
                if alive:
                    self.after_idle(lambda: self._flash_dialog_attention(alive[-1]))
                    return 0                  # swallow: do NOT close the app
            return user32.CallWindowProcW(self._old_wndproc, hwnd, msg, wparam, lparam)

        self._new_wndproc = WNDPROC(proc)     # keep a reference or it gets garbage collected and crashes
        self._old_wndproc = user32.SetWindowLongPtrW(
            self._hwnd(self), GWLP_WNDPROC, ctypes.cast(self._new_wndproc, ctypes.c_void_p))

    def _pulse_dialog(self, dialog, step=0, edges=None):
        """Pulse a red/yellow border using overlay frames (place() doesn't
        affect the dialog's layout, unlike highlightthickness)."""
        if not dialog.winfo_exists():
            return
        if edges is None:
            t = 4
            edges = []
            try:
                for kw in (dict(x=0, y=0, relwidth=1, height=t),                       # top
                        dict(x=0, rely=1, relwidth=1, height=t, anchor="sw"),       # bottom
                        dict(x=0, y=0, width=t, relheight=1),                       # left
                        dict(relx=1, y=0, width=t, relheight=1, anchor="ne")):      # right
                    f = tk.Frame(dialog, bg="#ff4d4d", bd=0, highlightthickness=0)
                    f.place(**kw)
                    edges.append(f)
            except Exception:
                return
        if step >= 9:
            for f in edges:
                try:
                    f.destroy()
                except Exception:
                    pass
            return
        color = "#ff4d4d" if step % 2 == 0 else "#ffd43b"
        for f in edges:
            try:
                f.configure(bg=color)
                f.lift()
            except Exception:
                pass
        self.after(40, lambda: self._pulse_dialog(dialog, step + 1, edges))

    # ------------------------------------------------------------------
    # Exit confirmation
    # ------------------------------------------------------------------
    def _make_exit_icon(self, size=32, color="#e03131"):
        """Hand-drawn power symbol (open ring + vertical bar), drawn at 4x and
        downscaled for smooth edges."""
        s = size * 4
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        w = int(s * 0.11)
        pad = s * 0.16
        cx, cy = s / 2, s / 2 + s * 0.04
        d.arc((pad, cy - (s / 2 - pad), s - pad, cy + (s / 2 - pad)),
            start=-50, end=230, fill=color, width=w)
        top, bottom = s * 0.10, s * 0.50
        d.line((cx, top, cx, bottom), fill=color, width=w)
        rc = (s / 2 - pad) - w / 2                      # radius of the ring's centerline
        caps = [(cx, top), (cx, bottom)]
        for a in (-50, 230):                            # round the ring's two open ends
            caps.append((cx + rc * math.cos(math.radians(a)),
                        cy + rc * math.sin(math.radians(a))))
        for x, y in caps:
            d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=color)
        return ImageTk.PhotoImage(img.resize((size, size), Image.LANCZOS))
    
    def _on_close_request(self):
        """Ask before closing the app, in a dialog that follows the
        current theme (a stock messagebox wouldn't)."""
        # Already asking? Just draw attention to the existing prompt
        # rather than stacking a second one.
        alive = [d for d in self._active_modal_dialogs if d.winfo_exists()]
        if alive:
            self._flash_dialog_attention(alive[-1])
            return

        theme = self._current_theme_colors
        dialog = tk.Toplevel(self)
        dialog._is_exit_prompt = True
        dialog.title("Exit Meraki")
        dialog.configure(bg=theme["dialog_bg"])
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        self._register_modal_dialog(dialog)
        try:
            # Kept on self, otherwise Tk garbage-collects the images and they vanish.
            self._exit_icon_small = self._make_exit_icon(32)
            self._exit_icon_big = self._make_exit_icon(56)
            dialog.iconphoto(False, self._exit_icon_small)
        except Exception:
            self._exit_icon_big = None

        frm = ttk.Frame(dialog, padding=22, style="Dialog.TFrame")
        frm.pack(fill="both", expand=True)

        body = ttk.Frame(frm, style="Dialog.TFrame")
        body.pack(pady=(0, 18))
        if self._exit_icon_big is not None:
            ttk.Label(body, image=self._exit_icon_big, style="Dialog.TLabel").pack(
                side="left", padx=(0, 16))
        txt = ttk.Frame(body, style="Dialog.TFrame")
        txt.pack(side="left")
        ttk.Label(txt, text="Are you sure you want to exit?",
                font=("Segoe UI", 12, "bold"), style="Dialog.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Label(txt, text="Anything not yet generated will be lost.",
                style="DialogSubtle.TLabel").pack(anchor="w")

        btn_row = ttk.Frame(frm, style="Dialog.TFrame")
        btn_row.pack()

        def do_exit():
            dialog.destroy()
            self.destroy()

        cancel_btn = ttk.Button(btn_row, text="Cancel", command=dialog.destroy)
        cancel_btn.pack(side="left", padx=6)
        ttk.Button(btn_row, text="Exit", command=do_exit).pack(side="left", padx=6)

        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)  # X on this prompt = Cancel
        dialog.bind("<Escape>", lambda e: dialog.destroy())

        dialog.update_idletasks()
        w, h = dialog.winfo_reqwidth(), dialog.winfo_reqheight()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        dialog.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        cancel_btn.focus_set()

    def _maximize_window(self):
        try:
            self.state("zoomed")
        except tk.TclError:
            try:
                self.attributes("-zoomed", True)
            except tk.TclError:
                sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
                self.geometry(f"{sw}x{sh}+0+0")

    # ------------------------------------------------------------------
    # Splash screen - shown before the main window appears. Deliberately
    # uses its own fixed multi-color palette (SPLASH_BG / SPLASH_PALETTE),
    # independent of the in-app theme system - it's identity/branding, not
    # a themeable surface. Auto-dismisses after SPLASH_DURATION_MS, or
    # instantly on click.
    # ------------------------------------------------------------------
    def _show_splash(self):
        splash = tk.Toplevel(self)
        splash.overrideredirect(True)
        w, h = 720, 500
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x, y = (sw - w) // 2, (sh - h) // 2
        splash.geometry(f"{w}x{h}+{x}+{y}")
        splash.configure(bg=SPLASH_BG)

        canvas = tk.Canvas(splash, width=w, height=h, highlightthickness=0, bg=SPLASH_BG)
        canvas.pack(fill="both", expand=True)

        def _load_logo(path, max_dim):
            if not os.path.isfile(path):
                return None
            try:
                img = Image.open(path).convert("RGBA")
                ratio = min(max_dim / img.width, max_dim / img.height, 1.0)
                size = (max(1, int(img.width * ratio)), max(1, int(img.height * ratio)))
                img = img.resize(size, Image.LANCZOS)
                # Flatten onto a solid SPLASH_BG-colored backing using the
                # logo's own alpha channel as the paste mask. A logo PNG
                # with a transparent background would otherwise let the
                # splash's animated rays show through the transparent
                # areas, reading as lines passing through the logo rather
                # than sitting behind it. Applied to both logos, not just
                # ORIC's - harmless for a logo that's already fully
                # opaque, and protects against the same problem if either
                # logo file is ever swapped later.
                backing = Image.new("RGBA", size, SPLASH_BG)
                backing.paste(img, (0, 0), img)
                return ImageTk.PhotoImage(backing)
            except Exception:
                return None

        # Row A is the app's own logo beside ORIC's, side by side.
        app_logo_img = _load_logo(APP_ICON_PNG, SPLASH_LOGO_SIZE)
        oric_logo_img = _load_logo(ORIC_LOGO_FILE, SPLASH_LOGO_SIZE)

        self._splash = splash
        self._splash_canvas = canvas
        self._splash_app_logo_img = app_logo_img
        self._splash_oric_logo_img = oric_logo_img
        self._splash_frame_i = 0
        self._splash_w, self._splash_h = w, h

        self._splash_after_id = self.after(SPLASH_DURATION_MS, self._finish_splash)
        self._animate_splash()

    def _animate_splash(self):
        canvas = getattr(self, "_splash_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return

        w, h = self._splash_w, self._splash_h
        cx, cy = w / 2, h / 2 - 60
        t = self._splash_frame_i / 30.0

        canvas.delete("anim")

        # A slow-rotating sunburst behind everything else, for extra depth
        # beyond the ribbon/orbit motifs alone.
        for i in range(16):
            angle = t * 0.12 + i * (2 * math.pi / 16)
            x1 = cx + 65 * math.cos(angle)
            y1 = cy + 65 * math.sin(angle) * 0.6
            x2 = cx + 210 * math.cos(angle)
            y2 = cy + 210 * math.sin(angle) * 0.6
            color = SPLASH_PALETTE[i % len(SPLASH_PALETTE)]
            canvas.create_line(x1, y1, x2, y2, fill=color, width=1, tags="anim")

        # A soft Lissajous curve trace - a genuinely mathematical motif,
        # drawn as a chain of short colored segments so it reads as a
        # smooth, colorful ribbon rather than a single flat line.
        pts = []
        for k in range(0, 200, 4):
            tt = t + k * 0.02
            lx = cx + 160 * math.sin(2 * tt)
            ly = cy + 75 * math.sin(3 * tt + 1.0)
            pts.append((lx, ly))
        for i in range(len(pts) - 1):
            color = SPLASH_PALETTE[i % len(SPLASH_PALETTE)]
            canvas.create_line(*pts[i], *pts[i + 1], fill=color, width=2,
                                capstyle="round", tags="anim")

        # Orbiting dots - simple circular parametric motion, each at a
        # different radius/speed/color for a layered feel.
        for i, color in enumerate(SPLASH_PALETTE):
            speed = 0.55 + i * 0.13
            radius = 100 + i * 15
            angle = t * speed + i * (math.pi / 3)
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle) * 0.6
            r = 4 + (i % 3)
            canvas.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="", tags="anim")

        # Row A: app logo + ORIC logo, side by side.
        gap = 26
        app_img = self._splash_app_logo_img
        oric_img = self._splash_oric_logo_img
        app_w = app_img.width() if app_img else 0
        oric_w = oric_img.width() if oric_img else 0
        total_w = app_w + (gap if app_w and oric_w else 0) + oric_w
        cursor_x = cx - total_w / 2
        if app_img is not None:
            canvas.create_image(cursor_x + app_w / 2, cy, image=app_img, tags="anim")
            cursor_x += app_w + gap
        if oric_img is not None:
            canvas.create_image(cursor_x + oric_w / 2, cy, image=oric_img, tags="anim")

        # Row B: single combined credit line beneath the logos.
        canvas.create_text(
            cx, cy + 145,
            text="Meraki by Office of Research, Innovation and Commercialization, "
                 "University of Karachi",
            fill="#e8e8f0", font=("Segoe UI", 10), tags="anim",
            width=w - 70, justify="center")

        # A spinning loading indicator beneath the branding, with an
        # animated "Initializing..." status line under that - top to
        # bottom: logos/credit line, then spinner, then status text.
        spinner_cy = cy + 195
        spinner_r = 15
        spin_angle = (t * 220) % 360
        canvas.create_arc(
            cx - spinner_r, spinner_cy - spinner_r, cx + spinner_r, spinner_cy + spinner_r,
            start=spin_angle, extent=270, style="arc", outline="#ffffff", width=3, tags="anim")

        dots = "." * (1 + (self._splash_frame_i // 15) % 3)
        canvas.create_text(cx, spinner_cy + spinner_r + 22, text=f"Initializing{dots}",
                            fill="#a9a9c0", font=("Segoe UI", 9), tags="anim")

        self._splash_frame_i += 1
        self._splash_anim_id = self.after(33, self._animate_splash)

    def _finish_splash(self):
        for attr in ("_splash_after_id", "_splash_anim_id"):
            after_id = getattr(self, attr, None)
            if after_id is not None:
                try:
                    self.after_cancel(after_id)
                except Exception:
                    pass
        splash = getattr(self, "_splash", None)
        if splash is not None and splash.winfo_exists():
            splash.destroy()
        self.deiconify()
        self._maximize_window()
        self._install_close_hook()      # <- new
        self._maybe_show_api_key_prompt()

    # ------------------------------------------------------------------
    # Settings persistence (Google Fonts API key + theme), stored per-user
    # in LocalAppData - independent of where the .exe itself lives.
    # ------------------------------------------------------------------
    def _load_settings(self):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        key = (data.get("google_fonts_api_key") or "").strip()
        if key:
            self.google_api_key.set(key)
        theme_name = data.get("theme")
        if theme_name in THEMES:
            self.theme.set(theme_name)
            self._current_theme_colors = THEMES[theme_name]
        recents = data.get("recent_colors")
        if isinstance(recents, list):
            self.recent_colors = [c for c in recents
                                if isinstance(c, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", c)][-10:]
        recent_files = data.get("recent_files")
        if isinstance(recent_files, list):
            self.recent_files = [p for p in recent_files if isinstance(p, str)][-8:]
        recent_cert_images = data.get("recent_cert_images")
        if isinstance(recent_cert_images, list):
            self.recent_cert_images = [p for p in recent_cert_images if isinstance(p, str)][-8:]

    def _save_settings(self):
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump({
                    "google_fonts_api_key": self.google_api_key.get().strip(),
                    "theme": self.theme.get(),
                    "recent_colors": self.recent_colors,
                    "recent_files": self.recent_files,
                    "recent_cert_images": self.recent_cert_images,
                }, f)
        except Exception:
            pass

    def _record_recent_color(self, hexcode):
        """Newest goes last; once past 10, the oldest (front of the list)
        is dropped - never the newest."""
        hexcode = hexcode.lower()
        self.recent_colors = [c for c in self.recent_colors if c.lower() != hexcode]
        self.recent_colors.append(hexcode)
        if len(self.recent_colors) > 10:
            self.recent_colors = self.recent_colors[-10:]
        self._save_settings()

    def _record_recent_file(self, path):
        """Same newest-last, capped, oldest-dropped-first convention as
        _record_recent_color."""
        path = os.path.abspath(path)
        self.recent_files = [p for p in self.recent_files if os.path.abspath(p) != path]
        self.recent_files.append(path)
        if len(self.recent_files) > 8:
            self.recent_files = self.recent_files[-8:]
        self._save_settings()
        if hasattr(self, "recent_files_frame"):
            self._refresh_recent_files_list()

    def _record_recent_cert_image(self, path):
        """Same newest-last, capped, oldest-dropped-first convention as
        _record_recent_file."""
        path = os.path.abspath(path)
        self.recent_cert_images = [p for p in self.recent_cert_images if os.path.abspath(p) != path]
        self.recent_cert_images.append(path)
        if len(self.recent_cert_images) > 8:
            self.recent_cert_images = self.recent_cert_images[-8:]
        self._save_settings()

    def _add_swatch(self, parent, hexcode, on_click, size=18):
        theme = self._current_theme_colors
        c = tk.Canvas(parent, width=size, height=size, highlightthickness=1,
                    highlightbackground=theme["border"], bg=hexcode, cursor="hand2")
        c.bind("<Button-1>", lambda e: on_click(hexcode))
        return c

    def _add_swatch_row(self, parent, hex_list, on_click, size=18):
        for i, hexcode in enumerate(hex_list):
            sw = self._add_swatch(parent, hexcode, on_click, size=size)
            sw.grid(row=0, column=i, padx=1)

    def _open_github_issues(self):
        # Replace with your actual GitHub repository URL
        issues_url = GITHUB_ISSUES_URL
        webbrowser.open_new_tab(issues_url)

    def _how_to_use_content(self):
        """User-facing help content: what each feature does and how to use
        it, from the point of view of someone using the app - not a
        developer README. Returned as (tag, text) blocks rendered into the
        Text widget in _open_how_to_use_dialog."""
        return [
            ("h1", "Getting Started"),
            ("body", "When you open Meraki, you'll first be asked to upload a source file - "
                      "a CSV or Excel file where each row is one person who should get a "
                      "certificate. You can browse for the file, drag and drop it onto the drop "
                      "zone, or pick one of your recently used files from the list on the left."),
            ("body", "Once your source file is loaded, upload a certificate template image "
                      "(Section 2 of the left panel) - the blank certificate design you already "
                      "have. Meraki prints each person's name (and an ID, if you choose) onto a "
                      "copy of it."),

            ("h1", "The Two Tabs: Source File View and Certificate View"),
            ("body", "Once both a source file and a certificate image are loaded, two tabs "
                      "appear above the main preview area:"),
            ("bullet", "\u2022 Source File View shows your data as a spreadsheet-style grid, and "
                        "lets you choose exactly which rows to generate certificates for."),
            ("bullet", "\u2022 Certificate View shows a live preview of the certificate, where you "
                        "can drag the name and ID directly to position them."),
            ("body", "You can drop a new file onto either tab at any time to replace what's "
                      "currently loaded - a new source file replaces the data, a new image "
                      "replaces the template."),

            ("h1", "Choosing Which Rows to Process"),
            ("body", "In Source File View, 'All rows' (the default) processes every row in your "
                      "file. Choose 'Custom' to process only some rows:"),
            ("bullet", "\u2022 Type a range like \"2-5, 8, 10-12\" directly into the box."),
            ("bullet", "\u2022 Or shift-click / ctrl-click rows in the grid to build a selection "
                        "visually - the box fills in automatically."),
            ("bullet", "\u2022 Rows that will be processed are highlighted green; skipped rows "
                        "are red."),
            ("body", "If you need more than one separate range (for example rows 2-5 AND rows "
                      "20-25, with a gap in between), type or select the first range and click "
                      "'Lock' - this protects it as its own chip so building the next range won't "
                      "disturb it. Each locked chip has its own '\u2212' button to remove it."),

            ("h1", "Positioning the Name and Certificate ID"),
            ("body", "Switch to Certificate View and simply click-and-drag the name (or the ID) "
                      "to wherever you want it on the certificate. You can also type exact pixel "
                      "coordinates in Section 3 (Name) or Section 4 (Certificate ID) if you need "
                      "precision, and use the Center X / Center Y buttons to snap to the middle."),

            ("h1", "Fonts"),
            ("body", "Click the font box and start typing to search - matching fonts appear "
                      "automatically as you type, just like in Word. Without a Google Fonts API "
                      "key, only the built-in 'Great Vibes' font is available; adding a free API "
                      "key (see below) unlocks over 1,800 Google Fonts to choose from."),
            ("body", "The Name and the Certificate ID each have their own independent font, "
                      "size, color, and Bold / Italic / Underline styling."),

            ("h1", "Choosing Colors"),
            ("body", "Click 'Choose...' next to Color to open the color picker. It has a grid "
                      "of standard colors and shaded palettes, a Recent Colors row (your last 10 "
                      "picks, saved between sessions), and a 'More colors' option that opens a "
                      "full color spectrum with hex and RGB entry boxes for exact colors."),

            ("h1", "Certificate ID"),
            ("body", "Section 4 lets you generate a unique Certificate ID for every row - useful "
                      "for verification or record-keeping. Choose the length and which characters "
                      "to use (numbers, uppercase, lowercase letters), and optionally have it "
                      "drawn on the certificate itself. IDs are saved back into your source file, "
                      "so re-running the same file later never changes IDs that were already "
                      "assigned - only rows without one yet get a new ID."),

            ("h1", "Recent Files"),
            ("body", "Meraki remembers your last 8 source files and your last 8 certificate "
                      "images, so you can pick up where you left off. Source files appear on the "
                      "initial upload screen; certificate images appear under 'Select from recent "
                      "files' in Section 2 of the left panel."),

            ("h1", "Themes"),
            ("body", "Open Settings (top right) to switch between Light, Dark, Ocean, and Sunset "
                      "themes. Your choice is saved and applied everywhere in the app, including "
                      "in dialogs like this one."),

            ("h1", "Adding a Google Fonts API Key"),
            ("body", "Open Settings and paste a free Google Fonts API key to unlock the full "
                      "font library. If you skip this, Meraki still works fine with the built-in "
                      "default font - the key is entirely optional, just an upgrade."),

            ("h1", "Generating Certificates"),
            ("body", "Once everything is set up, choose an output folder and a file format "
                      "(PDF, PNG, or JPG) in Section 5, then click 'Generate all certificates'. "
                      "Each file is named after the person (and their Certificate ID, if enabled). "
                      "A progress bar and status message appear only while generation is actually "
                      "running."),

            ("h1", "Getting Help"),
            ("body", "Click 'Help' (top right) to report an issue or ask a question, or reopen "
                      "this 'How to Use' guide any time you need a refresher."),
        ]

    def _open_how_to_use_dialog(self):
        theme = self._current_theme_colors

        dialog = tk.Toplevel(self)
        dialog.title("How to Use Meraki")
        dialog.configure(bg=theme["dialog_bg"])
        dialog.transient(self)
        dialog.grab_set()
        self._register_modal_dialog(dialog)
        try:
            self._how_to_use_icon_img = None
            if os.path.isfile(APP_ICON_PNG):
                icon_src = Image.open(APP_ICON_PNG).convert("RGBA")
                icon_src.thumbnail((32, 32), Image.LANCZOS)
                self._how_to_use_icon_img = ImageTk.PhotoImage(icon_src)
                dialog.iconphoto(False, self._how_to_use_icon_img)
        except Exception:
            pass

        frm = ttk.Frame(dialog, padding=16, style="Dialog.TFrame")
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="How to Use Meraki", font=("Segoe UI", 16, "bold"),
                  style="Dialog.TLabel").pack(anchor="w", pady=(0, 12))

        text_frame = ttk.Frame(frm, style="Dialog.TFrame")
        text_frame.pack(fill="both", expand=True)

        text_widget = tk.Text(text_frame, wrap="word", relief="flat", padx=14, pady=10,
                               bg=theme["dialog_bg"], fg=theme["text"], font=("Segoe UI", 10),
                               highlightthickness=0, borderwidth=0, cursor="arrow")
        vsb = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=vsb.set)
        text_widget.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        text_widget.tag_configure("h1", font=("Segoe UI", 13, "bold"), foreground=theme["accent2"],
                                   spacing1=14, spacing3=6)
        text_widget.tag_configure("body", font=("Segoe UI", 10), foreground=theme["text"],
                                   spacing3=4)
        text_widget.tag_configure("bullet", font=("Segoe UI", 10), foreground=theme["text"],
                                   lmargin1=18, lmargin2=30, spacing3=2)

        for block_type, block_text in self._how_to_use_content():
            text_widget.insert("end", block_text + "\n", block_type)
        text_widget.configure(state="disabled")

        ttk.Button(frm, text="Close", command=dialog.destroy).pack(anchor="e", pady=(12, 0))

        w, h = 760, 640
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        dialog.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    def _effective_api_key(self):
        return self.google_api_key.get().strip()

    # ------------------------------------------------------------------
    # Google Fonts catalog bootstrap (silent - runs automatically)
    # ------------------------------------------------------------------
    def _bootstrap_catalog(self):
        key = self._effective_api_key()
        if not key:
            return
        thread = threading.Thread(target=self._fetch_catalog_worker, args=(key,), daemon=True)
        thread.start()

    def _fetch_catalog_worker(self, key):
        try:
            catalog = fetch_google_fonts_catalog(key)
            self.after(0, lambda: self._catalog_fetch_done(catalog))
        except Exception as exc:
            message = str(exc)
            self.after(0, lambda: self._catalog_fetch_failed(message))

    def _catalog_fetch_done(self, catalog):
        self.google_catalog = catalog
        self._refresh_all_font_dropdowns()
        self.catalog_status.config(text=f"Full catalog loaded: {len(catalog)} fonts available.")

    def _catalog_fetch_failed(self, message):
        self.google_catalog = None
        self._refresh_all_font_dropdowns()
        self.catalog_status.config(
            text="Couldn't refresh the font catalog right now (check your internet connection).")

    def _on_left_panel_mousewheel(self, event):
        """Always-on handler for scrolling the left panel - never toggled
        by Enter/Leave, so a transient overlapping window (a font popup,
        the color-spectrum flyout, etc.) can never leave it stuck off.
        Scrolls whenever the pointer is geometrically over the panel,
        regardless of which specific child widget is directly under it."""
        # 1. Native ttk dropdown (arrow button): its own Listbox already
        #    scrolled itself, so the panel must not move.
        if "popdown" in str(event.widget):
            return

        # 2. Pointer over our custom popup: scroll that list, never the panel.
        key = self._popup_under_pointer()
        if key is not None:
            listbox = self._font_pickers[key]["popup_listbox"]
            # If the event targeted the listbox itself, its class binding
            # already scrolled it; scrolling again would double the speed.
            # If it targeted the combo (focus), scroll the list ourselves.
            if event.widget is not listbox:
                self._scroll_popup_list(key, event)
            return "break"

        # 3. A real panel scroll: close any open popup so it can't be
        #    left floating in the old position, then scroll the panel.
        self._hide_all_font_popups()
        self._close_native_popdowns()

        lc = getattr(self, "left_canvas", None)
        if lc is None or not lc.winfo_exists():
            return
        px, py = self.winfo_pointerxy()
        x, y = lc.winfo_rootx(), lc.winfo_rooty()
        if not (x <= px <= x + lc.winfo_width() and y <= py <= y + lc.winfo_height()):
            return
        if getattr(event, "num", None) == 4:
            lc.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            lc.yview_scroll(1, "units")
        else:
            lc.yview_scroll(int(-1 * (event.delta / 120)), "units")