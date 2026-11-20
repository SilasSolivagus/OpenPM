#!/usr/bin/env python3
"""Static preflight gate for walkthrough.html and spec.json (spec-v2) deliverables.

HTML checks:
  - Check A: Flow SVG <polyline> topology (data-from/data-to in NODES, <path marker-end> ban,
             NODES <-> <g data-node> bidirectional parity, endpoint-to-bbox distance <= 16px)
  - Check B: Flow SVG 4-vertex <polygon> decision diamonds (<g data-node="D_*" data-node-type="decision">
             and non-empty data-branch on all outgoing <polyline>s)
  - Check C: Interactive component anchors (data-comp-id & data-comp-name, including .wt-modal/.wt-tab,
             with conditional branch scope awareness for data-ctype-panel / data-scene-* / data-when-val)
  - Check D: NODES page references exist in DOM .page containers
  - Check E: Single-file offline integrity (no external http/https/// script/link/img/@import/url())
  - Check F: Pure grayscale (max-min <= 12) + single amber accent + invalid-memo red, and zero colorful Emoji
  - Check G: SPEC_CARDS page & non-empty anchor ([data-comp-id] or [data-anchor]) existence in DOM

Spec JSON checks (spec-v2):
  - Top-level fields & types, meta.project / meta.title / meta.entry_node existence
  - vars[].default in options, diamond & target references, when references
  - nodes[].page, decision branchVar, state_groups ref, nodes[].change enum ("unchanged"|"modified"|"new")
  - pages[].variant_of cycle-free inheritance
  - spec_cards page & component anchor validity
  - memos[] and memos[].targets schema structure
"""

import argparse
import colorsys
import json
import math
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple


VOID_TAGS: FrozenSet[str] = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)

GLOBAL_INTERACTIVE_CLASSES: FrozenSet[str] = frozenset({"pwx-track", "pwx-modal"})
PAGE_INTERACTIVE_CLASSES: FrozenSet[str] = frozenset(
    {
        "pwx-track",
        "pwx-modal",
        "wt-modal",
        "wt-tab",
        "wt-tabbar-item",
        "wt-btn",
        "wt-switch",
        "wt-slider",
        "wt-drawer",
    }
)
INTERACTIVE_TAGS_IN_PAGE: FrozenSet[str] = frozenset({"button", "input", "select", "textarea"})
INTERACTIVE_ROLES_IN_PAGE: FrozenSet[str] = frozenset({"button", "tab", "switch", "menuitem"})

ALLOWED_NODE_CHANGES: FrozenSet[str] = frozenset({"unchanged", "modified", "new"})
ALLOWED_SPECIAL_HEX: FrozenSet[str] = frozenset(
    {
        # Single engineering accent: Amber
        "#d97706",
        "#f59e0b",
        "#fef3c7",
        "#fffbeb",
        # Invalid-memo / danger warning red
        "#dc2626",
        "#fef2f2",
    }
)

# W3C CSS Color Module Level 4 named RGB colors (excluding neutral keywords like transparent/currentcolor)
CSS_NAMED_COLORS: Dict[str, Tuple[int, int, int]] = {
    "aliceblue": (240, 248, 255),
    "antiquewhite": (250, 235, 215),
    "aqua": (0, 255, 255),
    "aquamarine": (127, 255, 212),
    "azure": (240, 255, 255),
    "beige": (245, 245, 220),
    "bisque": (255, 228, 196),
    "black": (0, 0, 0),
    "blanchedalmond": (255, 235, 205),
    "blue": (0, 0, 255),
    "blueviolet": (138, 43, 226),
    "brown": (165, 42, 42),
    "burlywood": (222, 184, 135),
    "cadetblue": (95, 158, 160),
    "chartreuse": (127, 255, 0),
    "chocolate": (210, 105, 30),
    "coral": (255, 127, 80),
    "cornflowerblue": (100, 149, 237),
    "cornsilk": (255, 248, 220),
    "crimson": (220, 20, 60),
    "cyan": (0, 255, 255),
    "darkblue": (0, 0, 139),
    "darkcyan": (0, 139, 139),
    "darkgoldenrod": (184, 134, 11),
    "darkgray": (169, 169, 169),
    "darkgreen": (0, 100, 0),
    "darkgrey": (169, 169, 169),
    "darkkhaki": (189, 183, 107),
    "darkmagenta": (139, 0, 139),
    "darkolivegreen": (85, 107, 47),
    "darkorange": (255, 140, 0),
    "darkorchid": (153, 50, 204),
    "darkred": (139, 0, 0),
    "darksalmon": (233, 150, 122),
    "darkseagreen": (143, 188, 143),
    "darkslateblue": (72, 61, 139),
    "darkslategray": (47, 79, 79),
    "darkslategrey": (47, 79, 79),
    "darkturquoise": (0, 206, 209),
    "darkviolet": (148, 0, 211),
    "deeppink": (255, 20, 147),
    "deepskyblue": (0, 191, 255),
    "dimgray": (105, 105, 105),
    "dimgrey": (105, 105, 105),
    "dodgerblue": (30, 144, 255),
    "firebrick": (178, 34, 34),
    "floralwhite": (255, 250, 240),
    "forestgreen": (34, 139, 34),
    "fuchsia": (255, 0, 255),
    "gainsboro": (220, 220, 220),
    "ghostwhite": (248, 248, 255),
    "gold": (255, 215, 0),
    "goldenrod": (218, 165, 32),
    "gray": (128, 128, 128),
    "green": (0, 128, 0),
    "greenyellow": (173, 255, 47),
    "grey": (128, 128, 128),
    "honeydew": (240, 255, 240),
    "hotpink": (255, 105, 180),
    "indianred": (205, 92, 92),
    "indigo": (75, 0, 130),
    "ivory": (255, 255, 240),
    "khaki": (240, 230, 140),
    "lavender": (230, 230, 250),
    "lavenderblush": (255, 240, 245),
    "lawngreen": (124, 252, 0),
    "lemonchiffon": (255, 250, 205),
    "lightblue": (173, 216, 230),
    "lightcoral": (240, 128, 128),
    "lightcyan": (224, 255, 255),
    "lightgoldenrodyellow": (250, 250, 210),
    "lightgray": (211, 211, 211),
    "lightgreen": (144, 238, 144),
    "lightgrey": (211, 211, 211),
    "lightpink": (255, 182, 193),
    "lightsalmon": (255, 160, 122),
    "lightseagreen": (32, 178, 170),
    "lightskyblue": (135, 206, 250),
    "lightslategray": (119, 136, 153),
    "lightslategrey": (119, 136, 153),
    "lightsteelblue": (176, 196, 222),
    "lightyellow": (255, 255, 224),
    "lime": (0, 255, 0),
    "limegreen": (50, 205, 50),
    "linen": (250, 240, 230),
    "magenta": (255, 0, 255),
    "maroon": (128, 0, 0),
    "mediumaquamarine": (102, 205, 170),
    "mediumblue": (0, 0, 205),
    "mediumorchid": (186, 85, 211),
    "mediumpurple": (147, 112, 219),
    "mediumseagreen": (60, 179, 113),
    "mediumslateblue": (123, 104, 238),
    "mediumspringgreen": (0, 250, 154),
    "mediumturquoise": (72, 209, 204),
    "mediumvioletred": (199, 21, 133),
    "midnightblue": (25, 25, 112),
    "mintcream": (245, 255, 250),
    "mistyrose": (255, 228, 225),
    "moccasin": (255, 228, 181),
    "navajowhite": (255, 222, 173),
    "navy": (0, 0, 128),
    "oldlace": (253, 245, 230),
    "olive": (128, 128, 0),
    "olivedrab": (107, 142, 35),
    "orange": (255, 165, 0),
    "orangered": (255, 69, 0),
    "orchid": (218, 112, 214),
    "palegoldenrod": (238, 232, 170),
    "palegreen": (152, 251, 152),
    "paleturquoise": (175, 238, 238),
    "palevioletred": (219, 112, 147),
    "papayawhip": (255, 239, 213),
    "peachpuff": (255, 218, 185),
    "peru": (205, 133, 63),
    "pink": (255, 192, 203),
    "plum": (221, 160, 221),
    "powderblue": (176, 224, 230),
    "purple": (128, 0, 128),
    "rebeccapurple": (102, 51, 153),
    "red": (255, 0, 0),
    "rosybrown": (188, 143, 143),
    "royalblue": (65, 105, 225),
    "saddlebrown": (139, 69, 19),
    "salmon": (250, 128, 114),
    "sandybrown": (244, 164, 96),
    "seagreen": (46, 139, 87),
    "seashell": (255, 245, 238),
    "sienna": (160, 82, 45),
    "silver": (192, 192, 192),
    "skyblue": (135, 206, 235),
    "slateblue": (106, 90, 205),
    "slategray": (112, 128, 144),
    "slategrey": (112, 128, 144),
    "snow": (255, 250, 250),
    "springgreen": (0, 255, 127),
    "steelblue": (70, 130, 180),
    "tan": (210, 180, 140),
    "teal": (0, 128, 128),
    "thistle": (216, 191, 216),
    "tomato": (255, 99, 71),
    "turquoise": (64, 224, 208),
    "violet": (238, 130, 238),
    "wheat": (245, 222, 179),
    "white": (255, 255, 255),
    "whitesmoke": (245, 245, 245),
    "yellow": (255, 255, 0),
    "yellowgreen": (154, 205, 50),
}

