"""Meraki - source file view mixin: the Excel-like CSV/Excel grid,
drag-and-drop replacement, and the row-selection system (All rows /
Custom ranges, shift/ctrl-click, locked-range chips)."""

import os
import tkinter as tk
from tkinter import ttk, messagebox

from mck_dnd import (
    DND_FILES,
    DND_AVAILABLE as _DND_AVAILABLE
)


class SourceViewMixin:
    def _build_csv_view(self, parent):
        mode_row = ttk.Frame(parent)
        mode_row.pack(fill="x", pady=(0, 4))

        ttk.Label(mode_row, text="Rows to process:").pack(side="left")
        ttk.Radiobutton(mode_row, text="All rows", value="all",
                         variable=self.row_selection_mode,
                         command=self._on_row_selection_mode_changed).pack(side="left", padx=(6, 10))
        ttk.Radiobutton(mode_row, text="Custom", value="custom",
                         variable=self.row_selection_mode,
                         command=self._on_row_selection_mode_changed).pack(side="left")

        # Everything below only makes sense once "Custom" is chosen - kept
        # in its own frame so it can be shown/hidden as a whole, rather
        # than left visible (even if disabled) while "All rows" is active.
        self.custom_controls_frame = ttk.Frame(parent)

        entry_row = ttk.Frame(self.custom_controls_frame)
        entry_row.pack(fill="x")
        self.row_selection_entry = ttk.Entry(entry_row, textvariable=self.row_selection_text, width=22)
        self.row_selection_entry.pack(side="left", padx=(0, 4))
        self.row_selection_entry.bind("<KeyRelease>", lambda e: self._on_row_selection_text_changed())

        self.lock_range_btn = ttk.Button(entry_row, text="Lock", width=10,
                                          command=self._lock_current_range, state="disabled")
        self.lock_range_btn.pack(side="left")

        ttk.Label(self.custom_controls_frame,
                  text='Type a range ("2-5, 8, 10-12") or shift/ctrl-click rows below, '
                       'then click "Lock" to protect it before starting another.',
                  style="Subtle.TLabel", wraplength=520, justify="left").pack(anchor="w", pady=(2, 2))
        self.row_selection_status = ttk.Label(self.custom_controls_frame, text="", style="Subtle.TLabel")
        self.row_selection_status.pack(anchor="w", pady=(0, 2))

        # Locked ranges: a horizontally-scrollable strip of removable
        # "chips" rather than a growing list of text boxes, so any number
        # of locked ranges stays within a small, fixed vertical footprint.
        ttk.Label(self.custom_controls_frame, text="Locked ranges:",
                  style="Subtle.TLabel").pack(anchor="w", pady=(2, 0))
        theme = self._current_theme_colors
        self.chips_outer = tk.Frame(self.custom_controls_frame, height=34, bg=theme["bg"])
        self.chips_outer.pack(fill="x", pady=(0, 6))
        self.chips_outer.pack_propagate(False)
        self.chips_canvas = tk.Canvas(self.chips_outer, height=30, highlightthickness=0, bg=theme["bg"])
        chips_hsb = ttk.Scrollbar(self.chips_outer, orient="horizontal", command=self.chips_canvas.xview)
        self.chips_canvas.configure(xscrollcommand=chips_hsb.set)
        self.chips_canvas.pack(side="top", fill="x")
        self.chips_inner = tk.Frame(self.chips_canvas, bg=theme["bg"])
        self._chips_window = self.chips_canvas.create_window((0, 0), window=self.chips_inner, anchor="nw")
        self.chips_inner.bind("<Configure>", lambda e: self.chips_canvas.configure(
            scrollregion=self.chips_canvas.bbox("all")))

        def _chips_wheel(event):
            if getattr(event, "num", None) == 4:
                self.chips_canvas.xview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                self.chips_canvas.xview_scroll(1, "units")
            else:
                self.chips_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        self.chips_canvas.bind("<MouseWheel>", _chips_wheel)
        self.chips_canvas.bind("<Button-4>", _chips_wheel)
        self.chips_canvas.bind("<Button-5>", _chips_wheel)
        self._refresh_locked_chips_row()
        # Not packed here - _on_row_selection_mode_changed shows/hides it
        # based on the current mode; "All rows" is the default, so this
        # whole block starts hidden.

        grid_frame = ttk.Frame(parent)
        grid_frame.pack(fill="both", expand=True)
        grid_frame.rowconfigure(0, weight=1)
        grid_frame.columnconfigure(0, weight=1)

        self.csv_tree = ttk.Treeview(grid_frame, show="headings", selectmode="extended")
        vsb = ttk.Scrollbar(grid_frame, orient="vertical", command=self.csv_tree.yview)
        hsb = ttk.Scrollbar(grid_frame, orient="horizontal", command=self.csv_tree.xview)
        self.csv_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.csv_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # Fixed, theme-independent semantic colors - same convention as
        # the red/blue crosshair markers already used on the certificate
        # preview - green = will be processed, red = will be skipped.
        # Foreground is ALSO fixed (dark) rather than left to inherit the
        # theme's own text color: in Dark theme that color is near-white,
        # which is unreadable against these light pastel backgrounds -
        # since the backgrounds are intentionally theme-independent, the
        # text drawn on them needs to be too.
        self.csv_tree.tag_configure("row_selected", background="#d3f9d8", foreground="#1a2e1a")
        self.csv_tree.tag_configure("row_unselected", background="#ffe3e3", foreground="#3a1414")

        self.csv_tree.bind("<<TreeviewSelect>>", self._on_csv_tree_select)

        # Once a source file has been loaded, dropping a new CSV/Excel
        # file anywhere on this tab replaces it - same convention as the
        # Certificate View tab replacing the loaded image.
        if _DND_AVAILABLE:
            for widget in (parent, grid_frame, self.csv_tree):
                try:
                    widget.drop_target_register(DND_FILES)
                    widget.dnd_bind("<<Drop>>", self._on_source_view_drop)
                except Exception:
                    pass

    def _on_source_view_drop(self, event):
        try:
            paths = self.tk.splitlist(event.data)
        except Exception:
            paths = [event.data] if event.data else []
        if not paths:
            return
        ext = os.path.splitext(paths[0])[1].lower()
        if ext not in (".csv", ".xlsx", ".xlsm"):
            messagebox.showerror(
                "Unsupported file",
                f"'{os.path.basename(paths[0])}' isn't a CSV or Excel file.")
            return
        self._load_source_file(paths[0])

    def _populate_csv_tree(self):
        tree = self.csv_tree
        tree.delete(*tree.get_children())
        columns = ["#"] + self.csv_headers
        tree["columns"] = columns
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=50 if col == "#" else 130, anchor="w", stretch=False)
        for i, row in enumerate(self.csv_rows, start=1):
            values = [i] + [row.get(h, "") for h in self.csv_headers]
            tree.insert("", "end", iid=str(i), values=values)
        self._refresh_row_selection_tags()

    @staticmethod
    def _parse_row_selection(text, max_row):
        """Parse a print-dialog-style range string ("2-5, 8, 10-12") into
        a set of 1-based row indices, clipped to [1, max_row]. Returns
        (indices, error_message_or_None)."""
        indices = set()
        text = text.strip()
        if not text:
            return set(), None
        for part in text.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                bounds = part.split("-")
                if len(bounds) != 2:
                    return set(), f"Invalid range: '{part}'"
                try:
                    a, b = int(bounds[0]), int(bounds[1])
                except ValueError:
                    return set(), f"Invalid range: '{part}'"
                if a > b:
                    a, b = b, a
                for n in range(a, b + 1):
                    if 1 <= n <= max_row:
                        indices.add(n)
            else:
                try:
                    n = int(part)
                except ValueError:
                    return set(), f"Invalid row number: '{part}'"
                if 1 <= n <= max_row:
                    indices.add(n)
        return indices, None

    @staticmethod
    def _compress_indices_to_range_string(indices):
        """Inverse of _parse_row_selection - a sorted set of indices back
        into the shortest equivalent "2-5, 8, 10-12" string, used when the
        user shift/ctrl-clicks rows directly in the grid."""
        if not indices:
            return ""
        nums = sorted(indices)
        parts = []
        start = prev = nums[0]
        for n in nums[1:]:
            if n == prev + 1:
                prev = n
                continue
            parts.append(str(start) if start == prev else f"{start}-{prev}")
            start = prev = n
        parts.append(str(start) if start == prev else f"{start}-{prev}")
        return ", ".join(parts)

    def _get_selected_row_indices(self):
        """1-based indices of the rows that should actually be processed:
        every locked chip's rows, UNION the live (not-yet-locked) text
        box - so a single range never needs locking to take effect, while
        multiple disjoint ranges can be built up safely via '+ Lock
        range'. 'All rows' (the default) or an empty file always means
        every row."""
        max_row = len(self.csv_rows)
        if max_row == 0:
            return set()
        if self.row_selection_mode.get() == "all":
            return set(range(1, max_row + 1))
        result = set()
        for chip in self.row_selection_locked_chips:
            result |= chip["indices"]
        live_indices, _err = self._parse_row_selection(self.row_selection_text.get(), max_row)
        result |= live_indices
        return result

    def _refresh_row_selection_tags(self):
        if not hasattr(self, "csv_tree"):
            return
        total = len(self.csv_rows)
        selected = self._get_selected_row_indices()
        for i in range(1, total + 1):
            iid = str(i)
            if self.csv_tree.exists(iid):
                self.csv_tree.item(iid, tags=("row_selected" if i in selected else "row_unselected",))
        self.row_selection_status.config(
            text=f"{len(selected)} of {total} row(s) selected for processing.")

    def _update_custom_entry_validity(self):
        """Live feedback while typing: an invalid range turns the entry
        red (rather than a small status line that's easy to miss), and
        the 'Lock' button only enables once there's something
        valid and non-empty to actually lock in."""
        if not hasattr(self, "row_selection_entry"):
            return
        total = len(self.csv_rows)
        text = self.row_selection_text.get().strip()
        indices, err = self._parse_row_selection(text, total)
        if err:
            self.row_selection_entry.configure(style="Invalid.TEntry")
        else:
            self.row_selection_entry.configure(style="TEntry")
        if hasattr(self, "lock_range_btn"):
            self.lock_range_btn.config(state="normal" if (indices and not err) else "disabled")

    def _on_row_selection_mode_changed(self):
        if self.row_selection_mode.get() == "all":
            if hasattr(self, "custom_controls_frame"):
                self.custom_controls_frame.pack_forget()
            self._row_selection_syncing = True
            if hasattr(self, "csv_tree"):
                self.csv_tree.selection_remove(self.csv_tree.selection())
            # <<TreeviewSelect>> fires asynchronously in Tk - reset the
            # guard on the next idle pass, once that deferred event (if
            # any) has already had a chance to see it still set, rather
            # than immediately, or it can slip through unguarded.
            self.after_idle(lambda: setattr(self, "_row_selection_syncing", False))
        else:
            if hasattr(self, "custom_controls_frame"):
                self.custom_controls_frame.pack(fill="x", pady=(6, 0))
            self._update_custom_entry_validity()
        self._refresh_row_selection_tags()

    def _on_row_selection_text_changed(self):
        # Deliberately local-only: parse/validate what's typed, color the
        # entry accordingly, and refresh the green/red row highlighting.
        # This never touches the Treeview's own selection. It used to
        # also call csv_tree.selection_set(...) to mirror the typed text
        # into the grid's native highlight, but <<TreeviewSelect>> fires
        # asynchronously - that created a feedback loop where a deferred
        # callback from an earlier keystroke could fire after a later one
        # and stomp the text box back to an older value, which is exactly
        # what made typed ranges seem to "vanish" on Enter. The red/green
        # signals already give the visual feedback that matters; the
        # tree's own blue highlight is now reserved for genuine
        # shift/ctrl-clicks in the grid.
        self._update_custom_entry_validity()
        self._refresh_row_selection_tags()

    def _lock_current_range(self):
        """Lock in whatever is currently typed (or currently highlighted
        in the grid, since shift/ctrl-clicking fills the text box) as its
        own protected chip. Locked chips are never affected by a later
        shift/ctrl-click or by clearing the live text - only their own
        '-' button removes them. The button itself is only enabled once
        there's something valid to lock, so the failure dialogs below are
        a defensive backstop, not the everyday path."""
        total = len(self.csv_rows)
        text = self.row_selection_text.get().strip()
        indices, err = self._parse_row_selection(text, total)
        if err:
            messagebox.showerror("Invalid range", err)
            return
        if not indices:
            messagebox.showerror(
                "Nothing to lock in",
                "Type a range or shift/ctrl-click rows in the grid first.")
            return

        already_locked = set()
        for chip in self.row_selection_locked_chips:
            already_locked |= chip["indices"]
        overlap = indices & already_locked
        if overlap:
            overlap_label = self._compress_indices_to_range_string(overlap)
            messagebox.showerror(
                "Row(s) already locked",
                f"Row(s) {overlap_label} are already part of a locked range. "
                f"Remove that range first (its '\u2212' button) if you want to "
                f"change it, or adjust your selection to avoid it.")
            return

        label = self._compress_indices_to_range_string(indices)
        self.row_selection_mode.set("custom")
        self.row_selection_locked_chips.append({"indices": frozenset(indices), "label": label})
        self._refresh_locked_chips_row()

        # Clear the live entry + grid selection so the next shift/ctrl-
        # click or typed range starts fresh, unaffected by what's now locked.
        self._row_selection_syncing = True
        self.row_selection_text.set("")
        if hasattr(self, "csv_tree"):
            self.csv_tree.selection_remove(self.csv_tree.selection())
        self.after_idle(lambda: setattr(self, "_row_selection_syncing", False))
        self._update_custom_entry_validity()
        self._refresh_row_selection_tags()

    def _refresh_locked_chips_row(self):
        if not hasattr(self, "chips_inner"):
            return
        for w in self.chips_inner.winfo_children():
            w.destroy()
        theme = self._current_theme_colors
        if not self.row_selection_locked_chips:
            tk.Label(self.chips_inner, text="(none yet)", bg=theme["bg"],
                     fg=theme["subtle_text"], font=("Segoe UI", 8)).pack(side="left", padx=4, pady=6)
        else:
            for idx, chip in enumerate(self.row_selection_locked_chips):
                pill = tk.Frame(self.chips_inner, bg=theme["accent"])
                pill.pack(side="left", padx=3, pady=3)
                tk.Label(pill, text=chip["label"], bg=theme["accent"], fg="#ffffff",
                         font=("Segoe UI", 8, "bold"), padx=6, pady=3).pack(side="left")
                remove_btn = tk.Label(pill, text=" \u2212 ", bg=theme["accent2"], fg="#ffffff",
                                       font=("Segoe UI", 9, "bold"), cursor="hand2")
                remove_btn.pack(side="left", fill="y")
                remove_btn.bind("<Button-1>", lambda e, i=idx: self._remove_locked_chip(i))
        self.chips_inner.update_idletasks()
        self.chips_canvas.configure(scrollregion=self.chips_canvas.bbox("all"))

    def _remove_locked_chip(self, index):
        if 0 <= index < len(self.row_selection_locked_chips):
            del self.row_selection_locked_chips[index]
            self._refresh_locked_chips_row()
            self._refresh_row_selection_tags()

    def _on_csv_tree_select(self, _event=None):
        if self._row_selection_syncing:
            return
        sel = self.csv_tree.selection()
        if not sel:
            return
        indices = sorted(int(i) for i in sel)
        text = self._compress_indices_to_range_string(indices)
        self.row_selection_mode.set("custom")
        self.row_selection_text.set(text)
        self._update_custom_entry_validity()
        self._refresh_row_selection_tags()

