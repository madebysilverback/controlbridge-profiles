"""
Handles what players send in, using the project's GitHub posts ("issues"):

  wrong-button  When a profile gets enough reports, it is rebuilt with the
                reports given to the AI, republished, and the reports closed.
  new-profile   A profile shared from the Profile Maker is checked and, if it
                is valid and the game isn't in the library yet, added.

Runs inside GitHub Actions (uses GITHUB_TOKEN and GITHUB_REPOSITORY).
"""

import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import PROFILES, ROOT, load_state, rebuild_index, save_state, slug, validate, write_profile  # noqa: E402

THRESHOLD = int(os.environ.get("REPORTS_BEFORE_REBUILD", "2"))
API = "https://api.github.com"


def gh(method, path, body=None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                                          "Accept": "application/vnd.github+json", "User-Agent": "cb-factory"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    return json.loads(data) if data else None


def open_issues(label):
    repo = os.environ["GITHUB_REPOSITORY"]
    return gh("GET", f"/repos/{repo}/issues?state=open&per_page=100&labels={label}") or []


def close(issue, message, label=None):
    repo = os.environ["GITHUB_REPOSITORY"]
    gh("POST", f"/repos/{repo}/issues/{issue['number']}/comments", {"body": message})
    if label:
        gh("POST", f"/repos/{repo}/issues/{issue['number']}/labels", {"labels": [label]})
    else:
        gh("PATCH", f"/repos/{repo}/issues/{issue['number']}", {"state": "closed"})


def group_reports(issues):
    by_profile = {}
    for i in issues:
        m = re.search(r"^profile:\s*([a-z0-9_]+)", i.get("body") or "", re.M)
        if m:
            by_profile.setdefault(m.group(1), []).append(i)
    return by_profile


def extract_profile(body):
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", body or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def shared_to_library(p):
    """A player's shared profile -> library format, with keys kept as defaults."""
    p = {k: v for k, v in p.items() if not k.startswith("_") or k == "_note"}
    for m in p.get("buttons", {}).values():
        if "key" in m and "default_key" not in m:
            m["default_key"] = m.pop("key")
    ls = p.get("left_stick", {})
    for d in ("up", "down", "left", "right"):
        if d in ls and f"{d}_default" not in ls:
            ls[f"{d}_default"] = ls.pop(d)
    p["id"] = slug(p.get("name", "game"))
    p["format"] = 2
    p["status"] = "shared by a player"
    p["updated"] = time.strftime("%Y-%m-%d")
    return p


def handle_reports(key):
    import build
    import run
    state = load_state()
    for pid, issues in group_reports(open_issues("wrong-button")).items():
        path = os.path.join(PROFILES, f"{pid}.json")
        if len(issues) < THRESHOLD or not os.path.isfile(path):
            continue
        old = json.load(open(path, encoding="utf-8"))
        game = {"name": old["name"], "steam_appid": old.get("steam_appid"), "qid": old.get("wikidata"),
                "playstation": [old.get("playstation_version", "")]}
        text = "\n---\n".join((i.get("body") or "")[:800] for i in issues)
        try:
            facts = run.collect(game, {})
            facts["exes"] = old.get("exe", [])
            new = run.make(game, facts, reports=text)
            new["status"] = "fixed after player reports"
            write_profile(new)
            state["rebuilds"][pid] = time.strftime("%Y-%m-%d")
            for i in issues:
                close(i, "Thanks! The layout was rebuilt with your report. ControlBridge downloads "
                         "the fix next time it starts.")
            print(f"  rebuilt {pid} from {len(issues)} reports")
        except Exception as e:  # noqa: BLE001
            print(f"  could not rebuild {pid}: {e}")
    save_state(state)


def handle_shared():
    for i in open_issues("new-profile"):
        if any(lab.get("name") == "needs-review" for lab in i.get("labels", [])):
            continue                       # already waiting for a person
        p = extract_profile(i.get("body"))
        if not p:
            close(i, "Couldn't find a profile in this post. Please share it again from the Profile Maker.")
            continue
        p = shared_to_library(p)
        problems = validate(p)
        if problems:
            close(i, "This profile has problems: " + "; ".join(problems[:4]))
            continue
        if os.path.isfile(os.path.join(PROFILES, f"{p['id']}.json")):
            close(i, "This game is already in the library, so this one waits for a person to compare them.",
                  label="needs-review")
            continue
        write_profile(p)
        close(i, f"Added {p['name']} to the library. Thank you!")
        print(f"  added shared profile {p['id']}")


def ensure_labels():
    repo = os.environ["GITHUB_REPOSITORY"]
    for name, colour in (("wrong-button", "d93f0b"), ("new-profile", "2f63ff"), ("needs-review", "fbca04")):
        try:
            gh("POST", f"/repos/{repo}/labels", {"name": name, "color": colour})
        except Exception:  # noqa: BLE001
            pass                       # already there


def main():
    import build
    ensure_labels()
    handle_shared()
    if build.ai_available():
        handle_reports(None)
    print(f"Library: {rebuild_index()} games")


if __name__ == "__main__":
    main()