COLOR_BEARING_PROPS: FrozenSet[str] = frozenset(
    {
        "color",
        "background",
        "background-color",
        "background-image",
        "border",
        "border-color",
        "border-top",
        "border-right",
        "border-bottom",
        "border-left",
        "border-top-color",
        "border-right-color",
        "border-bottom-color",
        "border-left-color",
        "outline",
        "outline-color",
        "box-shadow",
        "text-shadow",
        "fill",
        "stroke",
        "stop-color",
        "flood-color",
        "accent-color",
        "caret-color",
        "text-decoration-color",
        "column-rule-color",
    }
)

# Standalone BMP colorful Emoji codepoints (monochrome symbols like ×✓✕←→↑↓★☆☐☑☰●○▸▾ are excluded)
BMP_COLOR_EMOJI_CODEPOINTS: FrozenSet[int] = frozenset(
    {
        0x231A, 0x231B, 0x23E9, 0x23EA, 0x23EB, 0x23EC, 0x23F0, 0x23F1, 0x23F2, 0x23F3,
        0x2614, 0x2615, 0x2648, 0x2649, 0x264A, 0x264B, 0x264C, 0x264D, 0x264E, 0x264F,
        0x2650, 0x2651, 0x2652, 0x2653, 0x267F, 0x2693, 0x26A0, 0x26A1, 0x26AA, 0x26AB,
        0x26BD, 0x26BE, 0x26C4, 0x26C5, 0x26CE, 0x26D4, 0x26EA, 0x26F2, 0x26F3, 0x26F5,
        0x26FA, 0x26FD, 0x2705, 0x270A, 0x270B, 0x2728, 0x274C, 0x274E, 0x2753, 0x2754,
        0x2755, 0x2757, 0x2764, 0x2795, 0x2796, 0x2797, 0x27B0, 0x27BF, 0x2B50, 0x2B55,
    }
)


def _find_colorful_emoji(text: str) -> Optional[str]:
    """Return the first colorful Emoji character/sequence found, or None if clean."""
    if not text:
        return None
    for idx, ch in enumerate(text):
        cp = ord(ch)
        if cp == 0xFE0F and idx > 0:
            return text[idx - 1 : idx + 1]
        if cp == 0x20E3 and idx > 0:
            return text[max(0, idx - 2) : idx + 1]
        if (
            0x1F300 <= cp <= 0x1FAFF
            or 0x1F1E6 <= cp <= 0x1F1FF
            or 0x1F191 <= cp <= 0x1F251
            or cp in (0x1F004, 0x1F0CF)
            or cp in BMP_COLOR_EMOJI_CODEPOINTS
        ):
            return ch
    return None


def _parse_points(points_str: str) -> List[Tuple[float, float]]:
    """Parse SVG polygon/polyline points string into float coordinate pairs."""
    tokens = re.findall(r"-?\d+(?:\.\d+)?", points_str or "")
    return [(float(tokens[i]), float(tokens[i + 1])) for i in range(0, len(tokens) - 1, 2)]


def _parse_translate(transform_str: str) -> Tuple[float, float]:
    """Extract cumulative translate(tx[, ty]) offset from an SVG transform attribute."""
    if not transform_str:
        return (0.0, 0.0)
    tx_total = 0.0
    ty_total = 0.0
    for m in re.finditer(r"translate\(\s*(-?\d+(?:\.\d+)?)(?:[\s,]+(-?\d+(?:\.\d+)?))?\s*\)", transform_str):
        tx_total += float(m.group(1))
        if m.group(2) is not None:
            ty_total += float(m.group(2))
    return (tx_total, ty_total)


def _is_external_url(val: str) -> bool:
    s = (val or "").strip()
    return bool(re.match(r"^(?:https?:)?//", s, re.IGNORECASE))


def _is_allowed_rgb(r: int, g: int, b: int) -> bool:
    r_c = max(0, min(255, int(round(r))))
    g_c = max(0, min(255, int(round(g))))
    b_c = max(0, min(255, int(round(b))))
    if max(r_c, g_c, b_c) - min(r_c, g_c, b_c) <= 12:
        return True
    hex6 = f"#{r_c:02x}{g_c:02x}{b_c:02x}"
    return hex6 in ALLOWED_SPECIAL_HEX


def _parse_rgb_channel(tok: str) -> Optional[int]:
    t = tok.strip()
    if t.endswith("%"):
        try:
            return int(round(float(t[:-1]) * 2.55))
        except ValueError:
            return None
    try:
        return int(round(float(t)))
    except ValueError:
        return None


def _scan_value_disallowed_colors(prop_name: str, raw_val: str) -> List[str]:
    """Return list of disallowed color tokens inside a single CSS/SVG value."""
    if not raw_val:
        return []
    # Strip CSS comments, quoted strings, and url(...) references
    cleaned = re.sub(r"/\*.*?\*/", " ", raw_val, flags=re.DOTALL)
    cleaned = re.sub(r"""(['"])(?:\\.|(?!\1).)*\1""", " ", cleaned)
    cleaned = re.sub(r"url\([^)]*\)", " ", cleaned, flags=re.IGNORECASE)

    bad: List[str] = []

    # 1. Hex colors (#RGB, #RGBA, #RRGGBB, #RRGGBBAA)
    for m in re.finditer(r"#([0-9a-fA-F]{3,8})\b", cleaned):
        h = m.group(1)
        token = m.group(0)
        if len(h) in (3, 4):
            if len(h) == 4 and int(h[3] * 2, 16) == 0:
                continue
            r, g, b = int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16)
        elif len(h) in (6, 8):
            if len(h) == 8 and int(h[6:8], 16) == 0:
                continue
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        else:
            continue
        if not _is_allowed_rgb(r, g, b):
            bad.append(token)
    cleaned_no_hex = re.sub(r"#[0-9a-fA-F]{3,8}\b", " ", cleaned)

    # 2. rgb() / rgba()
    for m in re.finditer(r"\brgba?\(\s*([^)]+)\)", cleaned_no_hex, re.IGNORECASE):
        inner = m.group(1)
        parts = [p for p in re.split(r"[\s,/]+", inner.strip()) if p]
        if len(parts) >= 3:
            if len(parts) >= 4:
                a_str = parts[3]
                try:
                    a_val = float(a_str[:-1]) / 100.0 if a_str.endswith("%") else float(a_str)
                    if a_val == 0.0:
                        continue
                except ValueError:
                    pass
            rv, gv, bv = _parse_rgb_channel(parts[0]), _parse_rgb_channel(parts[1]), _parse_rgb_channel(parts[2])
            if rv is not None and gv is not None and bv is not None and not _is_allowed_rgb(rv, gv, bv):
                bad.append(m.group(0))
    cleaned_no_fn = re.sub(r"\brgba?\([^)]*\)", " ", cleaned_no_hex, flags=re.IGNORECASE)

    # 3. hsl() / hsla()
    for m in re.finditer(r"\bhsla?\(\s*([^)]+)\)", cleaned_no_fn, re.IGNORECASE):
        inner = m.group(1)
        parts = [p for p in re.split(r"[\s,/]+", inner.strip()) if p]
        if len(parts) >= 3:
            try:
                hue = float(re.sub(r"(deg|rad|turn)$", "", parts[0], flags=re.IGNORECASE))
                sat = float(parts[1].rstrip("%")) / 100.0
                lig = float(parts[2].rstrip("%")) / 100.0
                rf, gf, bf = colorsys.hls_to_rgb((hue % 360.0) / 360.0, max(0.0, min(1.0, lig)), max(0.0, min(1.0, sat)))
                if not _is_allowed_rgb(int(round(rf * 255)), int(round(gf * 255)), int(round(bf * 255))):
                    bad.append(m.group(0))
            except ValueError:
                pass
    cleaned_no_fn = re.sub(r"\bhsla?\([^)]*\)", " ", cleaned_no_fn, flags=re.IGNORECASE)
    # Remove var(...) so custom property names like var(--card-red-ref) aren't matched as named colors
    cleaned_no_fn = re.sub(r"\bvar\([^)]*\)", " ", cleaned_no_fn, flags=re.IGNORECASE)

    # 4. Named CSS colors on color-bearing properties / custom properties
    p_low = prop_name.strip().lower()
    if p_low in COLOR_BEARING_PROPS or p_low.startswith("--"):
        for word_m in re.finditer(r"\b([a-zA-Z]+)\b", cleaned_no_fn):
            w_low = word_m.group(1).lower()
            if w_low in CSS_NAMED_COLORS:
                r, g, b = CSS_NAMED_COLORS[w_low]
                if not _is_allowed_rgb(r, g, b):
                    bad.append(word_m.group(1))

    return bad


def _scan_css_declarations_colors(decls_text: str) -> List[Tuple[str, str]]:
    """Scan semicolon-separated CSS declarations (`prop: val; ...`), returning (prop, color_tok)."""
    results: List[Tuple[str, str]] = []
    no_comments = re.sub(r"/\*.*?\*/", "", decls_text, flags=re.DOTALL)
    for decl in no_comments.split(";"):
        if ":" not in decl:
            continue
        prop, val = decl.split(":", 1)
        prop_s = prop.strip()
        if not prop_s:
            continue
        for bad_tok in _scan_value_disallowed_colors(prop_s, val):
            results.append((prop_s, bad_tok))
    return results


