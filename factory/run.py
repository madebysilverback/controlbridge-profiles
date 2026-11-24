"""
One factory run: takes the next games from the candidate list, collects
their facts, asks Claude for a profile, checks it and publishes it.

    python factory/run.py --count 20

Free: games with a controls table are read directly. Others use the free
Gemini key (GEMINI_API_KEY secret) if it's set; otherwise they wait.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build  # noqa: E402
import sources  # noqa: E402
import tables  # noqa: E402
from common import ROOT, load_state, rebuild_index, save_state, slug, validate, write_profile  # noqa: E402


def collect(game, exes_by_app):
    sw_url, sw_text = sources.strategywiki_controls(game["name"])
    pcgw_url, pcgw_text, native = sources.pcgamingwiki(game["name"], game.get("pcgw"))
    return {"sw_url": sw_url, "sw_text": sw_text, "pcgw_url": pcgw_url, "pcgw_text": pcgw_text,
            "native": native, "exes": exes_by_app.get(str(game.get("steam_appid")), [])}


def make(game, facts, key=None, reports=""):
    """Free route first (read the controls table); free AI only when there's no usable table."""
    if not reports and facts.get("sw_text"):
        gen, buttons = tables.from_wikitext(facts["sw_text"])
        if len(buttons) >= 5 and facts.get("exes"):
            profile = build.from_table(game, facts, gen, buttons)
            if not validate(profile):
                return profile
    if not build.ai_available():
        raise ValueError("no controls table to read; add the free Gemini key to use AI for this game")
    reply = build.parse(build.ask_ai(build.make_prompt(game, facts, reports)))
    profile = build.to_profile(game, facts, reply)
    problems = validate(profile)
    if problems:
        raise ValueError("; ".join(problems[:4]))
    return profile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=20)
    ap.add_argument("--retry-skipped", action="store_true")
    args = ap.parse_args()
    if not build.ai_available():
        print("No AI key set: only games with a controls table will be made (still free).")
    with open(os.path.join(ROOT, "factory", "candidates.json"), encoding="utf-8") as f:
        candidates = json.load(f)
    state = load_state()
    have = {fn[:-5] for fn in os.listdir(os.path.join(ROOT, "library", "profiles")) if fn.endswith(".json")}
    todo = []
    for g in candidates:
        gid = slug(g["name"])
        if gid in have or gid in state["done"]:
            continue
        if gid in state["skipped"] and not args.retry_skipped:
            continue
        todo.append(g)
        if len(todo) >= args.count:
            break
    print(f"Making {len(todo)} profiles...")
    exes = sources.steam_exes([g.get("steam_appid") for g in todo])
    made = 0
    for g in todo:
        gid = slug(g["name"])
        try:
            facts = collect(g, exes)
            if not facts["sw_text"] and not facts["pcgw_text"]:
                raise ValueError("no public controls information found")
            profile = make(g, facts)
            write_profile(profile)
            state["done"][gid] = time.strftime("%Y-%m-%d")
            state["skipped"].pop(gid, None)
            made += 1
            print(f"  + {g['name']}")
        except Exception as e:  # noqa: BLE001
            state["skipped"][gid] = f"{time.strftime('%Y-%m-%d')}: {str(e)[:160]}"
            print(f"  - {g['name']}: {e}")
        save_state(state)
    total = rebuild_index()
    print(f"Done: {made} new profiles, {total} in the library.")


if __name__ == "__main__":
    main()
