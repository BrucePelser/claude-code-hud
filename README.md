# claude-code-hud

A status line for [Claude Code](https://code.claude.com): two lines by default, a third when you point it at a notes folder. One Python file, standard library only, no network calls.

![Four renderings of the HUD: default, under pressure, with a brain folder, and plain icons](assets/preview.svg)

Line 1 is about you: model, how long you have worked and how long the session has been open, where you are in git. Line 2 is about limits: context window, 5-hour and 7-day usage, prompt cache timer. Line 3 is optional: which file in your notes folder (a "brain", wiki or docs vault) the session is working in.

## What it shows

| Segment | Shows |
| --- | --- |
| `model` | Model name, effort level (`high`, `xhi`, ...), `fast` when fast mode is on |
| `session` | Active time in this session |
| `elapsed` | How long the session has been open, e.g. `open 2h10m` |
| `today` | Active time across all sessions today |
| `month` | Active time this month, with `/160h` style target if you set one |
| `cost` | Session cost estimate in USD (list price, may differ from your bill) |
| `lines` | Lines added and removed this session |
| `name` | Session name, if you set one with `/rename` |
| `where` | Folder, git branch, `*` if dirty, `↑2` ahead, `↓1` behind |
| `brain` | Newest file the session touched in your notes folder, plus `+N` for other recent files. Needs `brain_path` |
| `context` | Context window bar. Shows a hint once you pass 75% |
| `five_hour` | 5-hour usage bar and time until reset |
| `seven_day` | 7-day usage bar. Reset time appears once you pass 70% |
| `cache` | Time left on the prompt cache, or `cache cold` |

Bars turn orange at 60% and red at 85%. A segment hides itself when Claude Code does not send its data. Rate limits only exist for Pro and Max plans, so API users will not see those two bars.

Default layout: `model session elapsed where today month` on line 1, `context five_hour seven_day cache` on line 2, `brain` on line 3. Line 3 stays hidden until you set `brain_path`. `cost`, `lines` and `name` are off until you add them.

## Install

You need Python 3.9 or newer. `git` is optional and only used for the branch.

```
git clone https://github.com/BrucePelser/claude-code-hud.git
cd claude-code-hud
python install.py --backfill
```

The installer copies `hud.py` into `~/.claude/hud/`, writes a starter `~/.claude/hud.config.json`, and sets `statusLine` in `~/.claude/settings.json`. It backs up `settings.json` first and refuses to replace a different status line unless you pass `--force`. Open a new Claude Code session to see it.

Options:

- `--backfill` reads this month's existing transcripts once, so `month` starts out right instead of at zero
- `--config-dir PATH` for a non-default config folder (it also honours `CLAUDE_CONFIG_DIR`)
- `--python python3` if `python` on your PATH is not the one you want
- `--refresh 15` seconds between refreshes
- `--uninstall` removes the `statusLine` entry

Preview without installing: `python hud.py --demo`

### Manual install

Copy `hud.py` anywhere and add this to `settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python /path/to/hud.py",
    "refreshInterval": 15
  }
}
```

`refreshInterval` is in seconds. The cache countdown and reset timers only move when the HUD runs, so keep it low. Each run takes about 0.2 seconds.

## Configure

Edit `~/.claude/hud.config.json`. Every key is optional. Set `CLAUDE_HUD_CONFIG` to point at a different file. [`hud.config.example.json`](hud.config.example.json) lists all defaults.

| Key | Default | Meaning |
| --- | --- | --- |
| `icons` | `"emoji"` | `"emoji"` or `"plain"` (text labels, no emoji) |
| `line1`, `line2`, `line3` | see above | Segment names in order. Put what matters most first |
| `max_width` | `100` | A segment that would push a line past this width is skipped. Later segments go first, so raise it if `month` disappears |
| `brain_path` | `null` | Folder to track, e.g. `"~/brain"`. Turns on the `brain` segment |
| `brain_max_len` | `44` | Longest brain label. Long paths keep the top folder and the file name |
| `brain_window_kb` | `4096` | How much recent transcript to scan for brain files |
| `monthly_target_hours` | `null` | Adds `/160h` to `month` and colours it by progress |
| `bar_width` | `6` | Cells per bar |
| `context_hint_at` | `75` | Percent where the context hint appears |
| `context_hint` | `"/compact?"` | Hint text. Empty string turns it off |
| `week_reset_above` | `70` | Percent where the 7d reset time appears |
| `idle_cap_minutes` | `10` | Longest gap that counts as active time |
| `git` | `true` | Set `false` to skip the git call |
| `colors` | | xterm 256 codes for `ok`, `warn`, `bad`, `dim`, `add`, `del` |
| `thresholds` | `60`, `85` | Percent where bars go orange and red |

`NO_COLOR=1` turns colour off.

Example, a compact HUD with cost and no emoji:

```json
{
  "icons": "plain",
  "line1": ["model", "cost", "session", "where"],
  "line2": ["context", "five_hour", "cache"]
}
```

## How the numbers work

**Active time** is the sum of the gaps between message timestamps in the session transcript, with each gap capped at 10 minutes. Leave a session open overnight and it still reads a few minutes, not 12 hours. It is an estimate of time spent working, not a billing record.

**Open time** is the session's own wall-clock figure from Claude Code. It leaves out the time a session was closed, so a resumed session does not read as days. Active time is usually the smaller number: open time includes the minutes you spent away.

**Brain** looks at the tool calls Claude made in the last 4 MB of the transcript (reads, edits, writes, shell commands) and keeps any path under `brain_path`. The newest one is shown. Search results and file listings do not count, only paths Claude actually used. If no file has been touched yet but the session started inside `brain_path`, it shows that folder instead.

**Today and month** come from per-day totals the HUD keeps in `<config dir>/hud-state/active.json`, updated each time it runs. Each Claude config directory gets its own file, so two accounts stay separate. Entries older than 70 days are dropped. Run `python hud.py --backfill` any time to rescan this month's transcripts.

**Cache** is the prompt cache timer from Claude Code. After it hits zero, your next prompt re-reads the whole context at full price. That is the moment to know about before you walk away from a long session.

## Privacy

Nothing leaves your machine. The HUD makes no network calls. It reads the JSON Claude Code gives it, your local session transcripts (timestamps only, message text is never stored), and runs `git status` in your working folder. It writes small files to `<config dir>/hud-state/`: the per-day time totals, a 5-second git cache, and (only with `brain_path` set) a cache of the brain file paths found in your transcripts. Delete that folder to reset.

## Troubleshooting

- **Nothing shows.** Run `python hud.py --demo`. If that works, check the `command` path in `settings.json`. Set `CLAUDE_HUD_DEBUG=1` in the environment to see errors instead of a bare model name.
- **Line wraps in a narrow pane.** Lower `max_width`, or remove segments from `line1`.
- **A segment is missing.** It did not fit in `max_width`. Raise it, or move that segment to `line3`.
- **No brain line.** Set `brain_path` and use a file in it. Only the last 4 MB of transcript is scanned, so a brain file touched long ago drops off.
- **Emoji look misaligned.** Set `"icons": "plain"`.
- **No `cache` segment.** It needs Claude Code 2.1.251 or newer.
- **`today` and `month` start at zero.** Run `python hud.py --backfill`, or reinstall with `--backfill`.
- **Windows: `python` not found.** Reinstall with `--python py` or the full path to your interpreter.

## Develop

```
python -m unittest discover -s tests -v
python scripts/render_preview.py     # rebuilds assets/preview.svg from real output
```

## License

MIT. See [LICENSE](LICENSE).