def _scan_stylesheet_colors(css_text: str) -> List[Tuple[str, str]]:
    """Extract declaration blocks `{ ... }` from a stylesheet and scan property values for colors."""
    results: List[Tuple[str, str]] = []
    no_comments = re.sub(r"/\*.*?\*/", "", css_text, flags=re.DOTALL)
    # Scan innermost { ... } blocks iteratively (handles @media nesting cleanly)
    for m in re.finditer(r"\{([^{}]*)\}", no_comments):
        results.extend(_scan_css_declarations_colors(m.group(1)))
    return results


def _find_css_external_urls(css_text: str) -> List[str]:
    """Return offending @import or external url(http/https///) snippets in CSS."""
    violations: List[str] = []
    no_comments = re.sub(r"/\*.*?\*/", "", css_text, flags=re.DOTALL)
    for m in re.finditer(r"@import\s+[^;\n]+", no_comments, re.IGNORECASE):
        violations.append(m.group(0).strip())
    for m in re.finditer(r"url\(\s*(['\"]?)\s*((?:https?:)?//[^)'\"\s]+)\s*\1\s*\)", no_comments, re.IGNORECASE):
        violations.append(m.group(0).strip())
    return violations


def _extract_js_json_var(script: str, var_name: str) -> Optional[Any]:
    """Extract a JSON object/array assigned to `var_name` in JS, skipping strings & comments."""
    n = len(script)
    i = 0
    ident_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_$")
    target_len = len(var_name)

    def _skip_ws_and_comments(pos: int) -> int:
        while pos < n:
            ch = script[pos]
            if ch in " \t\r\n":
                pos += 1
            elif script[pos : pos + 2] == "//":
                nl = script.find("\n", pos + 2)
                pos = n if nl < 0 else nl + 1
            elif script[pos : pos + 2] == "/*":
                end_c = script.find("*/", pos + 2)
                pos = n if end_c < 0 else end_c + 2
            else:
                break
        return pos

    while i < n:
        ch = script[i]
        # Skip single-line comment
        if ch == "/" and script[i : i + 2] == "//":
            nl = script.find("\n", i + 2)
            i = n if nl < 0 else nl + 1
            continue
        # Skip block comment
        if ch == "/" and script[i : i + 2] == "/*":
            end_c = script.find("*/", i + 2)
            i = n if end_c < 0 else end_c + 2
            continue
        # Skip string / template literal
        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            while i < n:
                c2 = script[i]
                if c2 == "\\":
                    i += 2
                    continue
                if c2 == quote:
                    i += 1
                    break
                i += 1
            continue

        # Match identifier `var_name` at token boundary (allow `window.NODES =` but not `other.NODES =`)
        if script.startswith(var_name, i):
            prev_ch = script[i - 1] if i > 0 else ""
            next_ch = script[i + target_len] if (i + target_len) < n else ""
            prev_ok = (prev_ch not in ident_chars) and (
                prev_ch != "." or script[max(0, i - 7) : i] == "window."
            )
            next_ok = next_ch not in ident_chars
            if prev_ok and next_ok:
                j = _skip_ws_and_comments(i + target_len)
                if j < n and script[j] == "=" and script[j : j + 2] != "==":
                    k = _skip_ws_and_comments(j + 1)
                    if k < n and script[k] in ("{", "["):
                        # Scan balanced JSON/JS literal while stripping JS comments outside strings
                        depth = 0
                        pos = k
                        cleaned_chars: List[str] = []
                        while pos < n:
                            c = script[pos]
                            if c in ("'", '"', "`"):
                                q = c
                                cleaned_chars.append(c)
                                pos += 1
                                while pos < n:
                                    sc = script[pos]
                                    cleaned_chars.append(sc)
                                    if sc == "\\":
                                        pos += 1
                                        if pos < n:
                                            cleaned_chars.append(script[pos])
                                            pos += 1
                                        continue
                                    pos += 1
                                    if sc == q:
                                        break
                                continue
                            if c == "/" and script[pos : pos + 2] == "//":
                                nl = script.find("\n", pos + 2)
                                if nl < 0:
                                    pos = n
                                else:
                                    cleaned_chars.append("\n")
                                    pos = nl + 1
                                continue
                            if c == "/" and script[pos : pos + 2] == "/*":
                                end_c = script.find("*/", pos + 2)
                                if end_c < 0:
                                    pos = n
                                else:
                                    cleaned_chars.append(" ")
                                    pos = end_c + 2
                                continue
                            if c in ("{", "["):
                                depth += 1
                            elif c in ("}", "]"):
                                depth -= 1
                                cleaned_chars.append(c)
                                pos += 1
                                if depth == 0:
                                    break
                                continue
                            cleaned_chars.append(c)
                            pos += 1

                        raw_json = "".join(cleaned_chars)
                        # Remove trailing commas outside strings if present
                        raw_json_clean = _strip_trailing_commas_outside_strings(raw_json)
                        return json.loads(raw_json_clean)
        i += 1

    return None


def _strip_trailing_commas_outside_strings(text: str) -> str:
    """Remove trailing commas before `}` or `]` without modifying string contents."""
    out: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in ('"', "'", "`"):
            q = ch
            out.append(ch)
            i += 1
            while i < n:
                c2 = text[i]
                out.append(c2)
                if c2 == "\\" and i + 1 < n:
                    i += 1
                    out.append(text[i])
                    i += 1
                    continue
                i += 1
                if c2 == q:
                    break
            continue
        if ch == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in ("}", "]"):
                i += 1
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def _conditions_mutually_exclusive(
    cond1: Dict[str, FrozenSet[str]],
    cond2: Dict[str, FrozenSet[str]],
) -> bool:
    """Return True iff two conditional scopes share a condition axis with disjoint allowed values."""
    for key, vals1 in cond1.items():
        if key in cond2:
            vals2 = cond2[key]
            if vals1 and vals2 and vals1.isdisjoint(vals2):
                return True
    return False


