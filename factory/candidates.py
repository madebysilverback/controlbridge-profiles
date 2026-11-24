"""
Finds games that came out on both Windows and a PlayStation, using Wikidata
(free, CC0). Most well-known games first (by how many Wikipedia languages
cover them). PS1/PS2 games are moved to the front, since their PC ports are
the ones most likely to be keyboard-only.

Writes factory/candidates.json.
"""

import json
import os

from common import ROOT, get

PLATFORMS = {"Q10677": "PS1", "Q10680": "PS2", "Q10683": "PS3", "Q5014725": "PS4",
             "Q63184502": "PS5", "Q170323": "PSP"}

QUERY = """
SELECT ?game ?gameLabel ?links ?steam ?pcgw (GROUP_CONCAT(DISTINCT ?p; separator="|") AS ?ps) WHERE {
  ?game wdt:P31 wd:Q7889 ;
        wdt:P400 wd:Q1406 ;
        wdt:P400 ?psp ;
        wikibase:sitelinks ?links .
  VALUES ?psp { %s }
  BIND(STRAFTER(STR(?psp), "entity/") AS ?p)
  OPTIONAL { ?game wdt:P1733 ?steam . }
  OPTIONAL { ?game wdt:P6337 ?pcgw . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
GROUP BY ?game ?gameLabel ?links ?steam ?pcgw
ORDER BY DESC(?links)
LIMIT 4000
""" % " ".join(f"wd:{q}" for q in PLATFORMS)


def main():
    data = get("https://query.wikidata.org/sparql", {"query": QUERY, "format": "json"}, timeout=120)
    games, seen = [], set()
    for row in data["results"]["bindings"]:
        qid = row["game"]["value"].rsplit("/", 1)[-1]
        name = row["gameLabel"]["value"]
        if qid in seen or name == qid:
            continue
        seen.add(qid)
        ps = sorted({PLATFORMS[p] for p in row["ps"]["value"].split("|") if p in PLATFORMS})
        games.append({"qid": qid, "name": name, "links": int(row["links"]["value"]),
                      "steam_appid": row.get("steam", {}).get("value"),
                      "pcgw": row.get("pcgw", {}).get("value"), "playstation": ps})
    old = [g for g in games if set(g["playstation"]) & {"PS1", "PS2", "PSP"}]
    new = [g for g in games if g not in old]
    ordered = old + new
    with open(os.path.join(ROOT, "factory", "candidates.json"), "w", encoding="utf-8") as f:
        json.dump(ordered, f, indent=1, ensure_ascii=False)
    print(f"{len(ordered)} candidate games ({len(old)} from the PS1/PS2/PSP era first)")


if __name__ == "__main__":
    main()
