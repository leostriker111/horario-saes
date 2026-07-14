from pathlib import Path
from tkinter import font as tkfont

import sys
import ctypes
import ctypes.util

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    _DIR = Path(sys._MEIPASS) / "horario_saes" / "fonts"
else:
    _DIR = Path(__file__).resolve().parent.parent / "fonts"

_FA_SOLID = str(_DIR / "fa-solid-900.ttf")
_FA_REGULAR = str(_DIR / "fa-regular-400.ttf")

FONT_SOLID = "FontAwesomeSolid"
FONT_REGULAR = "FontAwesomeRegular"

_loaded = False


def _cargar_font_ctypes(path: str) -> bool:
    try:
        if sys.platform.startswith("win"):
            # FR_PRIVATE = 0x10: font is private to the process and will be unloaded when process ends
            res = ctypes.windll.gdi32.AddFontResourceExW(path, 0x10, 0)
            return res > 0
        elif sys.platform.startswith("linux"):
            libfc_path = ctypes.util.find_library('fontconfig')
            if not libfc_path:
                return False
            libfc = ctypes.CDLL(libfc_path)
            libfc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
            libfc.FcConfigAppFontAddFile.restype = ctypes.c_int
            res = libfc.FcConfigAppFontAddFile(None, path.encode('utf-8'))
            return res != 0
        elif sys.platform.startswith("darwin"):
            # macOS CoreText / CoreFoundation font registration
            cf_lib = ctypes.util.find_library('CoreFoundation')
            ct_lib = ctypes.util.find_library('CoreText')
            if not cf_lib:
                cf_lib = '/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation'
            if not ct_lib:
                ct_lib = '/System/Library/Frameworks/CoreText.framework/CoreText'
            
            cf = ctypes.CDLL(cf_lib)
            ct = ctypes.CDLL(ct_lib)
            
            # Setup CFURLCreateFromFileSystemRepresentation
            cf.CFURLCreateFromFileSystemRepresentation.argtypes = [
                ctypes.c_void_p,
                ctypes.c_char_p,
                ctypes.c_long,
                ctypes.c_bool
            ]
            cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
            
            # Setup CFRelease
            cf.CFRelease.argtypes = [ctypes.c_void_p]
            cf.CFRelease.restype = None
            
            # Setup CTFontManagerRegisterFontsForURL
            ct.CTFontManagerRegisterFontsForURL.argtypes = [
                ctypes.c_void_p,
                ctypes.c_int,
                ctypes.c_void_p
            ]
            ct.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool
            
            path_bytes = path.encode('utf-8')
            url_ref = cf.CFURLCreateFromFileSystemRepresentation(None, path_bytes, len(path_bytes), False)
            if not url_ref:
                return False
            
            # scope = 1 (kCTFontManagerScopeProcess: registered for the current process only)
            success = ct.CTFontManagerRegisterFontsForURL(url_ref, 1, None)
            cf.CFRelease(url_ref)
            return success
    except Exception:
        pass
    return False


def cargar_fuentes(root=None):
    global _loaded
    if _loaded:
        return
    if root is None:
        import tkinter as tk
        root = tk._default_root

    # Try loading via ctypes first
    _cargar_font_ctypes(_FA_SOLID)
    _cargar_font_ctypes(_FA_REGULAR)

    # Search for Font Awesome in the available font families
    try:
        fams = tkfont.families(root)
        fa_family = None
        for f in fams:
            if "font awesome" in f.lower():
                fa_family = f
                break
        
        if fa_family:
            root.tk.call("font", "create", FONT_SOLID, "-family", fa_family, "-weight", "bold", "-size", 12)
            root.tk.call("font", "create", FONT_REGULAR, "-family", fa_family, "-weight", "normal", "-size", 12)
            _loaded = True
            return
    except Exception:
        pass

    # Fallback to the original Tcl -file method
    try:
        root.tk.call("font", "create", FONT_SOLID, "-file", _FA_SOLID, "-size", 12)
        root.tk.call("font", "create", FONT_REGULAR, "-file", _FA_REGULAR, "-size", 12)
        _loaded = True
        return
    except Exception:
        pass

    # Ultimate fallback: create named fonts using generic sans-serif so the app does not crash
    try:
        root.tk.call("font", "create", FONT_SOLID, "-family", "sans-serif", "-size", 12)
        root.tk.call("font", "create", FONT_REGULAR, "-family", "sans-serif", "-size", 12)
        _loaded = True
    except Exception:
        pass



class FA:
    FOLDER_OPEN = "\uf07c"
    SEARCH = "\uf002"
    SEEDLING = "\uf4d8"
    TREE = "\uf1bb"
    PLUS = "\uf067"
    CLIPBOARD = "\uf328"
    CHECK = "\uf00c"
    UPLOAD = "\uf093"
    TRASH = "\uf2ed"
    USERS = "\uf0c0"
    EXCLAMATION_TRIANGLE = "\uf071"
    STAR = "\uf005"
    TIMES = "\uf00d"
    EYE = "\uf06e"
    EYE_SLASH = "\uf070"


_tk_images = {}


def crear_imagen_icono(char, font_type=FONT_SOLID, size=14, color="#333333"):
    """
    Renders a FontAwesome character as a PIL image and returns it as a tk.PhotoImage.
    Uses caching to avoid recreating the same image repeatedly.
    """
    from PIL import Image, ImageDraw, ImageFont, ImageTk

    cache_key = (char, font_type, size, color)
    if cache_key in _tk_images:
        return _tk_images[cache_key]

    font_path = _FA_SOLID if font_type == FONT_SOLID else _FA_REGULAR

    # Create a small square image with transparent background
    img = Image.new("RGBA", (size + 4, size + 4), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(font_path, size)
    except Exception:
        return None

    # Calculate bounding box to center the icon perfectly
    bbox = draw.textbbox((0, 0), char, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    # Center position
    x = ((size + 4) - w) / 2 - bbox[0]
    y = ((size + 4) - h) / 2 - bbox[1]

    draw.text((x, y), char, font=font, fill=color)
    tk_img = ImageTk.PhotoImage(img)
    _tk_images[cache_key] = tk_img
    return tk_img

