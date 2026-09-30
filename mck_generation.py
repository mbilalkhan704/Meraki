"""Meraki - preview and generation mixin: output-folder/format
settings, the live certificate preview canvas (drawing, dragging the
name/ID), and the actual bulk-generation run (threaded worker,
progress, and the animated status pulse)."""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageDraw, ImageTk # type: ignore

from mck_constants import (
    SAMPLE_TEXT_FALLBACK,
    CERT_ID_COLUMN,
    INVALID_PATH_CHARS
)
from mck_utils import (
    sanitize_filename,
    name_to_filename,
    composite_styled_text
)


class PreviewGenerationMixin:
    def _choose_output_dir(self):
        path = filedialog.askdirectory(title="Choose output folder")
        if path:
            self.output_dir = path
            self.out_label.config(text=path)
            self._update_output_path_preview()

    def _update_output_path_preview(self):
        if not hasattr(self, "output_path_preview"):
            return
        raw = self.output_subfolder_name.get()
        if not raw.strip():
            self.output_path_preview.config(
                text="Please type a name for the certificates output folder above.")
            return
        if self.output_dir:
            full = os.path.join(self.output_dir, raw.strip())
            self.output_path_preview.config(text=f"Certificates will be saved to:\n{full}")
        else:
            self.output_path_preview.config(
                text=f"A '{raw.strip()}' folder will be created inside whatever "
                     f"output folder you choose above.")

    def _validate_output_subfolder_name(self):
        """Returns the folder name to use, or None (after showing an error
        dialog) if it's missing or contains characters that aren't valid
        in a folder name. Never silently fills in a default or strips
        anything - the user fixes it themselves."""
        raw = self.output_subfolder_name.get()
        name = raw.strip()
        if not name:
            messagebox.showerror(
                "Missing output folder name",
                "Please type a name for the certificates output folder "
                "(Section 6) before generating.")
            return None

        bad_chars = sorted(set(ch for ch in name if ch in INVALID_PATH_CHARS))
        if bad_chars:
            messagebox.showerror(
                "Invalid output folder name",
                f"The output folder name contains characters that aren't "
                f"allowed in folder names: {' '.join(bad_chars)}\n\n"
                f"Please remove them and try again.")
            return None

        return name

    # ------------------------------------------------------------------
    # Preview drawing / dragging
    # ------------------------------------------------------------------
    def _get_sample_text(self):
        col = self.name_col.get()
        if self.csv_rows and col in self.csv_headers:
            val = self.csv_rows[0].get(col, "")
            if val:
                return val
        return SAMPLE_TEXT_FALLBACK

    def _apply_name_casing(self, text):
        """Transform the name text for DISPLAY on the certificate only -
        the underlying source-file data is never modified, so switching
        casing (or switching it back) is always non-destructive. Options
        mirror Word's "Change Case" menu."""
        mode = self.name_casing.get()
        if mode == "UPPERCASE":
            return text.upper()
        if mode == "lowercase":
            return text.lower()
        if mode == "Title Case":
            return text.title()
        if mode == "Sentence case":
            return text.capitalize()
        if mode == "tOGGLE cASE":
            return text.swapcase()
        return text  # "As in file" - unchanged

    def _redraw_preview(self):
        preview_base = self._ensure_preview_base()
        if preview_base is None:
            return
        try:
            img = preview_base.copy()

            scaled_size = max(1, round(self.font_size.get() * self.preview_scale))
            font = self._load_font(scaled_size)
            text = self._apply_name_casing(self._get_sample_text())

            offset_x, offset_y = self._preview_offset
            px = self.pos_x.get() * self.preview_scale
            py = self.pos_y.get() * self.preview_scale

            composite_styled_text(img, text, font, self.font_color, scaled_size, px, py,
                                self.align_var.get(), self.bold_var.get(),
                                self.italic_var.get(), self.underline_var.get())

            draw = ImageDraw.Draw(img)
            draw.line([(px - 8, py), (px + 8, py)], fill="red", width=1)
            draw.line([(px, py - 8), (px, py + 8)], fill="red", width=1)

            if self.cert_id_enabled.get():
                id_text = self._get_preview_cert_id()
                id_scaled_size = max(1, round(self.cert_id_font_size.get() * self.preview_scale))
                id_font = self._load_cert_id_font(id_scaled_size)
                id_px = self.cert_id_pos_x.get() * self.preview_scale
                id_py = self.cert_id_pos_y.get() * self.preview_scale
                composite_styled_text(img, id_text, id_font, self.cert_id_font_color, id_scaled_size,
                                    id_px, id_py, self.cert_id_align_var.get(), self.cert_id_bold_var.get(),
                                    self.cert_id_italic_var.get(), self.cert_id_underline_var.get())
                draw.line([(id_px - 8, id_py), (id_px + 8, id_py)], fill="#1c7ed6", width=1)
                draw.line([(id_px, id_py - 8), (id_px, id_py + 8)], fill="#1c7ed6", width=1)
        except tk.TclError:
            # A position/size field is mid-edit (temporarily blank) - skip
            # this one redraw; the next keystroke (or FocusOut) will retry
            # once the field holds a valid number again.
            return

        self.tk_preview_img = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(offset_x, offset_y, anchor="nw", image=self.tk_preview_img)

    def _ensure_preview_base(self):
        """Return a display-sized copy of the certificate, scaled to fit
        (never overflow) the canvas's real, current on-screen size, and
        centered within it (letterboxed on whichever axis has slack).
        Cached and only recomputed when the canvas size or image changes,
        so dragging the name around stays smooth."""
        if self.cert_image is None:
            return None

        canvas_w = max(self.canvas.winfo_width(), 50)
        canvas_h = max(self.canvas.winfo_height(), 50)
        cache_key = (canvas_w, canvas_h, id(self.cert_image))
        if getattr(self, "_preview_cache_key", None) == cache_key:
            return self.preview_base

        img_w, img_h = self.cert_image.size
        scale = min(canvas_w / img_w, canvas_h / img_h, 1.0)
        self.preview_scale = scale
        disp_w = max(1, int(img_w * scale))
        disp_h = max(1, int(img_h * scale))
        self.preview_base = self.cert_image.resize((disp_w, disp_h), Image.LANCZOS)
        self._preview_offset = ((canvas_w - disp_w) // 2, (canvas_h - disp_h) // 2)
        self._preview_cache_key = cache_key
        return self.preview_base

    def _canvas_to_image_coords(self, cx, cy):
        if self.preview_scale <= 0:
            return 0, 0
        offset_x, offset_y = getattr(self, "_preview_offset", (0, 0))
        x = int(round((cx - offset_x) / self.preview_scale))
        y = int(round((cy - offset_y) / self.preview_scale))
        if self.cert_image:
            w, h = self.cert_image.size
            x = max(0, min(w, x))
            y = max(0, min(h, y))
        return x, y

    def _pick_drag_target(self, canvas_x, canvas_y):
        """Decide whether a click should move the Name or the Certificate
        ID, by proximity to each one's current on-screen marker - so
        there's no separate mode switch to remember to flip first."""
        if not self.cert_id_enabled.get():
            return "name"
        offset_x, offset_y = getattr(self, "_preview_offset", (0, 0))
        name_px = self.pos_x.get() * self.preview_scale + offset_x
        name_py = self.pos_y.get() * self.preview_scale + offset_y
        id_px = self.cert_id_pos_x.get() * self.preview_scale + offset_x
        id_py = self.cert_id_pos_y.get() * self.preview_scale + offset_y
        dist_name = (canvas_x - name_px) ** 2 + (canvas_y - name_py) ** 2
        dist_id = (canvas_x - id_px) ** 2 + (canvas_y - id_py) ** 2
        return "cert_id" if dist_id < dist_name else "name"

    def _on_canvas_press(self, event):
        if self.preview_base is None:
            return
        self.canvas.focus_set()
        self._dragging = True
        self._active_drag_target = self._pick_drag_target(event.x, event.y)
        x, y = self._canvas_to_image_coords(event.x, event.y)
        if self._active_drag_target == "cert_id":
            self.cert_id_pos_x.set(x)
            self.cert_id_pos_y.set(y)
        else:
            self.pos_x.set(x)
            self.pos_y.set(y)
        self._redraw_preview()

    def _on_canvas_drag(self, event):
        if not self._dragging or self.preview_base is None:
            return
        x, y = self._canvas_to_image_coords(event.x, event.y)
        if getattr(self, "_active_drag_target", "name") == "cert_id":
            self.cert_id_pos_x.set(x)
            self.cert_id_pos_y.set(y)
        else:
            self.pos_x.set(x)
            self.pos_y.set(y)
        self._redraw_preview()

    # ------------------------------------------------------------------
    # Bulk generation
    # ------------------------------------------------------------------
    def _start_generation(self):
        if not self.csv_rows:
            messagebox.showerror("Missing data", "Please upload a CSV or Excel file first.")
            return
        if self.cert_image is None:
            messagebox.showerror("Missing image", "Please upload a certificate image first.")
            return
        if not self.name_col.get():
            messagebox.showerror("Missing column", "Please select the name column.")
            return
        if not self.output_dir:
            messagebox.showerror("Missing output folder", "Please choose an output folder.")
            return
        validated_subfolder = self._validate_output_subfolder_name()
        if validated_subfolder is None:
            return
        if not self._get_selected_font_source():
            messagebox.showerror("Missing font", "Please select a valid font.")
            return
        if self.cert_id_enabled.get() and not self._get_selected_cert_id_font_source():
            messagebox.showerror("Missing font", "Please select a valid font for the Certificate ID.")
            return

        # Only the rows chosen in the CSV View's "Rows to process" control
        # are generated this run - "All rows" (the default) still means
        # everything, exactly as before.
        selected_indices = sorted(self._get_selected_row_indices())
        if not selected_indices:
            messagebox.showerror(
                "No rows selected",
                "No rows are selected to process. Switch to the Source File View and choose "
                "'All rows', or enter a valid range/list of row numbers.")
            return
        rows_with_index = [(i, self.csv_rows[i - 1]) for i in selected_indices]

        # Certificate IDs are always generated (for the data file + the
        # filename), regardless of whether they're drawn on the
        # certificate itself - make sure the chosen length/character set
        # actually has room for them before committing to anything. Only
        # rows in THIS run's selection count toward how many new IDs are
        # actually needed.
        charset = self._current_id_charset()
        length = self.cert_id_length.get()
        capacity = self._id_space_size(charset, length)
        rows_needing_id = sum(
            1 for _i, row in rows_with_index if not (row.get(CERT_ID_COLUMN) or "").strip()
        )
        if capacity < max(rows_needing_id, 1) * 20:
            messagebox.showerror(
                "Certificate ID settings too small",
                f"With the current length ({length}) and character set, there are "
                f"only {capacity:,} possible Certificate IDs - not enough headroom "
                f"to safely assign {rows_needing_id} unique ones. Please increase "
                f"the length or enable more character types.",
            )
            return

        self._assign_certificate_ids([row for _i, row in rows_with_index])
        if not self._save_data_file_with_ids():
            return
        if hasattr(self, "csv_tree"):
            self._populate_csv_tree()  # reflect any newly-assigned IDs

        self._validated_output_subfolder = validated_subfolder
        self.generate_btn.config(state="disabled")
        self.progress.pack(fill="x", before=self.status_label)
        self.progress.config(maximum=len(rows_with_index), value=0)
        self._start_status_pulse()

        thread = threading.Thread(target=self._generate_worker, args=(rows_with_index,), daemon=True)
        thread.start()

    def _generate_worker(self, rows_with_index):
        col = self.name_col.get()
        font_source = self._get_selected_font_source()
        size = self.font_size.get()
        font = self._make_font(font_source, size)
        fmt = self.output_format.get()
        ext = {"PDF": ".pdf", "PNG": ".png", "JPG": ".jpg"}[fmt]
        bold, italic, underline = self.bold_var.get(), self.italic_var.get(), self.underline_var.get()
        align = self.align_var.get()
        draw_id_on_cert = self.cert_id_enabled.get()
        id_pos_x, id_pos_y = self.cert_id_pos_x.get(), self.cert_id_pos_y.get()
        id_bold = self.cert_id_bold_var.get()
        id_italic = self.cert_id_italic_var.get()
        id_underline = self.cert_id_underline_var.get()
        id_color = self.cert_id_font_color
        id_align = self.cert_id_align_var.get()
        id_size = self.cert_id_font_size.get()
        id_font = self._load_cert_id_font(id_size) if draw_id_on_cert else None

        dest_dir = os.path.join(self.output_dir, self._validated_output_subfolder)
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except Exception as exc:
            message = str(exc)
            self.after(0, lambda: self._generation_failed(message))
            return

        done, skipped = 0, []
        used_names = {}

        for progress_i, (orig_i, row) in enumerate(rows_with_index, start=1):
            raw_name = (row.get(col) or "").strip()
            cert_id = (row.get(CERT_ID_COLUMN) or "").strip()
            if not raw_name:
                skipped.append(f"row {orig_i} (empty name)")
                self._report_progress(progress_i)
                continue

            out_img = self.cert_image.copy()
            display_name = self._apply_name_casing(raw_name)
            composite_styled_text(out_img, display_name, font, self.font_color, size,
                                   self.pos_x.get(), self.pos_y.get(), align,
                                   bold, italic, underline)
            if draw_id_on_cert and cert_id:
                composite_styled_text(out_img, cert_id, id_font, id_color, id_size,
                                       id_pos_x, id_pos_y, id_align,
                                       id_bold, id_italic, id_underline)

            base = name_to_filename(raw_name)
            if cert_id:
                base = f"{base}_{sanitize_filename(cert_id)}"
            count = used_names.get(base, 0)
            used_names[base] = count + 1
            filename = base if count == 0 else f"{base}_{count}"
            out_path = os.path.join(dest_dir, filename + ext)

            try:
                if fmt == "PDF":
                    out_img.convert("RGB").save(out_path, "PDF", resolution=300.0)
                elif fmt == "JPG":
                    out_img.convert("RGB").save(out_path, "JPEG", quality=95)
                else:
                    out_img.save(out_path, "PNG")
                done += 1
            except Exception as exc:
                skipped.append(f"row {orig_i} ({exc})")

            self._report_progress(progress_i)

        self.after(0, lambda: self._generation_done(done, skipped, dest_dir))

    def _generation_failed(self, message):
        self.generate_btn.config(state="normal")
        self.progress.pack_forget()
        self._stop_status_pulse("Failed.")
        messagebox.showerror("Could not create output folder", message)

    def _report_progress(self, i):
        self.after(0, lambda: self.progress.config(value=i))

    def _generation_done(self, done, skipped, dest_dir):
        self.generate_btn.config(state="normal")
        self.progress.pack_forget()
        self._stop_status_pulse(f"Done: {done} generated, {len(skipped)} skipped.")
        msg = f"Generated {done} certificate(s) ({self.output_format.get()}) to:\n{dest_dir}"
        if skipped:
            preview = "\n".join(skipped[:10])
            more = "" if len(skipped) <= 10 else f"\n...and {len(skipped) - 10} more"
            msg += f"\n\nSkipped {len(skipped)}:\n{preview}{more}"
        messagebox.showinfo("Generation complete", msg)

    def _start_status_pulse(self):
        """An animated 'Generating.' / '..' / '...' ellipsis while a run is
        in progress - a genuine motion cue rather than a static label.
        (This animates the status TEXT rather than the Generate button's
        own color: the button stays state="disabled" during a run to
        block re-entrant clicks, and ttk's disabled-state style mapping
        always overrides a base color change for a disabled widget, so
        pulsing the button itself would have been invisible the whole
        time it actually needed to show progress.)"""
        self._status_pulse_active = True
        self._pulse_status_label(0)

    def _pulse_status_label(self, i):
        if not getattr(self, "_status_pulse_active", False):
            return
        dots = "." * (1 + (i % 3))
        self.status_label.config(text=f"Generating{dots}")
        self._status_pulse_after_id = self.after(400, lambda: self._pulse_status_label(i + 1))

    def _stop_status_pulse(self, final_text):
        self._status_pulse_active = False
        pulse_id = getattr(self, "_status_pulse_after_id", None)
        if pulse_id is not None:
            try:
                self.after_cancel(pulse_id)
            except Exception:
                pass
            self._status_pulse_after_id = None
        self.status_label.config(text=final_text)