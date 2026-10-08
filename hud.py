#!/usr/bin/env python3
"""claude-code-hud: a two-line status line for Claude Code.

Claude Code pipes a JSON blob about the session to stdin. This script prints
two lines of ANSI text. Python 3.9+, standard library only, no network calls.

    python hud.py --demo        preview with sample data
    python hud.py --backfill    count active time from existing transcripts
    python hud.py --version
"""
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from datetime import datetime

__version__ = "1.0.0"

DEFAULTS = {
    "icons": "emoji",  # "emoji" or "plain"
    "max_width": 90,  # a segment that would push a line past this is skipped
    "line1": ["model", "session", "today", "month", "where"],
    "line2": ["context", "five_hour", "seven_day", "cache"],
    "monthly_target_hours": None,
    "bar_width": 6,
    "context_hint_at": 75,  # show the hint once context use reaches this percent
    "context_hint": "/compact?",
    "week_reset_above": 70,  # show the 7d reset countdown only above this percent
    "idle_cap_minutes": 10,  # a gap longer than this counts as this many minutes
    "git": True,
    "colors": {"ok": 71, "warn": 208, "bad": 196, "dim": 245, "add": 71, "del": 196},
    "thresholds": {"warn": 60, "bad": 85},
}

ICONS = {
    "model": "\u26a1 ",
    "session": "\u23f1 ",
    "today": "\U0001f4c5 ",
    "month": "\U0001f4c6 ",
    "cost": "\U0001f4b0 ",
    "where": "\U0001f4c1 ",
    "context": "\U0001f50b ",
    "reset": "\u23f3",
}

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
TS_RE = re.compile(rb'"timestamp"\s*:\s*"(\d{4}-\d\d-\d\dT[0-9:.]+(?:Z|[+-]\d\d:\d\d)?)"')
# These two are width 1 per unicodedata but draw as two cells in nearly every terminal.
WIDE_NARROW_EMOJI = "\u23f1\u23f3"
STATE_KEEP_DAYS = 70


# ---------------------------------------------------------------- small helpers

def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(out.get(k), dict) and isinstance(v, dict) else v
    return out


def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, obj):
    # temp file + replace, so two sessions refreshing at once never leave half a file
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = "%s.%d.tmp" % (path, os.getpid())
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f)
        os.replace(tmp, path)
    except Exception:
        pass


def vis_len(text):
    width = 0
    for ch in ANSI_RE.sub("", text):
        if unicodedata.combining(ch) or ch in "\ufe0f\u200d":
            continue
        wide = ch in WIDE_NARROW_EMOJI or unicodedata.east_asian_width(ch) in ("W", "F")
        width += 2 if wide else 1
    return width


