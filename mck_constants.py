"""
Meraki - constants module.
All fixed configuration values used across the app: resource paths,
settings file location, certificate-ID limits, theme definitions, and the
color-picker palette data. No app logic lives here - just data.
"""

import os
import sys
from mck_themes import THEMES as themes_dictionary

# ---------------------------------------------------------------------------
# Helpers for locating bundled resources (works both when run as a plain
# .py script AND when frozen into a onefile PyInstaller .exe).
# ---------------------------------------------------------------------------
def resource_path(relative_path: str) -> str:
    """Return an absolute path to a resource, whether running from source
    or from inside a PyInstaller onefile bundle."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def get_appdata_dir() -> str:
    """A per-user, always-writable folder for settings - independent of
    where the .exe itself is installed (Program Files, Desktop, etc.)."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "Meraki")
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    return path


SETTINGS_PATH = os.path.join(get_appdata_dir(), "settings.json")
FONTS_DIR = resource_path("fonts")
MAX_PREVIEW_W = 1100
MAX_PREVIEW_H = 720
SAMPLE_TEXT_FALLBACK = "Sample Name"
DEFAULT_FONT_FAMILY = "Great Vibes"
NO_FONTS_FOUND_TEXT = "No matching fonts found"
BUNDLED_DEFAULT_FONT_FILE = os.path.join(FONTS_DIR, "GreatVibes-Regular.ttf")
ORIC_LOGO_FILE = resource_path("icons/ORIC.png")
APP_ICON_PNG = resource_path("icons/app_icon.png")
APP_ICON_ICO = resource_path("icons/app_icon.ico")

# The splash screen deliberately uses its own fixed, multi-color palette,
# independent of the in-app theme system - it's brand/identity, not a
# themeable surface.
SPLASH_BG = "#0f1021"
SPLASH_PALETTE = ["#ff6b6b", "#feca57", "#1dd1a1", "#54a0ff", "#c56cf0", "#ff9ff3"]
SPLASH_DURATION_MS = 5000

GOOGLE_FONTS_CSS_URL = "https://fonts.googleapis.com/css?family={family}"
# Google's font CSS endpoint serves different file formats depending on the
# requesting browser. An older browser's user-agent string makes it serve a
# plain .ttf link (instead of .woff2), which is what Pillow/FreeType needs.
_LEGACY_USER_AGENT = ("Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/30.0.0.0 Safari/537.36")

GOOGLE_FONTS_API_URL = "https://www.googleapis.com/webfonts/v1/webfonts"

GITHUB_REPO_URL = "https://github.com/mbilalkhan704/Meraki"
GITHUB_ISSUES_URL = GITHUB_REPO_URL + "/issues"   # same name, so mck_core keeps working
APP_NAME = "Meraki"
APP_SUBTITLE = "Where Data Becomes Recognition."
APP_VERSION = "1.0.0"
LICENSE_NAME = "MIT License"        # set this to Meraki's real licence
COPYRIGHT_TEXT = "\u00a9 2026 Muhammad Bilal Khan"

APP_CREDIT_TEXT = "Developed by Muhammad Bilal Khan for ORIC, UoK"

CERT_ID_COLUMN = "Certificate ID"
INVALID_PATH_CHARS = '\\/*?:"<>|'
CERT_ID_MIN_LENGTH = 6
CERT_ID_MAX_LENGTH = 20
CERT_ID_DEFAULT_LENGTH = 6

SPLASH_LOGO_SIZE = 150

# ---------------------------------------------------------------------------
# Visual themes
# ---------------------------------------------------------------------------
THEMES = themes_dictionary
DEFAULT_THEME = "Light"

PALETTE_HUES = [0.0, 30/360, 60/360, 120/360, 210/360, 270/360]  # Red, Orange, Yellow, Green, Blue, Purple
PALETTE_SHADE_LIGHTNESS = [0.85, 0.68, 0.5, 0.34, 0.2]
STANDARD_GRAYS = ["#000000", "#434343", "#666666", "#999999", "#b7b7b7",
                  "#cccccc", "#d9d9d9", "#efefef", "#f3f3f3", "#ffffff"]
