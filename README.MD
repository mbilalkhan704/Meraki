# Certificate Bulk Generator

A standalone desktop app that works like Canva's "Bulk Create": upload a
CSV or Excel file, pick the name column, upload a certificate template,
drag the name into place, style it (font, Bold/Italic/Underline, color),
and generate one file per row as PDF, PNG, or JPG.

## 1. There is no bundled API key - each install needs its own

This app does **not** ship with a Google Fonts API key baked in. Every
person who runs it - including on a machine you've never touched - starts
with only the **Great Vibes** font available. The moment the splash screen
finishes, if no key has been saved yet, a dialog explains this and offers
to add one (with a link to get a free key from Google). "Save & Continue"
stays disabled until something is typed into the key field, and clicking
it doesn't just trust whatever was typed - the app makes a real request to
Google's API with that key and waits to see whether Google actually
accepts it, showing "Checking your key with Google..." while it does. Only
a key Google genuinely accepts gets saved; a rejected key is never written
to disk, the font list stays on Great Vibes only, and the dialog stays
open with an explanation so they can fix it and try again. "Continue with
Great Vibes only" skips this entirely and is always clickable - either
way, the reminder dialog reappears on every future launch until a key that
actually works has been saved. The same "Settings" button in the toolbar
also lets someone add or change the key at any time, with the same live
validation, without waiting for that dialog.

**In short: yes - every time this app is handed to someone new, on a new
computer, they'll need their own free Google Fonts API key if they want
more than Great Vibes.** There's nothing to configure or paste in before
bundling; this is fully self-serve for each person who runs the exe.

## 2. Set up

```
pip install -r requirements.txt
```

`tkinter` is not in requirements.txt because it ships with standard Python
installers on Windows and macOS. On some Linux distros you may need to
install it separately, e.g. `sudo apt install python3-tk`.

## 3. Add the Great Vibes backup font

Create a `fonts` folder right next to `certificate_generator.py` and put
your Great Vibes file in there, named exactly:

```
fonts/
  GreatVibes-Regular.ttf
```

This is **only a backup**. Great Vibes is fetched live from Google Fonts
like any other font in the dropdown, the same way every other font is -
this bundled copy just means the app still has a working default font
even on a machine with no internet connection on first launch, or if
Google Fonts is temporarily unreachable. If it's missing, the app simply
tries to fetch Great Vibes live instead and works exactly the same in
every other respect.

## 4. Add the ORIC logo for the splash screen (optional)

Place a file named exactly `ORIC.png` right next to
`certificate_generator.py`. It's shown on the animated splash screen the
app displays for a few seconds on launch, before the main window appears.
If it's missing, the splash screen still runs (animation and text only,
no logo) - nothing breaks either way.

When bundling with PyInstaller, add it to the build with its own
`--add-data` flag (see the bundling command below).

## 5. Run it and test

```
python certificate_generator.py
```

Try uploading a sample CSV or Excel file, a certificate image, dragging
the name around, toggling Bold/Italic/Underline, switching themes from
Settings, and generating a batch, before you bundle anything.

## 6. Bundle into a single .exe

```
pip install pyinstaller

# Windows (note the semicolon):
pyinstaller --onefile --windowed --name CertificateGenerator --add-data "fonts;fonts" --add-data "ORIC.png;." certificate_generator.py

# macOS / Linux (note the colon):
pyinstaller --onefile --windowed --name CertificateGenerator --add-data "fonts:fonts" --add-data "ORIC.png:." certificate_generator.py
```

- `--onefile` produces a single executable - this is the one file you hand
  to a client.
- `--windowed` stops a console window from popping up alongside the GUI.
- `--add-data "fonts;fonts"` bundles the Great Vibes backup file inside the
  exe.
- `--add-data "ORIC.png;."` bundles the splash screen logo. Skip this flag
  if you didn't add an `ORIC.png` - the splash screen works fine without
  it, just without a logo.
- Add `--icon=youricon.ico` if you want a custom taskbar icon.

The finished executable will be in `dist/CertificateGenerator.exe`. It is
fully self-contained - the person running it doesn't need Python, Pillow,
or any fonts installed on their machine.

## Splash screen

On launch, the app shows a brief animated splash screen (a colorful
Lissajous-curve trace with orbiting dots, on a fixed dark background) with
the ORIC logo and a small tagline - independent of whichever in-app theme
is selected, since it's identity/branding rather than app UI. It runs for
its full duration every time and cannot be skipped or clicked past - this
is deliberate, so it reads as the app actually loading rather than a
dismissible ad. The main window stays hidden until it finishes, then opens
maximized.

## Settings: API key & theme (top-right "Settings" button)

Clicking **Settings** in the toolbar opens a small dialog with two things:

