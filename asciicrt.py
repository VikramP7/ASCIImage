#!/usr/bin/env python3
"""
asciicrt.py - convert an image into ASCII art and render it as a high-resolution
CRT-style print.

Pipeline: image -> character grid -> ANSI -> rasterised glyphs -> CRT post-process
-> print-ready PNG or TIFF. Terminal and SVG output are also available.

Requires numpy and pillow.

    python asciicrt.py photo.jpg --rows 60 --show --no-raster
    python asciicrt.py photo.jpg --rows 180 --width-in 12 --height-in 18 --dpi 300 -o print.tiff
    python asciicrt.py photo.jpg --rows 120 --svg art.svg --no-raster
    python asciicrt.py photo.jpg --rows 140 --preset clean -o print.png

Iterating on the CRT look without repeating the ASCII pass:

    python asciicrt.py photo.jpg --rows 180 --dump-ansi art.txt --preview
    python asciicrt.py --from-ansi art.txt --sweep bloom=0,0.2,0.5,0.9
    python asciicrt.py --from-ansi art.txt --set bloom=0.2 --dump-params look.json
    python asciicrt.py --from-ansi art.txt --params look.json --width-in 12 --dpi 300

--list-params lists every CRT parameter, --list-ramps every density ramp.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import struct
import sys
import zlib
from dataclasses import dataclass, fields, asdict, replace

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Rec.709 luminance weights, used for brightness mapping and by the CRT chain.
LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
# Rec.601 weights, used where the chain emulates composite video encoding.
LUMA601 = np.array([0.299, 0.587, 0.114], dtype=np.float32)

# ==========================================================================
# 0. Character density ramps  (dense -> sparse, brightest pixel gets ramp[0])
# ==========================================================================

RAMPS = {
    # Paul Bourke's 70-level ramp; the default, sliced to 40 characters
    "bourke": list("$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "),
    # The 28-character scale from the original engine
    "original": ['Ñ', '@', '#', 'W', '$', '9', '8', '7', '6', '5', '4', '3', '2', '1',
                 '0', '?', '!', 'a', 'b', 'c', ';', ':', '+', '=', '-', ',', '.', '_'],

    "punc": ['@', '#', '&', '%', '$', '8', '?', '*', '+', '=', ';', ':', '~', '-',
             ',', '.', '`', ' '],
    "punct": ['@', '#', '&', '%', '$', '?', '!', '*', '+', '=', '/', '\\', '|', '(',
              ')', '[', ']', '<', '>', ';', ':', '"', "'", '~', '^', '-', ',', '.',
              '`', ' '],
    "nums": ['8', '0', '9', '6', '5', '3', '2', '4', '7', '1', ' '],
    "letters": ['M', 'W', 'N', 'Q', 'B', 'H', 'R', 'D', 'K', 'A', 'G', 'O', 'U', 'P',
                'X', 'E', 'Z', 'S', 'Y', 'F', 'T', 'C', 'L', 'J', 'I', 'o', 'e', 'a',
                'c', 'v', 'n', 'r', 's', 'x', 'z', 'i', 'l', 't', ';', ':', ',', '.', ' '],
    "letterspure": ['M', 'W', 'N', 'Q', 'B', 'H', 'R', 'D', 'K', 'A', 'G', 'O', 'U',
                    'P', 'X', 'E', 'Z', 'S', 'Y', 'F', 'T', 'C', 'L', 'J', 'I', 'o',
                    'e', 'a', 'c', 'u', 'v', 'n', 'r', 's', 'x', 'z', 'i', 'l', 'j'],
    "lower": ['m', 'w', 'q', 'b', 'h', 'd', 'k', 'a', 'o', 'g', 'p', 'e', 'u', 'n',
              'r', 'c', 's', 'v', 'x', 'z', 'y', 'f', 't', 'j', 'i', 'l'],
    "upper": ['M', 'W', 'N', 'Q', 'B', 'H', 'R', 'D', 'K', 'A', 'G', 'O', 'U', 'P',
              'X', 'E', 'Z', 'S', 'Y', 'F', 'T', 'C', 'L', 'J', 'I'],
    "blocks": ['█', '▓', '▒', '░', '▚', '▞', '▙', '▟', '▜', '▛', '▀', '▄', '▐', '▌',
               '■', '□', '▪', '▫', '·', ' '],
    "braille": ['⣿', '⣾', '⣽', '⣻', '⢿', '⡿', '⣷', '⣯', '⣟', '⣞', '⣝', '⣛', '⣚', '⣙',
                '⣘', '⣗', '⣖', '⣕', '⣔', '⣓', '⣒', '⣑', '⣐', '⣏', '⣎', '⣍', '⣌', '⣋',
                '⣊', '⣉', '⣈', '⡇', '⠿', '⠾', '⠽', '⠼', '⠻', '⠺', '⠹', '⠸', '⠷', '⠶',
                '⠵', '⠴', '⠳', '⠲', '⠱', '⠰', '⠯', '⠮', '⠭', '⠬', '⠫', '⠪', '⠩', '⠨',
                '⠧', '⠦', '⠥', '⠤', '⠣', '⠢', '⠡', '⠠', '⠟', '⠞', '⠝', '⠜', '⠛', '⠚',
                '⠙', '⠘', '⠗', '⠖', '⠕', '⠔', '⠓', '⠒', '⠑', '⠐', '⠏', '⠎', '⠍', '⠌',
                '⠋', '⠊', '⠉', '⠈', '⠇', '⠆', '⠅', '⠄', '⠃', '⠂', '⠁', '⠀'],
    "math": ['∰', '∯', '∮', '∑', '∏', '∆', '∇', '∞', '≈', '≡', '≠', '±', '∓', '×',
             '÷', '√', '∝', '∂', '∫', '∈', '∋', '∪', '⊆', '⊇', '∩', '⊂', '⊃', '∧',
             '∨', '¬', '→', '←', '↑', '↓', '·', '∘', '°', ' '],
    "shapes": ['█', '●', '◉', '◆', '◼', '■', '▲', '▼', '◀', '▶', '◈', '◇', '◊', '○',
               '◌', '◯', '△', '▽', '◁', '▷', '·', '˙', ' '],
    "currency": ['₩', '₿', '﷼', '₪', '€', '£', '¥', '$', '₽', '₹', '₺', '₱', '₴',
                 '₦', '₡', '₵', '¢', ' '],
    "arrows": ['⇚', '⇛', '⇐', '⇒', '⇑', '⇓', '⇔', '⇕', '←', '→', '↑', '↓', '↔', '↕',
               '↖', '↗', '↘', '↙', '↞', '↠', '↢', '↣', '⇠', '⇢', '⤂', '⤃', '·', ' '],
    "minimal": ['@', '%', '#', '*', '+', '=', '-', ':', '.', ' '],
}


def resolve_ramp(name, slice_n=0):
    """Look up a ramp by name, or treat a long string as a literal ramp."""
    key = name.lower().replace("chardensity", "").replace("charpuncdensity", "punc")
    ramp = RAMPS.get(key) or RAMPS.get(name)
    if ramp is None:
        if len(name) > 3:
            ramp = list(name)          # literal ramp, dense -> sparse
        else:
            raise SystemExit(f"Unknown ramp {name!r}. See --list-ramps.")
    ramp = list(ramp)
    return ramp[:slice_n] if slice_n else ramp


# ==========================================================================
# 1. Image -> ANSI
# ==========================================================================

def area_resize(arr, out_h, out_w):
    """Area-average an HxWx3 array to an exact output size.

    A box resize supporting non-integer scale factors, so the output lands on
    exactly the requested row and column counts and every source pixel
    contributes to the result.
    """
    h, w = arr.shape[:2]
    ys = np.linspace(0, h, out_h + 1).astype(np.int32)
    xs = np.linspace(0, w, out_w + 1).astype(np.int32)
    ys[1:] = np.maximum(ys[1:], ys[:-1] + 1)
    xs[1:] = np.maximum(xs[1:], xs[:-1] + 1)
    # integrate once, then take box sums - O(HW) rather than O(out_h*out_w*box)
    integ = np.zeros((h + 1, w + 1, 3), np.float64)
    integ[1:, 1:] = arr.astype(np.float64).cumsum(0).cumsum(1)
    y0, y1 = ys[:-1, None], ys[1:, None]
    x0, x1 = xs[None, :-1], xs[None, 1:]
    total = (integ[y1, x1] - integ[y0, x1] - integ[y1, x0] + integ[y0, x0])
    count = ((y1 - y0) * (x1 - x0))[..., None]
    return (total / count).astype(np.float32)


def brightness_to_index(rgb, n_levels, mode="mean"):
    """Map pixel brightness onto ramp positions.

    charIndex = round(bright * n), indexed from the end of the ramp, falling
    back to ramp[0] when charIndex == n. Brightest pixel gets the densest glyph.
    """
    if mode == "luma":
        bright = rgb @ LUMA
    else:
        bright = rgb.mean(axis=-1)
    idx = np.rint(np.clip(bright / 255.0, 0.0, 1.0) * n_levels).astype(np.int32)
    return np.clip(n_levels - 1 - idx, 0, n_levels - 1)


def image_to_ansi(path, rows, ramp, gamma_y=1.0, cell_aspect=2.0, reps=2,
                  brightness_mode="mean", cols=None):
    """Convert an image file into a list of ANSI-coloured strings, one per row.

    :param rows:         output height in character rows
    :param ramp:         density ramp, dense -> sparse
    :param gamma_y:      >1 lifts every channel toward white
    :param cell_aspect:  terminal cell height / width, normally ~2
    :param reps:         characters printed per source pixel horizontally
    :returns: (lines, n_rows, n_cols_in_characters)
    """
    image = Image.open(path).convert("RGB")
    arr = np.asarray(image, dtype=np.float32)
    h, w = arr.shape[:2]

    if cols is None:
        # square output pixels: each source pixel becomes `reps` cells wide
        cols = max(1, int(round(rows * (w / h) * cell_aspect / reps)))
    rows = max(1, int(rows))

    small = area_resize(arr, rows, cols)

    if gamma_y != 1.0:
        small = small + (255.0 - small) * (gamma_y - 1.0)

    # The averaged pixel is truncated to 8-bit before brightness is measured,
    # so the ramp index is derived from the same integers that get emitted.
    rgb = np.clip(small, 0, 255).astype(np.int32)
    pos = brightness_to_index(rgb.astype(np.float32), len(ramp), brightness_mode)
    chars = np.array(ramp, dtype=object)[pos]

    lines = []
    for y in range(rows):
        parts = []
        prev = None
        for x in range(cols):
            c = (int(rgb[y, x, 0]), int(rgb[y, x, 1]), int(rgb[y, x, 2]))
            if c != prev:
                parts.append(f"\x1b[38;2;{c[0]};{c[1]};{c[2]}m")
                prev = c
            parts.append(chars[y, x] * reps)
        lines.append("".join(parts))
    return lines, rows, cols * reps


# ==========================================================================
# 2. ANSI parsing -> character grid
# ==========================================================================

CSI_RE = re.compile(r"\x1b\[([0-9;:?<>=]*)([@-~])")
OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
OTHER_ESC_RE = re.compile(r"\x1b[()#][0-9A-Za-z]|\x1b[=>NOc78]")

# Windows Terminal "Campbell" palette, used to resolve 4-bit and 8-bit ANSI
# colour indices. Select an alternative with --palette.
PALETTE_CAMPBELL = [
    (12, 12, 12), (197, 15, 31), (19, 161, 14), (193, 156, 0),
    (0, 55, 218), (136, 23, 152), (58, 150, 221), (204, 204, 204),
    (118, 118, 118), (231, 72, 86), (22, 198, 12), (249, 241, 165),
    (59, 120, 255), (180, 0, 158), (97, 214, 214), (242, 242, 242),
]
PALETTE_VSCODE = [
    (0, 0, 0), (205, 49, 49), (13, 188, 121), (229, 229, 16),
    (36, 114, 200), (188, 63, 188), (17, 168, 205), (229, 229, 229),
    (102, 102, 102), (241, 76, 76), (35, 209, 139), (245, 245, 67),
    (59, 142, 234), (214, 112, 214), (41, 184, 219), (255, 255, 255),
]
PALETTES = {"campbell": PALETTE_CAMPBELL, "vscode": PALETTE_VSCODE}


def xterm256(n: int, palette) -> tuple:
    """Map an 8-bit (256 colour) index to RGB."""
    if n < 16:
        return palette[n]
    if n < 232:
        n -= 16
        levels = (0, 95, 135, 175, 215, 255)
        return (levels[n // 36 % 6], levels[n // 6 % 6], levels[n % 6])
    v = 8 + (n - 232) * 10
    return (v, v, v)


class Cell:
    __slots__ = ("ch", "fg", "bg", "bold")

    def __init__(self, ch, fg, bg, bold):
        self.ch, self.fg, self.bg, self.bold = ch, fg, bg, bold


class Grid:
    def __init__(self, rows, cols):
        self.rows = rows          # list[list[Cell]]
        self.cols = cols
        self.nrows = len(rows)

    @property
    def aspect_cells(self):
        return self.cols, self.nrows


def parse_ansi(text: str, default_fg=(204, 204, 204), default_bg=None,
               palette_name="campbell", tab=8, trim_blank_edges=True) -> Grid:
    """Parse an ANSI/SGR stream into a rectangular grid of coloured cells."""
    palette = PALETTES[palette_name]
    text = OSC_RE.sub("", text)
    text = OTHER_ESC_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\x1b[K", "")

    fg, bg, bold, reverse = default_fg, default_bg, False, False
    rows, line = [], []
    pos = 0

    def flush_line():
        rows.append(line[:])
        line.clear()

    for m in CSI_RE.finditer(text):
        chunk = text[pos:m.start()]
        pos = m.end()
        for ch in chunk:
            if ch == "\n":
                flush_line()
            elif ch == "\r":
                line.clear()
            elif ch == "\t":
                pad = tab - (len(line) % tab)
                for _ in range(pad):
                    line.append(Cell(" ", fg, bg, False))
            elif ch in ("\x00", "\x07", "\x08", "\x0b", "\x0c"):
                continue
            else:
                f, b = (bg or (0, 0, 0), fg) if reverse else (fg, bg)
                line.append(Cell(ch, f, b, bold))

        if m.group(2) != "m":
            continue  # cursor moves etc. are ignored - this art is line-linear

        params = m.group(1)
        codes = [p for p in params.replace(":", ";").split(";")]
        i = 0
        while i < len(codes):
            c = codes[i]
            n = int(c) if c.isdigit() else 0
            if n == 0:
                fg, bg, bold, reverse = default_fg, default_bg, False, False
            elif n == 1:
                bold = True
            elif n in (21, 22):
                bold = False
            elif n == 7:
                reverse = True
            elif n == 27:
                reverse = False
            elif 30 <= n <= 37:
                fg = palette[n - 30]
            elif 90 <= n <= 97:
                fg = palette[n - 90 + 8]
            elif 40 <= n <= 47:
                bg = palette[n - 40]
            elif 100 <= n <= 107:
                bg = palette[n - 100 + 8]
            elif n == 39:
                fg = default_fg
            elif n == 49:
                bg = default_bg
            elif n in (38, 48):
                mode = int(codes[i + 1]) if i + 1 < len(codes) and codes[i + 1].isdigit() else -1
                if mode == 2 and i + 4 < len(codes):
                    col = tuple(int(codes[i + 2 + k] or 0) for k in range(3))
                    i += 4
                elif mode == 5 and i + 2 < len(codes):
                    col = xterm256(int(codes[i + 2] or 0), palette)
                    i += 2
                else:
                    i += 1
                    col = None
                if col is not None:
                    col = tuple(max(0, min(255, v)) for v in col)
                    if n == 38:
                        fg = col
                    else:
                        bg = col
            i += 1

    for ch in text[pos:]:
        if ch == "\n":
            flush_line()
        elif ch == "\r":
            line.clear()
        elif ch not in ("\x00", "\x07", "\x08", "\x0b", "\x0c"):
            f, b = (bg or (0, 0, 0), fg) if reverse else (fg, bg)
            line.append(Cell(ch, f, b, bold))
    if line:
        flush_line()

    # Terminal captures usually carry a stray blank line at one or both ends.
    # At most two are trimmed per side: with the block and braille ramps a row
    # of spaces can be legitimate dark content rather than padding.
    if trim_blank_edges:
        def blank(r):
            return all(c.ch == " " and c.bg is None for c in r)

        for _ in range(2):
            if rows and blank(rows[0]):
                rows.pop(0)
        for _ in range(2):
            if rows and blank(rows[-1]):
                rows.pop()

    cols = max((len(r) for r in rows), default=0)
    for r in rows:
        while len(r) < cols:
            r.append(Cell(" ", default_fg, default_bg, False))
    return Grid(rows, cols)


# ==========================================================================
# 3. Glyph atlas + rasterisation
# ==========================================================================

FONT_CANDIDATES = [
    # Windows
    r"C:\Windows\Fonts\CascadiaCode.ttf",
    r"C:\Windows\Fonts\consola.ttf",
    r"C:\Windows\Fonts\terminal.ttf",
    r"C:\Windows\Fonts\lucon.ttf",
    # macOS
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/SFNSMono.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf",
]

# Consulted per-glyph when the primary font lacks a codepoint. Several common
# monospaced fonts, DejaVu Sans Mono among them, carry no Braille Patterns.
FALLBACK_CANDIDATES = [
    r"C:\Windows\Fonts\seguisym.ttf",
    r"C:\Windows\Fonts\DejaVuSans.ttf",
    "/System/Library/Fonts/Apple Symbols.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
    "/usr/share/fonts/truetype/unifont/unifont.ttf",
]

FULL_BLOCK = "\u2588"
NOTDEF_PROBE = chr(0x0FFFFD)   # unassigned plane-15 codepoint: renders as .notdef


def find_font(explicit=None):
    if explicit:
        if not os.path.isfile(explicit):
            raise SystemExit(f"Font not found: {explicit}")
        return explicit
    for p in FONT_CANDIDATES:
        if os.path.isfile(p):
            return p
    raise SystemExit("No monospaced font found - pass --font /path/to/font.ttf")


class GlyphAtlas:
    """Rasterise each distinct character once into a cell-sized coverage mask.

    When the primary font has no glyph for a codepoint, detected by comparing
    the render against that font's own .notdef, a secondary font supplies it.
    """

    def __init__(self, font_path, cell_w, cell_h, glyph_scale=1.0,
                 baseline_nudge=0.0, bold_stroke=0.0, block_fix=True,
                 supersample=2, fallbacks=None):
        self.cw, self.ch_ = int(cell_w), int(cell_h)
        self.ss = max(1, int(supersample))
        self.block_fix = block_fix
        self.bold_stroke = bold_stroke
        self.baseline_nudge = baseline_nudge
        self.target_adv = self.cw * self.ss * glyph_scale

        self.fonts = []          # list of (path, ImageFont, baseline, notdef_mask)
        self._add_font(font_path)
        for fp in (fallbacks if fallbacks is not None else FALLBACK_CANDIDATES):
            if fp and os.path.isfile(fp) and fp != font_path:
                self._add_font(fp)

        self.path = font_path
        self.size = self.fonts[0][1].size
        self.font = self.fonts[0][1]
        self._cache = {}
        self.used_fallback = set()
        self.missing = set()

    def _add_font(self, path):
        size = self._fit_size(path, self.target_adv)
        font = ImageFont.truetype(path, size)
        asc, desc = font.getmetrics()
        H = self.ch_ * self.ss
        baseline = (H - (asc + desc)) / 2.0 + asc + self.baseline_nudge * H
        entry = [path, font, baseline, None]
        entry[3] = self._draw(NOTDEF_PROBE, entry, False).tobytes()
        self.fonts.append(entry)

    @staticmethod
    def _fit_size(font_path, target_adv):
        lo, hi, best = 4, 2000, 4
        while lo <= hi:
            mid = (lo + hi) // 2
            f = ImageFont.truetype(font_path, mid)
            adv = f.getlength("M" * 8) / 8.0
            if adv <= target_adv:
                best, lo = mid, mid + 1
            else:
                hi = mid - 1
        return best

    def _draw(self, ch, entry, bold):
        """Render one glyph at supersampled size; returns a uint8 array."""
        W, H = self.cw * self.ss, self.ch_ * self.ss
        img = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(img)
        stroke = int(round(self.bold_stroke * self.ss)) if bold else 0
        d.text((W / 2.0, entry[2]), ch, font=entry[1], fill=255, anchor="ms",
               stroke_width=stroke, stroke_fill=255)
        return np.asarray(img, dtype=np.uint8)

    def mask(self, ch, bold=False):
        key = (ch, bold)
        m = self._cache.get(key)
        if m is not None:
            return m

        W, H = self.cw * self.ss, self.ch_ * self.ss
        if self.block_fix and ch == FULL_BLOCK:
            arr = np.full((H, W), 255, np.uint8)
        else:
            arr = None
            for i, entry in enumerate(self.fonts):
                a = self._draw(ch, entry, bold)
                if a.tobytes() != entry[3] or ch == NOTDEF_PROBE:
                    arr = a
                    if i:
                        self.used_fallback.add((ch, os.path.basename(entry[0])))
                    break
            if arr is None:
                self.missing.add(ch)
                arr = self._draw(ch, self.fonts[0], bold)

        img = Image.fromarray(arr, "L")
        if self.ss > 1:
            img = img.resize((self.cw, self.ch_), Image.LANCZOS)
        m = np.asarray(img, dtype=np.float32) / 255.0
        np.clip(m, 0.0, 1.0, out=m)
        self._cache[key] = m
        return m

    def warm(self, chars):
        """Pre-render every glyph so fallback and coverage reporting is complete."""
        for c in chars:
            self.mask(c)
        return self


# ==========================================================================
# 4. Layout
# ==========================================================================

@dataclass
class Layout:
    cols: int
    rows: int
    cell_w: int
    cell_h: int
    img_w: int
    img_h: int
    canvas_w: int
    canvas_h: int
    off_x: int
    off_y: int
    dpi: int


def plan_layout(grid, *, dpi=300, width_in=None, height_in=None,
                px_width=None, px_height=None, cell_aspect=2.0,
                margin_in=0.0, fit="contain"):
    """Work out integer cell sizes and canvas geometry."""
    cols, rows = grid.cols, grid.nrows
    if cols == 0 or rows == 0:
        raise SystemExit("Empty grid - nothing to render.")

    margin_px = int(round(margin_in * dpi))

    if px_width is None and width_in is not None:
        px_width = int(round(width_in * dpi))
    if px_height is None and height_in is not None:
        px_height = int(round(height_in * dpi))

    if px_width is None and px_height is None:
        px_width = 3600  # sensible default: 12in @ 300dpi

    if px_width is not None and px_height is not None:
        avail_w = max(1, px_width - 2 * margin_px)
        avail_h = max(1, px_height - 2 * margin_px)
        cw_f = avail_w / cols
        ch_f = avail_h / rows
        if fit == "contain":
            s = min(cw_f, ch_f / cell_aspect)
            cw_f, ch_f = s, s * cell_aspect
        elif fit == "cover":
            s = max(cw_f, ch_f / cell_aspect)
            cw_f, ch_f = s, s * cell_aspect
        elif fit != "stretch":
            raise SystemExit(f"Unknown fit mode {fit}")
        cell_w, cell_h = max(1, int(round(cw_f))), max(1, int(round(ch_f)))
        canvas_w, canvas_h = px_width, px_height
    else:
        if px_width is not None:
            cell_w = max(1, int(round((px_width - 2 * margin_px) / cols)))
            cell_h = max(1, int(round(cell_w * cell_aspect)))
        else:
            cell_h = max(1, int(round((px_height - 2 * margin_px) / rows)))
            cell_w = max(1, int(round(cell_h / cell_aspect)))
        canvas_w = cols * cell_w + 2 * margin_px
        canvas_h = rows * cell_h + 2 * margin_px

    img_w, img_h = cols * cell_w, rows * cell_h
    off_x = (canvas_w - img_w) // 2
    off_y = (canvas_h - img_h) // 2
    return Layout(cols, rows, cell_w, cell_h, img_w, img_h,
                  canvas_w, canvas_h, off_x, off_y, dpi)


def rasterise(grid, layout, atlas, bg_color=(0, 0, 0)):
    """Composite the grid into a float32 sRGB [0,1] image."""
    cw, ch = layout.cell_w, layout.cell_h
    # Render into an image-sized buffer, then place onto the canvas.
    buf = np.empty((layout.img_h, layout.img_w, 3), dtype=np.float32)
    buf[:] = np.asarray(bg_color, np.float32) / 255.0

    x0s = np.arange(layout.cols) * cw
    for r, row in enumerate(grid.rows):
        y0 = r * ch
        if y0 + ch > layout.img_h:
            break
        tile_row = buf[y0:y0 + ch]
        for c, cell in enumerate(row[:layout.cols]):
            has_bg = cell.bg is not None
            dark_fg = max(cell.fg) < 2
            if not has_bg and (cell.ch == " " or dark_fg):
                continue
            x0 = x0s[c]
            tile = tile_row[:, x0:x0 + cw]
            if has_bg:
                tile[:] = np.asarray(cell.bg, np.float32) / 255.0
            if cell.ch != " ":
                m = atlas.mask(cell.ch, cell.bold)[..., None]
                fg = np.asarray(cell.fg, np.float32) / 255.0
                tile *= (1.0 - m)
                tile += m * fg

    if (layout.canvas_w, layout.canvas_h) == (layout.img_w, layout.img_h):
        return buf
    canvas = np.empty((layout.canvas_h, layout.canvas_w, 3), dtype=np.float32)
    canvas[:] = np.asarray(bg_color, np.float32) / 255.0
    sx, sy = layout.off_x, layout.off_y
    # handle both letterboxing (positive offset) and cropping (negative)
    src_x0, dst_x0 = (0, sx) if sx >= 0 else (-sx, 0)
    src_y0, dst_y0 = (0, sy) if sy >= 0 else (-sy, 0)
    w = min(layout.img_w - src_x0, layout.canvas_w - dst_x0)
    h = min(layout.img_h - src_y0, layout.canvas_h - dst_y0)
    canvas[dst_y0:dst_y0 + h, dst_x0:dst_x0 + w] = buf[src_y0:src_y0 + h, src_x0:src_x0 + w]
    return canvas


# ==========================================================================
# 5. CRT post-processing
# ==========================================================================

@dataclass
class CRT:
    """CRT post-processing parameters.

    All spatial values are expressed in cell units, so a look tuned at one
    output resolution reproduces identically at any other.
    """
    # optics
    focus: float = 0.045           # beam defocus, in cell widths
    bloom: float = 0.50            # phosphor glow strength
    bloom_radius: float = 0.35     # in cell heights
    bloom_threshold: float = 0.35
    halation: float = 0.30         # red bias of the widest glow halo
    # analogue signal
    chroma_bleed: float = 0.40     # horizontal chroma smear, in cell widths
    luma_bleed: float = 0.05       # horizontal luma smear, in cell widths
    # raster structure
    scanline_depth: float = 0.75
    scanlines_per_row: float = 3.0
    scanline_sigma: float = 0.19    # beam half-width as a fraction of pitch
    scanline_shape: float = 1.0     # 1 = gaussian beam, >4 = hard square wave
    scanline_phase: float = 0.0     # shift the raster relative to the text grid
    mask_strength: float = 0.0     # aperture grille (off by default)
    mask_pitch: float = 0.34       # in cell widths
    # colour / tube
    phosphor: str = "color"        # color | green | amber | white | blue
    saturation: float = 1.06
    black_level: float = 0.012
    contrast: float = 1.05
    brightness: float = 1.0
    gamma: float = 1.0
    beam_gain: float = 0.75        # 0=none, 1=fully restore pre-CRT highlights
    # imperfections
    sharpen: float = 0.0           # unsharp amount, applied after the optics
    sharpen_radius: float = 0.12   # in cell widths
    noise: float = 0.010
    noise_grain: float = 2.0       # px
    hum: float = 0.0
    vignette: float = 0.22
    vignette_power: float = 2.2
    seed: int = 7


PHOSPHORS = {
    "color": None,
    "green": (0.30, 1.00, 0.42),
    "amber": (1.00, 0.62, 0.15),
    "white": (0.94, 0.97, 1.00),
    "blue": (0.45, 0.72, 1.00),
}

PRESETS = {
    "none": dict(focus=0, bloom=0, chroma_bleed=0, luma_bleed=0, scanline_depth=0,
                 mask_strength=0, saturation=1, black_level=0, contrast=1,
                 noise=0, vignette=0, beam_gain=0),
    "subtle": dict(focus=0.03, bloom=0.28, bloom_radius=0.38, chroma_bleed=0.22,
                   luma_bleed=0.03, scanline_depth=0.45, scanline_sigma=0.24,
                   noise=0.007, vignette=0.14),
    "classic": dict(),  # dataclass defaults
    "heavy": dict(focus=0.08, bloom=0.80, bloom_radius=0.65, bloom_threshold=0.26,
                  halation=0.45, chroma_bleed=0.75, luma_bleed=0.11,
                  scanline_depth=1.0, scanline_sigma=0.15, mask_strength=0.20,
                  saturation=1.15,
                  black_level=0.025, contrast=1.10, noise=0.018, hum=0.015,
                  vignette=0.38),
    "crisp": dict(focus=0.0, luma_bleed=0.0, chroma_bleed=0.25, bloom=0.22,
                  bloom_radius=0.22, bloom_threshold=0.55, halation=0.15,
                  scanline_depth=0.7, scanline_sigma=0.17, sharpen=0.35,
                  noise=0.008, vignette=0.16),
    # Screen-shader look: hard square-wave scanlines, no optics, deep blacks
    "clean": dict(focus=0.0, luma_bleed=0.0, chroma_bleed=0.0, bloom=0.4,
                  halation=0.0, scanline_depth=0.91, scanline_sigma=0.25,
                  scanline_shape=8.0, scanlines_per_row=4.0, scanline_phase=0.25,
                  beam_gain=0.0, saturation=1.15, black_level=0.0, contrast=1.0, brightness=1.0,
                  sharpen=0.0, noise=0.0, vignette=0.0),
    "green": dict(phosphor="green", bloom=0.70, bloom_radius=0.55, halation=0.0,
                  chroma_bleed=0.0, luma_bleed=0.06, scanline_depth=0.85,
                  scanline_sigma=0.17, black_level=0.018, contrast=1.08,
                  noise=0.014, vignette=0.32),
    "amber": dict(phosphor="amber", bloom=0.70, bloom_radius=0.55, halation=0.15,
                  chroma_bleed=0.0, luma_bleed=0.06, scanline_depth=0.85,
                  scanline_sigma=0.17, black_level=0.018, contrast=1.08,
                  noise=0.014, vignette=0.32),
}


def make_crt(preset="classic", overrides=None):
    p = CRT(**PRESETS.get(preset, {}))
    if overrides:
        p = replace(p, **overrides)
    return p


# Fast separable blurs

def _box1d(a, radius, axis):
    r = int(round(radius))
    if r < 1:
        return a
    a = np.moveaxis(a, axis, 0)
    pad = np.concatenate([np.repeat(a[:1], r + 1, 0), a, np.repeat(a[-1:], r, 0)], 0)
    cs = np.cumsum(pad, axis=0, dtype=np.float32)
    out = (cs[2 * r + 1:] - cs[:-(2 * r + 1)]) * np.float32(1.0 / (2 * r + 1))
    return np.moveaxis(out, 0, axis)


def blur_axis(a, sigma, axis, passes=3):
    """Gaussian approximation via repeated box blur along one axis."""
    if sigma <= 0.05:
        return a
    r = max(1, int(round(sigma * 1.24)))
    for _ in range(passes):
        a = _box1d(a, r, axis)
    return a


def blur(a, sigma):
    """Isotropic blur; large radii are computed on a downsampled copy."""
    if sigma <= 0.05:
        return a
    f = 1
    while sigma / f > 6 and min(a.shape[0], a.shape[1]) // (f * 2) > 32:
        f *= 2
    if f > 1:
        h, w = a.shape[0] // f * f, a.shape[1] // f * f
        small = a[:h, :w].reshape(h // f, f, w // f, f, -1).mean(axis=(1, 3))
        small = blur_axis(blur_axis(small, sigma / f, 0), sigma / f, 1)
        up = np.repeat(np.repeat(small, f, axis=0), f, axis=1)
        out = np.empty_like(a)
        out[:h, :w] = up
        if h < a.shape[0]:
            out[h:] = out[h - 1:h]
        if w < a.shape[1]:
            out[:, w:] = out[:, w - 1:w]
        return blur_axis(blur_axis(out, f * 0.6, 0), f * 0.6, 1)
    return blur_axis(blur_axis(a, sigma, 0), sigma, 1)


def srgb_to_linear(x):
    return np.where(x <= 0.04045, x / 12.92,
                    np.power((np.clip(x, 0, None) + 0.055) / 1.055, 2.4)).astype(np.float32)


def linear_to_srgb(x):
    x = np.clip(x, 0.0, None)
    return np.where(x <= 0.0031308, x * 12.92,
                    1.055 * np.power(x, 1.0 / 2.4) - 0.055).astype(np.float32)


def apply_crt(img, cell_w, cell_h, p: CRT, verbose=False):
    """img: float32 sRGB [0,1] HxWx3. Returns float32 sRGB [0,1]."""
    rng = np.random.default_rng(p.seed)
    H, W = img.shape[:2]

    def log(s):
        if verbose:
            print(f"    crt: {s}", flush=True)

    # 1. composite-video style horizontal bleed (done on the gamma signal,
    #        as a real encoder would: chroma bandwidth is far below luma).
    if p.chroma_bleed > 0 or p.luma_bleed > 0:
        log("chroma/luma bleed")
        y = img @ LUMA601
        cb = img - y[..., None]
        if p.chroma_bleed > 0:
            cb = blur_axis(cb, p.chroma_bleed * cell_w, 1)
        if p.luma_bleed > 0:
            y = blur_axis(y[..., None], p.luma_bleed * cell_w, 1)[..., 0]
        img = np.clip(y[..., None] + cb, 0.0, 4.0)

    # 2. everything below is light, so work in linear light.
    lin = srgb_to_linear(img)
    del img
    ref_hi = float(np.percentile(lin @ LUMA, 99.5)) if p.beam_gain > 0 else 0.0

    if p.focus > 0:
        log("beam defocus")
        lin = blur(lin, p.focus * cell_w)

    # 3. phosphor glow / halation
    if p.bloom > 0:
        log("bloom + halation")
        lum = lin @ LUMA
        thr = p.bloom_threshold
        over = np.clip(lum - thr, 0, None) / max(1e-4, 1.0 - thr)
        src = lin * (over / np.maximum(lum, 1e-4))[..., None]
        r = p.bloom_radius * cell_h
        del over, lum
        for weight, radius, tinted in ((0.55, r * 0.30, False),
                                       (0.35, r * 1.00, False),
                                       (0.10, r * 2.50, True)):
            g = blur(src, radius)
            g *= np.float32(p.bloom * weight)
            if tinted and p.halation > 0:
                g *= np.array([1.0 + p.halation, 1.0 - 0.25 * p.halation,
                               1.0 - 0.55 * p.halation], np.float32)
            lin += g
            del g
        del src

    # 4. raster structure: scanlines
    if p.scanline_depth > 0 and p.scanlines_per_row > 0:
        log("scanlines")
        pitch = cell_h / p.scanlines_per_row
        # Integrate the beam over each pixel instead of point-sampling it.
        # At fine pitches (2-3 px) point sampling can land on symmetric points
        # and cancel the modulation completely.
        SS = 16
        yy = (np.arange(H * SS, dtype=np.float32) + 0.5) / SS
        frac = (yy / pitch + p.scanline_phase) % 1.0
        d = np.abs(frac - 0.5) / max(0.03, p.scanline_sigma)
        # super-gaussian: shape=1 is a round beam, high shape is a square wave
        # whose bright duty cycle is 2 * scanline_sigma
        beam = np.exp(-0.5 * d ** (2.0 * max(1.0, p.scanline_shape)))
        prof = ((1.0 - p.scanline_depth) + p.scanline_depth * beam)
        prof = prof.reshape(H, SS).mean(axis=1)
        prof /= prof.mean()          # preserve overall exposure
        lin *= prof[:, None, None]

    # 5. aperture grille / shadow mask
    if p.mask_strength > 0:
        log("aperture mask")
        sub = max(1.0, p.mask_pitch * cell_w / 3.0)
        idx = (np.arange(W) / sub).astype(np.int32) % 3
        m = np.full((W, 3), 1.0 - p.mask_strength, np.float32)
        m[np.arange(W), idx] = 1.0
        m = blur_axis(m[None, ...], sub * 0.35, 1)[0]
        m /= m.mean()
        lin *= m[None, :, :]

    # 6. mains hum / slow vertical brightness ripple
    if p.hum > 0:
        yy = np.arange(H, dtype=np.float32) / H
        lin *= (1.0 + p.hum * np.sin(2 * np.pi * (yy * 3.0 + 0.2)))[:, None, None]

    # 6b. Beam gain. Blurring thin strokes costs peak brightness, so the
    #     highlight level measured before the optics is restored here.
    if p.beam_gain > 0 and ref_hi > 1e-5:
        cur = float(np.percentile(lin @ LUMA, 99.5))
        if cur > 1e-6:
            g = min(4.0, max(1.0, ref_hi / cur)) ** p.beam_gain
            log(f"beam gain x{g:.2f}")
            lin *= g

    # 7. tube colour
    ph = PHOSPHORS.get(p.phosphor)
    if ph is None and p.phosphor != "color":
        raise SystemExit(f"Unknown phosphor {p.phosphor}")
    if ph is not None:
        log(f"{p.phosphor} phosphor")
        lum = lin @ LUMA
        lin = lum[..., None] * srgb_to_linear(np.asarray(ph, np.float32))
    elif p.saturation != 1.0:
        lum = (lin @ LUMA)[..., None]
        lin = lum + (lin - lum) * p.saturation

    # 8. tube transfer: black level lift, contrast, brightness, gamma
    if p.black_level:
        lin = lin * (1.0 - p.black_level) + p.black_level
    if p.contrast != 1.0:
        lin = np.clip(lin, 0, None)
        lin = np.power(lin, p.contrast) * (0.5 ** (1.0 - p.contrast))
    if p.brightness != 1.0:
        lin *= p.brightness
    if p.gamma != 1.0:
        lin = np.power(np.clip(lin, 0, None), 1.0 / p.gamma)

    # 8b. Optional unsharp mask, recovering acutance lost to the optics
    if p.sharpen > 0:
        log("sharpen")
        lin = lin + p.sharpen * (lin - blur(lin, max(0.5, p.sharpen_radius * cell_w)))
        np.clip(lin, 0.0, None, out=lin)

    # 9. vignette (tube corners fall off)
    if p.vignette > 0:
        log("vignette")
        yy = (np.arange(H, dtype=np.float32) / (H - 1) * 2 - 1) ** 2
        xx = (np.arange(W, dtype=np.float32) / (W - 1) * 2 - 1) ** 2
        rr = np.sqrt(yy[:, None] + xx[None, :]) / math.sqrt(2.0)
        lin *= np.clip(1.0 - p.vignette * rr ** p.vignette_power, 0, 1)[..., None]

    out = linear_to_srgb(np.clip(lin, 0.0, 1.0))
    del lin

    # 10. analogue grain (in display space; also dithers 8-bit banding)
    if p.noise > 0:
        log("grain")
        g = max(1.0, p.noise_grain)
        sh = (max(2, int(H / g)), max(2, int(W / g)))
        n = rng.standard_normal(sh).astype(np.float32)
        n = np.asarray(Image.fromarray(n, "F").resize((W, H), Image.BILINEAR),
                       dtype=np.float32)
        amp = p.noise * (0.25 + 0.75 * np.sqrt(np.clip(out @ LUMA, 0, 1)))
        out += n[..., None] * amp[..., None]

    return np.clip(out, 0.0, 1.0)


# ==========================================================================
# 6. Output writers
# ==========================================================================

def _quantize(arr01, bits, rng=None):
    maxv = (1 << bits) - 1
    x = np.clip(arr01, 0, 1) * maxv
    if rng is not None:  # TPDF dither kills banding in smooth glows
        x += rng.random(x.shape, dtype=np.float32) - rng.random(x.shape, dtype=np.float32)
    return np.clip(np.rint(x), 0, maxv).astype(np.uint16 if bits > 8 else np.uint8)


def write_png16(path, arr_u16, dpi):
    H, W = arr_u16.shape[:2]

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    raw = np.empty((H, W * 6 + 1), dtype=np.uint8)
    raw[:, 0] = 0
    raw[:, 1:] = arr_u16.astype(">u2").view(np.uint8).reshape(H, W * 6)
    ppm = int(round(dpi / 0.0254))
    out = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 16, 2, 0, 0, 0))
           + chunk(b"pHYs", struct.pack(">IIB", ppm, ppm, 1))
           + chunk(b"IDAT", zlib.compress(raw.tobytes(), 6))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(out)


def write_tiff16(path, arr_u16, dpi, compress=True):
    H, W = arr_u16.shape[:2]
    data = arr_u16.astype("<u2").tobytes()
    comp = 8 if compress else 1
    if compress:
        data = zlib.compress(data, 6)

    entries = []          # (tag, type, count, value_or_payload)
    extra = bytearray()
    header = 8
    n_tags = 15
    ifd_size = 2 + n_tags * 12 + 4
    extra_off = header + ifd_size

    def add(tag, typ, count, value=None, payload=None):
        entries.append((tag, typ, count, value, payload))

    add(256, 3, 1, W)
    add(257, 3, 1, H)
    add(258, 3, 3, payload=struct.pack("<3H", 16, 16, 16))
    add(259, 3, 1, comp)
    add(262, 3, 1, 2)
    add(273, 4, 1, 0)      # StripOffsets, patched below
    add(277, 3, 1, 3)
    add(278, 3, 1, H)
    add(279, 4, 1, len(data))
    add(282, 5, 1, payload=struct.pack("<2I", int(dpi), 1))
    add(283, 5, 1, payload=struct.pack("<2I", int(dpi), 1))
    add(284, 3, 1, 1)
    add(296, 3, 1, 2)
    add(339, 3, 3, payload=struct.pack("<3H", 1, 1, 1))
    add(305, 2, 9, payload=b"crtprint\x00")
    entries.sort(key=lambda e: e[0])
    assert len(entries) == n_tags

    resolved = []
    for tag, typ, count, value, payload in entries:
        if payload is not None:
            off = extra_off + len(extra)
            extra += payload + (b"\x00" if len(payload) % 2 else b"")
            resolved.append((tag, typ, count, struct.pack("<I", off)))
        else:
            if typ == 3:
                resolved.append((tag, typ, count, struct.pack("<HH", value, 0)))
            else:
                resolved.append((tag, typ, count, struct.pack("<I", value)))

    strip_off = extra_off + len(extra)
    out = bytearray(b"II" + struct.pack("<HI", 42, header))
    out += struct.pack("<H", n_tags)
    for tag, typ, count, val in resolved:
        if tag == 273:
            val = struct.pack("<I", strip_off)
        out += struct.pack("<HHI", tag, typ, count) + val
    out += struct.pack("<I", 0)
    out += extra
    assert len(out) == strip_off, (len(out), strip_off)
    out += data
    with open(path, "wb") as f:
        f.write(out)


def save_image(path, arr01, dpi, bit_depth=8, dither=True, tiff_compress=True):
    ext = os.path.splitext(path)[1].lower()
    rng = np.random.default_rng(1234) if (dither and bit_depth == 8) else None
    if bit_depth == 16:
        a = _quantize(arr01, 16)
        if ext in (".tif", ".tiff"):
            write_tiff16(path, a, dpi, tiff_compress)
        else:
            if ext != ".png":
                path = os.path.splitext(path)[0] + ".png"
                print(f"  (16-bit output written as PNG: {path})")
            write_png16(path, a, dpi)
    else:
        a = _quantize(arr01, 8, rng)
        im = Image.fromarray(a, "RGB")
        if ext in (".tif", ".tiff"):
            im.save(path, dpi=(dpi, dpi),
                    compression="tiff_deflate" if tiff_compress else None)
        else:
            im.save(path, dpi=(dpi, dpi), optimize=False, compress_level=6)
    return path


# ==========================================================================
# 7. SVG output
# ==========================================================================

SVG_ESC = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}


def esc(s):
    return "".join(SVG_ESC.get(c, c) for c in s)


def write_svg(path, grid, cell_w, cell_h, bg="#000000", transparent=False,
              font_family="Fira Code, DejaVu Sans Mono, Consolas, monospace"):
    """Write the grid as vector text.

    Each run of same-coloured characters becomes one <text> element with an
    explicit textLength, which keeps spacing exact regardless of which font the
    viewer substitutes.
    """
    W, H = grid.cols * cell_w, grid.nrows * cell_h
    font_size = cell_h * 0.78
    baseline = cell_h * 0.76

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}">',
           f'<style>text{{font-family:{font_family};font-size:{font_size:.2f}px;'
           f'white-space:pre;dominant-baseline:alphabetic}}</style>']
    if not transparent:
        out.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{bg}"/>')

    for r, row in enumerate(grid.rows):
        y = r * cell_h + baseline
        c = 0
        while c < len(row):
            fg = row[c].fg
            start = c
            buf = []
            while c < len(row) and row[c].fg == fg:
                buf.append(row[c].ch)
                c += 1
            text = "".join(buf)
            if text.strip() == "":
                continue
            n = len(text)
            col = "#%02x%02x%02x" % fg
            out.append(f'<text x="{start*cell_w}" y="{y:.2f}" fill="{col}" '
                       f'textLength="{n*cell_w}" lengthAdjust="spacingAndGlyphs">'
                       f'{esc(text)}</text>')
    out.append("</svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    return path


# ==========================================================================
# 8. Pipeline
# ==========================================================================

def prepare(text, args, verbose=True):
    """Parse -> layout -> rasterise. Returns (grid, layout, atlas, sRGB image)."""
    grid = parse_ansi(text, default_fg=parse_color(args.fg), default_bg=None,
                      palette_name=args.palette,
                      trim_blank_edges=not args.no_trim)
    layout = plan_layout(grid, dpi=args.dpi, width_in=args.width_in,
                         height_in=args.height_in, px_width=args.px_width,
                         px_height=args.px_height, cell_aspect=args.cell_aspect,
                         margin_in=args.margin_in, fit=args.fit)

    font_path = find_font(args.font)
    chars = {c.ch for row in grid.rows for c in row}
    atlas = GlyphAtlas(font_path, layout.cell_w, layout.cell_h,
                       glyph_scale=args.glyph_scale,
                       baseline_nudge=args.baseline_nudge,
                       bold_stroke=args.bold_stroke,
                       block_fix=not args.no_block_fix,
                       supersample=args.supersample,
                       fallbacks=args.font_fallback).warm(chars)
    if atlas.used_fallback:
        srcs = sorted({f for _, f in atlas.used_fallback})
        n = len({c for c, _ in atlas.used_fallback})
        print(f"  note   : {n} glyph(s) not in {os.path.basename(font_path)}, "
              f"taken from {', '.join(srcs)}")
    if atlas.missing:
        print(f"  WARNING: no font has {''.join(sorted(atlas.missing))[:40]!r} - "
              f"these render blank. Pass --font-fallback FONT.ttf")
    if verbose:
        try:
            spr = build_params(args).scanlines_per_row
        except SystemExit:
            spr = None
        report(grid, layout, atlas, font_path, len(chars), spr)
    img = rasterise(grid, layout, atlas, bg_color=parse_color(args.bg))
    return grid, layout, atlas, img


def report(grid, layout, atlas, font_path, nchars, scan_per_row=None):
    dpi = layout.dpi
    print(f"  grid   : {grid.cols} cols x {grid.nrows} rows")
    print(f"  cell   : {layout.cell_w}x{layout.cell_h} px "
          f"({layout.cell_w/dpi:.3f}x{layout.cell_h/dpi:.3f} in)")
    print(f"  canvas : {layout.canvas_w}x{layout.canvas_h} px  "
          f"{layout.canvas_w/dpi:.2f}x{layout.canvas_h/dpi:.2f} in @ {dpi} dpi  "
          f"({layout.canvas_w*layout.canvas_h/1e6:.1f} MP)")
    if (layout.img_w, layout.img_h) != (layout.canvas_w, layout.canvas_h):
        kind = "letterboxed" if (layout.off_x >= 0 and layout.off_y >= 0) else "cropped"
        print(f"  art    : {layout.img_w}x{layout.img_h} px ({kind})")
    print(f"  font   : {os.path.basename(font_path)} @ {atlas.size}px, {nchars} glyphs")
    if scan_per_row:
        pitch = layout.cell_h / scan_per_row
        warn = ""
        if pitch < 3:
            warn = "  <- at this pitch scanline_phase matters; nudge it if bands vanish"
        elif pitch < 4:
            warn = "  <- too fine to print cleanly"
        print(f"  raster : scanline pitch {pitch:.1f} px "
              f"({pitch/dpi:.4f} in at {scan_per_row:g}/row){warn}")
    if layout.cell_w < 12:
        print(f"  NOTE   : cells are only {layout.cell_w}px wide, so CRT blur will "
              f"dominate the letterforms. For crisp characters aim for cell_w >= 16, "
              f"i.e. <= {int(layout.canvas_w/16)} columns at this width.")


def render(text, out_path, args, verbose=True):
    grid, layout, atlas, img = prepare(text, args, verbose)
    p = build_params(args)
    if verbose:
        print(f"  crt    : preset={args.preset}")
    img = apply_crt(img, layout.cell_w, layout.cell_h, p, verbose=verbose)
    out_path = save_image(out_path, img, layout.dpi, bit_depth=args.bit_depth,
                          tiff_compress=not args.no_tiff_compress)
    if verbose:
        print(f"  wrote  : {out_path}  ({os.path.getsize(out_path)/1e6:.1f} MB)")
    return out_path, layout, p


def sweep(text, out_path, args, key, values, verbose=True):
    """Build a contact sheet varying one CRT parameter, rasterising the grid once."""
    ftypes = {f.name: f.type for f in fields(CRT)}
    key = key.replace("-", "_")
    if key not in ftypes:
        raise SystemExit(f"Unknown CRT parameter {key!r}. See --list-params.")
    grid, layout, atlas, img = prepare(text, args, verbose)
    base = build_params(args)

    tiles = []
    for v in values:
        p = replace(base, **{key: _coerce(ftypes[key], v)})
        print(f"  sweep  : {key}={v}")
        o = apply_crt(img.copy(), layout.cell_w, layout.cell_h, p, verbose=False)
        im = Image.fromarray(_quantize(o, 8), "RGB")
        t = args.sweep_tile
        # A 1:1 centre crop preserves the texture that downscaling would hide
        if args.sweep_full or im.width < t or im.height < t:
            im.thumbnail((t, t * 6), Image.LANCZOS)
        else:
            cx, cy = im.width // 2, im.height // 2
            im = im.crop((cx - t // 2, cy - t // 2, cx + t // 2, cy + t // 2))
        d = ImageDraw.Draw(im)
        label = f"{key}={v}"
        d.rectangle([0, 0, 10 + 6 * len(label), 17], fill=(0, 0, 0))
        d.text((4, 4), label, fill=(255, 255, 255))
        tiles.append(im)

    tw, th = tiles[0].size
    sheet = Image.new("RGB", (tw * len(tiles), th), (24, 24, 24))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * tw, 0))
    if not out_path.lower().endswith((".png", ".jpg", ".jpeg")):
        out_path = os.path.splitext(out_path)[0] + "_sweep.png"
    sheet.save(out_path)
    print(f"  wrote  : {out_path}  ({sheet.size[0]}x{sheet.size[1]})")
    return out_path


def show_in_terminal(lines):
    """Print the art to the console."""
    sys.stdout.write("\n".join(lines))
    sys.stdout.write("\x1b[0m\n")
    sys.stdout.flush()


# ==========================================================================
# 9. CLI
# ==========================================================================

def parse_color(s):
    if isinstance(s, (tuple, list)):
        return tuple(s)
    s = str(s).strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        raise SystemExit(f"Bad colour {s!r}, expected #rrggbb")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def _coerce(field_type, value):
    # `from __future__ import annotations` makes dataclass field types strings
    name = field_type if isinstance(field_type, str) else getattr(field_type, "__name__", "")
    if name == "float":
        return float(value)
    if name == "int":
        return int(value)
    if name == "str":
        return str(value)
    return value


def build_params(args):
    over = {}
    if args.params:
        with open(args.params) as f:
            over.update(json.load(f))
    ftypes = {f.name: f.type for f in fields(CRT)}
    for kv in args.set or []:
        if "=" not in kv:
            raise SystemExit(f"--set expects key=value, got {kv!r}")
        k, v = kv.split("=", 1)
        k = k.strip().replace("-", "_")
        if k not in ftypes:
            raise SystemExit(f"Unknown CRT parameter {k!r}. See --list-params.")
        over[k] = v
    unknown = set(over) - set(ftypes)
    if unknown:
        raise SystemExit(f"Unknown CRT parameters: {sorted(unknown)}")
    return make_crt(args.preset, {k: _coerce(ftypes[k], v) for k, v in over.items()})


def apply_preview(args):
    if args.preview:
        args.px_width = args.px_width or 1400
        if args.width_in and args.height_in:
            args.px_height = int(round(args.px_width * args.height_in / args.width_in))
        else:
            args.px_height = None
        args.width_in = args.height_in = None
        args.dpi = 96
        args.supersample = min(args.supersample, 2)
        args.bit_depth = 8


def build_parser():
    ap = argparse.ArgumentParser(
        prog="asciicrt.py",
        description="Convert an image into ASCII art and render it as a CRT-style print.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("image", nargs="?", help="source image file")

    g = ap.add_argument_group("ascii generation")
    g.add_argument("--rows", type=int, default=180, help="art height in character rows")
    g.add_argument("--cols", type=int, help="force a column count (default: from aspect)")
    g.add_argument("--ramp", default="bourke", help="density ramp name, or a literal ramp string")
    g.add_argument("--ramp-slice", type=int, default=40,
                   help="use only the first N ramp characters (0 = all)")
    g.add_argument("--gamma-y", type=float, default=1.0,
                   help=">1 lifts all channels toward white before mapping")
    g.add_argument("--brightness-mode", choices=["mean", "luma"], default="mean",
                   help="'mean' averages the channels equally; 'luma' is perceptually weighted")
    g.add_argument("--reps", type=int, default=2,
                   help="characters per source pixel horizontally")
    g.add_argument("--from-ansi", metavar="FILE", help="skip generation, load ANSI text")
    g.add_argument("--list-ramps", action="store_true")

    g = ap.add_argument_group("outputs (any combination)")
    g.add_argument("-o", "--out", help="raster output .png/.tif (default if none given)")
    g.add_argument("--show", action="store_true", help="print the art to the terminal")
    g.add_argument("--svg", metavar="FILE", help="write vector SVG")
    g.add_argument("--svg-transparent", action="store_true")
    g.add_argument("--dump-ansi", metavar="FILE", help="save the raw ANSI stream")
    g.add_argument("--no-raster", action="store_true", help="skip the raster render")

    g = ap.add_argument_group("output geometry")
    g.add_argument("--dpi", type=int, default=300)
    g.add_argument("--width-in", type=float, help="target print width in inches")
    g.add_argument("--height-in", type=float, help="target print height in inches")
    g.add_argument("--px-width", type=int, help="target width in pixels (overrides --width-in)")
    g.add_argument("--px-height", type=int)
    g.add_argument("--fit", choices=["contain", "cover", "stretch"], default="contain")
    g.add_argument("--margin-in", type=float, default=0.0)
    g.add_argument("--preview", action="store_true", help="fast 1400px render for tuning")

    g = ap.add_argument_group("typography")
    g.add_argument("--font", help="path to a monospaced .ttf/.otf")
    g.add_argument("--font-fallback", action="append", metavar="FONT",
                   help="extra font for glyphs the main font lacks (repeatable)")
    g.add_argument("--cell-aspect", type=float, default=2.0,
                   help="cell height / width; also sets the ASCII aspect")
    g.add_argument("--glyph-scale", type=float, default=1.0)
    g.add_argument("--baseline-nudge", type=float, default=0.0)
    g.add_argument("--bold-stroke", type=float, default=0.0)
    g.add_argument("--supersample", type=int, default=3)
    g.add_argument("--no-block-fix", action="store_true")
    g.add_argument("--no-trim", action="store_true")

    g = ap.add_argument_group("colour")
    g.add_argument("--bg", default="#000000")
    g.add_argument("--fg", default="#cccccc")
    g.add_argument("--palette", choices=sorted(PALETTES), default="campbell")

    g = ap.add_argument_group("CRT look")
    g.add_argument("--preset", choices=sorted(PRESETS), default="classic")
    g.add_argument("--params", help="JSON file of CRT parameter overrides")
    g.add_argument("--set", action="append", metavar="KEY=VAL",
                   help="override one CRT parameter (repeatable)")
    g.add_argument("--dump-params", metavar="FILE")
    g.add_argument("--list-params", action="store_true")
    g.add_argument("--sweep", metavar="KEY=V1,V2,V3",
                   help="contact sheet varying one parameter (implies --preview)")
    g.add_argument("--sweep-tile", type=int, default=460)
    g.add_argument("--sweep-full", action="store_true")

    g = ap.add_argument_group("file output")
    g.add_argument("--bit-depth", type=int, choices=[8, 16], default=16)
    g.add_argument("--no-tiff-compress", action="store_true")
    return ap


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)

    if args.list_ramps:
        print("Density ramps (dense -> sparse):")
        for k, v in RAMPS.items():
            print(f"  {k:<13} {len(v):>3} chars   {''.join(v[:22])}")
        print("\nAny other string longer than 3 characters is used as a literal ramp.")
        return 0

    if args.list_params:
        p = CRT()
        w = max(len(f.name) for f in fields(CRT))
        print("CRT parameters (spatial values are in cell units):")
        for f in fields(CRT):
            print(f"  {f.name:<{w}}  default={getattr(p, f.name)}")
        print("\nPresets:", ", ".join(sorted(PRESETS)))
        return 0

    # Obtain the ANSI, either by generating it or by loading it
    if args.from_ansi:
        with open(args.from_ansi, encoding="utf-8", errors="replace") as f:
            text = f.read()
        lines = text.split("\n")
        stem = os.path.splitext(args.from_ansi)[0]
    else:
        if not args.image:
            ap.error("an image is required (or use --from-ansi FILE)")
        if not os.path.isfile(args.image):
            raise SystemExit(f"Source file doesn't exist: {args.image}")
        ramp = resolve_ramp(args.ramp, args.ramp_slice)
        lines, nrows, ncols = image_to_ansi(
            args.image, args.rows, ramp, gamma_y=args.gamma_y,
            cell_aspect=args.cell_aspect, reps=args.reps,
            brightness_mode=args.brightness_mode, cols=args.cols)
        print(f"  ascii  : {ncols}x{nrows} chars, ramp={args.ramp}[{len(ramp)}], "
              f"gamma_y={args.gamma_y}, brightness={args.brightness_mode}")
        text = "\n".join(lines)
        stem = os.path.splitext(args.image)[0]

    if args.show:
        show_in_terminal(lines)
    if args.dump_ansi:
        with open(args.dump_ansi, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"  ansi   : {args.dump_ansi}")

    if args.sweep:
        args.preview = True
    apply_preview(args)

    # Vector output
    if args.svg:
        grid = parse_ansi(text, default_fg=parse_color(args.fg),
                          palette_name=args.palette, trim_blank_edges=not args.no_trim)
        lay = plan_layout(grid, dpi=args.dpi, width_in=args.width_in,
                          height_in=args.height_in, px_width=args.px_width,
                          px_height=args.px_height, cell_aspect=args.cell_aspect,
                          margin_in=args.margin_in, fit=args.fit)
        write_svg(args.svg, grid, lay.cell_w, lay.cell_h, bg=args.bg,
                  transparent=args.svg_transparent)
        print(f"  wrote  : {args.svg}  ({os.path.getsize(args.svg)/1e6:.1f} MB, vector)")

    # Raster output
    if args.sweep:
        out = args.out or (stem + "_sweep.png")
        k, _, vs = args.sweep.partition("=")
        sweep(text, out, args, k, [v for v in vs.split(",") if v != ""])
        return 0

    if args.no_raster or (args.svg and not args.out) or (args.show and not args.out
                                                         and not args.svg):
        if not args.out:
            return 0

    out = args.out or (stem + ("_preview.png" if args.preview else "_print.png"))
    out, layout, p = render(text, out, args)
    if args.dump_params:
        with open(args.dump_params, "w") as f:
            json.dump(asdict(p), f, indent=2)
        print(f"  params : {args.dump_params}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
