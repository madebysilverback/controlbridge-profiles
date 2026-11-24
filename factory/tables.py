"""
Free, no-AI route: reads StrategyWiki controls tables directly.

Many controls pages are tables with one column per platform, for example
    | Xbox | Windows | PlayStation 2 | Action |
so each row already says "this PlayStation button = this PC key = this action".
"""

import re

from common import KEYS

PS_HEADERS = [("playstation 2", "PS2"), ("ps2", "PS2"), ("playstation portable", "PSP"), ("psp", "PSP"),
              ("playstation 3", "PS3"), ("ps3", "PS3"), ("playstation 4", "PS4"), ("ps4", "PS4"),
              ("playstation 5", "PS5"), ("ps5", "PS5"), ("playstation", "PS1"), ("ps1", "PS1"), ("psx", "PS1")]
PS_ORDER = ["PS1", "PS2", "PSP", "PS3", "PS4", "PS5"]
PC_HEADERS = ("windows", "pc", "keyboard", "mouse", "computer")
ACTION_HEADERS = ("action", "function", "effect", "description", "command", "use")

PS_BUTTONS = {
    "triangle": "triangle", "circle": "circle", "cross": "cross", "x": "cross", "square": "square",
    "l1": "l1", "r1": "r1", "l2": "l2", "r2": "r2", "l3": "l3", "r3": "r3",
    "start": "options", "options": "options", "select": "create", "share": "create", "create": "create",
    "touchpad": "touchpad", "touch pad": "touchpad",
    "up": "dpad_up", "down": "dpad_down", "left": "dpad_left", "right": "dpad_right",
}

KEY_WORDS = {
    "space": "SPACE", "spacebar": "SPACE", "space bar": "SPACE",
    "shift": "LSHIFT", "left shift": "LSHIFT", "lshift": "LSHIFT", "right shift": "RSHIFT",
    "ctrl": "LCTRL", "control": "LCTRL", "left ctrl": "LCTRL", "left control": "LCTRL", "right ctrl": "RCTRL",
    "alt": "LALT", "left alt": "LALT", "right alt": "RALT", "enter": "ENTER", "return": "ENTER",
    "esc": "ESCAPE", "escape": "ESCAPE", "tab": "TAB", "backspace": "BACKSPACE", "caps lock": "CAPSLOCK",
    "del": "DELETE", "delete": "DELETE", "ins": "INSERT", "insert": "INSERT", "home": "HOME", "end": "END",
    "page up": "PAGEUP", "pgup": "PAGEUP", "page down": "PAGEDOWN", "pgdn": "PAGEDOWN",
    "up": "UP", "up arrow": "UP", "down": "DOWN", "down arrow": "DOWN",
    "left": "LEFT", "left arrow": "LEFT", "right": "RIGHT", "right arrow": "RIGHT",
    "left mouse": "MOUSE_LEFT", "left mouse button": "MOUSE_LEFT", "left click": "MOUSE_LEFT",
    "lmb": "MOUSE_LEFT", "mouse 1": "MOUSE_LEFT", "mouse1": "MOUSE_LEFT", "left button": "MOUSE_LEFT",
    "right mouse": "MOUSE_RIGHT", "right mouse button": "MOUSE_RIGHT", "right click": "MOUSE_RIGHT",
    "rmb": "MOUSE_RIGHT", "mouse 2": "MOUSE_RIGHT", "mouse2": "MOUSE_RIGHT", "right button": "MOUSE_RIGHT",
    "middle mouse": "MOUSE_MIDDLE", "middle mouse button": "MOUSE_MIDDLE", "middle click": "MOUSE_MIDDLE",
    "mouse wheel click": "MOUSE_MIDDLE", "mmb": "MOUSE_MIDDLE", "mouse 3": "MOUSE_MIDDLE",
    "mouse wheel up": "WHEEL_UP", "scroll up": "WHEEL_UP", "wheel up": "WHEEL_UP",
    "mouse wheel down": "WHEEL_DOWN", "scroll down": "WHEEL_DOWN", "wheel down": "WHEEL_DOWN",
}
for _n in range(10):
    for _w in (f"keypad {_n}", f"numpad {_n}", f"num {_n}", f"kp {_n}", f"numpad{_n}"):
        KEY_WORDS[_w] = f"NUMPAD{_n}"


