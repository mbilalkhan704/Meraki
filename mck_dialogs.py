"""Meraki - dialogs mixin: hand-drawn title-bar icons, the Settings
dialog, the first-run API key prompt, and the master theme-application
routine that styles every ttk widget in the app."""

import sys
import math
import threading
import webbrowser
import ctypes
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk

from mck_constants import (
    THEMES, 
    DEFAULT_THEME
)

from mck_utils import validate_google_fonts_api_key


class DialogsMixin:
    def _make_gear_icon(self, size=32, color="#5b5fc7"):
        """A hand-drawn gear silhouette (polygon with alternating tooth/
        root radius points, plus a punched-out transparent center hole) -
        used as the Settings dialog's title-bar icon so it actually shows
        a gear instead of Tk's generic default icon. Drawn rather than
        rendered from a symbol font, since that would depend on a specific
        font (e.g. Segoe UI Symbol) being installed to render correctly."""
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        cx = cy = size / 2
        outer_r = size * 0.34
        tooth_r = size * 0.46
        inner_r = size * 0.16
        teeth = 8
        pts = []
        for i in range(teeth * 2):
            angle = i * math.pi / teeth
            r = tooth_r if i % 2 == 0 else outer_r
            pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        draw.polygon(pts, fill=color)
        draw.ellipse((cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r), fill=(0, 0, 0, 0))
        return ImageTk.PhotoImage(img)

    def _make_palette_icon(self, size=32):
        """A hand-drawn artist's palette (board + thumb hole + paint dabs)
        - used as the Choose Color dialog's title-bar icon, in place of
        Tk's generic default icon."""
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        cx, cy = size / 2, size / 2
        board_w, board_h = size * 0.92, size * 0.72
        draw.ellipse((cx - board_w / 2, cy - board_h / 2, cx + board_w / 2, cy + board_h / 2),
                     fill="#c69a5e", outline="#8a6a3f", width=1)
        hole_r = size * 0.11
        hx, hy = cx + board_w * 0.2, cy + board_h * 0.05
        draw.ellipse((hx - hole_r, hy - hole_r, hx + hole_r, hy + hole_r), fill=(0, 0, 0, 0))
        dab_colors = ["#e03131", "#2f9e44", "#1971c2", "#f08c00", "#ae3ec9"]
        dab_r = size * 0.075
        for i, col in enumerate(dab_colors):
            angle = math.pi * 1.08 + i * (math.pi * 0.95 / (len(dab_colors) - 1))
            dx = cx + (board_w * 0.32) * math.cos(angle)
            dy = cy + (board_h * 0.32) * math.sin(angle)
            draw.ellipse((dx - dab_r, dy - dab_r, dx + dab_r, dy + dab_r), fill=col)
        return ImageTk.PhotoImage(img)

    def _open_settings_dialog(self):
        original_key = self.google_api_key.get()
        original_theme = self.theme.get()
        theme = self._current_theme_colors

        dialog = tk.Toplevel(self)
        dialog.title("Settings")
        dialog.configure(bg=theme["dialog_bg"])
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        self._register_modal_dialog(dialog)
        try:
            # Kept on self (not a local var) - PhotoImage is garbage
            # collected the instant nothing references it, which would
            # blank the icon right after this call returns.
            self._settings_gear_icon_img = self._make_gear_icon(size=32, color=theme["accent"])
            dialog.iconphoto(False, self._settings_gear_icon_img)
        except Exception:
            pass

        frm = ttk.Frame(dialog, padding=18, style="Dialog.TFrame")
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Google Fonts API key", font=("Segoe UI", 11, "bold"),
                  style="Dialog.TLabel").pack(anchor="w")
        key_entry = ttk.Entry(frm, textvariable=self.google_api_key, width=40)
        key_entry.pack(fill="x", pady=(6, 0))
        link = ttk.Label(frm, text="Get a free key from Google →", foreground=theme["accent"],
                          style="Dialog.TLabel", cursor="hand2")
        link.pack(anchor="w", pady=(4, 0))
        link.bind("<Button-1>", lambda e: webbrowser.open(
            "https://developers.google.com/fonts/docs/developer_api"))

        status_label = ttk.Label(frm, text="", style="DialogSubtle.TLabel", wraplength=360, justify="left")
        status_label.pack(anchor="w", pady=(8, 0))

        ttk.Separator(frm).pack(fill="x", pady=(16, 14))

        ttk.Label(frm, text="Theme", font=("Segoe UI", 11, "bold"), style="Dialog.TLabel").pack(anchor="w")
        theme_combo = ttk.Combobox(frm, textvariable=self.theme, state="readonly",
                                    values=list(THEMES.keys()))
        theme_combo.pack(fill="x", pady=(6, 0))
        theme_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_theme(self.theme.get()))

        btn_row = ttk.Frame(frm, style="Dialog.TFrame")
        btn_row.pack(fill="x", pady=(22, 0))

        save_btn = ttk.Button(btn_row, text="Save")
        save_btn.pack(side="left", padx=(0, 6))
        cancel_btn = ttk.Button(btn_row, text="Cancel")
        cancel_btn.pack(side="left")

        def set_busy(busy, message="", is_error=False):
            state = "disabled" if busy else "normal"
            key_entry.config(state=state)
            cancel_btn.config(state=state)
            theme_combo.config(state="disabled" if busy else "readonly")
            save_btn.config(state=state)
            status_label.config(text=message, foreground=("#e03131" if is_error else theme["subtle_text"]))

        def on_save():
            key = self.google_api_key.get().strip()
            if not key:
                # clearing the key back to blank is always allowed - no
                # validation needed to remove something.
                self.google_catalog = None
                self._save_settings()
                self._refresh_all_font_dropdowns()
                dialog.destroy()
                return
            set_busy(True, "Checking your key with Google...")
            thread = threading.Thread(target=validate_worker, args=(key,), daemon=True)
            thread.start()

        def validate_worker(key):
            status, payload = validate_google_fonts_api_key(key)
            self.after(0, lambda: on_validated(key, status, payload))

        def on_validated(key, status, payload):
            if not dialog.winfo_exists():
                return
            if self.google_api_key.get().strip() != key:
                set_busy(False)
                return
            if status == "valid":
                self.google_catalog = payload
                self._save_settings()
                self._refresh_all_font_dropdowns()
                dialog.destroy()
            elif status == "invalid":
                set_busy(False, f"That key didn't work: {payload}", is_error=True)
            else:
                set_busy(False, f"Couldn't check the key right now ({payload}). "
                                 f"Check your internet connection and try again.", is_error=True)

        def on_cancel():
            self.google_api_key.set(original_key)
            self._apply_theme(original_theme)
            dialog.destroy()

        save_btn.config(command=on_save)
        cancel_btn.config(command=on_cancel)

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)

        dialog.update_idletasks()
        w = dialog.winfo_reqwidth()
        h = dialog.winfo_reqheight()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

    def _maybe_show_api_key_prompt(self):
        """Shown once per launch whenever no API key is on file - every
        time, not just the very first run, since a fresh install on a new
        machine (or a deleted settings file) has no key either."""
        if not self._effective_api_key():
            self._show_api_key_prompt_dialog()

    def _show_api_key_prompt_dialog(self):
        theme = self._current_theme_colors

        dialog = tk.Toplevel(self)
        dialog.title("Add a Google Fonts API key")
        dialog.configure(bg=theme["dialog_bg"])
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        self._register_modal_dialog(dialog)

        frm = ttk.Frame(dialog, padding=18, style="Dialog.TFrame")
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Unlock the full Google Fonts library",
                  font=("Segoe UI", 12, "bold"), style="Dialog.TLabel").pack(anchor="w")
        ttk.Label(frm, wraplength=380, justify="left", style="Dialog.TLabel",
                  text="Right now only the Great Vibes font is available. Adding a "
                       "free Google Fonts API key upgrades the font list to 1,800+ "
                       "fonts to choose from.").pack(anchor="w", pady=(8, 14))

        ttk.Label(frm, text="Google Fonts API key", font=("Segoe UI", 10, "bold"),
                  style="Dialog.TLabel").pack(anchor="w")
        key_entry = ttk.Entry(frm, textvariable=self.google_api_key, width=42)
        key_entry.pack(fill="x", pady=(6, 0))
        key_entry.focus_set()  # Focus entry field automatically

        link = ttk.Label(frm, text="Get a free key from Google →", foreground=theme["accent"],
                          style="Dialog.TLabel", cursor="hand2")
        link.pack(anchor="w", pady=(4, 0))
        link.bind("<Button-1>", lambda e: webbrowser.open(
            "https://developers.google.com/fonts/docs/developer_api"))

        status_label = ttk.Label(frm, text="", style="DialogSubtle.TLabel", wraplength=380, justify="left")
        status_label.pack(anchor="w", pady=(10, 0))

        ttk.Label(frm, style="DialogSubtle.TLabel", wraplength=380, justify="left",
                  text="You can add or change this anytime later from Settings.").pack(
            anchor="w", pady=(12, 0))

        btn_row = ttk.Frame(frm, style="Dialog.TFrame")
        btn_row.pack(fill="x", pady=(20, 0))

        save_btn = ttk.Button(btn_row, text="Save & Continue")
        save_btn.pack(side="left", padx=(0, 6))
        skip_btn = ttk.Button(btn_row, text="Continue with Great Vibes only")
        skip_btn.pack(side="left")

        def refit_dialog():
            """Recalculate window geometry so expanding text never overflows buttons."""
            dialog.update_idletasks()
            w = dialog.winfo_reqwidth()
            h = dialog.winfo_reqheight()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            x = (sw - w) // 2
            y = (sh - h) // 2
            dialog.geometry(f"{w}x{h}+{x}+{y}")

        def set_busy(busy, message="", is_error=False):
            state = "disabled" if busy else "normal"
            key_entry.config(state=state)
            skip_btn.config(state=state)
            save_btn.config(state="disabled" if busy else
                             ("normal" if self.google_api_key.get().strip() else "disabled"))
            status_label.config(text=message, foreground=("#e03131" if is_error else theme["subtle_text"]))
            refit_dialog()  # Re-center and adjust window height whenever message changes

        def on_save():
            key = self.google_api_key.get().strip()
            if not key:
                return
            set_busy(True, "Checking your key with Google...")
            thread = threading.Thread(target=validate_worker, args=(key,), daemon=True)
            thread.start()

        def validate_worker(key):
            status, payload = validate_google_fonts_api_key(key)
            self.after(0, lambda: on_validated(key, status, payload))

        def on_validated(key, status, payload):
            if not dialog.winfo_exists():
                return
            if self.google_api_key.get().strip() != key:
                set_busy(False)
                return
            if status == "valid":
                self.google_catalog = payload
                self._save_settings()
                self._refresh_all_font_dropdowns()
                try:
                    self.google_api_key.trace_remove("write", trace_id)
                except Exception:
                    pass
                dialog.destroy()
            elif status == "invalid":
                set_busy(False, f"That key didn't work: {payload}", is_error=True)
            else:
                set_busy(False, f"Couldn't check the key right now ({payload}). "
                                 f"Check your internet connection and try again.", is_error=True)

        def on_skip():
            try:
                self.google_api_key.trace_remove("write", trace_id)
            except Exception:
                pass
            dialog.destroy()

        def on_enter_key(event=None):
            """Enter key acts as Save if API key is present, otherwise acts as Skip."""
            if key_entry.cget("state") == "disabled":
                return
            if self.google_api_key.get().strip():
                on_save()
            else:
                on_skip()

        save_btn.config(command=on_save)
        skip_btn.config(command=on_skip)

        # Bind Enter key globally on the dialog and specifically on the entry
        dialog.bind("<Return>", on_enter_key)

        def update_save_state(*_args):
            if key_entry.cget("state") == "disabled":
                return
            save_btn.config(state="normal" if self.google_api_key.get().strip() else "disabled")

        trace_id = self.google_api_key.trace_add("write", update_save_state)
        update_save_state()

        dialog.protocol("WM_DELETE_WINDOW", on_skip)
        refit_dialog()

        
    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------
    def _apply_theme(self, name):
        """Freeze window painting, apply the whole theme, let Tk finish its
        redraws while frozen, then unfreeze: one clean repaint, no staging."""
        locked = False
        if sys.platform.startswith("win") and self.winfo_viewable():
            try:
                locked = bool(ctypes.windll.user32.LockWindowUpdate(self._hwnd(self)))
            except Exception:
                locked = False
        try:
            self._apply_theme_impl(name)
            self.update_idletasks()
        finally:
            if locked:
                ctypes.windll.user32.LockWindowUpdate(0)

    def _apply_theme_impl(self, name):
        theme = THEMES.get(name, THEMES[DEFAULT_THEME])
        self._current_theme_colors = theme
        self.theme.set(name)
        self.configure(bg=theme["bg"])
        for d in self._active_modal_dialogs:      # e.g. an open Settings dialog
            try:
                if d.winfo_exists():
                    d.configure(bg=theme["dialog_bg"])
            except Exception:
                pass
        self._recolor_upload_background()

        # Update toolbar container and labels dynamically
        if hasattr(self, "title_frame"):
            self.title_frame.config(bg=theme["toolbar_bg"])
            if getattr(self, "toolbar_icon_label", None) is not None:
                self.toolbar_icon_label.config(bg=theme["toolbar_bg"])
            self.brand_label.config(bg=theme["toolbar_bg"], fg=theme["toolbar_fg"])
            self.sub_label.config(
                bg=theme["toolbar_bg"], 
                fg=theme.get("toolbar_sub", theme["toolbar_fg"])
            )
        if hasattr(self, "toolbar"):
            self.toolbar.configure(bg=theme["toolbar_bg"])
            
            # Style Settings Button
            self.settings_btn.configure(
                bg=theme["accent"], fg="#ffffff",
                activebackground=theme["accent_active"],
                activeforeground="#ffffff",
                highlightthickness=0
            )
            
            # Style Issues Button
            if hasattr(self, "issues_btn"):
                self.issues_btn.configure(
                    bg=theme["accent"], fg="#ffffff",
                    activebackground=theme["accent_active"],
                    activeforeground="#ffffff",
                    highlightthickness=0
                )

            # Style How to Use Button
            if hasattr(self, "how_to_use_btn"):
                self.how_to_use_btn.configure(
                    bg=theme["accent2"], fg="#ffffff",
                    activebackground=theme["accent2_active"],
                    activeforeground="#ffffff",
                    highlightthickness=0
                )
        if hasattr(self, "left_canvas"):
            self.left_canvas.configure(bg=theme["bg"])
        if hasattr(self, "footer_bar"):
            self.footer_bar.configure(bg=theme["bg"])
            self.footer_note.configure(bg=theme["bg"], fg=theme["subtle_text"])
        if hasattr(self, "_toggle_redraws"):
            for redraw in self._toggle_redraws:
                redraw()
        if hasattr(self, "canvas"):
            self.canvas.configure(bg=theme["canvas_bg"])
        if hasattr(self, "color_swatch"):
            pass  # swatch color reflects the chosen text color, not the theme

        style = ttk.Style(self)
        if style.theme_use() != "clam":
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass

        style.configure("TFrame", background=theme["bg"])
        style.configure("TLabelframe", background=theme["bg"], bordercolor=theme["accent2"],
                         borderwidth=2)
        style.configure("TLabelframe.Label", background=theme["bg"], foreground=theme["accent2_active"],
                         font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background=theme["bg"], foreground=theme["text"])
        style.configure("Subtle.TLabel", background=theme["bg"], foreground=theme["subtle_text"])
        style.configure("TButton", background=theme["accent"], foreground="#ffffff",
                         padding=6, borderwidth=0, focuscolor=theme["accent"])
        style.map("TButton",
                   background=[("active", theme["accent_active"]), ("disabled", theme["border"])],
                   foreground=[("disabled", theme["subtle_text"])],
                   focuscolor=[("active", theme["accent_active"]), ("disabled", theme["border"])])

        # Dialog-scoped variants: custom dialogs (Settings, API key prompt,
        # Choose color) use their own dialog_bg rather than the main
        # window's bg, so their ttk.Frame/ttk.Label children need their
        # own styles too - otherwise the plain "TFrame"/"TLabel" styles
        # (always tied to the main app's bg) mismatch the dialog's actual
        # background and the theme looks broken/patchy inside it.
        style.configure("Dialog.TFrame", background=theme["dialog_bg"])
        style.configure("Dialog.TLabel", background=theme["dialog_bg"], foreground=theme["text"])
        style.configure("DialogSubtle.TLabel", background=theme["dialog_bg"], foreground=theme["subtle_text"])

        style.configure("TCheckbutton", background=theme["bg"], foreground=theme["text"],
                         focuscolor=theme["bg"])
        style.map(
            "TCheckbutton",
            indicatorbackground=[("selected", theme["accent"]), ("!selected", theme["entry_bg"])],
            indicatorforeground=[("selected", "#ffffff"), ("!selected", theme["entry_bg"])],
        )
        style.configure("TRadiobutton", background=theme["bg"], foreground=theme["text"],
                         focuscolor=theme["bg"])
        style.map(
            "TRadiobutton",
            indicatorbackground=[("selected", theme["accent"]), ("!selected", theme["entry_bg"])],
            indicatorforeground=[("selected", "#ffffff"), ("!selected", theme["entry_bg"])],
        )
        style.configure("TCombobox", fieldbackground=theme["entry_bg"], background=theme["entry_bg"],
                         foreground=theme["text"], arrowcolor=theme["text"])
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", theme["entry_bg"]), ("!readonly", theme["entry_bg"])],
            foreground=[("readonly", theme["text"]), ("!readonly", theme["text"])],
            selectbackground=[("readonly", theme["entry_bg"]), ("!readonly", theme["entry_bg"])],
            selectforeground=[("readonly", theme["text"]), ("!readonly", theme["text"])],
            arrowcolor=[("readonly", theme["text"]), ("!readonly", theme["text"])],
        )
        style.configure("FontEntry.TCombobox", fieldbackground=theme["entry_bg"],
                background=theme["entry_bg"], foreground=theme["text"],
                arrowcolor=theme["text"])
        style.map(
            "FontEntry.TCombobox",
            fieldbackground=[("readonly", theme["entry_bg"]), ("!readonly", theme["entry_bg"])],
            foreground=[("readonly", theme["text"]), ("!readonly", theme["text"])],
            selectbackground=[("!disabled", theme["accent"])],
            selectforeground=[("!disabled", "#ffffff")],
            arrowcolor=[("readonly", theme["text"]), ("!readonly", theme["text"])],
        )
        style.configure("TEntry", fieldbackground=theme["entry_bg"], foreground=theme["text"])
        style.configure("Invalid.TEntry", fieldbackground=theme["invalid_bg"], foreground=theme["text"],
                         bordercolor=theme["invalid_border"])
        style.map("Invalid.TEntry", fieldbackground=[("focus", theme["invalid_bg"])],
                   bordercolor=[("focus", theme["invalid_border"])])
        style.configure("TSpinbox", fieldbackground=theme["entry_bg"], foreground=theme["text"])
        style.configure("TProgressbar", background=theme["accent"], troughcolor=theme["border"])
        style.configure("TSeparator", background=theme["border"])
        style.configure("Horizontal.TScrollbar", background=theme["accent"],
                         troughcolor=theme["bg"], bordercolor=theme["border"])
        style.configure("Vertical.TScrollbar", background=theme["accent"],
                         troughcolor=theme["bg"], bordercolor=theme["border"])

        # The Combobox dropdown list itself is a plain Tk Listbox under the
        # hood, not a ttk-styled widget - color it separately or it stays
        # unreadable regardless of the TCombobox style above.
        self.option_add("*TCombobox*Listbox.background", theme["entry_bg"])
        self.option_add("*TCombobox*Listbox.foreground", theme["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", theme["accent"])
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

        # CSV View grid (ttk.Treeview) - its own colors, since the default
        # theme doesn't touch Treeview. Heading uses accent2 for a splash
        # of color instead of blending into the panel background.
        style.configure("Treeview", background=theme["entry_bg"], fieldbackground=theme["entry_bg"],
                         foreground=theme["text"], rowheight=22, bordercolor=theme["border"])
        style.map("Treeview", background=[("selected", theme["accent"])],
                   foreground=[("selected", "#ffffff")])
        style.configure("Treeview.Heading", background=theme["accent2"], foreground="#ffffff",
                         font=("Segoe UI", 9, "bold"))
        style.map("Treeview.Heading", background=[("active", theme["accent2_active"])])

        if hasattr(self, "view_tabs_bar"):
            self._restyle_view_tabs()
        if hasattr(self, "upload_dropzone"):
            self._draw_upload_dropzone()
        if hasattr(self, "cert_dropzone"):
            self._draw_cert_dropzone()
        if hasattr(self, "chips_inner"):
            self.chips_outer.configure(bg=theme["bg"])
            self.chips_canvas.configure(bg=theme["bg"])
            self.chips_inner.configure(bg=theme["bg"])
            self._refresh_locked_chips_row()
        if hasattr(self, "recent_files_frame"):
            self._refresh_recent_files_list()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------