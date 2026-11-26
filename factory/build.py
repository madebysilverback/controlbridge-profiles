"""Turns the collected facts into a Tapsquatch profile with Claude."""

import json
import os
import re
import time
import urllib.error
import urllib.request

from common import BUTTONS, KEYS, slug

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")


def ai_available():
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))


def ask_ai(prompt):
    """Free Gemini key first; a paid Claude key only if that's all there is."""
    if os.environ.get("GEMINI_API_KEY"):
        return ask_gemini(prompt, os.environ["GEMINI_API_KEY"])
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ask_claude(prompt, os.environ["ANTHROPIC_API_KEY"])
    raise RuntimeError("no AI key set")


def ask_gemini(prompt, key):
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}}).encode()
    url = GEMINI_URL.format(model=GEMINI_MODEL)
    for i in range(4):
        req = urllib.request.Request(url, data=body, method="POST", headers={
            "x-goog-api-key": key, "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read().decode())
            time.sleep(7)                      # stay well inside the free per-minute limit
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and i < 3:
                time.sleep(30 * (i + 1))       # free limit reached: wait and try again
                continue
            raise RuntimeError(f"Gemini API {e.code}: {e.read().decode(errors='ignore')[:200]}")
    raise RuntimeError("Gemini API did not answer (free daily limit may be used up)")

PROMPT = """You are building a controller profile for Tapsquatch, a free Windows app that lets a
PS5 DualSense play a PC game using the button layout of the game's PlayStation version.
Keys are NOT fixed in the profile: on each player's PC the app reads the game's own key
settings and finds the key bound to each "command". So for every button, give the PC game's
command names for that action (as they would appear in its settings files, e.g. "Jump",
"Duck", "Use", "Fire", "AltFire", "NextWeapon") and the PC version's normal default key.

GAME: {name}
PLAYSTATION VERSIONS: {ps}
STEAM PROGRAM FILES: {exes}

CONTROLS (StrategyWiki, may list several platforms):
<<<
{sw}
>>>

PC DETAILS (PCGamingWiki):
<<<
{pcgw}
>>>
{reports}
Rules:
- Use the OLDEST PlayStation version listed above whose controls you can see, and name it.
- Only map what the sources support. Leave out buttons you can't support from the sources.
- default_key must be one of: {keys}
- Two buttons must not share a default_key.
- Set "sure": false when the PC key or the PlayStation button is a guess.
- If the sources don't describe this game's controls at all, reply {{"skip": "reason"}}.

Reply with ONLY this JSON:
{{
  "playstation_version": "PS2 (2004)",
  "exe": ["Game.exe"],
  "buttons": {{
    "<one of {buttons}>": {{"action": "Jump", "commands": ["Jump"], "default_key": "SPACE", "sure": true}}
  }},
  "left_stick": {{"up_commands": ["MoveForward"], "up_default": "W", "down_commands": ["MoveBackward"], "down_default": "S",
                  "left_commands": ["StrafeLeft"], "left_default": "A", "right_commands": ["StrafeRight"], "right_default": "D"}},
  "right_stick_mouse": true,
  "analog_speed_by_mouse_wheel": false,
  "config_hints": ["%DOCUMENTS%\\\\My Games\\\\Game\\\\config.ini"],
  "notes": "one short sentence for players"
}}"""


def ask_claude(prompt, key):
    body = json.dumps({"model": MODEL, "max_tokens": 3000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    for i in range(3):
        req = urllib.request.Request(API_URL, data=body, method="POST", headers={
            "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read().decode())
            return "".join(p.get("text", "") for p in data.get("content", []))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 529) and i < 2:
                time.sleep(20 * (i + 1))
                continue
            raise RuntimeError(f"Claude API {e.code}: {e.read().decode(errors='ignore')[:200]}")
    raise RuntimeError("Claude API did not answer")


def parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON in reply")
    return json.loads(m.group(0))


def make_prompt(game, facts, reports=""):
    return PROMPT.format(
        name=game["name"], ps=", ".join(game.get("playstation", [])) or "unknown",
        exes=", ".join(facts.get("exes") or []) or "unknown",
        sw=facts.get("sw_text") or "(no controls page found)",
        pcgw=facts.get("pcgw_text") or "(no PC page found)",
        reports=f"\nPLAYER REPORTS ABOUT THE CURRENT PROFILE (fix these):\n<<<\n{reports}\n>>>\n" if reports else "",
        keys=", ".join(KEYS), buttons=", ".join(BUTTONS))


COMMON_WORDS = {"the", "of", "and", "tom", "clancy", "clancys", "edition", "game", "remastered", "definitive",
                "grand", "theft", "auto", "star", "wars", "final", "fantasy", "need", "for", "speed", "call", "duty"}
ROMAN = {"ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7", "viii": "8", "ix": "9", "x": "10"}


def folder_words(name):
    """The most telling words of a game's name, for finding its folder when
    the Steam ID doesn't match (e.g. 'San Andreas', not 'Grand Theft')."""
    words = [w for w in re.split(r"[^a-z0-9]+", name.lower()) if w]
    telling = [w for w in words if w not in COMMON_WORDS and (len(w) > 2 or w.isdigit() or w in ROMAN)]
    # Steam folders often write numbers as digits ("Grand Theft Auto 3")
    telling = [ROMAN.get(w, w) for w in telling]
    return telling[-2:] or words[-1:]


def from_table(game, facts, generation, buttons):
    """A profile straight from a StrategyWiki controls table - no AI needed."""
    reply = {"playstation_version": generation, "exe": facts.get("exes") or [],
             "buttons": {b: {**m, "sure": True} for b, m in buttons.items()},
             "left_stick": {}, "analog_speed_by_mouse_wheel": False,
             "notes": "Read from the controls table on StrategyWiki."}
    p = to_profile(game, facts, reply)
    p["status"] = "read from a public controls table"
    p["_note"] = p["_note"].replace("Made automatically with AI from public sources.",
                                    "Made automatically from a public controls table.")
    return p


def to_profile(game, facts, reply):
    """Claude's reply -> profile in Tapsquatch's library format (format 2)."""
    if reply.get("skip"):
        raise ValueError(f"skipped by AI: {reply['skip']}")
    buttons = {}
    for b, m in (reply.get("buttons") or {}).items():
        if b not in BUTTONS or not isinstance(m, dict):
            continue
        k = str(m.get("default_key") or "NONE").upper()
        e = {"action": str(m.get("action", ""))[:40],
             "commands": [str(c)[:40] for c in (m.get("commands") or [])][:4],
             "default_key": k if k in KEYS else "NONE"}
        if not m.get("sure", True) or e["default_key"] == "NONE":
            e["check"] = True
        buttons[b] = e
    buttons["ps"] = {"action": "Hold: show this button list", "default_key": "NONE"}
    ls_in = reply.get("left_stick") or {}
    ls = {"mode": "keys", "deadzone": 0.2, "diagonal_threshold": 0.38,
          "analog_speed": {"enabled": bool(reply.get("analog_speed_by_mouse_wheel")), "levels": 5,
                           "rezero_on_release": True}}
    for d, dflt in (("up", "W"), ("down", "S"), ("left", "A"), ("right", "D")):
        ls[f"{d}_commands"] = [str(c)[:40] for c in (ls_in.get(f"{d}_commands") or [])][:3]
        k = str(ls_in.get(f"{d}_default") or dflt).upper()
        ls[f"{d}_default"] = k if k in KEYS else dflt
    exes = [os.path.basename(e.replace("\\", "/")) for e in (reply.get("exe") or facts.get("exes") or [])]
    sources = {k: v for k, v in (("strategywiki", facts.get("sw_url")), ("pcgamingwiki", facts.get("pcgw_url"))) if v}
    return {
        "id": slug(game["name"]),
        "format": 2,
        "status": "made with AI",
        "updated": time.strftime("%Y-%m-%d", time.gmtime()),
        "name": game["name"],
        "playstation_version": str(reply.get("playstation_version") or ", ".join(game.get("playstation", [])))[:40],
        "exe": sorted({e for e in exes if e.lower().endswith(".exe")}),
        "steam_appid": game.get("steam_appid"),
        "wikidata": game.get("qid"),
        "overlay_button": "ps",
        "config_hints": [str(h)[:200] for h in (reply.get("config_hints") or [])][:3],
        "game_files": {"folder_contains": folder_words(game["name"]),
                       "text_folders": ["system", "System", "Localization", "localization"]},
        "_note": "Made automatically with AI from public sources. Keys are read from your own game "
                 "files when the game starts. " + str(reply.get("notes", ""))[:200],
        "sources": sources,
        "credits": "Controls from StrategyWiki (CC BY-SA 4.0); facts from PCGamingWiki. Layout licence: CC BY-SA 4.0.",
        "native_controller_support": facts.get("native"),
        "buttons": buttons,
        "left_stick": ls,
        "right_stick": {"mode": "mouse" if reply.get("right_stick_mouse", True) else "none",
                        "sensitivity": 18, "curve": 2.0, "deadzone": 0.12, "invert_y": False},
    }
