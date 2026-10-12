# FPV Arabia Checker 🔍

A Discord bot for **FPV Arabia**, the Arabic-speaking FPV community. Members upload a Betaflight settings dump or a Blackbox log, and the bot replies with a settings check, noise analysis and recommendations, explained in Arabic.

---

## Features

**Settings file** (Betaflight CLI `diff all`)
- Quad summary: firmware, board, motor protocol, rates type
- Settings checks: ARM switch, RPM filter, failsafe, battery limits and more
- Every warning comes with a ready-to-paste CLI command

**Blackbox log** (`.BBL` / `.BFL`, up to 3 files per message)
- The same settings checks, read from the log headers
- Gyro noise spectrum before and after filtering, with detected peaks
- Noise vs throttle heatmap from all flights in the file, with gyro filter cutoffs
- Advanced plots from BlackBox_CSV_Render (optional)

**Final recommendations**
- One summary at the end of every analysis, ordered by priority, with CLI commands

Analyses run one at a time, so simultaneous uploads never mix up their plots.

---

## Project layout

| File | Purpose |
|---|---|
| `bot.py` | The Discord bot |
| `cli_parser.py` | Parses `diff all` dumps and Blackbox log headers |
| `rules.py` | Settings checks |
| `report.py` | Formats the settings report |
| `noise.py` | Noise spectrum and heatmap |
| `recommend.py` | Final recommendations |
| `render_tool.py` | BlackBox_CSV_Render integration |
| `orangebox/` | Bundled Blackbox log parser (see Credits) |
| `test_local.py` | Run the checks without Discord |

---

## Running locally

```
pip install -r requirements.txt
```
Copy `.env.example` to `.env`, fill in the values, then:
```
python bot.py
```

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Bot token from the Discord Developer Portal |
| `CHECK_CHANNEL_ID` | Channel the bot answers in (`0` = all channels) |
| `ENABLE_RENDER` | `1` to enable BlackBox_CSV_Render plots |
| `RENDER_BIN` | Path to the BlackBox_CSV_Render binary, if not in the default location |

To test the checks without Discord:
```
python test_local.py sample_diff.txt
```

## Hosting

The bot runs on Railway. The `Dockerfile` builds BlackBox_CSV_Render from source (pinned to a specific commit) and packages the bot. Every push to `main` is deployed automatically.

## Adding a check

```python
def rule_my_check(cfg):
    if cfg.get("some_setting") == "X":
        return Finding(WARN, "Title", "Explanation", "set some_setting = Y")
    return None
```
Then add it to the `RULES` list at the end of `rules.py`.

---

## Credits

**[BlackBox_CSV_Render](https://github.com/nerdCopter/BlackBox_CSV_Render)** by **nerdCopter**
The advanced analysis plots come from BlackBox_CSV_Render, used unmodified and with the author's permission. Every report that includes its plots credits the tool and links to its repository. Licensed under AGPL-3.0. Thank you, nerdCopter!

**[orangebox](https://github.com/atomgomba/orangebox)** by **Károly Kiripolszky**
Blackbox log parser, bundled in `orangebox/`. Licensed under GPL-3.0.

---

## License

This bot is free and non-commercial: no profit and no paid features.
Licensed under **GPL-3.0**, see `LICENSE`.
