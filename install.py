#!/usr/bin/env python3
"""Install claude-code-hud into a Claude Code config directory.

    python install.py                 copy hud.py, set statusLine in settings.json
    python install.py --backfill      also count this month's existing transcripts
    python install.py --uninstall     remove the statusLine entry again

Your old settings.json is copied to settings.json.bak-hud-<time> before any change.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def resolve_config_dir(arg):
    if arg:
        return Path(arg).expanduser()
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def load_settings(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as err:
        sys.exit("Stopping: %s is not valid JSON (%s). Fix it first, nothing was changed." % (path, err))


def save_settings(path, settings):
    if path.exists():
        backup = path.with_name("%s.bak-hud-%s" % (path.name, time.strftime("%Y%m%d-%H%M%S")))
        shutil.copy2(path, backup)
        print("Backed up settings to %s" % backup)
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Install claude-code-hud.")
    ap.add_argument("--config-dir", help="Claude Code config dir (default: $CLAUDE_CONFIG_DIR or ~/.claude)")
    ap.add_argument("--python", help="python command to put in settings (default: python on Windows, python3 elsewhere)")
    ap.add_argument("--refresh", type=int, default=15, help="refreshInterval in seconds (default 15)")
    ap.add_argument("--backfill", action="store_true", help="count this month's existing transcripts")
    ap.add_argument("--force", action="store_true", help="replace a statusLine that is not this HUD")
    ap.add_argument("--uninstall", action="store_true", help="remove the statusLine entry")
    args = ap.parse_args()

    cfg_dir = resolve_config_dir(args.config_dir)
    settings_path = cfg_dir / "settings.json"
    dest = cfg_dir / "hud" / "hud.py"
    settings = load_settings(settings_path)
    current = settings.get("statusLine") or {}
    ours = "hud.py" in str(current.get("command", ""))

    if args.uninstall:
        if not ours:
            sys.exit("The statusLine in %s is not claude-code-hud. Nothing changed." % settings_path)
        del settings["statusLine"]
        save_settings(settings_path, settings)
        print("Removed statusLine. Files in %s and your hud.config.json were left alone." % (cfg_dir / "hud"))
        return

    if current and not ours and not args.force:
        sys.exit("A different statusLine is already set:\n  %s\nRun again with --force to replace it "
                 "(your settings are backed up first)." % current.get("command"))

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "hud.py", dest)
    config_target = cfg_dir / "hud.config.json"
    if not config_target.exists():
        shutil.copy2(HERE / "hud.config.example.json", config_target)

    py = args.python or ("python" if os.name == "nt" else "python3")
    wanted = {
        "type": "command",
        "command": '%s "%s"' % (py, dest.as_posix()),
        "refreshInterval": args.refresh,
    }
    if current != wanted:
        settings["statusLine"] = wanted
        save_settings(settings_path, settings)

    print("Installed %s" % dest)
    print("Config:    %s" % config_target)
    if args.backfill:
        subprocess.run([sys.executable, str(dest), "--backfill"],
                       env=dict(os.environ, CLAUDE_CONFIG_DIR=str(cfg_dir)), check=False)
    print("Open a new Claude Code session to see it. Preview now with: %s %s --demo" % (py, dest.as_posix()))


if __name__ == "__main__":
    main()