def plain(cell):
    """Wiki markup -> plain words. {{Key|Shift}} -> Shift, {{Mouse|Left}} -> Left mouse."""
    s = cell

    def tmpl(m):
        parts = [p.strip() for p in m.group(1).split("|")]
        name, args = parts[0].lower(), [a for a in parts[1:] if "=" not in a]
        if "mouse" in name and args:
            return f"{args[-1]} mouse"
        return args[-1] if args else parts[0]
    for _ in range(3):
        s = re.sub(r"\{\{([^{}]*)\}\}", tmpl, s)
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"<[^>]+>", " / ", s)
    s = re.sub(r"'{2,}", "", s)
    return re.sub(r"\s+", " ", s).strip(" /")


def first_option(text):
    return re.split(r"\s*(?:/|,| or |;)\s*", text, maxsplit=1)[0].strip()


def ps_button(text):
    t = first_option(text).lower()
    t = re.sub(r"\b(button|key|the|directional|d-pad|dpad|digital|pad)\b", "", t).strip(" -")
    if "stick" in t or "analog" in t:
        return None
    return PS_BUTTONS.get(t)


def pc_key(text):
    t = first_option(text).strip().lower()
    t = re.sub(r"\b(key|button)\b$", "", t).strip()
    if t in KEY_WORDS:
        return KEY_WORDS[t]
    if re.fullmatch(r"[a-z0-9]", t):
        return t.upper()
    if re.fullmatch(r"f([1-9]|1[0-2])", t):
        return t.upper()
    up = t.upper().replace(" ", "_")
    return up if up in KEYS and up != "NONE" else None


def tables(wikitext):
    """Each wikitable as a list of rows (lists of cell text); first row = headers."""
    out = []
    for block in re.findall(r"\{\|(.*?)\n\|\}", wikitext, re.S):
        rows, row = [], []
        for line in block.split("\n"):
            line = line.strip()
            if line.startswith("|-"):
                if row:
                    rows.append(row)
                row = []
            elif line.startswith("!") or (line.startswith("|") and not line.startswith("|+")):
                sep = "!!" if line.startswith("!") else "||"
                for cell in line[1:].split(sep):
                    if "|" in cell and not cell.strip().startswith(("{{", "[[")) and "=" in cell.split("|")[0]:
                        cell = cell.split("|", 1)[1]          # drop cell styling
                    row.append(cell.strip())
        if row:
            rows.append(row)
        if len(rows) > 1:
            out.append(rows)
    return out


def from_wikitext(wikitext):
    """
    Returns (playstation_version, buttons) where buttons is
    {button: {"action", "commands", "default_key"}} or (None, {}) if no usable table.
    """
    best = (None, {})
    for rows in tables(wikitext or ""):
        head = [plain(h).lower() for h in rows[0]]
        ps_cols = {}
        for i, h in enumerate(head):
            for word, gen in PS_HEADERS:
                if word in h:
                    ps_cols.setdefault(gen, i)
                    break
        pc_col = next((i for i, h in enumerate(head) if any(w in h for w in PC_HEADERS)), None)
        act_col = next((i for i, h in enumerate(head) if any(w == h or h.startswith(w) for w in ACTION_HEADERS)),
                       len(head) - 1)
        if not ps_cols or pc_col is None:
            continue
        gen = min(ps_cols, key=PS_ORDER.index)
        ps_col = ps_cols[gen]
        buttons, used = {}, set()
        for r in rows[1:]:
            if len(r) <= max(ps_col, pc_col, act_col):
                continue
            btn = ps_button(plain(r[ps_col]))
            key = pc_key(plain(r[pc_col]))
            action = first_option(plain(r[act_col]))[:40]
            if not btn or not key or not action or btn in buttons or key in used:
                continue
            words = [w for w in re.split(r"\s*(?:/|,| and |;)\s*", plain(r[act_col])) if w][:3]
            buttons[btn] = {"action": action, "commands": [re.sub(r"[^A-Za-z0-9 ]", "", w).title().replace(" ", "")
                                                           for w in words][:3], "default_key": key}
            used.add(key)
        if len(buttons) > len(best[1]):
            best = (gen, buttons)
    return best
