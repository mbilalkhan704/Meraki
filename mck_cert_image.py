"""Meraki - source/certificate loading mixin: loading a source file
(shared by the gate screen, the left-panel button, and drag-and-drop),
loading a certificate image (shared the same way), the recent-
certificate-images pill/popup, and preview position helpers."""

import os
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox
from PIL import Image # type: ignore

from mck_utils import read_tabular_file


class CertImageMixin:
    def _load_source_file(self, path):
        """Load and validate a source file, then run all the bookkeeping
        that follows a successful load - shared by the initial Upload
        Source File screen (browse button + drag-and-drop) and the left
        panel's 'Change source file' button, so both stay in sync and
        never diverge in behavior. Returns True on success; on failure an
        error dialog has already been shown and the caller should just
        leave things where they are."""
        try:
            headers, rows = read_tabular_file(path)
        except Exception as exc:
            messagebox.showerror("Could not read file", str(exc))
            return False
        if not headers or not rows:
            messagebox.showerror("Empty file", "That file has no columns or no data rows.")
            return False

        self.csv_path = path
        self.csv_headers = headers
        self.csv_rows = rows
        self._cert_id_preview_override = False
        self.csv_label.config(text=f"{os.path.basename(path)}  ({len(rows)} rows)")
        self.name_combo["values"] = headers
        self._record_recent_file(path)

        guess = next((h for h in headers if h.strip().lower() == "name"), headers[0])
        self.name_col.set(guess)
        self._refresh_cert_id_sample()
        self._redraw_preview()

        # A fresh file defaults back to "process everything", and its
        # grid (and any locked ranges from a previous file) is replaced.
        self.row_selection_mode.set("all")
        self.row_selection_text.set("")
        self.row_selection_locked_chips = []
        if hasattr(self, "custom_controls_frame"):
            self.custom_controls_frame.pack_forget()
        if hasattr(self, "row_selection_entry"):
            self.row_selection_entry.configure(style="TEntry")
        if hasattr(self, "lock_range_btn"):
            self.lock_range_btn.config(state="disabled")
        if hasattr(self, "chips_inner"):
            self._refresh_locked_chips_row()
        if hasattr(self, "csv_tree"):
            self._populate_csv_tree()
        if hasattr(self, "view_tabs_bar"):
            self._build_view_tabs()
            self._show_view("csv")
        return True

    def _upload_data_file(self):
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
        self._load_source_file(path)

    # ------------------------------------------------------------------
    # Image handling
    # ------------------------------------------------------------------
    def _upload_image(self):
        path = filedialog.askopenfilename(
            title="Choose a certificate image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.webp")],
        )
        if not path:
            return
        self._load_certificate_image(path)

    def _load_certificate_image(self, path):
        """Load and apply a certificate image - shared by the file-dialog
        button, drag-and-drop (onto either the left-panel dropzone before
        the first image, or the Certificate View tab afterward), and
        picking one from the recent-images list, so all of these stay in
        sync."""
        try:
            img = Image.open(path).convert("RGBA")
        except Exception as exc:
            messagebox.showerror("Could not open image", str(exc))
            return

        self.cert_image = img
        w, h = img.size
        note = ""
        expected_ratio = 2000 / 1414
        ratio = w / h if h else 0
        if abs(ratio - expected_ratio) > 0.08:
            note = "  (unusual proportions for a certificate - double check it)"
        self.img_label.config(text=f"{os.path.basename(path)}  {w}x{h}px{note}")
        self._record_recent_cert_image(path)
        self._update_cert_upload_controls()

        self._preview_cache_key = None  # force a fresh fit-to-panel recompute

        # Default positions are computed from THIS image's real dimensions
        # (never a fixed assumed size) and marked as centered where that's
        # literally true, so the "Center" checkboxes start accurate.
        self.pos_x.set(round(w * 0.5))
        self.pos_y.set(round(h * 0.5))
        self.center_name_x.set(True)
        self.center_name_y.set(True)

        self.cert_id_pos_x.set(round(w * 0.5))
        self.cert_id_pos_y.set(round(h * 0.65))
        self.center_id_x.set(True)
        self.center_id_y.set(False)  # deliberately offset below center, not centered

        self._redraw_preview()
        if hasattr(self, "view_tabs_bar"):
            self._build_view_tabs()
            self._show_view("certificate")

    def _update_cert_upload_controls(self):
        """Once an image has been loaded, the left panel's dropzone gets
        out of the way (drag-and-drop for replacing the image moves to
        the Certificate View tab itself, where it's registered
        separately - see _build_ui), and the button relabels to 'Change
        certificate image...'. 'Select from recent files' stays visible
        either way."""
        has_image = self.cert_image is not None
        if hasattr(self, "cert_dropzone"):
            if has_image:
                self.cert_dropzone.pack_forget()
            else:
                self.cert_dropzone.pack(fill="x", pady=(0, 8), before=self.cert_upload_btn)
        if hasattr(self, "cert_upload_btn"):
            self.cert_upload_btn.config(
                text="Change certificate image..." if has_image else "Upload certificate image...")

    # ------------------------------------------------------------------
    # Certificate image dropzone (drag-and-drop + click-to-browse) and
    # the "Select from recent files" pill + popup - mirrors the same
    # pattern used for the source-file upload screen, scaled to fit
    # inline within the left panel's Section 2 box.
    # ------------------------------------------------------------------
    def _draw_cert_dropzone(self):
        if not hasattr(self, "cert_dropzone") or not self.cert_dropzone.winfo_exists():
            return
        theme = self._current_theme_colors
        c = self.cert_dropzone
        c.configure(bg=theme["panel_bg"], cursor="hand2")
        c.delete("all")
        w = max(c.winfo_width(), 320)
        h = max(c.winfo_height(), 90)
        c.create_rectangle(4, 4, w - 4, h - 4, outline=theme["border"], width=2, dash=(5, 3))
        c.create_text(w / 2, h / 2 - 9, text="Drag & drop certificate image here",
                       fill=theme["text"], font=("Segoe UI", 9, "bold"))
        c.create_text(w / 2, h / 2 + 11, text="or click to browse",
                       fill=theme["subtle_text"], font=("Segoe UI", 8))

    def _on_cert_image_drop(self, event):
        # Shared by the left-panel dropzone (before the first image) and
        # the Certificate View tab's canvas (afterward, once dropping
        # there is how a new image gets swapped in).
        try:
            paths = self.tk.splitlist(event.data)
        except Exception:
            paths = [event.data] if event.data else []
        if not paths:
            return
        ext = os.path.splitext(paths[0])[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".bmp", ".webp"):
            messagebox.showerror(
                "Unsupported file",
                f"'{os.path.basename(paths[0])}' isn't a supported image type "
                f"(PNG, JPG, BMP, or WEBP).")
            return
        self._load_certificate_image(paths[0])

    def _make_pill_button(self, parent, text, command):
        """A small hand-drawn pill/rounded button - ttk.Button has no
        native rounded-corner support, so this uses the same
        self-drawn-Canvas approach already used for the custom checkboxes
        elsewhere in this app, kept in sync with theme changes via the
        existing _toggle_redraws list. Darkens slightly on hover for
        tactile feedback, matching how a real button would feel."""
        theme = self._current_theme_colors
        font = ("Segoe UI", 8, "bold")
        text_w = tkfont.Font(font=font).measure(text) + 26
        height = 24
        c = tk.Canvas(parent, width=text_w, height=height, highlightthickness=0, cursor="hand2")
        state = {"hover": False}

        def redraw():
            theme = self._current_theme_colors
            c.configure(bg=theme["bg"])
            c.delete("all")
            w, h = text_w, height
            r = h / 2
            fill = theme["accent2_active"] if state["hover"] else theme["accent2"]
            c.create_oval(0, 0, h, h, fill=fill, outline=fill)
            c.create_oval(w - h, 0, w, h, fill=fill, outline=fill)
            c.create_rectangle(r, 0, w - r, h, fill=fill, outline=fill)
            c.create_text(w / 2, h / 2, text=text, fill="#ffffff", font=font)

        def on_enter(_e=None):
            state["hover"] = True
            redraw()

        def on_leave(_e=None):
            state["hover"] = False
            redraw()

        c.bind("<Button-1>", lambda e: command())
        c.bind("<Enter>", on_enter)
        c.bind("<Leave>", on_leave)
        redraw()
        self._toggle_redraws.append(redraw)
        return c

    def _toggle_recent_cert_popup(self):
        existing = getattr(self, "_recent_cert_popup", None)
        if existing is not None and existing.winfo_exists():
            self._hide_recent_cert_popup()
            return
        self._show_recent_cert_popup()

    def _show_recent_cert_popup(self):
        self._hide_recent_cert_popup()
        theme = self._current_theme_colors

        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg=theme["dialog_bg"])
        self._recent_cert_popup = popup

        frm = tk.Frame(popup, bg=theme["dialog_bg"], highlightthickness=1,
                        highlightbackground=theme["border"])
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="Recent certificate images", bg=theme["dialog_bg"], fg=theme["text"],
                 font=("Segoe UI", 9, "bold"), padx=8).pack(anchor="w", pady=(6, 4))

        if not self.recent_cert_images:
            tk.Label(frm, text="No recent images yet.", bg=theme["dialog_bg"],
                     fg=theme["subtle_text"], font=("Segoe UI", 8), padx=8).pack(anchor="w", pady=(0, 8))
        else:
            for path in reversed(self.recent_cert_images):
                row = tk.Frame(frm, bg=theme["tab_inactive_bg"], highlightthickness=1,
                                highlightbackground=theme["tab_border"], cursor="hand2")
                row.pack(fill="x", padx=6, pady=2)
                name_lbl = tk.Label(row, text=os.path.basename(path), bg=theme["tab_inactive_bg"],
                                     fg=theme["text"], font=("Segoe UI", 9, "bold"), anchor="w", padx=8)
                name_lbl.pack(fill="x", pady=(5, 0))
                dir_lbl = tk.Label(row, text=os.path.dirname(path), bg=theme["tab_inactive_bg"],
                                    fg=theme["subtle_text"], font=("Segoe UI", 7), anchor="w", padx=8)
                dir_lbl.pack(fill="x", pady=(0, 5))
                for widget in (row, name_lbl, dir_lbl):
                    widget.bind("<Button-1>", lambda e, p=path: self._select_recent_cert_image(p))
            tk.Frame(frm, bg=theme["dialog_bg"], height=4).pack()

        popup.update_idletasks()
        x = self.recent_cert_pill.winfo_rootx()
        y = self.recent_cert_pill.winfo_rooty() + self.recent_cert_pill.winfo_height() + 4
        w = max(240, popup.winfo_reqwidth())
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(0, min(sw - w, x))
        popup.geometry(f"{w}x{popup.winfo_reqheight()}+{x}+{y}")

        self._recent_cert_poll_token = self.after(150, self._poll_recent_cert_popup)

    def _poll_recent_cert_popup(self):
        popup = getattr(self, "_recent_cert_popup", None)
        if popup is None or not popup.winfo_exists():
            return

        def _inside(widget):
            if not widget.winfo_exists():
                return False
            wx, wy = widget.winfo_rootx(), widget.winfo_rooty()
            px, py = self.winfo_pointerxy()
            return wx <= px <= wx + widget.winfo_width() and wy <= py <= wy + widget.winfo_height()

        if _inside(popup) or _inside(self.recent_cert_pill):
            self._recent_cert_poll_token = self.after(150, self._poll_recent_cert_popup)
        else:
            self._hide_recent_cert_popup()

    def _hide_recent_cert_popup(self):
        token = getattr(self, "_recent_cert_poll_token", None)
        if token is not None:
            try:
                self.after_cancel(token)
            except Exception:
                pass
            self._recent_cert_poll_token = None
        popup = getattr(self, "_recent_cert_popup", None)
        if popup is not None and popup.winfo_exists():
            popup.destroy()
        self._recent_cert_popup = None

    def _select_recent_cert_image(self, path):
        self._hide_recent_cert_popup()
        if not os.path.isfile(path):
            messagebox.showerror(
                "File not found",
                f"'{path}' no longer exists, so it's being removed from your recent files.")
            self.recent_cert_images = [p for p in self.recent_cert_images if p != path]
            self._save_settings()
            return
        self._load_certificate_image(path)

    def _on_position_changed(self, target, axis):
        """If the corresponding 'Center' checkbox is on, and this position
        has drifted away from the image's true center (via typing, arrow
        spinners, or dragging), automatically uncheck it - it no longer
        reflects reality."""
        if self.cert_image is None:
            return
        if target == "name":
            pos_var = self.pos_x if axis == "x" else self.pos_y
            center_var = self.center_name_x if axis == "x" else self.center_name_y
        else:
            pos_var = self.cert_id_pos_x if axis == "x" else self.cert_id_pos_y
            center_var = self.center_id_x if axis == "x" else self.center_id_y
        if not center_var.get():
            return
        try:
            current = pos_var.get()
        except tk.TclError:
            # The field is mid-edit (temporarily blank) - nothing to compare
            # yet; the next keystroke will fire this trace again once it
            # holds a valid number.
            return
        dim = self.cert_image.size[0] if axis == "x" else self.cert_image.size[1]
        if current != round(dim / 2):
            center_var.set(False)

    def _toggle_center(self, target, axis):
        """Snap a position exactly to the image's true center on that
        axis - computed from the actual uploaded image, never a fixed
        assumed size - rather than relying on eyeballing it via drag."""
        if target == "name":
            pos_var = self.pos_x if axis == "x" else self.pos_y
            center_var = self.center_name_x if axis == "x" else self.center_name_y
        else:
            pos_var = self.cert_id_pos_x if axis == "x" else self.cert_id_pos_y
            center_var = self.center_id_x if axis == "x" else self.center_id_y
        if center_var.get() and self.cert_image is not None:
            dim = self.cert_image.size[0] if axis == "x" else self.cert_image.size[1]
            pos_var.set(round(dim / 2))
        self._redraw_preview()

    # ------------------------------------------------------------------
    # Color picker: live preview, with Cancel to revert
    # ------------------------------------------------------------------
    @staticmethod
    def _hex_to_rgb(hexcode):
        hexcode = hexcode.lstrip("#")
        return tuple(int(hexcode[i:i + 2], 16) for i in (0, 2, 4))

