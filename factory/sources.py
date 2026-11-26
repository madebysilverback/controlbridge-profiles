"""
Public sources the factory reads. Only facts (which button does what, which
key a PC version uses, the program's file name) are taken from them.

  StrategyWiki  - controls pages, often PlayStation and PC side by side.
                  Text is CC BY-SA 4.0: credited in each profile.
  PCGamingWiki  - PC details: input notes, where settings files live.
                  CC BY-NC-SA 3.0: fine while Tapsquatch is free.
  SteamCMD      - the program file Steam launches (no login needed).
"""

import os
import re
import subprocess

from common import get

SW_API = "https://strategywiki.org/w/api.php"
PCGW_API = "https://www.pcgamingwiki.com/w/api.php"
STEAMCMD = os.environ.get("STEAMCMD", os.path.expanduser("~/steamcmd/steamcmd.sh"))


def _wikitext(api, title):
    try:
        d = get(api, {"action": "parse", "page": title, "prop": "wikitext", "format": "json",
                      "formatversion": "2", "redirects": "1"})
    except RuntimeError:
        return None, None
    if "error" in d:
        return None, None
    return d["parse"]["title"], d["parse"]["wikitext"]


def _search(api, text):
    try:
        d = get(api, {"action": "query", "list": "search", "srsearch": text, "srlimit": "5",
                      "format": "json", "formatversion": "2"})
    except RuntimeError:
        return []
    return [r["title"] for r in d.get("query", {}).get("search", [])]


def _clean(wt, limit):
    wt = re.sub(r"<!--.*?-->", "", wt, flags=re.S)
    wt = re.sub(r"\[\[(?:File|Image):[^\]]*\]\]", "", wt)
    wt = re.sub(r"\n{3,}", "\n\n", wt)
    return wt.strip()[:limit]


def strategywiki_controls(name):
    """(page url, controls text) or (None, None)."""
    titles = []
    for t in _search(SW_API, name):
        if "/" not in t:
            titles.append(t)
    for base in titles[:3] or [name]:
        title, wt = _wikitext(SW_API, f"{base}/Controls")
        if not wt:
            title, wt = _wikitext(SW_API, base)
            if wt:
                m = re.search(r"==\s*Controls\s*==(.*?)(\n==[^=]|\Z)", wt, re.S | re.I)
                wt = m.group(1) if m else None
        if wt and re.search(r"(PlayStation|PS2|PS1|Triangle|Circle|Cross|Square)", wt, re.I):
            url = "https://strategywiki.org/wiki/" + title.replace(" ", "_")
            return url, _clean(wt, 12000)
    return None, None


def pcgamingwiki(name, pcgw_id=None):
    """(page url, PC details text, native controller support guess) or (None, None, None)."""
    title, wt = _wikitext(PCGW_API, pcgw_id or name)
    if not wt:
        for t in _search(PCGW_API, name)[:1]:
            title, wt = _wikitext(PCGW_API, t)
    if not wt:
        return None, None, None
    parts = []
    for heading in ("Configuration file\\(s\\) location", "Input", "Game data"):
        m = re.search(r"==+\s*" + heading + r"\s*==+(.*?)(\n==[^=]|\Z)", wt, re.S | re.I)
        if m:
            parts.append(m.group(0))
    native = None
    m = re.search(r"\|\s*controller support\s*=\s*(\w+)", wt, re.I)
    if m:
        native = m.group(1).lower() == "true"
    url = "https://www.pcgamingwiki.com/wiki/" + title.replace(" ", "_")
    return url, _clean("\n".join(parts), 7000), native


# ---------------------------------------------------------------- SteamCMD

def parse_vdf(text):
    """Small reader for Valve's text format: quoted strings and { }."""
    tokens = re.findall(r'"((?:[^"\\]|\\.)*)"|([{}])', text)
    pos = 0

    def block():
        nonlocal pos
        out = {}
        while pos < len(tokens):
            s, brace = tokens[pos]
            pos += 1
            if brace == "}":
                return out
            if brace == "{":
                continue
            key = s
            if pos < len(tokens) and tokens[pos][1] == "{":
                pos += 1
                out[key] = block()
            elif pos < len(tokens):
                out[key] = tokens[pos][0]
                pos += 1
        return out
    return block()


def launch_exes(appinfo):
    """Windows program files from one app's info."""
    exes = []
    launch = appinfo.get("config", {}).get("launch", {})
    for entry in launch.values():
        if not isinstance(entry, dict):
            continue
        exe = entry.get("executable", "")
        osl = entry.get("config", {}).get("oslist", "windows") if isinstance(entry.get("config"), dict) else "windows"
        if exe.lower().endswith(".exe") and "windows" in osl:
            exes.append(exe.replace("\\\\", "\\"))
    return exes


def steam_exes(appids):
    """{appid: [program files]} for many games in one SteamCMD run."""
    appids = [str(a) for a in appids if a]
    if not appids or not os.path.isfile(STEAMCMD):
        return {}
    cmd = [STEAMCMD, "+login", "anonymous", "+app_info_update", "1"]
    for a in appids:
        cmd += ["+app_info_print", a]
    cmd += ["+quit"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=600).stdout
    except (subprocess.TimeoutExpired, OSError):
        return {}
    result = {}
    for a in appids:
        m = re.search(r'^"%s"\s*\{' % re.escape(a), out, re.M)
        if not m:
            continue
        depth, i = 0, m.end() - 1
        for j in range(i, len(out)):
            if out[j] == "{":
                depth += 1
            elif out[j] == "}":
                depth -= 1
                if depth == 0:
                    info = parse_vdf(out[m.start():j + 1]).get(a, {})
                    result[a] = launch_exes(info)
                    break
    return result
