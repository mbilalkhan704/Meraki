"""Meraki - upload screen mixin: the "Upload Source File" gate screen
(recent files + drag-and-drop dropzone + animated background), and the
Certificate View / Source File View tab-switching machinery."""

import os
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from mck_dnd import (
    DND_FILES,
    DND_AVAILABLE as _DND_AVAILABLE
)


class UploadScreenMixin:
    def _build_upload_screen(self):
        theme = self._current_theme_colors
        frame = ttk.Frame(self, padding=40)

        # Ambient animated background - a slow-rotating mathematical "rose
        # curve" (a genuine flower shape from polar equation r=cos(k*theta)).
        # Created FIRST so it stacks behind everything else placed after it
        # in this same parent. Drawn faint/thin so it never competes with
        # the actual controls on top of it, and the animation loop stops
        # itself automatically once this screen is no longer visible (see
        # _animate_upload_background).
        self.upload_bg_canvas = tk.Canvas(frame, highlightthickness=0, bg=theme["bg"])
        self.upload_bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._upload_bg_frame_i = 0
        self._animate_upload_background()

        content = ttk.Frame(frame)
        content.place(relx=0.5, rely=0.5, anchor="center")

        # ---- Centered heading, above both columns ----
        ttk.Label(content, text="Get started", font=("Segoe UI", 20, "bold")).pack(pady=(0, 6))
        ttk.Label(content, text="Upload the source file you want to generate certificates "
                                "from (CSV or Excel).",
                  style="Subtle.TLabel", wraplength=560, justify="center").pack(pady=(0, 22))

        columns = ttk.Frame(content)
        columns.pack()

        # ---- Left half: recently used source files ----
        left_half = ttk.Frame(columns, width=260)
        left_half.pack(side="left", fill="y", padx=(0, 30))
        left_half.pack_propagate(False)
        ttk.Label(left_half, text="Recent files", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(left_half, text="Pick up where you left off.",
                  style="Subtle.TLabel").pack(anchor="w", pady=(0, 12))
        self.recent_files_frame = ttk.Frame(left_half)
        self.recent_files_frame.pack(fill="both", expand=True)
        self._refresh_recent_files_list()

        ttk.Separator(columns, orient="vertical").pack(side="left", fill="y")

        # ---- Right half: drag-and-drop / browse ----
        right_half = ttk.Frame(columns, padding=(30, 0, 0, 0))
        right_half.pack(side="left")

        self.upload_dropzone = tk.Canvas(right_half, width=460, height=220,
                                          highlightthickness=0, bg=theme["panel_bg"])
        self.upload_dropzone.pack()
        self.upload_dropzone.bind("<Button-1>", lambda e: self._browse_source_file_from_upload_screen())
        self.upload_dropzone.bind("<Configure>", lambda e: self._draw_upload_dropzone())

        ttk.Button(right_half, text="Browse for source file...",
                   command=self._browse_source_file_from_upload_screen).pack(pady=(20, 0))

        self.upload_screen_status = ttk.Label(right_half, text="", style="Subtle.TLabel",
                                               wraplength=440, justify="center")
        self.upload_screen_status.pack(pady=(10, 0))

        self._draw_upload_dropzone()
        self._setup_upload_screen_drag_and_drop()
        return frame

    def _recolor_upload_background(self):
        canvas = getattr(self, "upload_bg_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        theme = self._current_theme_colors
        canvas.configure(bg=theme["bg"])
        for i, item in enumerate(getattr(self, "_bg_line_ids", None) or []):
            canvas.itemconfigure(item, fill=theme["accent2"] if (i // 20) % 2 == 0 else theme["accent"])

    def _animate_upload_background(self):
        canvas = getattr(self, "upload_bg_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        if hasattr(self, "upload_screen_frame") and not self.upload_screen_frame.winfo_ismapped():
            return

        w = max(canvas.winfo_width(), 900)
        h = max(canvas.winfo_height(), 600)
        cx, cy = w / 2, h / 2
        t = self._upload_bg_frame_i
        k, steps = 5, 240
        scale = min(w, h) * 0.42

        pts = []
        for i in range(steps + 1):
            theta = (i / steps) * 2 * math.pi + t * 0.002
            r = scale * math.cos(k * theta)
            pts.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))

        if getattr(self, "_bg_line_ids", None) is None:
            self._bg_line_ids = [
                canvas.create_line(*pts[i], *pts[i + 1], width=1, stipple="gray25", tags="bgart")
                for i in range(steps)]
            canvas.tag_lower("bgart")
            self._recolor_upload_background()
        else:
            for i, item in enumerate(self._bg_line_ids):
                canvas.coords(item, *pts[i], *pts[i + 1])

        self._upload_bg_frame_i += 1
        self._upload_bg_anim_id = self.after(50, self._animate_upload_background)

    def _refresh_recent_files_list(self):
        if not hasattr(self, "recent_files_frame"):
            return
        for w in self.recent_files_frame.winfo_children():
            w.destroy()
        theme = self._current_theme_colors
        if not self.recent_files:
            ttk.Label(self.recent_files_frame, text="No recent files yet.",
                      style="Subtle.TLabel", wraplength=240, justify="left").pack(anchor="w")
            return
        # Newest first for display, same convention as the recent colors row.
        for path in reversed(self.recent_files):
            row = tk.Frame(self.recent_files_frame, bg=theme["tab_inactive_bg"],
                            highlightthickness=1, highlightbackground=theme["tab_border"],
                            cursor="hand2")
            row.pack(fill="x", pady=3)
            name_lbl = tk.Label(row, text=os.path.basename(path), bg=theme["tab_inactive_bg"],
                                 fg=theme["text"], font=("Segoe UI", 9, "bold"), anchor="w",
                                 padx=8)
            name_lbl.pack(fill="x", pady=(5, 0))
            dir_lbl = tk.Label(row, text=os.path.dirname(path), bg=theme["tab_inactive_bg"],
                                fg=theme["subtle_text"], font=("Segoe UI", 7), anchor="w", padx=8)
            dir_lbl.pack(fill="x", pady=(0, 5))
            for widget in (row, name_lbl, dir_lbl):
                widget.bind("<Button-1>", lambda e, p=path: self._open_recent_file(p))

    def _open_recent_file(self, path):
        if not os.path.isfile(path):
            messagebox.showerror(
                "File not found",
                f"'{path}' no longer exists, so it's being removed from your recent files.")
            self.recent_files = [p for p in self.recent_files if p != path]
            self._save_settings()
            self._refresh_recent_files_list()
            return
        self._handle_upload_screen_file(path)

    def _draw_upload_dropzone(self):
        if not hasattr(self, "upload_dropzone") or not self.upload_dropzone.winfo_exists():
            return
        theme = self._current_theme_colors
        c = self.upload_dropzone
        c.configure(bg=theme["panel_bg"], cursor="hand2")
        c.delete("all")
        w = max(c.winfo_width(), 460)
        h = max(c.winfo_height(), 220)
        c.create_rectangle(6, 6, w - 6, h - 6, outline=theme["border"], width=2, dash=(6, 4))
        c.create_text(w / 2, h / 2 - 14, text="Drag & drop your source file here",
                       fill=theme["text"], font=("Segoe UI", 12, "bold"))
        c.create_text(w / 2, h / 2 + 14, text="or click / use the button below to browse",
                       fill=theme["subtle_text"], font=("Segoe UI", 9))

    def _setup_upload_screen_drag_and_drop(self):
        """Register the drop-zone canvas with tkinterdnd2. If the package
        isn't installed (_DND_AVAILABLE is False), this degrades to
        browse-only - nothing here should ever crash the app."""
        if not hasattr(self, "upload_dropzone") or not _DND_AVAILABLE:
            return
        try:
            self.update_idletasks()
            self.upload_dropzone.drop_target_register(DND_FILES)
            self.upload_dropzone.dnd_bind("<<Drop>>", self._on_upload_screen_drop)
        except Exception:
            pass

    def _on_upload_screen_drop(self, event):
        # event.data is a Tcl-list-formatted string (paths with spaces are
        # wrapped in {braces}) - self.tk.splitlist parses that correctly,
        # which naive string splitting on spaces would not.
        try:
            paths = self.tk.splitlist(event.data)
        except Exception:
            paths = [event.data] if event.data else []
        if not paths:
            return
        self._handle_upload_screen_file(paths[0])

    def _browse_source_file_from_upload_screen(self):
        path = filedialog.askopenfilename(
            title="Choose a source file (CSV or Excel)",
            filetypes=[
                ("CSV or Excel files", "*.csv *.xlsx *.xlsm"),
                ("CSV files", "*.csv"),
                ("Excel files", "*.xlsx *.xlsm"),
            ],
        )
        if not path:
            return
        self._handle_upload_screen_file(path)

    def _handle_upload_screen_file(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".csv", ".xlsx", ".xlsm"):
            self.upload_screen_status.config(
                text=f"'{os.path.basename(path)}' isn't a CSV or Excel file - "
                     f"please choose a .csv, .xlsx or .xlsm file.")
            return
        self.upload_screen_status.config(text="")
        if self._load_source_file(path):
            self._reveal_main_ui()
        # on failure, _load_source_file already showed an error dialog -
        # the user stays on the upload screen to try again.

    def _reveal_main_ui(self):
        if hasattr(self, "upload_screen_frame") and self.upload_screen_frame.winfo_exists():
            self.upload_screen_frame.pack_forget()
        self.main_root_frame.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # View tabs: switch the preview area between the Source File grid
    # and the certificate canvas, without altering either view's own
    # behavior. A tab only exists once its underlying data exists - the
    # Certificate View tab in particular must not appear at all until an
    # image has actually been uploaded.
    # ------------------------------------------------------------------
    def _build_view_tabs(self):
        for w in self.view_tabs_bar.winfo_children():
            w.destroy()
        self._view_tab_buttons = {}

        def make_tab(key, label):
            # highlightthickness/highlightbackground give the tab a real,
            # always-visible outline (not just a focus ring) so it reads
            # as a button even when inactive, instead of blending into
            # the surrounding background like plain text. takefocus=0
            # stops a click from ever assigning keyboard focus to it, so
            # no separate OS/Tk focus-ring artifact can appear on top of
            # our own intentional outline.
            btn = tk.Label(self.view_tabs_bar, text=label, padx=14, pady=6,
                            font=("Segoe UI", 9, "bold"), cursor="hand2",
                            bd=0, highlightthickness=2, takefocus=0)
            btn.pack(side="left", padx=(0, 6))
            btn.bind("<Button-1>", lambda e, k=key: self._show_view(k))
            self._view_tab_buttons[key] = btn

        # Source file is uploaded first in the workflow, so its tab sits
        # on the left; Certificate View only appears once it has data.
        if self.csv_rows:
            make_tab("csv", "Source File View")
        if self.cert_image is not None:
            make_tab("certificate", "Certificate View")

        # A thin colored bar that slides beneath the active tab on switch,
        # rather than the active state just snapping between buttons.
        theme = self._current_theme_colors
        self.view_tabs_underline = tk.Frame(self.view_tabs_bar, height=3, bg=theme["accent"])

        self._restyle_view_tabs()
        self.after(20, lambda: self._move_tab_underline(animate=False))

    def _restyle_view_tabs(self):
        theme = self._current_theme_colors
        if not hasattr(self, "_view_tab_buttons"):
            return
        for key, btn in self._view_tab_buttons.items():
            if not btn.winfo_exists():
                continue
            if key == self.current_view:
                btn.configure(bg=theme["accent"], fg="#ffffff",
                               highlightbackground=theme["accent_active"],
                               highlightcolor=theme["accent_active"])
            else:
                btn.configure(bg=theme["tab_inactive_bg"], fg=theme["text"],
                               highlightbackground=theme["tab_border"],
                               highlightcolor=theme["tab_border"])
        self.view_tabs_bar.configure(bg=theme["bg"])
        if hasattr(self, "view_tabs_underline") and self.view_tabs_underline.winfo_exists():
            self.view_tabs_underline.configure(bg=theme["accent"])

    def _move_tab_underline(self, animate=True):
        underline = getattr(self, "view_tabs_underline", None)
        if underline is None or not underline.winfo_exists():
            return
        btn = self._view_tab_buttons.get(self.current_view)
        if btn is None or not btn.winfo_exists():
            underline.place_forget()
            return
        target_x = btn.winfo_x()
        target_w = btn.winfo_width()
        target_y = btn.winfo_height() + 2
        if target_w <= 1:
            # Geometry not laid out yet on this pass - try again shortly.
            self.after(20, lambda: self._move_tab_underline(animate))
            return

        if not animate or not underline.winfo_ismapped():
            underline.place(x=target_x, y=target_y, width=target_w, height=3)
            return

        start_x = underline.winfo_x()
        start_w = underline.winfo_width()
        steps = 8

        def step(i):
            if not underline.winfo_exists():
                return
            frac = i / steps
            x = start_x + (target_x - start_x) * frac
            width = start_w + (target_w - start_w) * frac
            underline.place(x=x, y=target_y, width=max(1, width), height=3)
            if i < steps:
                self._tab_underline_anim_id = self.after(15, lambda: step(i + 1))

        step(1)

    def _show_view(self, key):
        if key == "csv" and not self.csv_rows:
            return
        if key == "certificate" and self.cert_image is None:
            return
        self.current_view = key
        if key == "certificate":
            self.csv_view_frame.pack_forget()
            self.cert_view_frame.pack(fill="both", expand=True)
        else:
            self.cert_view_frame.pack_forget()
            self.csv_view_frame.pack(fill="both", expand=True)
        self._restyle_view_tabs()
        self._move_tab_underline(animate=True)

    # ------------------------------------------------------------------
    # CSV view: an Excel-like grid of the uploaded file, plus controls
    # for choosing which rows to actually process on "Generate".
    # ------------------------------------------------------------------
