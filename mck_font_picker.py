"""Meraki - font picker mixin: the Word-style autocomplete font boxes
(both Name and Certificate ID pickers), their popup dropdown, and
Google Fonts fetching/loading."""

import os
import io
import threading
import tkinter as tk
from tkinter import messagebox
from PIL import ImageFont # type: ignore

from mck_constants import (
    DEFAULT_FONT_FAMILY,
    NO_FONTS_FOUND_TEXT,
    BUNDLED_DEFAULT_FONT_FILE
)
from mck_utils import (
    fetch_google_font_bytes,
    fetch_bytes
)


class FontPickerMixin:
    def _register_font_picker(self, key, choice_var, combo, status_label, spinner):
        """Register an independent Google Fonts picker - the app has two:
        one for the Name, one for the Certificate ID - both driven by the
        same fetch/search logic below, but each keeping its own selection,
        loading state, and Word-style autocomplete popup."""
        self._font_pickers[key] = {
            "choice": choice_var, "combo": combo, "status": status_label, "spinner": spinner,
            "suppress_focus": False,
        }
        combo.bind("<<ComboboxSelected>>", lambda e: self._on_font_selected_for(key))
        combo.bind("<KeyRelease>", lambda e: self._on_font_typed_for(key, e))
        combo.bind("<Return>", lambda e, k=key: self._on_font_return(k))
        combo.bind("<Escape>", lambda e, k=key: self._hide_font_popup(k))
        combo.bind("<Down>", lambda e, k=key: self._move_popup_selection(k, 1))
        combo.bind("<Up>", lambda e, k=key: self._move_popup_selection(k, -1))
        combo.bind("<FocusOut>", lambda e, k=key: (
            self._try_commit_typed_font_for(k),
            self._hide_font_popup(k),
            self._font_pickers[k]["combo"].selection_clear()))
        combo.bind("<FocusIn>", lambda e, k=key: self._on_font_focus_in(k))
        # add="+" so this fires alongside (before) the Entry's own default
        # click handler, not instead of it - see _on_font_click for why order matters.
        combo.bind("<Button-1>", lambda e, k=key: self._on_font_click(k), add="+")
        self._populate_font_dropdown(key)

        # The combo's own MouseWheel binding must still return "break" to
        # stop ttk.Combobox's built-in cycle-through-values behavior - but
        # that also stops the event from reaching the left panel's own
        # scroll handling (instance-level bindings always run before
        # bind_all ones). So explicitly scroll the panel ourselves here
        # instead of just swallowing the event - this is what makes BOTH
        # font boxes scroll the left panel exactly like every other
        # widget, rather than only one of them working by coincidence.
        combo.bind("<MouseWheel>", self._forward_wheel_to_left_panel)
        combo.bind("<Button-4>", self._forward_wheel_to_left_panel)
        combo.bind("<Button-5>", self._forward_wheel_to_left_panel)

        if not getattr(self, "_font_popup_global_click_bound", False):
            self.bind_all("<Button-1>", self._maybe_hide_all_font_popups, add="+")
            self._font_popup_global_click_bound = True

    def _forward_wheel_to_left_panel(self, event):
        self._on_left_panel_mousewheel(event)
        return "break"

    def _refresh_all_font_dropdowns(self):
        for key in self._font_pickers:
            self._populate_font_dropdown(key)

    def _populate_font_dropdown(self, key):
        # Without a working API key, only the default font is offered -
        # the full library only unlocks once a catalog has been fetched.
        picker = self._font_pickers[key]
        source = sorted(self.google_catalog.keys()) if self.google_catalog else [DEFAULT_FONT_FAMILY]
        picker["combo"]["values"] = source

    def _on_font_typed_for(self, key, event=None):
        ignored = {"Up", "Down", "Return", "Escape", "Tab",
                "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"}
        if event is not None and event.keysym in ignored:
            return

        picker = self._font_pickers[key]
        source = sorted(self.google_catalog.keys()) if self.google_catalog else [DEFAULT_FONT_FAMILY]
        query = picker["choice"].get().strip().lower()
        filtered = [f for f in source if query in f.lower()] if query else source
        picker["combo"]["values"] = filtered if filtered else [NO_FONTS_FOUND_TEXT]

        if not query:
            picker["status"].config(text="")
        elif filtered:
            count = len(filtered)
            picker["status"].config(text=f"{count} matching font{'s' if count != 1 else ''}")
        else:
            picker["status"].config(text="No matching fonts found")

        # A real keystroke means the user is actively editing, not merely
        # having clicked in - the next click should place a cursor, not
        # re-select everything.
        picker["just_focused"] = False

        self._show_font_popup(key, filtered if filtered else [NO_FONTS_FOUND_TEXT])

    # ------------------------------------------------------------------
    # Word-style click/selection behavior for the font entry
    # ------------------------------------------------------------------
    def _on_font_focus_in(self, key):
        picker = self._font_pickers[key]
        if picker.get("suppress_focus"):
            return
        combo = picker["combo"]
        combo.select_range(0, tk.END)
        combo.icursor(tk.END)

    def _safe_focus_get(self):
        try:
            return self.focus_get()
        except (KeyError, tk.TclError):
            return None

    def _on_font_click(self, key):
        """Bound alongside (before) the Entry's built-in click handler.
        If the field doesn't already have focus, this click is the one
        about to give it focus - let the default handler place a cursor
        (it'll be immediately overridden) and then select the whole font
        name, exactly like Word's first click. If it's already focused,
        this is a genuine second click - do nothing and let the default
        handler place the cursor where clicked."""
        picker = self._font_pickers[key]
        combo = picker["combo"]
        if self._safe_focus_get() is not combo:
            combo.after_idle(lambda: combo.select_range(0, tk.END))

    # ------------------------------------------------------------------
    # Custom autocomplete popup - a borderless Toplevel + Listbox that
    # never takes keyboard focus, so typing in the font entry is never
    # swallowed. This replaces reliance on ttk.Combobox's native popdown
    # for the "show suggestions while typing" behavior; the native
    # popdown is left completely alone elsewhere.
    # ------------------------------------------------------------------
    def _show_font_popup(self, key, items):
        picker = self._font_pickers[key]
        combo = picker["combo"]
        picker["suppress_focus"] = True     # <-- add
        popup = picker.get("popup")

        if popup is None or not popup.winfo_exists():
            popup = tk.Toplevel(self)
            popup.overrideredirect(True)
            popup.attributes("-topmost", True)
            theme = self._current_theme_colors
            listbox = tk.Listbox(popup, activestyle="none", highlightthickness=1,
                                bg=theme["entry_bg"], fg=theme["text"],
                                selectbackground=theme["accent"], selectforeground="#ffffff",
                                exportselection=False, relief="solid", borderwidth=1)
            listbox.pack(fill="both", expand=True)
            listbox.bind("<ButtonRelease-1>", lambda e, k=key: self._on_popup_pick(k))
            listbox.bind("<Motion>", lambda e: self._hover_popup_row(e))
            picker["popup"] = popup
            picker["popup_listbox"] = listbox

        listbox = picker["popup_listbox"]
        listbox.delete(0, tk.END)
        for name in items:
            listbox.insert(tk.END, name)
        if items:
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(0)

        combo.update_idletasks()
        x = combo.winfo_rootx()
        y = combo.winfo_rooty() + combo.winfo_height()
        w = combo.winfo_width()
        row_h = 20
        h = min(200, max(row_h, row_h * len(items)))
        popup.geometry(f"{w}x{h}+{x}+{y}")
        popup.deiconify()
        popup.lift()

        combo.focus_set()                                  # <-- add: reclaim focus explicitly
        self.after_idle(lambda: picker.__setitem__("suppress_focus", False))  # <-- add

    def _hover_popup_row(self, event):
        listbox = event.widget
        row = listbox.nearest(event.y)
        listbox.selection_clear(0, tk.END)
        listbox.selection_set(row)

    def _hide_font_popup(self, key, reclaim_focus=True):
        picker = self._font_pickers.get(key)
        if not picker:
            return
        popup = picker.get("popup")
        if popup is not None and popup.winfo_exists():
            had_focus = reclaim_focus and self._safe_focus_get() is picker["combo"]
            picker["suppress_focus"] = True
            popup.withdraw()
            if had_focus:
                picker["combo"].focus_set()
            self.after_idle(lambda: picker.__setitem__("suppress_focus", False))

    def _maybe_hide_all_font_popups(self, event):
        """Global click watcher. Two jobs:
        1. Close any open font popup when the click lands outside that
        popup's own entry/listbox.
        2. Make sure keyboard focus actually leaves the font entry when the
        user clicks some other control. Entry/Combobox widgets claim
        focus on click automatically; plain Buttons and Canvases do not
        - so without this, clicking a Button would run its command but
        silently leave the caret/selection stuck in the font box, since
        no FocusOut would ever fire on its own."""
        widget = event.widget
        for key, picker in self._font_pickers.items():
            combo = picker["combo"]
            if widget is combo or widget is picker.get("popup_listbox"):
                continue

            self._hide_font_popup(key, reclaim_focus=False)

            if self._safe_focus_get() is combo:
                self._try_commit_typed_font_for(key)
                combo.selection_clear()
                if isinstance(widget, tk.Widget):
                    widget.focus_set()
                else:
                    self.focus_set()

    def _move_popup_selection(self, key, delta):
        picker = self._font_pickers[key]
        popup = picker.get("popup")
        if popup is None or not popup.winfo_exists() or str(popup.state()) == "withdrawn":
            # Not open yet - Up/Down opens it with the current filtered list,
            # same as before (previously done via the native popdown).
            source = sorted(self.google_catalog.keys()) if self.google_catalog else [DEFAULT_FONT_FAMILY]
            query = picker["choice"].get().strip().lower()
            filtered = [f for f in source if query in f.lower()] if query else source
            self._show_font_popup(key, filtered if filtered else [NO_FONTS_FOUND_TEXT])
            return "break"

        listbox = picker["popup_listbox"]
        size = listbox.size()
        if size == 0:
            return "break"
        cur = listbox.curselection()
        idx = cur[0] if cur else -1
        idx = max(0, min(size - 1, idx + delta))
        listbox.selection_clear(0, tk.END)
        listbox.selection_set(idx)
        listbox.see(idx)
        return "break"

    def _on_font_return(self, key):
        picker = self._font_pickers[key]
        popup = picker.get("popup")
        if popup is not None and popup.winfo_exists() and str(popup.state()) != "withdrawn":
            self._on_popup_pick(key)
        else:
            self._try_commit_typed_font_for(key)
        return "break"

    def _on_popup_pick(self, key):
        picker = self._font_pickers[key]
        listbox = picker["popup_listbox"]
        sel = listbox.curselection()
        if not sel:
            return
        family = listbox.get(sel[0])
        self._hide_font_popup(key)
        if family == NO_FONTS_FOUND_TEXT:
            return
        picker["choice"].set(family)
        picker["combo"].focus_set()
        picker["combo"].icursor(tk.END)
        self._on_font_selected_for(key)

    def _try_commit_typed_font_for(self, key):
        """If the typed text is an exact (case-insensitive) match for a
        real font family, treat it as though it had been picked from the
        dropdown - so pressing Enter (or clicking away) after typing a
        full font name works, not just clicking a list item."""
        picker = self._font_pickers[key]
        typed = picker["choice"].get().strip()
        if not typed or typed == NO_FONTS_FOUND_TEXT:
            return
        source = sorted(self.google_catalog.keys()) if self.google_catalog else [DEFAULT_FONT_FAMILY]
        match = next((f for f in source if f.lower() == typed.lower()), None)
        if match:
            picker["choice"].set(match)
            self._on_font_selected_for(key)
            self._hide_font_popup(key)

    # ------------------------------------------------------------------
    # Default font bootstrap: instant bundled copy, with a silent
    # background attempt to upgrade to a freshly-fetched live copy.
    # ------------------------------------------------------------------
    def _init_default_font(self):
        if os.path.isfile(BUNDLED_DEFAULT_FONT_FILE):
            self.available_fonts[DEFAULT_FONT_FAMILY] = BUNDLED_DEFAULT_FONT_FILE
            self._redraw_preview()
        thread = threading.Thread(target=self._silent_refresh_default_font, daemon=True)
        thread.start()

    def _silent_refresh_default_font(self):
        try:
            data = self._fetch_font_bytes_for_family(DEFAULT_FONT_FAMILY)
            self.after(0, lambda: self._silent_refresh_done(data))
        except Exception:
            pass  # the bundled copy (if present) already covers us

    def _silent_refresh_done(self, data):
        self.available_fonts[DEFAULT_FONT_FAMILY] = data
        if DEFAULT_FONT_FAMILY in (self.font_choice.get(), self.cert_id_font_choice.get()):
            self._redraw_preview()

    def _fetch_font_bytes_for_family(self, family):
        if self.google_catalog and family in self.google_catalog:
            return fetch_bytes(self.google_catalog[family])
        return fetch_google_font_bytes(family)

    # ------------------------------------------------------------------
    # Font selection (one Google Fonts picker for the Name, and an
    # independent one for the Certificate ID)
    # ------------------------------------------------------------------
    def _on_font_selected_for(self, key, _event=None):
        self._hide_font_popup(key)
        picker = self._font_pickers[key]
        family = picker["choice"].get()
        if not family or family == NO_FONTS_FOUND_TEXT:
            return

        # A selection just "closed" the search - restore the full list so
        # the next time the dropdown opens (e.g. the arrow is clicked) it
        # shows everything again, not just whatever the last search had
        # narrowed it down to.
        self._populate_font_dropdown(key)

        if family in self.available_fonts:
            picker["status"].config(text="")
            self._redraw_preview()
            return

        picker["combo"].config(state="disabled")
        picker["spinner"].pack(side="left", padx=(8, 0))
        picker["spinner"].start(12)
        picker["status"].config(text=f"Fetching \"{family}\" from Google Fonts...")

        thread = threading.Thread(target=self._fetch_font_worker_for, args=(key, family), daemon=True)
        thread.start()

    def _fetch_font_worker_for(self, key, family):
        try:
            data = self._fetch_font_bytes_for_family(family)
            self.after(0, lambda: self._font_fetch_done_for(key, family, data))
        except Exception as exc:
            message = str(exc)
            self.after(0, lambda: self._font_fetch_failed_for(key, family, message))

    def _font_fetch_done_for(self, key, family, data):
        self.available_fonts[family] = data
        self._fetch_finished_for(key, f"Loaded \"{family}\".")
        self._redraw_preview()

    def _font_fetch_failed_for(self, key, family, message):
        self._fetch_finished_for(key, "")
        if family == DEFAULT_FONT_FAMILY and DEFAULT_FONT_FAMILY in self.available_fonts:
            # already have the bundled backup in place - fail quietly
            return
        messagebox.showerror(
            "Couldn't fetch font",
            f"Could not download \"{family}\" from Google Fonts.\n\n{message}\n\n"
            f"Check your internet connection and try again.",
        )

    def _fetch_finished_for(self, key, status_text):
        picker = self._font_pickers[key]
        picker["spinner"].stop()
        picker["spinner"].pack_forget()
        picker["combo"].config(state="normal")  # editable, not readonly - it doubles as the search box
        picker["status"].config(text=status_text)
        if key == "cert_id":
            # a fetch may finish after the user unchecked "Add Certificate
            # ID" - re-assert the correct disabled/enabled state rather
            # than blindly leaving it editable.
            self._update_cert_id_controls_state()

    def _get_selected_font_source(self):
        return self.available_fonts.get(self.font_choice.get())

    def _get_selected_cert_id_font_source(self):
        return self.available_fonts.get(self.cert_id_font_choice.get())

    def _make_font(self, source, size):
        size = max(1, size)
        if isinstance(source, bytes):
            return ImageFont.truetype(io.BytesIO(source), size)
        return ImageFont.truetype(source, size)

    def _load_font(self, size):
        source = self._get_selected_font_source()
        if source:
            try:
                return self._make_font(source, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def _load_cert_id_font(self, size):
        """The Certificate ID has its own independent font choice; fall
        back to whatever font the Name is using if its own isn't
        available yet (e.g. still being fetched)."""
        source = self._get_selected_cert_id_font_source()
        if source:
            try:
                return self._make_font(source, size)
            except Exception:
                pass
        return self._load_font(size)

    # ------------------------------------------------------------------
    # Settings dialog (API key + theme)
    # ------------------------------------------------------------------
