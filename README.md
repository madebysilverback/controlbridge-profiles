# Tapsquatch game library

The free, shared library of game layouts for **Tapsquatch**: play PC games
on a DualSense with the controls from each game's PlayStation version.

Made by Silverback · [madebysilverback.com](https://madebysilverback.com)

## How it fills itself

Every night a robot (GitHub Actions) runs the **profile factory**:

1. **Finds games** released on both Windows and PlayStation (from Wikidata),
   oldest PlayStation generations first, best-known games first.
2. **Collects public facts** for each one: the controls (StrategyWiki), PC
   details such as where settings are kept (PCGamingWiki), and the program
   Steam launches (SteamCMD, no login needed).
3. **Builds the layout for free.** Where the controls page has a table of
   PlayStation buttons, PC keys and actions, it's read directly with no AI.
   Otherwise Google's Gemini (free tier) turns the facts into a layout.
4. **Checks** the result automatically and **publishes** it to `library/`.

Tapsquatch downloads new layouts when it starts. On each player's PC it
reads the game's own settings file to find the real key for each action, so
nobody needs to own the games for the library to grow.

**Players keep it accurate.** "Report a problem" in Tapsquatch opens a
ready-filled post here. When a layout gets two reports, the robot rebuilds it
with the reports and closes them. Profiles shared from the Profile Maker are
checked and added automatically.

## Folders

| Folder | What's in it |
|---|---|
| `library/index.json` | The list Tapsquatch downloads |
| `library/profiles/` | One layout per game |
| `factory/` | The scripts the robot runs |
| `factory/state.json` | Which games were made, and why others were skipped |

## Credits and licence

Layouts are made from facts collected from:

* [StrategyWiki](https://strategywiki.org) – text under CC BY-SA 4.0
* [PCGamingWiki](https://www.pcgamingwiki.com) – text under CC BY-NC-SA 3.0
* [Wikidata](https://www.wikidata.org) – CC0

It costs nothing to run: GitHub Actions is free for public projects, and the AI used is Gemini's free tier.

The layouts in `library/` are shared under **CC BY-SA 4.0**: free to use and
share with credit, under the same licence. Each layout names its sources.
From PCGamingWiki only plain facts are used (such as where a game keeps its
settings), never its text.

DualSense and PlayStation are trademarks of Sony Interactive Entertainment Inc.
Tapsquatch is an independent project and is not affiliated with or endorsed
by Sony. Game names belong to their owners.
