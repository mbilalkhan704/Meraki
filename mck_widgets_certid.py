"""Meraki - widgets and certificate-ID mixin: the reusable section/
toggle-checkbox builders used throughout the left panel, plus all
Certificate ID logic (charset, sampling, unique-ID assignment, saving
IDs back to the source file)."""

import random
import string
import tkinter as tk
from tkinter import ttk, messagebox
from mck_constants import CERT_ID_COLUMN
from mck_utils import write_tabular_file


class WidgetsCertIdMixin:
    def _section(self, parent, title):
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.pack(fill="x", pady=(0, 10))
        return frame

    def _subsection(self, parent, title):
        """A nested, visually distinct grouping inside a top-level section
        (e.g. Position / Font / Style within the Name section)."""
        frame = ttk.LabelFrame(parent, text=title, padding=6)
        frame.pack(fill="x", pady=(0, 8))
        return frame

    def _make_toggle(self, parent, label_text, variable, label_font=None, on_toggle=None):
        """A small self-drawn checkbox (canvas square + checkmark) plus a
        text label. Deliberately NOT a ttk.Checkbutton - ttk's indicator
        glyph rendering has proven inconsistent across Tk builds/platforms,
        so this draws its own box and tick for guaranteed, identical
        results everywhere, and stays in sync with the active theme."""
        size = 20
        wrapper = ttk.Frame(parent)
        box = tk.Canvas(wrapper, width=size, height=size, highlightthickness=0, bd=0)
        box.pack(side="left")
        label = tk.Label(wrapper, text=label_text, font=label_font, cursor="hand2")
        label.pack(side="left", padx=(5, 0))

        toggle_state = {"enabled": True}

        def redraw():
            theme = self._current_theme_colors
            box.configure(bg=theme["bg"])
            enabled = toggle_state["enabled"]
            label.configure(bg=theme["bg"], fg=theme["text"] if enabled else theme["subtle_text"])
            box.delete("all")
            checked = variable.get()
            if not enabled:
                # Dimmed, inert look - still shows checked/unchecked, but
                # in muted colors so it visually reads as unavailable.
                box.create_rectangle(2, 2, size - 2, size - 2, fill=theme["bg"],
                                      outline=theme["border"], width=2)
                if checked:
                    box.create_line(5, 10, 9, 14, fill=theme["subtle_text"], width=2, capstyle="round")
                    box.create_line(9, 14, 16, 6, fill=theme["subtle_text"], width=2, capstyle="round")
                return
            if checked:
                box.create_rectangle(2, 2, size - 2, size - 2, fill=theme["accent"],
                                      outline=theme["accent"], width=1)
                box.create_line(5, 10, 9, 14, fill="#ffffff", width=2, capstyle="round")
                box.create_line(9, 14, 16, 6, fill="#ffffff", width=2, capstyle="round")
            else:
                # A thin outline in `border` (close to `bg` in every theme)
                # was nearly invisible against the page background - use
                # the higher-contrast `subtle_text` color instead, and a
                # thicker line, so an unchecked box always reads clearly.
                box.create_rectangle(2, 2, size - 2, size - 2, fill=theme["entry_bg"],
                                      outline=theme["subtle_text"], width=2)

        # Redraw whenever the variable changes, no matter what changed it -
        # a click, or code elsewhere (e.g. a "Center" checkbox that gets
        # unchecked automatically when the position no longer matches).
        # Without this, the widget's own click handler was the only thing
        # that ever repainted it, so external changes left it visually
        # stuck showing the old state even though the variable was correct.
        variable.trace_add("write", lambda *_a: redraw())

        def toggle(_event=None):
            if not toggle_state["enabled"]:
                return
            box.focus_set()          # <-- add: claim keyboard focus here so the
                                    #     font box (or anything else) correctly
                                    #     releases it
            variable.set(not variable.get())
            self._redraw_preview()
            if on_toggle:
                on_toggle()

        def set_enabled(value):
            toggle_state["enabled"] = bool(value)
            cursor = "hand2" if toggle_state["enabled"] else "arrow"
            box.configure(cursor=cursor)
            label.configure(cursor=cursor)
            redraw()

        box.bind("<Button-1>", toggle)
        label.bind("<Button-1>", toggle)
        redraw()
        self._toggle_redraws.append(redraw)
        wrapper.set_enabled = set_enabled  # so disable-lists can treat this like a ttk widget
        return wrapper

    def _make_exclusive_group_toggle(self, parent, label_text, variable, group_vars,
                                      label_font=None, on_change=None):
        """Same look as _make_toggle, but refuses to turn itself off if
        it's the only variable in `group_vars` still on - used for the
        Certificate ID character-set choices, where at least one of
        digits/uppercase/lowercase must always stay selected."""
        size = 20
        wrapper = ttk.Frame(parent)
        box = tk.Canvas(wrapper, width=size, height=size, highlightthickness=0, bd=0)
        box.pack(side="left")
        label = tk.Label(wrapper, text=label_text, font=label_font, cursor="hand2")
        label.pack(side="left", padx=(5, 0))

        def redraw():
            theme = self._current_theme_colors
            box.configure(bg=theme["bg"])
            label.configure(bg=theme["bg"], fg=theme["text"])
            box.delete("all")
            checked = variable.get()
            if checked:
                box.create_rectangle(2, 2, size - 2, size - 2, fill=theme["accent"],
                                      outline=theme["accent"], width=1)
                box.create_line(5, 10, 9, 14, fill="#ffffff", width=2, capstyle="round")
                box.create_line(9, 14, 16, 6, fill="#ffffff", width=2, capstyle="round")
            else:
                box.create_rectangle(2, 2, size - 2, size - 2, fill=theme["entry_bg"],
                                      outline=theme["subtle_text"], width=2)

        variable.trace_add("write", lambda *_a: redraw())

        def toggle(_event=None):
            if variable.get() and sum(1 for v in group_vars if v.get()) <= 1:
                return
            box.focus_set()          # <-- add
            variable.set(not variable.get())
            if on_change:
                on_change()

        box.bind("<Button-1>", toggle)
        label.bind("<Button-1>", toggle)
        redraw()
        self._toggle_redraws.append(redraw)
        return wrapper

    # ------------------------------------------------------------------
    # CSV / Excel handling
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Certificate ID: format controls, sample preview, and generation
    # ------------------------------------------------------------------
    def _current_id_charset(self):
        charset = ""
        if self.cert_id_use_digits.get():
            charset += string.digits
        if self.cert_id_use_upper.get():
            charset += string.ascii_uppercase
        if self.cert_id_use_lower.get():
            charset += string.ascii_lowercase
        return charset or string.digits

    def _generate_sample_id(self):
        charset = self._current_id_charset()
        length = self.cert_id_length.get()
        return "".join(random.choice(charset) for _ in range(length))

    def _get_preview_cert_id(self):
        """Prefer a real ID already sitting in the first data row (so the
        preview reflects actual data once available) - unless the user has
        since explicitly changed the Length/Charset settings, in which case
        they clearly want to preview THAT instead of stale old data."""
        if not self._cert_id_preview_override and self.csv_rows:
            existing = (self.csv_rows[0].get(CERT_ID_COLUMN) or "").strip()
            if existing:
                return existing
        return self._cert_id_format_sample or self._generate_sample_id()
    
    def _refresh_cert_id_sample(self, *_args):
        self._cert_id_format_sample = self._generate_sample_id()
        if hasattr(self, "cert_id_sample_label"):
            self.cert_id_sample_label.config(text=f"Sample: {self._get_preview_cert_id()}")
        if self.cert_id_enabled.get():
            self._redraw_preview()

    def _on_cert_id_format_changed(self, *_args):
        """The user explicitly touched Length or a character-set checkbox -
        from now on the sample should preview THAT choice, not whatever
        Certificate ID happened to already be sitting in row 1 from an
        earlier generation run."""
        self._cert_id_preview_override = True
        self._refresh_cert_id_sample()

    @staticmethod
    def _id_space_size(charset, length):
        return len(charset) ** length

    def _generate_unique_id(self, charset, length, used_ids, max_attempts=10000):
        for _ in range(max_attempts):
            candidate = "".join(random.choice(charset) for _ in range(length))
            if candidate not in used_ids:
                return candidate
        # Astronomically unlikely fallback: keep extending with a numeric
        # suffix until it's unique, so this can never actually fail.
        base = "".join(random.choice(charset) for _ in range(length))
        suffix = 1
        while f"{base}{suffix}" in used_ids:
            suffix += 1
        return f"{base}{suffix}"

    def _assign_certificate_ids(self, rows):
        """Fill in a Certificate ID for every row in `rows` (a subset of
        self.csv_rows - only the rows selected for THIS run) that doesn't
        already have one. Existing values are never touched or
        regenerated, and rows not in `rows` (i.e. not selected this run)
        are left completely untouched, even if they're still missing an
        ID - they simply haven't been processed yet."""
        if CERT_ID_COLUMN not in self.csv_headers:
            self.csv_headers.append(CERT_ID_COLUMN)

        # Collisions are checked against the WHOLE file's existing IDs,
        # not just the subset - two different runs' worth of IDs must
        # never clash even though they were assigned at different times.
        used_ids = set()
        for row in self.csv_rows:
            existing = (row.get(CERT_ID_COLUMN) or "").strip()
            if existing:
                used_ids.add(existing)

        charset = self._current_id_charset()
        length = self.cert_id_length.get()
        for row in rows:
            existing = (row.get(CERT_ID_COLUMN) or "").strip()
            if existing:
                continue
            new_id = self._generate_unique_id(charset, length, used_ids)
            row[CERT_ID_COLUMN] = new_id
            used_ids.add(new_id)

    def _save_data_file_with_ids(self):
        """Write the (now ID-filled) data back to the original file,
        retrying with a clear prompt if it's currently open elsewhere."""
        while True:
            try:
                write_tabular_file(self.csv_path, self.csv_headers, self.csv_rows,
                                    new_columns={CERT_ID_COLUMN})
                return True
            except PermissionError:
                retry = messagebox.askretrycancel(
                    "File is open elsewhere",
                    f"Couldn't save Certificate IDs to:\n{self.csv_path}\n\n"
                    f"This usually means the file is currently open in Excel or "
                    f"another program. Please close it, then click Retry.",
                )
                if not retry:
                    return False
            except Exception as exc:
                messagebox.showerror("Could not save data file", str(exc))
                return False

    def _update_cert_id_controls_state(self):
        enabled = self.cert_id_enabled.get()
        state = "normal" if enabled else "disabled"
        for widget in getattr(self, "_cert_id_dependent_widgets", []):
            if hasattr(widget, "set_enabled"):
                widget.set_enabled(enabled)
            else:
                widget.config(state=state)
        self._redraw_preview()