class WalkthroughParser(HTMLParser):
    """HTML parser that collects DOM topology, geometry, styles, anchors, and script blocks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: List[Tuple[str, Dict[str, str], int]] = []

        # Flow SVG topology & geometry
        self.flow_polylines: List[Tuple[int, Dict[str, str], Tuple[float, float]]] = []
        self.flow_polygons: List[Tuple[int, Dict[str, str], List[Tuple[str, Dict[str, str], int]]]] = []
        self.flow_path_markers: List[Tuple[int, Dict[str, str]]] = []
        self.flow_nodes: Dict[str, List[int]] = {}
        self.flow_node_types: Dict[str, str] = {}
        self.flow_node_bboxes: Dict[str, List[float]] = {}  # node_id -> [min_x, min_y, max_x, max_y]

        # Pages & anchors
        self.dom_page_ids: Set[str] = set()
        self.page_anchors: Dict[str, Set[str]] = {}
        self.interactive_elements: List[Tuple[int, str, Dict[str, str]]] = []
        # key: f"{page_id}::{comp_id}" -> list of (line, cond_map)
        self.comp_occurrences: Dict[str, List[Tuple[int, Dict[str, FrozenSet[str]]]]] = {}

        # Offline, Emoji & Color checks
        self.external_refs: List[Tuple[int, str, str, str]] = []
        self.inline_css_external_refs: List[Tuple[int, str]] = []
        self.emoji_violations: List[Tuple[int, str, str]] = []
        self.color_violations: List[Tuple[int, str, str]] = []

        # Scripts & styles
        self.scripts: List[Tuple[int, str]] = []
        self.styles: List[Tuple[int, Dict[str, str], bool, str]] = []  # (line, attrs, scan_colors, css)
        self._in_script = False
        self._script_start_line = 0
        self._script_chunks: List[str] = []
        self._in_style = False
        self._style_start_line = 0
        self._style_attrs: Dict[str, str] = {}
        self._style_scan_colors = False
        self._style_chunks: List[str] = []

    @staticmethod
    def _is_page_attrs(attrs: Dict[str, str]) -> bool:
        classes = set((attrs.get("class") or "").split())
        return (
            "page" in classes
            or "proto-page" in classes
            or bool(attrs.get("data-page", "").strip())
            or bool(attrs.get("data-page-id", "").strip())
        )

    @staticmethod
    def _page_keys_from_attrs(attrs: Dict[str, str]) -> List[str]:
        keys: List[str] = []
        for attr_name in ("data-page-id", "data-page", "id"):
            val = (attrs.get(attr_name) or "").strip()
            if val and val not in keys:
                keys.append(val)
        return keys

    def _current_page_keys(self) -> List[str]:
        for _, attrs, _ in reversed(self.stack):
            if self._is_page_attrs(attrs):
                keys = self._page_keys_from_attrs(attrs)
                return keys if keys else ["<unknown-page>"]
        return []

    def _current_page_id(self) -> Optional[str]:
        keys = self._current_page_keys()
        return keys[0] if keys else None

    def _in_proto_page(self) -> bool:
        return bool(self._current_page_keys())

    def _in_defs_or_marker(self) -> bool:
        return any(tag in {"defs", "marker"} for tag, _, _ in self.stack)

    def _in_any_svg(self) -> bool:
        return any(tag == "svg" for tag, _, _ in self.stack)

    def _in_flow_svg(self) -> bool:
        """True when inside a flow diagram <svg> (outside .page and not #tether-svg)."""
        if self._in_proto_page():
            return False
        for tag, attrs, _ in reversed(self.stack):
            if tag == "svg":
                classes = set((attrs.get("class") or "").split())
                if attrs.get("id") == "tether-svg" or "tether-svg" in classes:
                    return False
                return True
        return False

    def _svg_translate_offset(self) -> Tuple[float, float]:
        """Accumulate translate(tx, ty) on <g> ancestors inside the active <svg>."""
        tx, ty = 0.0, 0.0
        in_svg = False
        for tag, attrs, _ in self.stack:
            if tag == "svg":
                in_svg = True
                tx, ty = 0.0, 0.0
            elif in_svg and tag == "g":
                dx, dy = _parse_translate(attrs.get("transform", ""))
                tx += dx
                ty += dy
        return (tx, ty)

    def _enclosing_flow_node_id(self) -> Optional[str]:
        for tag, attrs, _ in reversed(self.stack):
            if tag == "svg":
                break
            if tag == "g" and attrs.get("data-node", "").strip():
                return attrs["data-node"].strip()
        return None

    def _update_node_bbox(self, node_id: str, min_x: float, min_y: float, max_x: float, max_y: float) -> None:
        if node_id not in self.flow_node_bboxes:
            self.flow_node_bboxes[node_id] = [min_x, min_y, max_x, max_y]
        else:
            box = self.flow_node_bboxes[node_id]
            box[0] = min(box[0], min_x)
            box[1] = min(box[1], min_y)
            box[2] = max(box[2], max_x)
            box[3] = max(box[3], max_y)

    def _collect_conditional_scope(self, self_attrs: Dict[str, str]) -> Dict[str, FrozenSet[str]]:
        """Collect conditional visibility branch attributes across page ancestors + current element."""
        conds: Dict[str, FrozenSet[str]] = {}
        chain_attrs: List[Dict[str, str]] = []
        in_page = False
        for _, a, _ in self.stack:
            if self._is_page_attrs(a):
                in_page = True
            if in_page:
                chain_attrs.append(a)
        chain_attrs.append(self_attrs)

        for a in chain_attrs:
            when_val = (a.get("data-when-val") or "").strip()
            when_var = (a.get("data-when-var") or "").strip()
            if when_val:
                axis = f"when:{when_var}" if when_var else "data-when-val"
                vals = frozenset(v.strip() for v in when_val.split(",") if v.strip())
                if vals:
                    conds[axis] = conds[axis] & vals if axis in conds else vals

            for k, v in a.items():
                val_s = (v or "").strip()
                if not val_s:
                    continue
                if k in ("data-ctype-panel", "data-branch-panel", "data-state-panel", "data-tab-panel") or (
                    k == "data-scene" or k.startswith("data-scene-")
                ):
                    vals = frozenset(x.strip() for x in val_s.split(",") if x.strip())
                    if vals:
                        conds[k] = conds[k] & vals if k in conds else vals
        return conds

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        line, _ = self.getpos()
        t = tag.lower()
        attr_dict = {k.lower(): (v if v is not None else "") for k, v in attrs}
        classes = set(attr_dict.get("class", "").split())

        # Bug Fix 1: Only collect dom_page_ids on actual page containers
        is_self_page = self._is_page_attrs(attr_dict)
        if is_self_page:
            p_keys = self._page_keys_from_attrs(attr_dict)
            for pk in p_keys:
                self.dom_page_ids.add(pk)
                self.page_anchors.setdefault(pk, set())

        active_page_keys = self._page_keys_from_attrs(attr_dict) if is_self_page else self._current_page_keys()
        in_page = bool(active_page_keys)
        in_svg = (t == "svg") or self._in_any_svg()
        in_flow_svg = self._in_flow_svg() or (
            t == "svg"
            and not in_page
            and attr_dict.get("id") != "tether-svg"
            and "tether-svg" not in classes
        )

        # Check E: External resource URLs on <script src>, <link href>, <img src>, <image href>
        if t == "script" and _is_external_url(attr_dict.get("src", "")):
            self.external_refs.append((line, t, "src", attr_dict["src"].strip()))
        elif t == "link" and _is_external_url(attr_dict.get("href", "")):
            self.external_refs.append((line, t, "href", attr_dict["href"].strip()))
        elif t in ("img", "image"):
            for src_attr in ("src", "href", "xlink:href"):
                if _is_external_url(attr_dict.get(src_attr, "")):
                    self.external_refs.append((line, t, src_attr, attr_dict[src_attr].strip()))

        if "style" in attr_dict and attr_dict["style"].strip():
            for ext_css in _find_css_external_urls(attr_dict["style"]):
                self.inline_css_external_refs.append((line, ext_css))

        # Check F: Emoji in data-comp-name, and colors on .page elements or SVG elements
        comp_name_val = attr_dict.get("data-comp-name", "")
        if comp_name_val:
            em = _find_colorful_emoji(comp_name_val)
            if em:
                self.emoji_violations.append((line, f'data-comp-name="{comp_name_val}"', em))

        if in_page or in_svg:
            if "style" in attr_dict and attr_dict["style"].strip():
                for prop_s, bad_tok in _scan_css_declarations_colors(attr_dict["style"]):
                    self.color_violations.append((line, f"<{t} style ({prop_s})>", bad_tok))
            for color_attr in ("fill", "stroke", "stop-color", "flood-color", "color", "bgcolor"):
                if color_attr in attr_dict and attr_dict[color_attr].strip():
                    for bad_tok in _scan_value_disallowed_colors(color_attr, attr_dict[color_attr]):
                        self.color_violations.append((line, f"<{t} {color_attr}>", bad_tok))

        # Collect anchors inside .page for Check G & Check C
        cid = attr_dict.get("data-comp-id", "").strip()
        legacy_anchor = attr_dict.get("data-anchor", "").strip()
        if active_page_keys:
            for pk in active_page_keys:
                bucket = self.page_anchors.setdefault(pk, set())
                if cid:
                    bucket.add(cid)
                if legacy_anchor:
                    bucket.add(legacy_anchor)

        if cid:
            page_scope = active_page_keys[0] if active_page_keys else "<global>"
            cond_scope = self._collect_conditional_scope(attr_dict) if in_page else {}
            self.comp_occurrences.setdefault(f"{page_scope}::{cid}", []).append((line, cond_scope))

        # Flow SVG topology & node bounding boxes (Check A & Check B)
        if in_flow_svg and not self._in_defs_or_marker():
            if t == "g" and attr_dict.get("data-node", "").strip():
                nid = attr_dict["data-node"].strip()
                self.flow_nodes.setdefault(nid, []).append(line)
                ntype = attr_dict.get("data-node-type", "").strip()
                if ntype:
                    self.flow_node_types[nid] = ntype

            tx, ty = self._svg_translate_offset()
            if t == "g":
                dx, dy = _parse_translate(attr_dict.get("transform", ""))
                tx += dx
                ty += dy

            if t == "polyline":
                self.flow_polylines.append((line, attr_dict, (tx, ty)))
            elif t == "polygon":
                self.flow_polygons.append((line, attr_dict, list(self.stack)))
                pts = _parse_points(attr_dict.get("points", ""))
                enclosing_nid = self._enclosing_flow_node_id()
                if pts and enclosing_nid:
                    xs = [p[0] + tx for p in pts]
                    ys = [p[1] + ty for p in pts]
                    self._update_node_bbox(enclosing_nid, min(xs), min(ys), max(xs), max(ys))
            elif t == "rect":
                enclosing_nid = self._enclosing_flow_node_id()
                if enclosing_nid and "width" in attr_dict and "height" in attr_dict:
                    try:
                        rx = float(attr_dict.get("x") or 0.0) + tx
                        ry = float(attr_dict.get("y") or 0.0) + ty
                        rw = float(attr_dict.get("width") or 0.0)
                        rh = float(attr_dict.get("height") or 0.0)
                        if rw > 0 and rh > 0:
                            self._update_node_bbox(enclosing_nid, rx, ry, rx + rw, ry + rh)
                    except ValueError:
                        pass
            elif t in ("circle", "ellipse"):
                enclosing_nid = self._enclosing_flow_node_id()
                if enclosing_nid:
                    try:
                        cx = float(attr_dict.get("cx") or 0.0) + tx
                        cy = float(attr_dict.get("cy") or 0.0) + ty
                        rx = float(attr_dict.get("r") or attr_dict.get("rx") or 0.0)
                        ry = float(attr_dict.get("r") or attr_dict.get("ry") or 0.0)
                        if rx > 0 and ry > 0:
                            self._update_node_bbox(enclosing_nid, cx - rx, cy - ry, cx + rx, cy + ry)
                    except ValueError:
                        pass
            elif t == "path":
                me = attr_dict.get("marker-end", "").strip()
                style_str = attr_dict.get("style", "")
                has_style_me = bool(
                    re.search(r"marker-end\s*:\s*(?!none\b)[^;]+", style_str, re.IGNORECASE)
                )
                if (me and me.lower() != "none") or has_style_me:
                    self.flow_path_markers.append((line, attr_dict))

        # Check C: Interactive elements inside .page (plus legacy global pwx-* elements)
        is_global_target = bool(classes & GLOBAL_INTERACTIVE_CLASSES)
        is_page_class_target = in_page and bool(classes & PAGE_INTERACTIVE_CLASSES)
        is_hidden_input = t == "input" and attr_dict.get("type", "").strip().lower() == "hidden"
        is_page_tag_target = in_page and not is_hidden_input and (
            t in INTERACTIVE_TAGS_IN_PAGE
            or attr_dict.get("role", "").strip().lower() in INTERACTIVE_ROLES_IN_PAGE
        )
        if is_global_target or is_page_class_target or is_page_tag_target:
            self.interactive_elements.append((line, t, attr_dict))

        if t == "script":
            self._in_script = True
            self._script_start_line = line
            self._script_chunks = []
        elif t == "style":
            self._in_style = True
            self._style_start_line = line
            self._style_attrs = attr_dict
            style_id = attr_dict.get("id", "").strip().lower()
            self._style_scan_colors = (
                style_id in ("skeleton-css", "custom-theme") or in_page or in_svg
            )
            self._style_chunks = []

        # Bug Fix 2: Never push HTML5 VOID_TAGS onto self.stack
        if t not in VOID_TAGS:
            self.stack.append((t, attr_dict, line))

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self.handle_starttag(tag, attrs)
        t = tag.lower()
        if t not in VOID_TAGS and self.stack and self.stack[-1][0] == t:
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t == "script" and self._in_script:
            self.scripts.append((self._script_start_line, "".join(self._script_chunks)))
            self._in_script = False
            self._script_chunks = []
        elif t == "style" and self._in_style:
            self.styles.append(
                (
                    self._style_start_line,
                    self._style_attrs,
                    self._style_scan_colors,
                    "".join(self._style_chunks),
                )
            )
            self._in_style = False
            self._style_chunks = []

        if t in VOID_TAGS:
            return

        for idx in range(len(self.stack) - 1, -1, -1):
            if self.stack[idx][0] == t:
                del self.stack[idx:]
                break

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self._script_chunks.append(data)
            return
        if self._in_style:
            self._style_chunks.append(data)
            return
        if not self._in_defs_or_marker():
            em = _find_colorful_emoji(data)
            if em:
                line, _ = self.getpos()
                snippet = re.sub(r"\s+", " ", data).strip()[:36]
                self.emoji_violations.append((line, f'text "{snippet}"', em))


def _point_to_bbox_distance(px: float, py: float, bbox: Sequence[float]) -> float:
    min_x, min_y, max_x, max_y = bbox[0], bbox[1], bbox[2], bbox[3]
    dx = max(min_x - px, 0.0, px - max_x)
    dy = max(min_y - py, 0.0, py - max_y)
    return math.hypot(dx, dy)


def _extract_script_vars(
    scripts: List[Tuple[int, str]],
) -> Tuple[Optional[Dict[str, Any]], Optional[List[Any]], Optional[List[Any]], List[str]]:
    """Extract NODES, VARS, SPEC_CARDS across <script> blocks using _extract_js_json_var."""
    nodes_obj: Optional[Dict[str, Any]] = None
    vars_arr: Optional[List[Any]] = None
    spec_cards_arr: Optional[List[Any]] = None
    parse_errors: List[str] = []

    for line, script in scripts:
        for var_name in ("NODES", "VARS", "SPEC_CARDS"):
            try:
                val = _extract_js_json_var(script, var_name)
            except ValueError as exc:
                parse_errors.append(
                    f"[Check D - ScriptJSON] Line {line}: Failed to parse {var_name} JSON literal: {exc}"
                )
                continue
            if val is None:
                continue
            if var_name == "NODES":
                if isinstance(val, dict):
                    nodes_obj = val
                else:
                    parse_errors.append(f"[Check D - NODES] Line {line}: NODES must be a JSON object")
            elif var_name == "VARS":
                if isinstance(val, list):
                    vars_arr = val
                else:
                    parse_errors.append(f"[Check D - VARS] Line {line}: VARS must be a JSON array")
            elif var_name == "SPEC_CARDS":
                if isinstance(val, list):
                    spec_cards_arr = val
                else:
                    parse_errors.append(
                        f"[Check G - SpecCards] Line {line}: SPEC_CARDS must be a JSON array"
                    )

    return nodes_obj, vars_arr, spec_cards_arr, parse_errors


def run_preflight(html_path: Path) -> List[str]:
    """Run all static preflight checks on a walkthrough.html file and return error messages."""
    content = html_path.read_text(encoding="utf-8")
    parser = WalkthroughParser()
    parser.feed(content)
    parser.close()

    errors: List[str] = []
    nodes_obj, vars_arr, spec_cards_arr, script_parse_errors = _extract_script_vars(parser.scripts)
    errors.extend(script_parse_errors)

    # Identify decision nodes from both SVG and NODES
    decision_node_ids: Set[str] = set()
    for nid, ntype in parser.flow_node_types.items():
        if ntype == "decision" or nid.startswith("D_"):
            decision_node_ids.add(nid)
    if nodes_obj is not None:
        for nid, ndef in nodes_obj.items():
            if isinstance(ndef, dict) and (ndef.get("isDecision") is True or ndef.get("type") == "decision"):
                decision_node_ids.add(nid)

    # Map branchVar options from VARS if available
    vars_by_id: Dict[str, Dict[str, Any]] = {}
    if vars_arr is not None:
        for v in vars_arr:
            if isinstance(v, dict) and isinstance(v.get("id"), str):
                vars_by_id[v["id"]] = v

    # --- Check A: Flow SVG <path marker-end>, <g data-node> parity, <polyline> topology & geometry ---
    for line, path_attrs in parser.flow_path_markers:
        errors.append(
            f"[Check A - PathEdge] Line {line}: Flow SVG must not use <path marker-end> for edges; "
            "use <polyline data-from=\"...\" data-to=\"...\">"
        )

    for nid, lines in parser.flow_nodes.items():
        if len(lines) > 1:
            errors.append(
                f"[Check A - NodeParity] Duplicate <g data-node=\"{nid}\"> in flow SVG at lines "
                f"{', '.join(map(str, lines))}"
            )

    if nodes_obj is not None and parser.flow_nodes:
        svg_node_keys = set(parser.flow_nodes.keys())
        js_node_keys = set(nodes_obj.keys())
        for missing_in_svg in sorted(js_node_keys - svg_node_keys):
            errors.append(
                f"[Check A - NodeParity] Node \"{missing_in_svg}\" is in NODES but missing <g data-node=\"{missing_in_svg}\"> in flow SVG"
            )
        for missing_in_js in sorted(svg_node_keys - js_node_keys):
            errors.append(
                f"[Check A - NodeParity] Flow SVG <g data-node=\"{missing_in_js}\"> is not registered in NODES"
            )
    elif nodes_obj is not None and not parser.flow_nodes:
        errors.append("[Check A - NodeParity] Flow SVG contains no <g data-node=\"...\"> elements")

    outgoing_by_node: Dict[str, List[Tuple[int, Dict[str, str]]]] = {}
    for line, attrs, (tx, ty) in parser.flow_polylines:
        src = attrs.get("data-from", "").strip()
        dst = attrs.get("data-to", "").strip()
        missing = [k for k, v in (("data-from", src), ("data-to", dst)) if not v]
        if missing:
            errors.append(
                f"[Check A - Polyline] Line {line}: <polyline> missing {', '.join(missing)}"
            )
            continue

        outgoing_by_node.setdefault(src, []).append((line, attrs))

        if nodes_obj is not None:
            if src not in nodes_obj:
                errors.append(
                    f"[Check A - Polyline] Line {line}: <polyline> data-from=\"{src}\" does not exist in NODES"
                )
            if dst not in nodes_obj:
                errors.append(
                    f"[Check A - Polyline] Line {line}: <polyline> data-to=\"{dst}\" does not exist in NODES"
                )

        if src in decision_node_ids:
            branch_val = attrs.get("data-branch", "").strip()
            if not branch_val:
                errors.append(
                    f"[Check B - Decision] Line {line}: Outgoing <polyline> from decision node \"{src}\" "
                    "missing non-empty data-branch"
                )
            elif nodes_obj and isinstance(nodes_obj.get(src), dict):
                bvar_id = nodes_obj[src].get("branchVar")
                if isinstance(bvar_id, str) and bvar_id in vars_by_id:
                    valid_opts = {
                        str(o.get("id"))
                        for o in (vars_by_id[bvar_id].get("options") or [])
                        if isinstance(o, dict) and o.get("id")
                    }
                    if valid_opts and branch_val not in valid_opts:
                        errors.append(
                            f"[Check B - Decision] Line {line}: <polyline> data-branch=\"{branch_val}\" from "
                            f"\"{src}\" is not in VARS[\"{bvar_id}\"].options ({sorted(valid_opts)})"
                        )

        pts = _parse_points(attrs.get("points", ""))
        if len(pts) < 2:
            errors.append(
                f"[Check A - Geometry] Line {line}: <polyline> must contain at least 2 coordinate points"
            )
            continue

        start_pt = (pts[0][0] + tx, pts[0][1] + ty)
        end_pt = (pts[-1][0] + tx, pts[-1][1] + ty)
        if src in parser.flow_node_bboxes:
            dist_start = _point_to_bbox_distance(start_pt[0], start_pt[1], parser.flow_node_bboxes[src])
            if dist_start > 16.0:
                errors.append(
                    f"[Check A - Geometry] Line {line}: <polyline> start {start_pt} is {dist_start:.1f}px "
                    f"(> 16px) away from source <g data-node=\"{src}\"> bbox {parser.flow_node_bboxes[src]}"
                )
        if dst in parser.flow_node_bboxes:
            dist_end = _point_to_bbox_distance(end_pt[0], end_pt[1], parser.flow_node_bboxes[dst])
            if dist_end > 16.0:
                errors.append(
                    f"[Check A - Geometry] Line {line}: <polyline> end {end_pt} is {dist_end:.1f}px "
                    f"(> 16px) away from target <g data-node=\"{dst}\"> bbox {parser.flow_node_bboxes[dst]}"
                )

    # --- Check B: 4-vertex <polygon> inside flow <svg> & D_* decision rules ---
    for line, attrs, ancestors in parser.flow_polygons:
        points = _parse_points(attrs.get("points", ""))
        if len(points) != 4:
            continue
        g_ancestors = [(t, a, ln) for t, a, ln in ancestors if t == "g"]
        if not g_ancestors:
            errors.append(
                f"[Check B - Decision] Line {line}: 4-vertex diamond <polygon> in flow SVG is not wrapped in a <g> element"
            )
            continue
        matched_g = None
        for _, a, ln in reversed(g_ancestors):
            if a.get("data-node", "").strip():
                matched_g = (a, ln)
                break
        if matched_g is None:
            nearest_g_line = g_ancestors[-1][2]
            errors.append(
                f"[Check B - Decision] Line {line} (in <g> at line {nearest_g_line}): "
                "diamond <polygon> ancestor <g> must have data-node=\"D_*\" and data-node-type=\"decision\""
            )
            continue
        g_attrs, g_line = matched_g
        dn = g_attrs.get("data-node", "").strip()
        dt = g_attrs.get("data-node-type", "").strip()
        if dt != "decision":
            errors.append(
                f"[Check B - Decision] Line {line} (in <g> at line {g_line}): "
                f"diamond <polygon> <g data-node=\"{dn}\"> must have data-node-type=\"decision\""
            )
        if not dn.startswith("D_"):
            errors.append(
                f"[Check B - Decision] Line {line} (in <g> at line {g_line}): "
                f"decision diamond data-node=\"{dn}\" must start with \"D_\""
            )

    for nid in sorted(decision_node_ids):
        if nid in parser.flow_nodes:
            if not nid.startswith("D_"):
                errors.append(
                    f"[Check B - Decision] Decision node \"{nid}\" in flow SVG must start with \"D_\""
                )
            if parser.flow_node_types.get(nid) != "decision":
                errors.append(
                    f"[Check B - Decision] <g data-node=\"{nid}\"> must declare data-node-type=\"decision\""
                )
            if not outgoing_by_node.get(nid):
                errors.append(
                    f"[Check B - Decision] Decision node \"{nid}\" has no outgoing <polyline> edges"
                )

    # --- Check C: Interactive elements anchors & conditional branch duplicate check ---
    for line, tag, attrs in parser.interactive_elements:
        missing = [k for k in ("data-comp-id", "data-comp-name") if not attrs.get(k, "").strip()]
        if missing:
            cls = attrs.get("class", "")
            desc = f'<{tag} class="{cls}">' if cls else f"<{tag}>"
            errors.append(
                f"[Check C - Anchor] Line {line}: {desc} missing {', '.join(missing)}"
            )

    for scoped_cid, occs in parser.comp_occurrences.items():
        if len(occs) <= 1:
            continue
        conflicting_lines: Set[int] = set()
        for i in range(len(occs)):
            ln1, c1 = occs[i]
            for j in range(i + 1, len(occs)):
                ln2, c2 = occs[j]
                if not _conditions_mutually_exclusive(c1, c2):
                    conflicting_lines.add(ln1)
                    conflicting_lines.add(ln2)
        if conflicting_lines:
            sorted_lns = sorted(conflicting_lines)
            errors.append(
                f"[Check C - Anchor] Duplicate data-comp-id=\"{scoped_cid}\" in non-exclusive scope at lines "
                f"{', '.join(map(str, sorted_lns))}"
            )

    # --- Check D: NODES referenced pages exist in DOM (.page / .proto-page / data-page / data-page-id) ---
    if nodes_obj is None:
        errors.append("[Check D - NODES] Could not find NODES definition in <script> blocks")
    else:
        for node_id, node_def in nodes_obj.items():
            if not isinstance(node_def, dict):
                errors.append(f"[Check D - NODES] Node \"{node_id}\" in NODES must be an object")
                continue
            page_id = str(node_def.get("page") or "").strip()
            if page_id and page_id not in parser.dom_page_ids:
                errors.append(
                    f"[Check D - NODES] Node \"{node_id}\" references page=\"{page_id}\", "
                    "which does not exist in DOM (.page / .proto-page / data-page / data-page-id)"
                )

    # --- Check E: Single-file offline integrity ---
    for line, tag, attr_name, url_val in parser.external_refs:
        errors.append(
            f"[Check E - Offline] Line {line}: External resource <{tag} {attr_name}=\"{url_val}\"> is forbidden"
        )
    for line, ext_css in parser.inline_css_external_refs:
        errors.append(
            f"[Check E - Offline] Line {line}: External CSS reference \"{ext_css}\" in inline style is forbidden"
        )
    for s_line, _, _, css_text in parser.styles:
        for ext_css in _find_css_external_urls(css_text):
            errors.append(
                f"[Check E - Offline] <style> at line {s_line}: External CSS reference \"{ext_css}\" is forbidden"
            )

    # --- Check F: Pure Grayscale + Single Amber Accent & Zero Emoji ---
    for line, location, em in parser.emoji_violations:
        errors.append(
            f"[Check F - Emoji] Line {line}: Colorful Emoji {em!r} found in {location} "
            "(use monochrome wireframe symbols only)"
        )
    for line, location, bad_color in parser.color_violations:
        errors.append(
            f"[Check F - Color] Line {line}: Disallowed non-grayscale skin color \"{bad_color}\" in {location}"
        )
    for s_line, s_attrs, scan_colors, css_text in parser.styles:
        if scan_colors:
            sid = s_attrs.get("id") or "inline-page-style"
            for prop_s, bad_color in _scan_stylesheet_colors(css_text):
                errors.append(
                    f"[Check F - Color] <style id=\"{sid}\"> (line {s_line}): "
                    f"Disallowed non-grayscale skin color \"{bad_color}\" in property \"{prop_s}\""
                )

    # --- Check G: SPEC_CARDS page & anchor existence in DOM ---
    if spec_cards_arr is not None:
        for idx, card in enumerate(spec_cards_arr):
            if not isinstance(card, dict):
                errors.append(f"[Check G - SpecCards] SPEC_CARDS[{idx}] must be an object")
                continue
            cid = str(card.get("id") or f"#{idx}")
            cpage = str(card.get("page") or "").strip()
            canchor = str(card.get("anchor") or "").strip()
            if not cpage or cpage not in parser.dom_page_ids:
                errors.append(
                    f"[Check G - SpecCards] Card \"{cid}\" references page=\"{cpage}\", "
                    "which does not exist in DOM"
                )
                continue
            if canchor and canchor not in parser.page_anchors.get(cpage, set()):
                errors.append(
                    f"[Check G - SpecCards] Card \"{cid}\" anchor=\"{canchor}\" not found in page \"{cpage}\" "
                    f"(expected [data-comp-id=\"{canchor}\"] or [data-anchor=\"{canchor}\"])"
                )

    return errors


def _resolve_spec_page_anchors(
    page_id: str,
    pages: Dict[str, Any],
    visited: Optional[Set[str]] = None,
) -> Optional[Set[str]]:
    """Resolve declared component IDs/anchors for a page in spec.json (including variant_of chain).

    Returns None if neither the page nor its base declares a `components` list.
    """
    seen = visited or set()
    if page_id in seen or page_id not in pages or not isinstance(pages[page_id], dict):
        return None
    seen.add(page_id)
    pdef = pages[page_id]

    anchors: Optional[Set[str]] = None
    base_id = pdef.get("variant_of")
    if isinstance(base_id, str) and base_id.strip():
        anchors = _resolve_spec_page_anchors(base_id.strip(), pages, seen)

    comps = pdef.get("components")
    if isinstance(comps, list):
        if anchors is None:
            anchors = set()
        for comp in comps:
            if isinstance(comp, dict):
                if isinstance(comp.get("comp_id"), str) and comp["comp_id"].strip():
                    anchors.add(comp["comp_id"].strip())
                if isinstance(comp.get("anchor"), str) and comp["anchor"].strip():
                    anchors.add(comp["anchor"].strip())

    overrides = pdef.get("overrides")
    if isinstance(overrides, dict):
        removed = overrides.get("remove_components")
        if isinstance(removed, list) and anchors is not None:
            for rem in removed:
                if isinstance(rem, str):
                    anchors.discard(rem)
        added = overrides.get("add_components")
        if isinstance(added, list):
            if anchors is None:
                anchors = set()
            for comp in added:
                if isinstance(comp, dict):
                    if isinstance(comp.get("comp_id"), str) and comp["comp_id"].strip():
                        anchors.add(comp["comp_id"].strip())
                    if isinstance(comp.get("anchor"), str) and comp["anchor"].strip():
                        anchors.add(comp["anchor"].strip())

    return anchors


def run_spec_preflight(spec_path: Path) -> List[str]:
    """Run static preflight checks on a spec-v2 JSON file and return error messages."""
    try:
        raw = spec_path.read_text(encoding="utf-8")
        data: Any = json.loads(raw)
    except Exception as exc:
        return [f"[Spec - JSON] Failed to parse JSON: {exc}"]

    if not isinstance(data, dict):
        return ["[Spec - Root] Top-level value must be a JSON object"]

    errors: List[str] = []

    # 1. Required top-level fields & types
    if data.get("version") != "spec-v2":
        errors.append(f"[Spec - Version] version must be \"spec-v2\", got {data.get('version')!r}")

    required_types: Dict[str, type] = {
        "meta": dict,
        "vars": list,
        "nodes": dict,
        "pages": dict,
    }
    for key, expected_type in required_types.items():
        if key not in data:
            errors.append(f"[Spec - Required] Missing required top-level field \"{key}\"")
        elif not isinstance(data[key], expected_type):
            errors.append(
                f"[Spec - Type] Field \"{key}\" must be {expected_type.__name__}, got {type(data[key]).__name__}"
            )

    if errors:
        return errors

    meta: Dict[str, Any] = data["meta"]
    nodes: Dict[str, Any] = data["nodes"]
    pages: Dict[str, Any] = data["pages"]
    vars_list: List[Any] = data["vars"]

    if not nodes:
        errors.append("[Spec - Nodes] \"nodes\" must be a non-empty object")
    if not pages:
        errors.append("[Spec - Pages] \"pages\" must be a non-empty object")

    # 1b. Validate meta.project, meta.title, meta.entry_node
    for meta_req in ("project", "title"):
        val = meta.get(meta_req)
        if not isinstance(val, str) or not val.strip():
            errors.append(f"[Spec - Meta] meta.{meta_req} must be a non-empty string")

    entry_node = meta.get("entry_node")
    if not isinstance(entry_node, str) or not entry_node.strip():
        errors.append("[Spec - Meta] meta.entry_node must be a non-empty string")
    elif entry_node not in nodes:
        errors.append(
            f"[Spec - Meta] meta.entry_node=\"{entry_node}\" does not exist in nodes"
        )

    var_ids: Set[str] = set()
    var_options_map: Dict[str, Set[str]] = {}
    for idx, v in enumerate(vars_list):
        if isinstance(v, dict) and isinstance(v.get("id"), str) and v["id"].strip():
            vid = v["id"].strip()
            if vid in var_ids:
                errors.append(f"[Spec - Vars] Duplicate var id=\"{vid}\"")
            var_ids.add(vid)
            opts = v.get("options")
            if isinstance(opts, list):
                var_options_map[vid] = {
                    o["id"].strip()
                    for o in opts
                    if isinstance(o, dict) and isinstance(o.get("id"), str) and o["id"].strip()
                }
        else:
            errors.append(f"[Spec - Vars] vars[{idx}] must be an object with non-empty \"id\"")

    # 2. Validate pages & variant_of inheritance
    for page_id, page_def in pages.items():
        if not isinstance(page_def, dict):
            errors.append(f"[Spec - Pages] Page \"{page_id}\" must be an object")
            continue
        frame = page_def.get("frame")
        if frame not in ("phone", "wide"):
            errors.append(
                f"[Spec - Pages] Page \"{page_id}\" frame must be \"phone\" or \"wide\", got {frame!r}"
            )
        base_id = page_def.get("variant_of")
        if base_id is not None:
            if not isinstance(base_id, str) or not base_id.strip():
                errors.append(f"[Spec - Variant] Page \"{page_id}\" has invalid variant_of={base_id!r}")
            elif base_id not in pages:
                errors.append(
                    f"[Spec - Variant] Page \"{page_id}\" variant_of=\"{base_id}\" does not exist in pages"
                )
            else:
                seen: Set[str] = {page_id}
                cur: Optional[str] = base_id
                while cur is not None:
                    if cur in seen:
                        errors.append(
                            f"[Spec - Variant] Cycle detected in variant_of chain starting at \"{page_id}\""
                        )
                        break
                    seen.add(cur)
                    cur_def = pages.get(cur)
                    cur = cur_def.get("variant_of") if isinstance(cur_def, dict) else None

    # Validate state_groups early so nodes[].state can cross-check against it
    state_groups = data.get("state_groups")
    valid_state_refs: Set[str] = set()
    if state_groups is not None:
        if not isinstance(state_groups, dict):
            errors.append("[Spec - StateGroups] state_groups must be an object")
        else:
            for gid, gdef in state_groups.items():
                if not isinstance(gdef, dict) or not isinstance(gdef.get("states"), list) or not gdef["states"]:
                    errors.append(f"[Spec - StateGroups] Group \"{gid}\" must contain a non-empty \"states\" array")
                    continue
                for st in gdef["states"]:
                    if not isinstance(st, dict):
                        errors.append(f"[Spec - StateGroups] Group \"{gid}\" state entry must be an object")
                        continue
                    sid = st.get("id")
                    spage = st.get("page")
                    if isinstance(sid, str) and sid.strip():
                        valid_state_refs.add(f"{gid}/{sid.strip()}")
                    if spage not in pages:
                        errors.append(
                            f"[Spec - StateGroups] State \"{gid}/{sid}\" references unknown page=\"{spage}\""
                        )

    # 3. Validate nodes[].page, decision branchVar, state, and nodes[].change enum
    for node_id, node_def in nodes.items():
        if not isinstance(node_def, dict):
            errors.append(f"[Spec - Nodes] Node \"{node_id}\" must be an object")
            continue
        title = node_def.get("title")
        if not isinstance(title, str) or not title.strip():
            errors.append(f"[Spec - Nodes] Node \"{node_id}\" missing non-empty \"title\"")
        page_ref = node_def.get("page")
        if not isinstance(page_ref, str) or not page_ref.strip():
            errors.append(f"[Spec - Nodes] Node \"{node_id}\" missing non-empty \"page\"")
        elif page_ref not in pages:
            errors.append(
                f"[Spec - Nodes] Node \"{node_id}\" references page=\"{page_ref}\", which does not exist in pages"
            )

        if "change" in node_def:
            chg = node_def.get("change")
            if not isinstance(chg, str) or chg not in ALLOWED_NODE_CHANGES:
                errors.append(
                    f"[Spec - Nodes] Node \"{node_id}\" has invalid change={chg!r} "
                    f"(expected one of {sorted(ALLOWED_NODE_CHANGES)})"
                )

        if "state" in node_def and node_def["state"] is not None:
            st_ref = node_def["state"]
            if not isinstance(st_ref, str) or st_ref not in valid_state_refs:
                errors.append(
                    f"[Spec - Nodes] Node \"{node_id}\" references state={st_ref!r}, which is not in state_groups"
                )

        if node_def.get("isDecision") is True:
            if not node_id.startswith("D_"):
                errors.append(
                    f"[Spec - Nodes] Decision node \"{node_id}\" (isDecision: true) must have an ID starting with \"D_\""
                )
            bvar = node_def.get("branchVar")
            if not isinstance(bvar, str) or bvar not in var_ids:
                errors.append(
                    f"[Spec - Nodes] Decision node \"{node_id}\" references branchVar={bvar!r}, which is not in vars"
                )

    # 4. Validate vars[].kind, vars[].default in options, diamond, target, and when
    for idx, v in enumerate(vars_list):
        if not isinstance(v, dict):
            continue
        vid = v.get("id", f"vars[{idx}]")
        kind = v.get("kind")
        if kind not in ("global", "local", "branch"):
            errors.append(
                f"[Spec - Vars] Var \"{vid}\" kind must be \"global\", \"local\", or \"branch\", got {kind!r}"
            )

        if kind == "branch":
            diamond = v.get("diamond")
            if not isinstance(diamond, str) or not diamond.strip():
                errors.append(f"[Spec - Vars] Branch var \"{vid}\" missing non-empty \"diamond\"")
            elif diamond not in nodes:
                errors.append(
                    f"[Spec - Vars] Branch var \"{vid}\" diamond=\"{diamond}\" does not exist in nodes"
                )
            elif not (isinstance(nodes[diamond], dict) and nodes[diamond].get("isDecision") is True):
                errors.append(
                    f"[Spec - Vars] Branch var \"{vid}\" diamond=\"{diamond}\" is not a decision node (isDecision: true)"
                )
            v_nodes = v.get("nodes")
            if isinstance(v_nodes, list):
                for vn in v_nodes:
                    if vn not in nodes:
                        errors.append(
                            f"[Spec - Vars] Branch var \"{vid}\" nodes entry \"{vn}\" does not exist in nodes"
                        )

        if kind == "local":
            v_pages = v.get("pages")
            if not isinstance(v_pages, list) or not v_pages:
                errors.append(f"[Spec - Vars] Local var \"{vid}\" must declare a non-empty \"pages\" array")
            else:
                for p in v_pages:
                    if p not in pages:
                        errors.append(
                            f"[Spec - Vars] Local var \"{vid}\" references page=\"{p}\", which does not exist in pages"
                        )

        options = v.get("options")
        opt_ids: Set[str] = set()
        if not isinstance(options, list) or not options:
            errors.append(f"[Spec - Vars] Var \"{vid}\" must have a non-empty \"options\" array")
        else:
            for opt_idx, opt in enumerate(options):
                if not isinstance(opt, dict):
                    errors.append(f"[Spec - Vars] Var \"{vid}\" options[{opt_idx}] must be an object")
                    continue
                oid = opt.get("id")
                olabel = opt.get("label")
                if not isinstance(oid, str) or not oid.strip():
                    errors.append(f"[Spec - Vars] Var \"{vid}\" options[{opt_idx}] missing non-empty \"id\"")
                else:
                    if oid in opt_ids:
                        errors.append(f"[Spec - Vars] Var \"{vid}\" has duplicate option id=\"{oid}\"")
                    opt_ids.add(oid)
                if not isinstance(olabel, str) or not olabel.strip():
                    errors.append(f"[Spec - Vars] Var \"{vid}\" options[{opt_idx}] missing non-empty \"label\"")

                target = opt.get("target")
                if kind == "branch" and (not isinstance(target, str) or not target.strip()):
                    errors.append(
                        f"[Spec - Vars] Branch var \"{vid}\" option \"{opt.get('id', opt_idx)}\" missing \"target\""
                    )
                elif isinstance(target, str) and target not in nodes:
                    errors.append(
                        f"[Spec - Vars] Var \"{vid}\" option \"{opt.get('id', opt_idx)}\" "
                        f"target=\"{target}\" does not exist in nodes"
                    )

        default_val = v.get("default")
        if not isinstance(default_val, str) or not default_val.strip():
            errors.append(f"[Spec - Vars] Var \"{vid}\" missing non-empty \"default\"")
        elif opt_ids and default_val not in opt_ids:
            errors.append(
                f"[Spec - Vars] Var \"{vid}\" default=\"{default_val}\" is not in options ({sorted(opt_ids)})"
            )

        when_obj = v.get("when")
        if when_obj is not None:
            if not isinstance(when_obj, dict):
                errors.append(f"[Spec - Vars] Var \"{vid}\" when must be an object")
            else:
                for dep_var, dep_expected in when_obj.items():
                    if dep_var not in var_ids:
                        errors.append(
                            f"[Spec - Vars] Var \"{vid}\" when references unknown var \"{dep_var}\""
                        )
                    else:
                        allowed_dep_opts = var_options_map.get(dep_var, set())
                        exp_vals = [dep_expected] if isinstance(dep_expected, str) else (
                            dep_expected if isinstance(dep_expected, list) else []
                        )
                        if not exp_vals:
                            errors.append(
                                f"[Spec - Vars] Var \"{vid}\" when[\"{dep_var}\"] must be a non-empty string or array"
                            )
                        for ev in exp_vals:
                            if not isinstance(ev, str) or (allowed_dep_opts and ev not in allowed_dep_opts):
                                errors.append(
                                    f"[Spec - Vars] Var \"{vid}\" when[\"{dep_var}\"] value {ev!r} not in options"
                                )

    # 5. Validate spec_cards references & component anchors
    spec_cards = data.get("spec_cards")
    card_ids: Set[str] = set()
    if spec_cards is not None:
        if not isinstance(spec_cards, list):
            errors.append("[Spec - SpecCards] spec_cards must be an array")
        else:
            for c_idx, card in enumerate(spec_cards):
                if not isinstance(card, dict):
                    errors.append(f"[Spec - SpecCards] spec_cards[{c_idx}] must be an object")
                    continue
                cid = card.get("id")
                if not isinstance(cid, str) or not cid.strip():
                    errors.append(f"[Spec - SpecCards] spec_cards[{c_idx}] missing non-empty \"id\"")
                    cid_str = f"#{c_idx}"
                else:
                    cid_str = cid.strip()
                    if cid_str in card_ids:
                        errors.append(f"[Spec - SpecCards] Duplicate spec_card id=\"{cid_str}\"")
                    card_ids.add(cid_str)

                for req_f in ("title", "body"):
                    if not isinstance(card.get(req_f), str) or not card[req_f].strip():
                        errors.append(
                            f"[Spec - SpecCards] Card \"{cid_str}\" missing non-empty \"{req_f}\""
                        )

                cpage = card.get("page")
                if not isinstance(cpage, str) or cpage not in pages:
                    errors.append(
                        f"[Spec - SpecCards] Card \"{cid_str}\" references unknown page={cpage!r}"
                    )
                    continue

                canchor = card.get("anchor")
                if isinstance(canchor, str) and canchor.strip():
                    declared_anchors = _resolve_spec_page_anchors(cpage, pages)
                    if declared_anchors is not None and canchor.strip() not in declared_anchors:
                        errors.append(
                            f"[Spec - SpecCards] Card \"{cid_str}\" anchor=\"{canchor.strip()}\" "
                            f"is not declared in page \"{cpage}\" components"
                        )

    # 6. Validate memos[] and memos[].targets structure (anchor-schema v2)
    memos = data.get("memos")
    if memos is not None:
        if not isinstance(memos, list):
            errors.append("[Spec - Memos] memos must be an array")
        else:
            for m_idx, memo in enumerate(memos):
                if not isinstance(memo, dict):
                    errors.append(f"[Spec - Memos] memos[{m_idx}] must be an object")
                    continue
                mid = memo.get("id") or f"#{m_idx}"
                if "granularity" in memo:
                    errors.append(
                        f"[Spec - Memos] Memo \"{mid}\" uses deprecated field \"granularity\"; "
                        "use targets: [{page, comp_id, comp_name, fallback_selector}]"
                    )
                for req_str in ("id", "version_hash", "page", "text"):
                    if not isinstance(memo.get(req_str), str) or not memo[req_str].strip():
                        errors.append(
                            f"[Spec - Memos] Memo \"{mid}\" missing required non-empty string \"{req_str}\""
                        )
                if memo.get("status") not in ("valid", "invalid"):
                    errors.append(
                        f"[Spec - Memos] Memo \"{mid}\" status must be \"valid\" or \"invalid\", "
                        f"got {memo.get('status')!r}"
                    )
                if memo.get("view") not in ("flow", "spec"):
                    errors.append(
                        f"[Spec - Memos] Memo \"{mid}\" view must be \"flow\" or \"spec\", "
                        f"got {memo.get('view')!r}"
                    )
                if not isinstance(memo.get("node"), str):
                    errors.append(f"[Spec - Memos] Memo \"{mid}\" field \"node\" must be a string")
                elif memo["node"].strip() and memo.get("status") == "valid" and memo["node"] not in nodes:
                    errors.append(
                        f"[Spec - Memos] Valid memo \"{mid}\" references unknown node=\"{memo['node']}\""
                    )
                if isinstance(memo.get("page"), str) and memo.get("status") == "valid" and memo["page"] not in pages:
                    errors.append(
                        f"[Spec - Memos] Valid memo \"{mid}\" references unknown page=\"{memo['page']}\""
                    )
                if not isinstance(memo.get("vars"), dict):
                    errors.append(f"[Spec - Memos] Memo \"{mid}\" field \"vars\" must be an object")
                if not isinstance(memo.get("time"), str):
                    errors.append(f"[Spec - Memos] Memo \"{mid}\" field \"time\" must be a string")

                targets = memo.get("targets")
                if not isinstance(targets, list):
                    errors.append(
                        f"[Spec - Memos] Memo \"{mid}\" must contain a \"targets\" array"
                    )
                else:
                    for t_idx, tgt in enumerate(targets):
                        if not isinstance(tgt, dict):
                            errors.append(
                                f"[Spec - Memos] Memo \"{mid}\" targets[{t_idx}] must be an object"
                            )
                            continue
                        for t_req in ("page", "comp_id", "comp_name"):
                            if not isinstance(tgt.get(t_req), str) or not tgt[t_req].strip():
                                errors.append(
                                    f"[Spec - Memos] Memo \"{mid}\" targets[{t_idx}] missing non-empty \"{t_req}\""
                                )
                        if "fallback_selector" not in tgt or not isinstance(tgt.get("fallback_selector"), str):
                            errors.append(
                                f"[Spec - Memos] Memo \"{mid}\" targets[{t_idx}] missing string \"fallback_selector\""
                            )
                        if (
                            memo.get("status") == "valid"
                            and isinstance(tgt.get("page"), str)
                            and tgt["page"].strip()
                            and tgt["page"] not in pages
                        ):
                            errors.append(
                                f"[Spec - Memos] Valid memo \"{mid}\" targets[{t_idx}] references unknown page=\"{tgt['page']}\""
                            )

    return errors


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="preflight_check.py",
        description=(
            "Static preflight gate for walkthrough.html or spec.json (spec-v2).\n"
            "HTML checks: (A) flow SVG <polyline> topology & <=16px endpoint geometry, "
            "(B) D_* decision diamonds & data-branch, "
            "(C) interactive anchors (.wt-modal/.wt-tab & conditional branch scopes), "
            "(D) NODES -> DOM .page references, "
            "(E) offline integrity, "
            "(F) pure grayscale + single amber accent & zero colorful Emoji, "
            "(G) SPEC_CARDS page & anchor existence.\n"
            "JSON checks: spec-v2 meta/vars/nodes/pages/state_groups/spec_cards/memos.targets."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "target_file",
        type=Path,
        help="Path to the walkthrough.html or spec.json file to validate.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    arg_parser = build_arg_parser()
    args = arg_parser.parse_args(argv)

    target_path: Path = args.target_file
    if not target_path.is_file():
        print(f"ERROR: File not found: {target_path}", file=sys.stderr)
        return 2

    if target_path.suffix.lower() == ".json":
        errors = run_spec_preflight(target_path)
    else:
        errors = run_preflight(target_path)

    if errors:
        print(f"PREFLIGHT FAILED ({len(errors)} issue(s)) for {target_path}:", file=sys.stderr)
        for idx, err in enumerate(errors, start=1):
            print(f"  {idx}. {err}", file=sys.stderr)
        return 1

    print(f"PREFLIGHT PASSED: {target_path} (all checks passed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
