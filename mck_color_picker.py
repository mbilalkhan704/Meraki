"""Meraki - color picker mixin: the advanced color-choosing dialog -
standard-colors grid, shaded palette, recent colors, and the
"More colors" HSV spectrum flyout with hex/RGB entry. Kept in its own
file since it is one large, mostly self-contained method."""

import sys
import colorsys
import re
import tkinter as tk
from tkinter import ttk
import ctypes
from ctypes import wintypes
from PIL import ImageTk

from mck_constants import (
     PALETTE_HUES,
     PALETTE_SHADE_LIGHTNESS, 
     STANDARD_GRAYS
)
from mck_utils import (
    _hls_hex, 
    _build_sv_square_image,
    _build_hue_strip_image
)


class ColorPickerMixin:
    def _choose_color(self, target="name"):
        if target == "name":
            original_color = self.font_color
            swatch = self.color_swatch
        else:
            original_color = self.cert_id_font_color
            swatch = self.cert_id_color_swatch

        theme = self._current_theme_colors
        state = {"color": original_color, "hue": 0.0, "spectrum_open": False,
                "hover_count": 0, "open_token": None, "close_token": None}

        dialog = tk.Toplevel(self)
        dialog.title("Choose text color")
        dialog.configure(bg=theme["dialog_bg"])
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        self._register_modal_dialog(dialog)
        try:
            self._palette_icon_img = self._make_palette_icon(size=32)
            dialog.iconphoto(False, self._palette_icon_img)
        except Exception:
            pass

        frm = ttk.Frame(dialog, padding=14, style="Dialog.TFrame")
        frm.pack(fill="both", expand=True)

        preview = tk.Label(frm, text="", bg=original_color, width=20, height=2, relief="sunken")
        preview.pack(fill="x", pady=(0, 10))

        def apply_color(hexcode, record=False):
            state["color"] = hexcode
            if target == "name":
                self.font_color = hexcode
            else:
                self.cert_id_font_color = hexcode
            swatch.config(bg=hexcode)
            preview.config(bg=hexcode)
            self._redraw_preview()
            if record:
                self._record_recent_color(hexcode)

        # ---- Standard colors row ----
        ttk.Label(frm, text="Standard Colors", style="DialogSubtle.TLabel").pack(anchor="w")
        std_row = tk.Frame(frm, bg=theme["dialog_bg"])
        std_row.pack(anchor="w", pady=(2, 10))
        self._add_swatch_row(std_row, STANDARD_GRAYS, lambda hc: apply_color(hc, record=True))

        # ---- Palette grid: one column per base hue, shades top(light) to bottom(dark) ----
        ttk.Label(frm, text="Palette", style="DialogSubtle.TLabel").pack(anchor="w")
        grid_frame = tk.Frame(frm, bg=theme["dialog_bg"])
        grid_frame.pack(anchor="w", pady=(2, 10))
        for col, hue in enumerate(PALETTE_HUES):
            col_frame = tk.Frame(grid_frame, bg=theme["dialog_bg"])
            col_frame.grid(row=0, column=col, padx=1)
            for l in PALETTE_SHADE_LIGHTNESS:
                hexcode = _hls_hex(hue, l, 0.65)
                self._add_swatch(col_frame, hexcode,
                                lambda hc=hexcode: apply_color(hc, record=True)).pack(pady=1)

        # ---- Recent colors row ----
        ttk.Label(frm, text="Recent Colors", style="DialogSubtle.TLabel").pack(anchor="w")
        recent_row = tk.Frame(frm, bg=theme["dialog_bg"])
        recent_row.pack(anchor="w", pady=(2, 10))

        def refresh_recent_row():
            for child in recent_row.winfo_children():
                child.destroy()
            if not self.recent_colors:
                tk.Label(recent_row, text="(none yet)", fg=theme["subtle_text"],
                        bg=theme["dialog_bg"], font=("Segoe UI", 8)).pack(side="left")
                return
            self._add_swatch_row(recent_row, list(reversed(self.recent_colors)),
                                lambda hc: apply_color(hc, record=True))

        refresh_recent_row()

        # ---- More colors trigger (last, before OK/Cancel) ----
        more_label = tk.Label(frm, text="More colors \u25be", fg=theme["accent"],
                            bg=theme["dialog_bg"], cursor="hand2", font=("Segoe UI", 9, "underline"))
        more_label.pack(anchor="w", pady=(0, 10))

        # ---- Spectrum flyout: a SEPARATE window, built once, shown/hidden ----
        canvas_size = 180
        strip_w, strip_h = 22, canvas_size

        spectrum_win = tk.Toplevel(dialog)
        spectrum_win.overrideredirect(True)
        spectrum_win.attributes("-topmost", True)
        spectrum_win.configure(bg=theme["dialog_bg"])
        spectrum_win.withdraw()

        spec_frm = tk.Frame(spectrum_win, bg=theme["dialog_bg"], padx=10, pady=10,
                            highlightthickness=1, highlightbackground=theme["border"])
        spec_frm.pack()

        sv_canvas = tk.Canvas(spec_frm, width=canvas_size, height=canvas_size,
                            highlightthickness=1, highlightbackground=theme["border"])
        sv_canvas.grid(row=0, column=0, padx=(0, 8))
        hue_canvas = tk.Canvas(spec_frm, width=strip_w, height=strip_h,
                                highlightthickness=1, highlightbackground=theme["border"])
        hue_canvas.grid(row=0, column=1)

        controls = tk.Frame(spec_frm, bg=theme["dialog_bg"])
        controls.grid(row=1, column=0, columnspan=2, pady=(8, 0), sticky="w")

        hex_var = tk.StringVar()
        r_var, g_var, b_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        guard = {"on": False}

        tk.Label(controls, text="Hex:", bg=theme["dialog_bg"], fg=theme["text"]).grid(row=0, column=0, sticky="w")
        hex_entry = ttk.Entry(controls, textvariable=hex_var, width=9)
        hex_entry.grid(row=0, column=1, padx=(4, 12))
        for i, (lbl, var) in enumerate((("R", r_var), ("G", g_var), ("B", b_var))):
            tk.Label(controls, text=lbl + ":", bg=theme["dialog_bg"], fg=theme["text"]).grid(
                row=0, column=2 + i * 2, sticky="w")
            ttk.Entry(controls, textvariable=var, width=4).grid(row=0, column=3 + i * 2, padx=(2, 8))

        def redraw_sv_square():
            img = _build_sv_square_image(state["hue"], canvas_size)
            sv_canvas._img_ref = ImageTk.PhotoImage(img)
            sv_canvas.delete("bg")
            sv_canvas.create_image(0, 0, anchor="nw", image=sv_canvas._img_ref, tags="bg")
            sv_canvas.tag_lower("bg")

        def redraw_hue_strip():
            img = _build_hue_strip_image(strip_w, strip_h)
            hue_canvas._img_ref = ImageTk.PhotoImage(img)
            hue_canvas.delete("bg")
            hue_canvas.create_image(0, 0, anchor="nw", image=hue_canvas._img_ref, tags="bg")
            hue_canvas.tag_lower("bg")
            y = int(state["hue"] * (strip_h - 1))
            hue_canvas.delete("cursor")
            hue_canvas.create_line(0, y, strip_w, y, fill="#ffffff", width=2, tags="cursor")
            hue_canvas.create_line(0, y, strip_w, y, fill="#000000", width=1, tags="cursor")

        def position_sv_cursor(r, g, b):
            _, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            x = int(s * (canvas_size - 1))
            y = int((1 - v) * (canvas_size - 1))
            sv_canvas.delete("cursor")
            rad = 5
            sv_canvas.create_oval(x - rad, y - rad, x + rad, y + rad, outline="#ffffff", width=2, tags="cursor")
            sv_canvas.create_oval(x - rad, y - rad, x + rad, y + rad, outline="#000000", width=1, tags="cursor")

        def set_from_rgb(r, g, b, update_hue=True):
            guard["on"] = True
            hexcode = "#{:02x}{:02x}{:02x}".format(r, g, b)
            hex_var.set(hexcode)
            r_var.set(str(r)); g_var.set(str(g)); b_var.set(str(b))
            guard["on"] = False
            if update_hue:
                h, _s, _v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
                state["hue"] = h
                redraw_hue_strip()
            redraw_sv_square()
            position_sv_cursor(r, g, b)
            apply_color(hexcode)

        def on_sv_click(event):
            x = max(0, min(canvas_size - 1, event.x))
            y = max(0, min(canvas_size - 1, event.y))
            sat = x / (canvas_size - 1)
            val = 1 - (y / (canvas_size - 1))
            r, g, b = colorsys.hsv_to_rgb(state["hue"], sat, val)
            set_from_rgb(int(r * 255), int(g * 255), int(b * 255), update_hue=False)

        def on_hue_click(event):
            y = max(0, min(strip_h - 1, event.y))
            state["hue"] = y / (strip_h - 1)
            redraw_hue_strip()
            redraw_sv_square()
            hexc = hex_var.get().strip()
            if re.fullmatch(r"#[0-9a-fA-F]{6}", hexc):
                r, g, b = self._hex_to_rgb(hexc)
                _h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
                r2, g2, b2 = colorsys.hsv_to_rgb(state["hue"], s, v)
                set_from_rgb(int(r2 * 255), int(g2 * 255), int(b2 * 255), update_hue=False)

        sv_canvas.bind("<Button-1>", on_sv_click)
        sv_canvas.bind("<B1-Motion>", on_sv_click)
        hue_canvas.bind("<Button-1>", on_hue_click)
        hue_canvas.bind("<B1-Motion>", on_hue_click)

        def on_hex_entered(_event=None):
            if guard["on"]:
                return
            text = hex_var.get().strip()
            if not text.startswith("#"):
                text = "#" + text
            if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
                r, g, b = self._hex_to_rgb(text)
                set_from_rgb(r, g, b)

        def on_rgb_entered(_event=None):
            if guard["on"]:
                return
            try:
                r = max(0, min(255, int(r_var.get())))
                g = max(0, min(255, int(g_var.get())))
                b = max(0, min(255, int(b_var.get())))
            except ValueError:
                return
            set_from_rgb(r, g, b)

        hex_entry.bind("<Return>", on_hex_entered)
        hex_entry.bind("<FocusOut>", on_hex_entered)
        rgb_entries = [w for w in controls.winfo_children() if isinstance(w, ttk.Entry)][1:]
        for e in rgb_entries:
            e.bind("<Return>", on_rgb_entered)
            e.bind("<FocusOut>", on_rgb_entered)

        # ---- hover open/close via pointer-position polling, NOT Enter/Leave
        # crossing events. Binding <Enter>/<Leave> on a container fires on
        # every crossing into a CHILD widget too (Tk quirk) - so using the
        # spectrum (clicking the canvas, typing in an entry) would spuriously
        # "leave" spec_frm and close the panel mid-use. Polling raw pointer
        # coordinates against each widget's actual on-screen bounding box
        # avoids that entirely.
        #
        # Grab handling is the fragile part here: spectrum_win is a
        # SEPARATE top-level window from dialog, so while dialog holds a
        # local grab, clicks on spectrum_win would be swallowed unless the
        # grab is handed over to it while it's open, then handed back.
        # If anything throws while spectrum_win holds that grab, it gets
        # stuck there forever and EVERY button in the app (including this
        # dialog's own OK/Cancel) stops responding - which is exactly what
        # happened. So every grab operation below is wrapped defensively,
        # and close_spectrum() always tries to restore dialog's grab
        # regardless of what state things were left in.
        def _safe_grab_release(widget):
            try:
                widget.grab_release()
            except Exception:
                pass

        def _safe_grab_set(widget):
            try:
                widget.grab_set()
            except Exception:
                pass

        def _work_area():
            """Usable screen rectangle (excludes the taskbar on Windows)."""
            if sys.platform.startswith("win"):
                try:
                    rect = wintypes.RECT()
                    if ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
                        return rect.left, rect.top, rect.right, rect.bottom
                except Exception:
                    pass
            return 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()

        def position_spectrum():
            dialog.update_idletasks()
            spec_frm.update_idletasks()
            panel_w = spectrum_win.winfo_reqwidth()
            panel_h = spectrum_win.winfo_reqheight()
            left, top, right, bottom = _work_area()
            gap, margin = 6, 6

            x = dialog.winfo_rootx() + dialog.winfo_width() + gap
            if x + panel_w > right - margin:                      # no room on the right -> flip left
                x = dialog.winfo_rootx() - panel_w - gap
            x = max(left + margin, min(right - panel_w - margin, x))

            label_mid = more_label.winfo_rooty() + more_label.winfo_height() // 2
            y = label_mid - panel_h // 2                          # start centered on the label...
            y = max(top + margin, min(bottom - panel_h - margin, y))   # ...then slide to stay fully visible
            spectrum_win.geometry(f"{panel_w}x{panel_h}+{x}+{y}")

        def open_spectrum():
            if state["spectrum_open"] or not dialog.winfo_exists():
                return
            state["spectrum_open"] = True
            if state["color"]:
                r, g, b = self._hex_to_rgb(state["color"])
                h, _s, _v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
                state["hue"] = h
                redraw_hue_strip()
                set_from_rgb(r, g, b, update_hue=False)
            position_spectrum()
            spectrum_win.deiconify()
            spectrum_win.lift()
            _safe_grab_release(dialog)
            _safe_grab_set(spectrum_win)
            try:
                spectrum_win.focus_force()
            except Exception:
                pass

        def close_spectrum():
            if not state["spectrum_open"]:
                return
            state["spectrum_open"] = False
            _safe_grab_release(spectrum_win)
            if spectrum_win.winfo_exists():
                spectrum_win.withdraw()
            if dialog.winfo_exists():
                _safe_grab_set(dialog)

        dialog._on_attention = close_spectrum

        def on_click(_event=None):
            if state["spectrum_open"]:
                close_spectrum()
            else:
                open_spectrum()

        def on_spectrum_click(event):
            """Runs for every click in the app while the flyout holds the grab.
            Clicks on the flyout's own controls have coordinates inside its bounds
            and are ignored; anything else closes it."""
            if not state["spectrum_open"] or not spectrum_win.winfo_exists():
                return
            wx, wy = spectrum_win.winfo_rootx(), spectrum_win.winfo_rooty()
            inside = (wx <= event.x_root < wx + spectrum_win.winfo_width() and
                    wy <= event.y_root < wy + spectrum_win.winfo_height())
            if not inside:
                close_spectrum()

        more_label.bind("<Button-1>", on_click)
        spectrum_win.bind("<Button-1>", on_spectrum_click, add="+")
        spectrum_win.bind("<Escape>", lambda e: close_spectrum())

        # Minimizing the main window doesn't automatically hide an
        # overrideredirect + topmost Toplevel on Windows - it would stay
        # floating on screen. Explicitly withdraw this dialog and the
        # spectrum flyout when the app is minimized, and bring the
        # dialog back when restored.
        def _on_root_unmap(event):
            if event.widget is self and dialog.winfo_exists():
                close_spectrum()
                dialog.withdraw()

        def _on_root_map(event):
            if event.widget is self and dialog.winfo_exists() and str(dialog.state()) == "withdrawn":
                dialog.deiconify()

        unmap_id = self.bind("<Unmap>", _on_root_unmap, add="+")
        map_id = self.bind("<Map>", _on_root_map, add="+")

        # ---- OK / Cancel ----
        def on_ok():
            close_spectrum()
            self._record_recent_color(state["color"])
            dialog.destroy()

        def on_cancel():
            close_spectrum()
            apply_color(original_color)
            dialog.destroy()

        btn_row = ttk.Frame(frm, style="Dialog.TFrame")
        btn_row.pack(fill="x", pady=(4, 0))
        ttk.Button(btn_row, text="OK", command=on_ok).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Cancel", command=on_cancel).pack(side="left", padx=6)

        def on_dialog_destroy(event=None):
            if event is not None and event.widget is not dialog:
                return
            if state.get("poll_token") is not None:
                try:
                    dialog.after_cancel(state["poll_token"])
                except Exception:
                    pass
            # Unbind the two root-level handlers this dialog added, or
            # they'd keep firing (harmlessly, but pointlessly) against a
            # destroyed dialog, and stack up further on every future
            # "Choose color" click.
            try:
                self.unbind("<Unmap>", unmap_id)
            except Exception:
                pass
            try:
                self.unbind("<Map>", map_id)
            except Exception:
                pass
            _safe_grab_release(spectrum_win)
            if spectrum_win.winfo_exists():
                spectrum_win.destroy()

        dialog.bind("<Destroy>", on_dialog_destroy, add="+")
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)

        dialog.update_idletasks()
        w, h = dialog.winfo_reqwidth(), dialog.winfo_reqheight()
        left, top, right, bottom = _work_area()      # helper added in the previous step
        gap, margin = 8, 6

        # The button that opened this dialog (falls back to the color swatch if missing).
        anchor = getattr(self, "color_choose_btn" if target == "name"
                        else "cert_id_color_choose_btn", None) or swatch
        ax, ay = anchor.winfo_rootx(), anchor.winfo_rooty()
        aw, ah = anchor.winfo_width(), anchor.winfo_height()

        x = ax + aw + gap                              # immediately right of the button
        if x + w > right - margin:                     # no room on the right -> flip to the left
            x = ax - w - gap
        x = max(left + margin, min(right - w - margin, x))

        y = ay + ah // 2 - h // 2                      # centered on the button...
        y = max(top + margin, min(bottom - h - margin, y))   # ...but kept fully on screen

        dialog.geometry(f"{w}x{h}+{x}+{y}")