- **Google Fonts API key** - blank until someone enters one. Saved
  automatically to a per-user settings file (see below) so it's
  remembered across launches - they only ever enter it once, unless they
  want to change it later.
- **Theme** - Light, Dark, Ocean, or Sunset. Changes apply live as you
  pick one in the dropdown, so you can preview before deciding.

Both **Save** and **Cancel** are available: Save persists your changes;
Cancel reverts the API key field and the theme back to whatever was active
before you opened the dialog.

There's also a dedicated reminder dialog (separate from Settings) that
appears automatically right after the splash screen finishes, but only
when no key is on file yet - see "There is no bundled API key" near the
top of this file.

Settings are stored in:

```
%LOCALAPPDATA%\ORICCertificateGenerator\settings.json
```

This is a per-Windows-user folder, independent of where the .exe itself is
installed - it works whether the exe sits on the Desktop, in Documents, or
anywhere else the user's account can normally write to. (Installing the
exe itself into `C:\Program Files\` is fine; just don't expect the app to
also be able to write files *into* that folder - it doesn't need to,
since settings live under LocalAppData instead.)

## Fonts: one searchable Google Fonts dropdown

There's a single font picker (Section 4, "Font & style"). Type in the
Search box to filter, then pick from the dropdown - it fetches that font
live the first time you select it (a small spinner shows while it's
downloading) and reuses it instantly for the rest of the session after
that. Nothing is written to disk; fonts are held in memory only.

- **Without an API key**, the dropdown only offers **Great Vibes** - that's
  the one font guaranteed to work with zero setup (see "Add the Great
  Vibes backup font" below for how its offline fallback works).
- **With a working API key**, the dropdown switches to the full official
  Google Fonts library - 1,800+ fonts, searchable.
- The reminder dialog described in "There is no bundled API key" above is
  how most people will end up adding a key; the same can also be done
  anytime from Settings.

## Bold / Italic / Underline

Simple B / I / U checkboxes sit right under the font picker. These work
with **any** font, including ones with no actual bold or italic file of
their own - bold is simulated with a text outline/stroke, italic with a
slant transform, and underline with a drawn line. All three can be
combined, and they update the live preview immediately. These are
custom-drawn toggle boxes (not the OS's native checkbox widget), so they
render identically across machines and always follow the selected theme.

## Live color picker

Clicking "Choose..." next to Color opens a small dialog with R/G/B sliders
and a hex box. The color applies live to both the dialog's own preview and
the main certificate preview as you drag - no need to click OK to see it.
Click **Cancel** (or close the dialog) to revert to whatever color you had
before opening it; click **OK** to keep the new color.

## Data file: CSV or Excel

Section 1 accepts either a `.csv` file or an `.xlsx`/`.xlsm` Excel file.
Excel reading uses the `openpyxl` package (already in requirements.txt) -
it reads the first (active) sheet, treats row 1 as the column headers, and
skips any fully blank rows. Everything downstream (the name-column
dropdown, generation, filenames) works the same regardless of which
format you uploaded.

## Notes on how positioning works

- X/Y are pixel coordinates on the *original, full-resolution* certificate
  image, not the shrunk-down preview. The app converts between the two
  automatically, so a position you set by dragging on the preview lines up
  exactly with the final output.
- The app was built assuming certificates around 2000x1414px (a common
  export size), but it works with any image size - it just warns you if
  the proportions look unusual.
- Vertical placement is always centered on the Y value you set; horizontal
  alignment (left/center/right) is controlled by the alignment radio
  buttons, which is the standard way name-plate certificates are laid out.

## Output files

Certificates are saved into a `certificates` subfolder created inside
whatever output directory you choose - e.g. if you pick `C:\Output`, files
land in `C:\Output\certificates\`. Use the "Save as" dropdown to choose
PDF, PNG, or JPG.

Each filename is built from the row's name: every word is capitalized and
words are joined with underscores. For example:

- `bilal` → `Bilal.pdf` (or `.png` / `.jpg`, depending on your choice)
- `Muhammad bilal khan` → `Muhammad_Bilal_Khan.pdf`

If two rows produce the same filename, later ones get `_1`, `_2`, etc.
appended so nothing gets overwritten.

## The window opens maximized

The app opens filling the screen automatically on launch (right after the
splash screen closes). The whole left panel (all 5 numbered sections)
scrolls independently of the preview on the right, so it stays usable even
on smaller screens or if more options get added later - scroll with the
mouse wheel or the scrollbar while hovering over the left panel.

## Credit footer

A small "Developed by Muhammad Bilal Khan for ORIC, UoK" note sits in the
bottom-right corner of the app window itself. This is purely part of the
app's UI chrome - it is never drawn onto certificate images, and never
appears in generated PDF/PNG/JPG output. Certificates only ever contain
what you explicitly put on them: the name and (optionally) your
certificate template's own design.