def fmt_hm(minutes):
    minutes = int(round(minutes))
    return "%dm" % minutes if minutes < 60 else "%dh%02dm" % (minutes // 60, minutes % 60)


def fmt_countdown(seconds):
    if seconds <= 0:
        return "now"
    days, rem = divmod(int(seconds), 86400)
    hours, rem = divmod(rem, 3600)
    mins = rem // 60
    if days:
        return "%dd%dh" % (days, hours)
    if hours:
        return "%dh%02dm" % (hours, mins)
    return "%dm" % max(mins, 1)


def parse_ts(value):
    """ISO-8601 string or bytes to epoch seconds, or None. Before Python 3.11 fromisoformat only takes 3 or 6 fraction digits."""
    if isinstance(value, bytes):
        value = value.decode("ascii", "ignore")
    value = value.replace("Z", "+00:00")
    value = re.sub(r"\.(\d+)", lambda m: "." + (m.group(1) + "000000")[:6], value)
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None


# ---------------------------------------------------------------- config

def config_dir(data):
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        return env
    # transcript_path is <config dir>/projects/<project>/<session>.jsonl
    tp = (data.get("transcript_path") or "").replace("\\", "/")
    m = re.match(r"^(.*)/projects/[^/]+/[^/]+\.jsonl$", tp)
    if m and os.path.isdir(m.group(1)):
        return m.group(1)
    return os.path.join(os.path.expanduser("~"), ".claude")


def load_config(cfg_dir):
    path = os.environ.get("CLAUDE_HUD_CONFIG") or os.path.join(cfg_dir, "hud.config.json")
    cfg = _merge(DEFAULTS, read_json(path, {}))
    cfg["color"] = not os.environ.get("NO_COLOR")
    return cfg


# ---------------------------------------------------------------- active time

def new_entry():
    return {"off": 0, "prev": None, "act": 0.0, "days": {}}


def scan_transcript(path, store, cap_minutes):
    """Add the new part of a transcript to store[path].

    Active time is the sum of gaps between message timestamps, each gap capped, so a
    session left open overnight does not read as 12 hours of work. Each gap is booked
    to the local day it ended on, which is what makes the today and month totals work.
    """
    ent = store.get(path) or new_entry()
    size = os.path.getsize(path)
    if size < ent["off"]:
        ent = new_entry()
    prev, act, days, off = ent["prev"], ent["act"], ent["days"], ent["off"]
    if size > off:
        with open(path, "rb") as f:
            f.seek(off)
            buf = b""
            while True:
                block = f.read(1 << 24)
                if not block:
                    break
                buf += block
                nl = buf.rfind(b"\n")
                if nl < 0:
                    continue
                for line in buf[:nl].split(b"\n"):
                    m = TS_RE.search(line)
                    t = parse_ts(m.group(1)) if m else None
                    if t is None:
                        continue
                    if prev is not None and t > prev:
                        gap = min((t - prev) / 60.0, cap_minutes)
                        act += gap
                        day = datetime.fromtimestamp(t).strftime("%Y-%m-%d")
                        days[day] = days.get(day, 0.0) + gap
                    prev = t
                off += nl + 1
                buf = buf[nl + 1:]
    ent = {"off": off, "prev": prev, "act": act, "days": days}
    store[path] = ent
    return ent


def prune_store(store, keep_path=None):
    cutoff = datetime.fromtimestamp(time.time() - STATE_KEEP_DAYS * 86400).strftime("%Y-%m-%d")
    for key in [k for k, e in store.items() if k != keep_path and max(e["days"], default="") < cutoff]:
        del store[key]


def time_totals(store, today, month):
    day_min = sum(e["days"].get(today, 0.0) for e in store.values())
    month_min = sum(v for e in store.values() for d, v in e["days"].items() if d[:7] == month)
    return day_min, month_min


# ---------------------------------------------------------------- git

def parse_git_status(text):
    """Parse `git status --porcelain=v2 --branch` output."""
    info = {"branch": "", "dirty": False, "ahead": 0, "behind": 0}
    oid = ""
    for line in text.splitlines():
        if line.startswith("# branch.oid "):
            oid = line.split(" ", 2)[2]
        elif line.startswith("# branch.head "):
            info["branch"] = line.split(" ", 2)[2]
        elif line.startswith("# branch.ab "):
            _, _, plus, minus = line.split(" ")
            info["ahead"], info["behind"] = int(plus), abs(int(minus))
        elif line and not line.startswith("#"):
            info["dirty"] = True
    if info["branch"] == "(detached)":
        info["branch"] = oid[:7] or "detached"
    return info if info["branch"] else None


def git_info(cwd, state_dir, ttl=5):
    cache_path = os.path.join(state_dir, "git.json")
    cache = read_json(cache_path, {})
    hit = cache.get(cwd)
    if hit and time.time() - hit["ts"] < ttl:
        return hit["info"]
    info = None
    try:
        flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
        env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
        out = subprocess.run(
            ["git", "-C", cwd, "status", "--porcelain=v2", "--branch", "-uno"],
            capture_output=True, text=True, timeout=1.5, env=env,
            stdin=subprocess.DEVNULL, creationflags=flags,
        )
        if out.returncode == 0:
            info = parse_git_status(out.stdout)
    except Exception:
        info = hit["info"] if hit else None
    cache[cwd] = {"ts": time.time(), "info": info}
    if len(cache) > 20:
        for k in list(cache)[:len(cache) - 20]:
            del cache[k]
    write_json(cache_path, cache)
    return info


# ---------------------------------------------------------------- drawing

def paint(cfg, code, text):
    return "\x1b[38;5;%dm%s\x1b[0m" % (code, text) if cfg["color"] else text


def bold(cfg, text):
    return "\x1b[1m%s\x1b[0m" % text if cfg["color"] else text


def dim(cfg, text):
    return paint(cfg, cfg["colors"]["dim"], text)


def level_color(cfg, pct):
    th, c = cfg["thresholds"], cfg["colors"]
    return c["ok"] if pct < th["warn"] else (c["warn"] if pct < th["bad"] else c["bad"])


def bar(cfg, pct):
    width = int(cfg["bar_width"])
    filled = max(0, min(width, int(round(pct / 100.0 * width))))
    return paint(cfg, level_color(cfg, pct), "\u2588" * filled) + dim(cfg, "\u2591" * (width - filled))


def icon(cfg, name, plain=""):
    return ICONS.get(name, "") if cfg["icons"] == "emoji" else plain


def pct_of(node):
    value = (node or {}).get("used_percentage")
    return value if isinstance(value, (int, float)) else None


# ---------------------------------------------------------------- segments
# Each takes (data, cfg, st) and returns a string, or None to hide itself.

def seg_model(d, cfg, st):
    model = d.get("model") or {}
    name = model.get("display_name") or model.get("id") or "?"
    name = re.sub(r"\s*\(.*?\)", "", re.sub(r"^Claude\s+", "", name))
    out = icon(cfg, "model") + bold(cfg, name)
    effort = (d.get("effort") or {}).get("level")
    if effort:
        out += dim(cfg, "\u00b7" + {"medium": "med", "xhigh": "xhi"}.get(effort, effort))
    if d.get("fast_mode"):
        out += dim(cfg, "\u00b7fast")
    return out


def seg_session(d, cfg, st):
    if st.get("session") is None:
        return None
    return icon(cfg, "session", "session ") + fmt_hm(st["session"])


def seg_today(d, cfg, st):
    if st.get("today") is None:
        return None
    return icon(cfg, "today") + "today " + fmt_hm(st["today"])


def seg_month(d, cfg, st):
    if st.get("month") is None:
        return None
    text = fmt_hm(st["month"])
    target = cfg["monthly_target_hours"]
    if target:
        used = paint(cfg, level_color(cfg, st["month"] / (target * 60.0) * 100), text)
        text = used + dim(cfg, "/%gh" % target)
    return icon(cfg, "month") + "month " + text


def seg_cost(d, cfg, st):
    cost = (d.get("cost") or {}).get("total_cost_usd")
    return icon(cfg, "cost") + "$%.2f" % cost if isinstance(cost, (int, float)) else None


def seg_lines(d, cfg, st):
    cost = d.get("cost") or {}
    added, removed = cost.get("total_lines_added") or 0, cost.get("total_lines_removed") or 0
    if not (added or removed):
        return None
    return paint(cfg, cfg["colors"]["add"], "+%d" % added) + " " + paint(cfg, cfg["colors"]["del"], "-%d" % removed)


def seg_name(d, cfg, st):
    name = d.get("session_name")
    return dim(cfg, str(name)[:28]) if name else None


def seg_where(d, cfg, st):
    cwd = (d.get("workspace") or {}).get("current_dir") or d.get("cwd") or ""
    if not cwd:
        return None
    out = icon(cfg, "where") + (os.path.basename(cwd.rstrip("\\/")) or cwd)
    git = st.get("git")
    if git:
        out += " \u2192 " + git["branch"] + ("*" if git["dirty"] else "")
        if git["ahead"]:
            out += "\u2191%d" % git["ahead"]
        if git["behind"]:
            out += "\u2193%d" % git["behind"]
    return out


def seg_context(d, cfg, st):
    pct = pct_of(d.get("context_window"))
    if pct is None:
        return None
    out = icon(cfg, "context") + "ctx " + bar(cfg, pct) + " %.0f%%" % pct
    if pct >= cfg["context_hint_at"] and cfg["context_hint"]:
        out += " " + paint(cfg, cfg["colors"]["warn"], cfg["context_hint"])
    return out


def _limit(d, cfg, key, label, reset_above):
    node = (d.get("rate_limits") or {}).get(key) or {}
    pct = pct_of(node)
    if pct is None:
        return None
    out = "%s %s %.0f%%" % (label, bar(cfg, pct), pct)
    resets = node.get("resets_at")
    if pct >= reset_above and isinstance(resets, (int, float)):
        out += " " + icon(cfg, "reset", "reset ") + fmt_countdown(resets - time.time())
    return out


def seg_five_hour(d, cfg, st):
    return _limit(d, cfg, "five_hour", "5h", 0)


def seg_seven_day(d, cfg, st):
    return _limit(d, cfg, "seven_day", "7d", cfg["week_reset_above"])


def seg_cache(d, cfg, st):
    # Past this time the next prompt re-reads the whole context at full price.
    pc = d.get("prompt_cache") or {}
    if not pc.get("caching_observed", False):
        return None
    left = (pc.get("expires_at") or 0) - time.time()
    if pc.get("warm") and left > 0:
        return dim(cfg, "cache " + fmt_countdown(left))
    return paint(cfg, cfg["colors"]["warn"], "cache cold")


SEGMENTS = {
    "model": seg_model, "session": seg_session, "today": seg_today, "month": seg_month,
    "cost": seg_cost, "lines": seg_lines, "name": seg_name, "where": seg_where,
    "context": seg_context, "five_hour": seg_five_hour, "seven_day": seg_seven_day,
    "cache": seg_cache,
}


# ---------------------------------------------------------------- assembly

def compose(names, d, cfg, st):
    sep = " " + dim(cfg, "\u2502") + " "
    sep_w = vis_len(sep)
    parts, used = [], 0
    for name in names:
        fn = SEGMENTS.get(name)
        if not fn:
            continue
        try:
            text = fn(d, cfg, st)
        except Exception:
            text = None
        if not text:
            continue
        cost = vis_len(text) + (sep_w if parts else 0)
        if parts and used + cost > cfg["max_width"]:
            continue
        parts.append(text)
        used += cost
    return sep.join(parts)


def render(d, cfg, st):
    lines = [compose(cfg["line1"], d, cfg, st), compose(cfg["line2"], d, cfg, st)]
    return "\n".join(line for line in lines if line)


def build_state(d, cfg, cfg_dir):
    state_dir = os.path.join(cfg_dir, "hud-state")
    st = {"session": None, "today": None, "month": None, "git": None}
    layout = cfg["line1"] + cfg["line2"]

    tp = d.get("transcript_path") or ""
    if tp and os.path.exists(tp) and {"session", "today", "month"} & set(layout):
        path = os.path.join(state_dir, "active.json")
        store = read_json(path, {})
        ent = scan_transcript(tp, store, cfg["idle_cap_minutes"])
        prune_store(store, tp)
        write_json(path, store)
        now = datetime.now()
        day_min, month_min = time_totals(store, now.strftime("%Y-%m-%d"), now.strftime("%Y-%m"))
        st["session"], st["today"], st["month"] = ent["act"], day_min, month_min

    cwd = (d.get("workspace") or {}).get("current_dir") or d.get("cwd") or ""
    if cwd and cfg["git"] and "where" in layout:
        st["git"] = git_info(cwd, state_dir)
    return st


def demo_data():
    now = time.time() + 30  # headroom so countdowns floor to the round numbers below
    return {
        "model": {"id": "claude-sonnet-5-5", "display_name": "Sonnet 5.5"},
        "workspace": {"current_dir": "/home/you/projects/my-app"},
        "cost": {"total_cost_usd": 1.37, "total_lines_added": 212, "total_lines_removed": 48},
        "context_window": {"used_percentage": 42},
        "effort": {"level": "high"},
        "rate_limits": {
            "five_hour": {"used_percentage": 63, "resets_at": now + 2 * 3600 + 14 * 60},
            "seven_day": {"used_percentage": 78, "resets_at": now + 3 * 86400 + 5 * 3600},
        },
        "prompt_cache": {"warm": True, "caching_observed": True, "expires_at": now + 54 * 60},
    }


DEMO_STATE = {
    "session": 83, "today": 220, "month": 904,
    "git": {"branch": "main", "dirty": True, "ahead": 1, "behind": 0},
}


def backfill(cfg_dir, cfg):
    """Scan this month's transcripts once so the month total starts out right."""
    start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
    root = os.path.join(cfg_dir, "projects")
    path = os.path.join(cfg_dir, "hud-state", "active.json")
    store = read_json(path, {})
    count = 0
    if os.path.isdir(root):
        for proj in os.listdir(root):
            pdir = os.path.join(root, proj)
            if not os.path.isdir(pdir):
                continue
            for fname in os.listdir(pdir):
                fpath = os.path.join(pdir, fname)
                if fname.endswith(".jsonl") and os.path.getmtime(fpath) >= start:
                    scan_transcript(fpath, store, cfg["idle_cap_minutes"])
                    count += 1
    prune_store(store)
    write_json(path, store)
    now = datetime.now()
    _, month_min = time_totals(store, now.strftime("%Y-%m-%d"), now.strftime("%Y-%m"))
    print("Scanned %d transcripts in %s. Month so far: %s." % (count, root, fmt_hm(month_min)))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if "--version" in argv:
        print(__version__)
        return 0

    if "--demo" in argv or "--backfill" in argv:
        cfg_dir = config_dir({})
        cfg = load_config(cfg_dir)
        if "--backfill" in argv:
            backfill(cfg_dir, cfg)
        else:
            print(render(demo_data(), cfg, DEMO_STATE))
        return 0

    if sys.stdin is None or sys.stdin.isatty():
        print("claude-code-hud reads JSON from stdin. Try: python hud.py --demo")
        return 1

    try:
        # bytes, not text mode: the Windows locale codec would garble non-ASCII paths
        data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    except Exception:
        data = {}
    try:
        cfg_dir = config_dir(data)
        cfg = load_config(cfg_dir)
        print(render(data, cfg, build_state(data, cfg, cfg_dir)))
    except Exception:
        if os.environ.get("CLAUDE_HUD_DEBUG"):
            raise
        print(((data.get("model") or {}).get("display_name")) or "claude")
    return 0


if __name__ == "__main__":
    sys.exit(main())
