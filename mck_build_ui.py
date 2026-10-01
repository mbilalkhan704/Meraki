"""Meraki - build_ui mixin: constructs the entire main window - toolbar,
footer, scrollable left panel (all 5 numbered sections), and the
Certificate View / Source File View tab container. One large method,
kept in its own file since splitting it further would cut through a
single continuous widget-construction sequence."""

import os
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from PIL import Image, ImageTk # type: ignore

from mck_constants import (
    APP_ICON_PNG,
    APP_CREDIT_TEXT,
    CERT_ID_MIN_LENGTH,
    CERT_ID_MAX_LENGTH
)
from mck_dnd import (
    DND_FILES,
    DND_AVAILABLE as _DND_AVAILABLE
)


class BuildUiMixin:
    def _build_ui(self):
        theme = self._current_theme_colors

        # ---- top toolbar --------------------------------------------
        self.toolbar = tk.Frame(self, bg=theme["toolbar_bg"], height=52)
        self.toolbar.pack(side="top", fill="x")

        # Create container frame for title
        self.title_frame = tk.Frame(self.toolbar, bg=theme["toolbar_bg"])
        self.title_frame.pack(side="left", padx=18, pady=10)

        # App icon, shown before the brand name
        self.toolbar_icon_label = None
        if os.path.isfile(APP_ICON_PNG):
            try:
                icon_src = Image.open(APP_ICON_PNG).convert("RGBA")
                icon_size = 65  # matches the toolbar's visual height comfortably
                ratio = min(icon_size / icon_src.width, icon_size / icon_src.height, 1.0)
                size = (max(1, int(icon_src.width * ratio)), max(1, int(icon_src.height * ratio)))
                icon_src = icon_src.resize(size, Image.LANCZOS)
                # Kept on self - a local variable here would be garbage-collected
                # and the icon would vanish right after this function returns.
                self._toolbar_icon_img = ImageTk.PhotoImage(icon_src)
                self.toolbar_icon_label = tk.Label(
                    self.title_frame,
                    image=self._toolbar_icon_img,
                    bg=theme["toolbar_bg"],
                )
                self.toolbar_icon_label.pack(side="left", padx=(0, 8))
            except Exception:
                self.toolbar_icon_label = None

        # Main brand label
        self.brand_label = tk.Label(
            self.title_frame,
            text="MERAKI",
            bg=theme["toolbar_bg"],
            fg=theme["toolbar_fg"],
            font=("Segoe UI Black", 16)
        )
        self.brand_label.pack(side="left")

        # Subtitle label
        self.sub_label = tk.Label(
            self.title_frame,
            text=" │ Where Data Becomes Recognition.",
            bg=theme["toolbar_bg"],
            fg=theme.get("toolbar_sub", theme["toolbar_fg"]),
            font=("Segoe UI Semibold", 10)
        )
        self.sub_label.pack(side="left", padx=(4, 0), pady=(2, 0))

        # ---- top toolbar right actions ------------------------------
        
        # 1. Settings Button (packed far right)
        self.settings_btn = tk.Button(self.toolbar, text="\u2699 Settings", relief="flat",
                                       bd=0, padx=16, pady=8, cursor="hand2",
                                       font=("Segoe UI", 11, "bold"),
                                       command=self._open_settings_dialog)
        self.settings_btn.pack(side="right", padx=18, pady=10)

        # 2. Issues Button (packed next to Settings)
        self.issues_btn = tk.Button(
            self.toolbar, 
            text="\u2753 Help", 
            relief="flat",
            bd=0, padx=14, pady=6, cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            command=self._open_github_issues
        )
        self.issues_btn.pack(side="right", padx=(0, 4), pady=10)

        # 3. How to Use Button (packed next to Help)
        self.how_to_use_btn = tk.Button(
            self.toolbar,
            text="\U0001F4D6 How to Use",
            relief="flat",
            bd=0, padx=14, pady=6, cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            command=self._open_how_to_use_dialog
        )
        self.how_to_use_btn.pack(side="right", padx=(0, 4), pady=10)

        # Settings Button


        # ---- bottom credit footer (app UI only - never drawn on certificates) ----
        self.footer_bar = tk.Frame(self, height=26)
        self.footer_bar.pack(side="bottom", fill="x")
        self.footer_note = tk.Label(
            self.footer_bar, 
            text=APP_CREDIT_TEXT,
            font=("Segoe UI", 12, "italic")
        )
        self.footer_note.pack(side="right", padx=14, pady=4)

        self.main_root_frame = ttk.Frame(self, padding=10)
        root = self.main_root_frame
        # Not packed yet - the Upload Source File screen occupies this
        # space first; _reveal_main_ui() packs this in once a source
        # file has been loaded.

        # ---- scrollable left panel ------------------------------------
        left_container = ttk.Frame(root, width=400)
        left_container.pack(side="left", fill="y", padx=(0, 10))
        left_container.pack_propagate(False)

        self.left_canvas = tk.Canvas(left_container, highlightthickness=0, bd=0)
        left_scrollbar = ttk.Scrollbar(left_container, orient="vertical",
                                        command=self.left_canvas.yview)
        scroll_frame = ttk.Frame(self.left_canvas)
        scroll_frame.bind("<Configure>",
                           lambda e: self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all")))
        self._left_window = self.left_canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        self.left_canvas.bind("<Configure>",
                               lambda e: self.left_canvas.itemconfig(self._left_window, width=e.width))
        self.left_canvas.configure(yscrollcommand=left_scrollbar.set)
        self.left_canvas.pack(side="left", fill="both", expand=True)
        left_scrollbar.pack(side="right", fill="y")

        # Permanent, geometry-based scroll handling: bound once, forever,
        # rather than toggled on <Enter>/<Leave> of the canvas. The old
        # toggle scheme broke down whenever a transient overlapping
        # window (e.g. the font autocomplete popup) caused a stray Leave
        # on left_canvas - scrolling would then stay disabled until the
        # mouse did a perfectly clean re-entry. This version just checks
        # "is the pointer currently over the left panel?" on every wheel
        # event, so it can never get stuck in a bad state.
        if not getattr(self, "_left_panel_wheel_bound", False):
            self.bind_all("<MouseWheel>", self._on_left_panel_mousewheel, add="+")
            self.bind_all("<Button-4>", self._on_left_panel_mousewheel, add="+")
            self.bind_all("<Button-5>", self._on_left_panel_mousewheel, add="+")
            self._left_panel_wheel_bound = True

        left = scroll_frame

        right = ttk.Frame(root)
        right.pack(side="left", fill="both", expand=True)

        # ---- 1. Source file -----------------------------------------------
        box = self._section(left, "1. Source file")
        ttk.Button(box, text="Change source file...", command=self._upload_data_file).pack(fill="x")
        self.csv_label = ttk.Label(box, text="No file selected", style="Subtle.TLabel")
        self.csv_label.pack(fill="x", pady=(4, 8))

        ttk.Label(box, text="Column to use as the name:").pack(anchor="w")
        self.name_combo = ttk.Combobox(box, textvariable=self.name_col, state="readonly")
        self.name_combo.pack(fill="x", pady=(2, 0))
        self.name_combo.bind("<<ComboboxSelected>>", lambda e: self._redraw_preview())

        # ---- 2. Certificate image ---------------------------------------
        box = self._section(left, "2. Certificate template")

        self.cert_dropzone = tk.Canvas(box, height=90, highlightthickness=0)
        self.cert_dropzone.pack(fill="x", pady=(0, 8))
        self.cert_dropzone.bind("<Button-1>", lambda e: self._upload_image())
        self.cert_dropzone.bind("<Configure>", lambda e: self._draw_cert_dropzone())

        self.cert_upload_btn = ttk.Button(box, text="Upload certificate image...",
                                           command=self._upload_image)
        self.cert_upload_btn.pack(fill="x")

        pill_row = ttk.Frame(box)
        pill_row.pack(fill="x", pady=(6, 0))
        self.recent_cert_pill = self._make_pill_button(
            pill_row, "Select from recent files", self._toggle_recent_cert_popup)
        self.recent_cert_pill.pack(side="right")

        self.img_label = ttk.Label(box, text="No image selected", style="Subtle.TLabel")
        self.img_label.pack(fill="x", pady=(8, 0))

        self._draw_cert_dropzone()
        if _DND_AVAILABLE:
            try:
                self.cert_dropzone.drop_target_register(DND_FILES)
                self.cert_dropzone.dnd_bind("<<Drop>>", self._on_cert_image_drop)
            except Exception:
                pass

        # ---- 3. Name (position, font, style) -----------------------------
        box = self._section(left, "3. Name")

        pos_sub = self._subsection(box, "Position (pixels, on the original image)")
        row = ttk.Frame(pos_sub)
        row.pack(fill="x")
        ttk.Label(row, text="X:").pack(side="left")
        x_spin = ttk.Spinbox(row, from_=0, to=20000, textvariable=self.pos_x, width=8,
                              command=self._redraw_preview)
        x_spin.pack(side="left", padx=(4, 14))
        ttk.Label(row, text="Y:").pack(side="left")
        y_spin = ttk.Spinbox(row, from_=0, to=20000, textvariable=self.pos_y, width=8,
                              command=self._redraw_preview)
        y_spin.pack(side="left", padx=(4, 0))
        for w in (x_spin, y_spin):
            w.bind("<KeyRelease>", lambda e: self._redraw_preview())

        center_row = ttk.Frame(pos_sub)
        center_row.pack(fill="x", pady=(6, 0))
        self._make_toggle(center_row, "Center X", self.center_name_x,
                           on_toggle=lambda: self._toggle_center("name", "x")).pack(side="left")
        self._make_toggle(center_row, "Center Y", self.center_name_y,
                           on_toggle=lambda: self._toggle_center("name", "y")).pack(side="left", padx=(20, 0))

        ttk.Label(pos_sub, text="Tip: click and drag directly on the preview \u2192",
                  style="Subtle.TLabel").pack(anchor="w", pady=(6, 0))

        font_sub = self._subsection(box, "Font")
        ttk.Label(font_sub, text="Type to search:").pack(anchor="w")
        self.font_combo = ttk.Combobox(font_sub, textvariable=self.font_choice, style="FontEntry.TCombobox")
        self.font_combo.pack(fill="x", pady=(2, 0))

        spinner_row = ttk.Frame(font_sub)
        spinner_row.pack(fill="x", pady=(2, 2))
        self.font_status = ttk.Label(spinner_row, text="", style="Subtle.TLabel",
                                      wraplength=300, justify="left")
        self.font_status.pack(side="left")
        self.font_spinner = ttk.Progressbar(spinner_row, mode="indeterminate", length=90)
        # only packed while a fetch is in progress

        self._register_font_picker("name", self.font_choice, self.font_combo,
                                    self.font_status, self.font_spinner)

        self.catalog_status = ttk.Label(font_sub, text="", style="Subtle.TLabel",
                                         wraplength=320, justify="left")
        self.catalog_status.pack(anchor="w", pady=(4, 0))

        style_sub = self._subsection(box, "Style")
        bold_font = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        italic_font = tkfont.Font(family="Segoe UI", size=10, slant="italic")
        underline_font = tkfont.Font(family="Segoe UI", size=10, underline=1)

        style_row = ttk.Frame(style_sub)
        style_row.pack(fill="x", pady=(0, 8))
        self._make_toggle(style_row, "B", self.bold_var, bold_font).pack(side="left")
        self._make_toggle(style_row, "I", self.italic_var, italic_font).pack(side="left", padx=(10, 0))
        self._make_toggle(style_row, "U", self.underline_var, underline_font).pack(side="left", padx=(10, 0))

        row = ttk.Frame(style_sub)
        row.pack(fill="x", pady=(0, 8))
        ttk.Label(row, text="Size:").pack(side="left")
        size_spin = ttk.Spinbox(row, from_=6, to=1000, textvariable=self.font_size, width=6,
                                 command=self._redraw_preview)
        size_spin.pack(side="left", padx=(4, 14))
        size_spin.bind("<KeyRelease>", lambda e: self._redraw_preview())

        ttk.Label(row, text="Color:").pack(side="left")
        self.color_swatch = tk.Label(row, text="  ", bg=self.font_color, relief="sunken", width=3)
        self.color_swatch.pack(side="left", padx=(4, 4))
        choose_btn = ttk.Button(row, text="Choose...",command=lambda: self._choose_color("name"))
        choose_btn.pack(side="left")
        self.color_choose_btn = choose_btn

        row2 = ttk.Frame(style_sub)
        row2.pack(fill="x")
        ttk.Label(row2, text="Alignment:").pack(side="left")
        for val, label in (("left", "Left"), ("center", "Center"), ("right", "Right")):
            ttk.Radiobutton(row2, text=label, value=val, variable=self.align_var,
                             command=self._redraw_preview).pack(side="left", padx=4)

        row3 = ttk.Frame(style_sub)
        row3.pack(fill="x", pady=(8, 0))
        ttk.Label(row3, text="Casing:").pack(side="left")
        casing_combo = ttk.Combobox(
            row3, textvariable=self.name_casing, state="readonly", width=14,
            values=["As in file", "UPPERCASE", "lowercase", "Title Case",
                    "Sentence case", "tOGGLE cASE"])
        casing_combo.pack(side="left", padx=(6, 0))
        casing_combo.bind("<<ComboboxSelected>>", lambda e: self._redraw_preview())

        # ---- 4. Certificate ID -------------------------------------------
        box = self._section(left, "4. Certificate ID")
        ttk.Label(box, wraplength=360, justify="left", style="Subtle.TLabel",
                  text="A unique Certificate ID is always generated for every row and "
                       "saved into the data file and filename. Putting it on the "
                       "certificate image itself is optional.").pack(anchor="w", pady=(0, 8))

        self._make_toggle(box, "Add Certificate ID to the certificate image",
                           self.cert_id_enabled, on_toggle=self._update_cert_id_controls_state
                           ).pack(anchor="w", pady=(0, 10))

        length_sub = self._subsection(box, "Length & Characters")
        length_row = ttk.Frame(length_sub)
        length_row.pack(fill="x", pady=(0, 8))
        ttk.Label(length_row, text=f"Length ({CERT_ID_MIN_LENGTH}-{CERT_ID_MAX_LENGTH}):").pack(side="left")
        length_spin = ttk.Spinbox(length_row, from_=CERT_ID_MIN_LENGTH, to=CERT_ID_MAX_LENGTH,
                           textvariable=self.cert_id_length, width=6,
                           command=self._on_cert_id_format_changed)
        length_spin.pack(side="left", padx=(4, 0))
        length_spin.bind("<KeyRelease>", self._on_cert_id_format_changed)

        charset_row = ttk.Frame(length_sub)
        charset_row.pack(fill="x", pady=(0, 8))
        ttk.Label(charset_row, text="Characters:").pack(side="left", padx=(0, 8))
        charset_vars = [self.cert_id_use_digits, self.cert_id_use_upper, self.cert_id_use_lower]
        self._make_exclusive_group_toggle(charset_row, "0-9", self.cert_id_use_digits, charset_vars,
                                   on_change=self._on_cert_id_format_changed).pack(side="left")
        self._make_exclusive_group_toggle(charset_row, "A-Z", self.cert_id_use_upper, charset_vars,
                                        on_change=self._on_cert_id_format_changed).pack(side="left", padx=(10, 0))
        self._make_exclusive_group_toggle(charset_row, "a-z", self.cert_id_use_lower, charset_vars,
                                        on_change=self._on_cert_id_format_changed).pack(side="left", padx=(10, 0))
        
        self.cert_id_sample_label = ttk.Label(length_sub, text="Sample: ", style="Subtle.TLabel")
        self.cert_id_sample_label.pack(anchor="w")

        id_pos_sub = self._subsection(box, "Position (pixels, on the original image)")
        id_pos_row = ttk.Frame(id_pos_sub)
        id_pos_row.pack(fill="x")
        ttk.Label(id_pos_row, text="X:").pack(side="left")
        id_x_spin = ttk.Spinbox(id_pos_row, from_=0, to=20000, textvariable=self.cert_id_pos_x,
                                 width=8, command=self._redraw_preview)
        id_x_spin.pack(side="left", padx=(4, 14))
        ttk.Label(id_pos_row, text="Y:").pack(side="left")
        id_y_spin = ttk.Spinbox(id_pos_row, from_=0, to=20000, textvariable=self.cert_id_pos_y,
                                 width=8, command=self._redraw_preview)
        id_y_spin.pack(side="left", padx=(4, 0))
        for w in (id_x_spin, id_y_spin):
            w.bind("<KeyRelease>", lambda e: self._redraw_preview())

        id_center_row = ttk.Frame(id_pos_sub)
        id_center_row.pack(fill="x", pady=(6, 0))
        id_center_x_toggle = self._make_toggle(
            id_center_row, "Center X", self.center_id_x,
            on_toggle=lambda: self._toggle_center("cert_id", "x"))
        id_center_x_toggle.pack(side="left")
        id_center_y_toggle = self._make_toggle(
            id_center_row, "Center Y", self.center_id_y,
            on_toggle=lambda: self._toggle_center("cert_id", "y"))
        id_center_y_toggle.pack(side="left", padx=(20, 0))

        ttk.Label(id_pos_sub, text="Tip: click near the Certificate ID's blue marker "
                                    "on the preview to drag it (dragging near the name "
                                    "instead moves the name).",
                  style="Subtle.TLabel", wraplength=300, justify="left").pack(anchor="w", pady=(6, 0))

        id_font_sub = self._subsection(box, "Font")
        ttk.Label(id_font_sub, text="Type to search:",
                  wraplength=300, justify="left").pack(anchor="w")
        self.cert_id_font_combo = ttk.Combobox(id_font_sub, textvariable=self.cert_id_font_choice, style="FontEntry.TCombobox")
        self.cert_id_font_combo.pack(fill="x", pady=(2, 0))

        cert_id_spinner_row = ttk.Frame(id_font_sub)
        cert_id_spinner_row.pack(fill="x", pady=(2, 2))
        self.cert_id_font_status = ttk.Label(cert_id_spinner_row, text="", style="Subtle.TLabel",
                                              wraplength=280, justify="left")
        self.cert_id_font_status.pack(side="left")
        self.cert_id_font_spinner = ttk.Progressbar(cert_id_spinner_row, mode="indeterminate", length=90)
        # only packed while a fetch is in progress

        self._register_font_picker("cert_id", self.cert_id_font_choice, self.cert_id_font_combo,
                                    self.cert_id_font_status, self.cert_id_font_spinner)

        id_style_sub = self._subsection(box, "Style")
        id_style_row = ttk.Frame(id_style_sub)
        id_style_row.pack(fill="x", pady=(0, 8))
        id_bold_toggle = self._make_toggle(id_style_row, "B", self.cert_id_bold_var, bold_font)
        id_bold_toggle.pack(side="left")
        id_italic_toggle = self._make_toggle(id_style_row, "I", self.cert_id_italic_var, italic_font)
        id_italic_toggle.pack(side="left", padx=(10, 0))
        id_underline_toggle = self._make_toggle(id_style_row, "U", self.cert_id_underline_var, underline_font)
        id_underline_toggle.pack(side="left", padx=(10, 0))

        id_size_row = ttk.Frame(id_style_sub)
        id_size_row.pack(fill="x", pady=(0, 8))
        ttk.Label(id_size_row, text="Size:").pack(side="left")
        id_size_spin = ttk.Spinbox(id_size_row, from_=6, to=1000, textvariable=self.cert_id_font_size,
                                    width=6, command=self._redraw_preview)
        id_size_spin.pack(side="left", padx=(4, 14))
        id_size_spin.bind("<KeyRelease>", lambda e: self._redraw_preview())

        ttk.Label(id_size_row, text="Color:").pack(side="left")
        self.cert_id_color_swatch = tk.Label(id_size_row, text="  ", bg=self.cert_id_font_color,
                                              relief="sunken", width=3)
        self.cert_id_color_swatch.pack(side="left", padx=(4, 4))
        id_color_btn = ttk.Button(id_size_row, text="Choose...",
                                   command=lambda: self._choose_color("cert_id"))
        id_color_btn.pack(side="left")
        self.cert_id_color_choose_btn = id_color_btn

        id_align_row = ttk.Frame(id_style_sub)
        id_align_row.pack(fill="x")
        ttk.Label(id_align_row, text="Alignment:").pack(side="left")
        id_align_radios = []
        for val, label in (("left", "Left"), ("center", "Center"), ("right", "Right")):
            radio = ttk.Radiobutton(id_align_row, text=label, value=val, variable=self.cert_id_align_var,
                                     command=self._redraw_preview)
            radio.pack(side="left", padx=4)
            id_align_radios.append(radio)

        self._cert_id_dependent_widgets = [
            id_x_spin, id_y_spin, id_center_x_toggle, id_center_y_toggle,
            self.cert_id_font_combo,
            id_bold_toggle, id_italic_toggle, id_underline_toggle,
            id_size_spin, id_color_btn, *id_align_radios,
        ]

        # ---- 5. Output -------------------------------------------------
        box = self._section(left, "5. Output & generate")
        ttk.Button(box, text="Choose output folder...", command=self._choose_output_dir).pack(fill="x")
        self.out_label = ttk.Label(box, text="No output folder selected", style="Subtle.TLabel")
        self.out_label.pack(fill="x", pady=(2, 8))

        subfolder_row = ttk.Frame(box)
        subfolder_row.pack(fill="x", pady=(0, 2))
        ttk.Label(subfolder_row, text="Certificates folder name:").pack(side="left")
        subfolder_entry = ttk.Entry(subfolder_row, textvariable=self.output_subfolder_name, width=20)
        subfolder_entry.pack(side="left", padx=(6, 0))

        self.output_path_preview = ttk.Label(box, text="", style="Subtle.TLabel",
                                              wraplength=360, justify="left")
        self.output_path_preview.pack(anchor="w", pady=(2, 8))
        self.output_subfolder_name.trace_add("write", lambda *_a: self._update_output_path_preview())

        ttk.Label(box, text='Each file is named after the row\'s name plus its '
                             'Certificate ID, e.g. "Muhammad bilal khan" \u2192 '
                             '"Muhammad_Bilal_Khan_4K9P2Q".',
                  style="Subtle.TLabel", wraplength=360, justify="left").pack(anchor="w", pady=(0, 8))

        row = ttk.Frame(box)
        row.pack(fill="x", pady=(0, 8))
        ttk.Label(row, text="Save as:").pack(side="left")
        ttk.Combobox(row, textvariable=self.output_format, state="readonly", width=8,
                     values=["PDF", "PNG", "JPG"]).pack(side="left", padx=4)

        self.generate_btn = ttk.Button(box, text="Generate all certificates",
                                        command=self._start_generation)
        self.generate_btn.pack(fill="x", pady=(10, 6))
        # Not packed here - only shown while generation is actually
        # running (see _start_generation / _generation_done / _generation_failed),
        # rather than sitting empty on screen at rest.
        self.progress = ttk.Progressbar(box, mode="determinate")
        self.status_label = ttk.Label(box, text="", style="Subtle.TLabel")
        self.status_label.pack(fill="x", pady=(4, 10))

        # ---- View tabs (Certificate View / CSV View) ----------------------
        # The certificate preview below is completely unchanged - it is
        # simply moved inside its own tab frame (cert_view_frame) so it can
        # be shown/hidden alongside the new CSV view, still filling the
        # exact same area at the exact same size.
        self.view_tabs_bar = tk.Frame(right, bg=theme["bg"])
        self.view_tabs_bar.pack(side="top", fill="x", pady=(0, 4))

        self.view_container = ttk.Frame(right)
        self.view_container.pack(fill="both", expand=True)

        self.cert_view_frame = ttk.Frame(self.view_container)

        # ---- Preview canvas (unchanged) -----------------------------------
        ttk.Label(self.cert_view_frame, text="Live preview (click & drag either the name or "
                               "the certificate ID to reposition it)",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")

        self.canvas = tk.Canvas(self.cert_view_frame, bg=theme["canvas_bg"], highlightthickness=1,
                                 highlightbackground=theme["border"])
        self.canvas.pack(fill="both", expand=True, pady=(6, 0))
        self.canvas.bind("<Button-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<Configure>", lambda e: self._redraw_preview())
        # Once a certificate has been loaded, this tab (not the left
        # panel's now-hidden dropzone) is where dropping a new image
        # replaces it - reuses the exact same handler/validation as the
        # dropzone did.
        if _DND_AVAILABLE:
            try:
                self.canvas.drop_target_register(DND_FILES)
                self.canvas.dnd_bind("<<Drop>>", self._on_cert_image_drop)
            except Exception:
                pass

        # ---- CSV view (new) -------------------------------------------------
        self.csv_view_frame = ttk.Frame(self.view_container)
        self._build_csv_view(self.csv_view_frame)

        self._build_view_tabs()
        # Neither view has data yet at build time (no source file, no
        # certificate image) - nothing is shown here; _load_source_file()
        # reveals the CSV view for the first time once a file is loaded.

        # ---- Upload Source File gate screen --------------------------------
        # The main UI above is fully built but NOT packed yet. Instead this
        # screen occupies the window until the user provides a source file
        # (browse or drag-and-drop); _reveal_main_ui() then swaps it out for
        # self.main_root_frame. Built last so it can sit on top of/replace
        # everything above without needing any of it to exist yet.
        self.upload_screen_frame = self._build_upload_screen()
        self.upload_screen_frame.pack(fill="both", expand=True)