"""Shared helpers for the Tapsquatch profile factory."""

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "library")
PROFILES = os.path.join(LIB, "profiles")
STATE = os.path.join(ROOT, "factory", "state.json")
AGENT = "TapsquatchProfileFactory/0.1 (+https://madebysilverback.com; free controller layouts)"

BUTTONS = ["cross", "circle", "square", "triangle", "l1", "r1", "l2", "r2", "l3", "r3",
           "create", "options", "touchpad", "dpad_up", "dpad_down", "dpad_left", "dpad_right"]

KEYS = (["ESCAPE", "TAB", "ENTER", "SPACE", "BACKSPACE", "CAPSLOCK", "LSHIFT", "RSHIFT", "LCTRL", "RCTRL",
         "LALT", "RALT", "UP", "DOWN", "LEFT", "RIGHT", "INSERT", "DELETE", "HOME", "END", "PAGEUP", "PAGEDOWN",
         "MINUS", "EQUALS", "LBRACKET", "RBRACKET", "SEMICOLON", "APOSTROPHE", "GRAVE", "BACKSLASH",
         "COMMA", "PERIOD", "SLASH", "NUMLOCK", "SCROLLLOCK", "NUMPAD_MULTIPLY", "NUMPAD_MINUS",
         "NUMPAD_PLUS", "NUMPAD_PERIOD", "NUMPAD_ENTER", "NUMPAD_DIVIDE",
         "MOUSE_LEFT", "MOUSE_RIGHT", "MOUSE_MIDDLE", "WHEEL_UP", "WHEEL_DOWN", "NONE"]
        + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
        + [f"F{n}" for n in range(1, 13)] + [f"NUMPAD{n}" for n in range(10)])


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:80]


def get(url, params=None, timeout=40, tries=3, as_json=True):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            time.sleep(1.0)                       # be polite to free services
            return json.loads(data) if as_json else data.decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"{url[:90]}: {last}")


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {"done": {}, "skipped": {}, "rebuilds": {}}


def save_state(state):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, sort_keys=True)


def validate(p):
    """List of problems; empty means the profile can be published."""
    problems = []
    if not p.get("name"):
        problems.append("no name")
    if not p.get("exe"):
        problems.append("no program file")
    btns = p.get("buttons", {})
    keyed = 0
    used = {}
    for b, m in btns.items():
        if b not in BUTTONS + ["ps"]:
            problems.append(f"unknown button {b}")
            continue
        k = m.get("default_key", "NONE")
        if k not in KEYS:
            problems.append(f"{b}: unknown key {k}")
        if k != "NONE":
            keyed += 1
            if k in used and not m.get("check"):
                problems.append(f"{b} and {used[k]} both use {k}")
            used.setdefault(k, b)
    if keyed < 4:
        problems.append("fewer than 4 buttons mapped")
    ls = p.get("left_stick", {})
    for d in ("up", "down", "left", "right"):
        if ls.get(f"{d}_default", "W") not in KEYS:
            problems.append(f"left stick {d}: unknown key")
    return problems


def write_profile(p):
    os.makedirs(PROFILES, exist_ok=True)
    path = os.path.join(PROFILES, f"{p['id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(p, f, indent=2, ensure_ascii=False)
    return path


def rebuild_index():
    entries = []
    for fn in sorted(os.listdir(PROFILES)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(PROFILES, fn)
        data = open(path, "rb").read()
        p = json.loads(data)
        entries.append({"id": p.get("id", fn[:-5]), "name": p.get("name"), "file": f"profiles/{fn}",
                        "sha256": hashlib.sha256(data).hexdigest(), "exe": p.get("exe", []),
                        "steam_appid": p.get("steam_appid"), "status": p.get("status", "made with AI"),
                        "updated": p.get("updated")})
    index = {"version": 1, "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "count": len(entries), "profiles": entries}
    with open(os.path.join(LIB, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, indent=1, ensure_ascii=False)
    return len(entries)
