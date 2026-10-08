import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import hud  # noqa: E402


def make_cfg(**over):
    over.setdefault("max_width", 100)  # tests must not depend on the COLUMNS of whoever runs them
    cfg = hud.make_config(over)
    cfg["color"] = over.get("color", False)
    return cfg


def write_transcript(path, stamps, trailing_partial=False):
    with open(path, "w", encoding="utf-8") as f:
        for ts in stamps:
            f.write(json.dumps({"type": "user", "timestamp": ts}) + "\n")
        if trailing_partial:
            f.write('{"type": "user", "timestamp": "2026-10-0')


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


class HelperTests(unittest.TestCase):
    def test_vis_len_ignores_ansi_and_counts_wide_chars(self):
        self.assertEqual(hud.vis_len("\x1b[1mabc\x1b[0m"), 3)
        self.assertEqual(hud.vis_len("⚡ x"), 4)
        self.assertEqual(hud.vis_len("⏱ x"), 4)

    def test_fmt_hm(self):
        self.assertEqual(hud.fmt_hm(0), "0m")
        self.assertEqual(hud.fmt_hm(59.6), "1h00m")
        self.assertEqual(hud.fmt_hm(125), "2h05m")

    def test_fmt_countdown(self):
        self.assertEqual(hud.fmt_countdown(-5), "now")
        self.assertEqual(hud.fmt_countdown(30), "1m")
        self.assertEqual(hud.fmt_countdown(2 * 3600 + 14 * 60), "2h14m")
        self.assertEqual(hud.fmt_countdown(3 * 86400 + 5 * 3600), "3d5h")

    def test_parse_ts_handles_odd_fraction_digits(self):
        a = hud.parse_ts("2026-10-07T10:00:00Z")
        b = hud.parse_ts("2026-10-07T10:00:00.5Z")
        self.assertAlmostEqual(b - a, 0.5, places=3)
        self.assertIsNone(hud.parse_ts("not a time"))

    def test_merge_keeps_unset_nested_defaults(self):
        cfg = hud._merge(hud.DEFAULTS, {"colors": {"ok": 2}})
        self.assertEqual(cfg["colors"]["ok"], 2)
        self.assertEqual(cfg["colors"]["warn"], hud.DEFAULTS["colors"]["warn"])


class GitTests(unittest.TestCase):
    def test_clean_branch_with_upstream(self):
        text = "# branch.oid abc1234\n# branch.head main\n# branch.upstream origin/main\n# branch.ab +2 -1\n"
        info = hud.parse_git_status(text)
        self.assertEqual(info, {"branch": "main", "dirty": False, "ahead": 2, "behind": 1})

    def test_dirty_when_changes_listed(self):
        text = "# branch.oid abc1234\n# branch.head dev\n1 .M N... 100644 100644 100644 a b file.txt\n"
        self.assertTrue(hud.parse_git_status(text)["dirty"])

    def test_detached_head_shows_short_sha(self):
        text = "# branch.oid 0123456789abcdef\n# branch.head (detached)\n"
        self.assertEqual(hud.parse_git_status(text)["branch"], "0123456")

    def test_empty_output_is_none(self):
        self.assertIsNone(hud.parse_git_status(""))


class ActiveTimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "session.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_idle_gap_is_capped(self):
        t0 = datetime.now(timezone.utc) - timedelta(hours=3)
        write_transcript(self.path, [iso(t0), iso(t0 + timedelta(minutes=2)), iso(t0 + timedelta(minutes=122))])
        ent = hud.scan_transcript(self.path, {}, 10)
        self.assertAlmostEqual(ent["act"], 12.0, places=2)

    def test_rescan_is_incremental_and_skips_partial_line(self):
        t0 = datetime.now(timezone.utc) - timedelta(hours=1)
        write_transcript(self.path, [iso(t0), iso(t0 + timedelta(minutes=3))], trailing_partial=True)
        store = {}
        first = hud.scan_transcript(self.path, store, 10)["act"]
        again = hud.scan_transcript(self.path, store, 10)["act"]
        self.assertAlmostEqual(first, 3.0, places=2)
        self.assertEqual(first, again)

    def test_gaps_are_booked_to_the_day_they_end_on(self):
        t0 = datetime.now(timezone.utc) - timedelta(days=3)
        stamps = [iso(t0), iso(t0 + timedelta(minutes=5)), iso(t0 + timedelta(days=2)), iso(t0 + timedelta(days=2, minutes=4))]
        write_transcript(self.path, stamps)
        ent = hud.scan_transcript(self.path, {}, 10)
        self.assertEqual(len(ent["days"]), 2)
        self.assertAlmostEqual(sum(ent["days"].values()), 5 + 10 + 4, places=2)

    def test_truncated_file_resets_the_entry(self):
        t0 = datetime.now(timezone.utc) - timedelta(hours=1)
        write_transcript(self.path, [iso(t0), iso(t0 + timedelta(minutes=5)), iso(t0 + timedelta(minutes=9))])
        store = {}
        hud.scan_transcript(self.path, store, 10)
        write_transcript(self.path, [iso(t0)])
        ent = hud.scan_transcript(self.path, store, 10)
        self.assertEqual(ent["act"], 0.0)

    def test_totals(self):
        store = {"a": {"days": {"2026-10-07": 30, "2026-10-01": 60, "2026-09-30": 99}},
                 "b": {"days": {"2026-10-07": 15}}}
        day, month = hud.time_totals(store, "2026-10-07", "2026-10")
        self.assertEqual((day, month), (45, 105))


class RenderTests(unittest.TestCase):
    def test_default_layout_is_two_rows_with_the_project_on_row_one(self):
        lines = hud.render(hud.demo_data(), make_cfg(), hud.DEMO_STATE).split("\n")
        self.assertEqual(len(lines), 2)
        self.assertIn("my-app", lines[0])
        self.assertIn("main*", lines[0])
        self.assertIn("ctx", lines[1])

    def test_rows_layout_is_three_themed_rows(self):
        out = hud.render(hud.demo_data(), make_cfg(layout="rows"), hud.DEMO_STATE)
        lines = out.split("\n")
        self.assertEqual(len(lines), 3)
        self.assertIn("Sonnet 5.5", lines[0])
        self.assertIn("3h40m", lines[0])
        self.assertIn("ctx", lines[1])
        self.assertIn("5h", lines[1])
        self.assertIn("cache 54m", lines[1])
        self.assertIn("my-app", lines[2])
        self.assertIn("main*", lines[2])

    def test_width_auto_follows_columns(self):
        old = os.environ.get("COLUMNS")
        try:
            os.environ["COLUMNS"] = "120"
            self.assertEqual(hud.resolve_width("auto"), 116)
            os.environ["COLUMNS"] = "40"
            self.assertEqual(hud.resolve_width("auto"), 60)
            os.environ["COLUMNS"] = "wide"
            self.assertEqual(hud.resolve_width("auto"), 100)
            del os.environ["COLUMNS"]
            self.assertEqual(hud.resolve_width("auto"), 100)
            self.assertEqual(hud.resolve_width(88), 88)
        finally:
            if old is not None:
                os.environ["COLUMNS"] = old
            else:
                os.environ.pop("COLUMNS", None)

    def test_explicit_lines_beat_the_layout(self):
        cfg = make_cfg(line1=["model"], line2=["cache"], line3=[])
        lines = hud.render(hud.demo_data(), cfg, hud.DEMO_STATE).split("\n")
        self.assertEqual(len(lines), 2)
        self.assertNotIn("my-app", "\n".join(lines))

    def test_custom_icons_use_the_font_glyphs_and_no_emoji(self):
        out = hud.render(hud.demo_data(), make_cfg(icons="custom"), hud.DEMO_STATE)
        for glyph in ("model", "active", "open", "today", "month", "folder", "branch", "context", "cache_warm", "reset"):
            self.assertIn(hud.GLYPHS[glyph], out)
        self.assertNotIn("\U0001f550", out)
        self.assertNotIn("open ", out)

    def test_custom_cache_is_a_snowflake_when_cold(self):
        data = hud.demo_data()
        data["prompt_cache"] = {"warm": False, "caching_observed": True, "expires_at": None}
        out = hud.render(data, make_cfg(icons="custom"), hud.DEMO_STATE)
        self.assertIn(hud.GLYPHS["cache_cold"], out)
        self.assertIn("cold", out)
        self.assertNotIn(hud.GLYPHS["cache_warm"], out)

    def test_custom_icons_take_their_own_colours(self):
        out = hud.render(hud.demo_data(), make_cfg(icons="custom", color=True), hud.DEMO_STATE)
        self.assertIn("\x1b[38;5;80m" + hud.GLYPHS["active"], out)

    def test_glyph_table_matches_the_icon_font_source(self):
        from icons import design
        self.assertEqual({k: chr(v) for k, v in design.CODEPOINTS.items()}, hud.GLYPHS)

    def test_no_color_has_no_escape_codes(self):
        out = hud.render(hud.demo_data(), make_cfg(color=False), hud.DEMO_STATE)
        self.assertNotIn("\x1b", out)

    def test_color_adds_escape_codes(self):
        out = hud.render(hud.demo_data(), make_cfg(color=True), hud.DEMO_STATE)
        self.assertIn("\x1b[", out)

    def test_empty_input_does_not_crash(self):
        self.assertIn("?", hud.render({}, make_cfg(), {}))

    def test_plain_icons_have_no_emoji(self):
        out = hud.render(hud.demo_data(), make_cfg(icons="plain"), hud.DEMO_STATE)
        self.assertTrue(all(ord(ch) < 0x2000 or ch in "█░│→↑↓" for ch in out))

    def test_lines_stay_inside_max_width(self):
        for width in (40, 60, 90):
            out = hud.render(hud.demo_data(), make_cfg(max_width=width), hud.DEMO_STATE)
            for line in out.split("\n"):
                self.assertLessEqual(hud.vis_len(line), width)

    def test_first_segment_is_kept_even_when_too_wide(self):
        out = hud.render(hud.demo_data(), make_cfg(max_width=3), hud.DEMO_STATE)
        self.assertIn("Sonnet 5.5", out)

    def test_month_target_is_shown(self):
        out = hud.render(hud.demo_data(), make_cfg(monthly_target_hours=160, max_width=120), hud.DEMO_STATE)
        self.assertIn("/160h", out)

    def test_cold_cache_and_context_hint(self):
        data = hud.demo_data()
        data["prompt_cache"] = {"warm": False, "caching_observed": True, "expires_at": None}
        data["context_window"]["used_percentage"] = 90
        out = hud.render(data, make_cfg(), hud.DEMO_STATE)
        self.assertIn("cache cold", out)
        self.assertIn("/compact?", out)

    def test_elapsed_shows_open_time_and_hides_without_data(self):
        self.assertIn("\U0001f550 2h10m", hud.render(hud.demo_data(), make_cfg(), hud.DEMO_STATE))
        self.assertIn("open 2h10m", hud.render(hud.demo_data(), make_cfg(icons="plain"), hud.DEMO_STATE))
        data = hud.demo_data()
        del data["cost"]["total_duration_ms"]
        self.assertNotIn("2h10m", hud.render(data, make_cfg(), hud.DEMO_STATE))

    def test_unknown_segment_names_are_ignored(self):
        out = hud.render(hud.demo_data(), make_cfg(line1=["nope", "model"], line2=[]), hud.DEMO_STATE)
        self.assertIn("Sonnet 5.5", out)


def tool_use_line(name, **tool_input):
    block = {"type": "tool_use", "id": "t1", "name": name, "input": tool_input}
    return json.dumps({"type": "assistant", "message": {"content": [block]}})


class BrainTests(unittest.TestCase):
    ROOT = "C:/Notes/brain"

    def write_lines(self, tmp, lines):
        path = os.path.join(tmp, "s.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return path

    def test_label_short_and_long(self):
        self.assertEqual(hud.brain_label("sessions/hud-2026.md", 44), "sessions/hud-2026")
        self.assertEqual(hud.brain_label("plans/so/some-project/plan.md", 40), "plans/so/some-project/plan")
        long =hud.brain_label("plans/so/a-very-long-project-name-here/plan.md", 30)
        self.assertTrue(long.startswith("plans/\u2026/"))
        self.assertLessEqual(len(long), 30)
        self.assertLessEqual(len(hud.brain_label("x/" + "y" * 90 + ".md", 30)), 30)

    def test_touches_reads_tool_use_only_in_order_with_dedupe(self):
        with tempfile.TemporaryDirectory() as tmp:
            result_line = json.dumps({"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "C:\\Notes\\brain\\ignored.md"}]}})
            path = self.write_lines(tmp, [
                tool_use_line("Read", file_path="C:\\Notes\\brain\\sessions\\a.md"),
                tool_use_line("Bash", command='cat /c/Notes/brain/plans/x/plan.md:5 | head'),
                result_line,
                tool_use_line("Edit", file_path="c:/notes/BRAIN/sessions/a.md", old_string="x"),
                tool_use_line("Read", file_path="C:\\Elsewhere\\other.md"),
            ])
            files = hud.brain_touches(path, self.ROOT, 1 << 20)
            self.assertEqual(files, ["plans/x/plan.md", "sessions/a.md"])

    def test_window_drops_old_activity(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = tool_use_line("Read", file_path="C:/Notes/brain/old.md")
            filler = json.dumps({"type": "user", "pad": "x" * 5000})
            new = tool_use_line("Read", file_path="C:/Notes/brain/new.md")
            path = self.write_lines(tmp, [old, filler, new])
            self.assertEqual(hud.brain_touches(path, self.ROOT, 1000), ["new.md"])

    def test_relative_to_root(self):
        self.assertEqual(hud.relative_to_root("C:\\Notes\\brain\\plans\\x", self.ROOT), "plans/x")
        self.assertIsNone(hud.relative_to_root("C:/Notes/brain", self.ROOT))
        self.assertIsNone(hud.relative_to_root("C:/Other", self.ROOT))

    def test_build_state_finds_brain_and_caches(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_lines(tmp, [tool_use_line("Read", file_path=self.ROOT + "/skills/style.md")])
            cfg = make_cfg(brain_path=self.ROOT)
            st = hud.build_state({"transcript_path": path}, cfg, tmp)
            self.assertEqual(st["brain"]["files"], ["skills/style.md"])
            self.assertTrue(os.path.exists(os.path.join(tmp, "hud-state", "tools.json")))
            again = hud.build_state({"transcript_path": path}, cfg, tmp)
            self.assertEqual(again["brain"]["files"], ["skills/style.md"])

    def test_no_brain_without_brain_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_lines(tmp, [tool_use_line("Read", file_path=self.ROOT + "/skills/style.md")])
            st = hud.build_state({"transcript_path": path}, make_cfg(), tmp)
            self.assertIsNone(st["brain"])

    def test_cwd_inside_brain_is_a_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(brain_path=tmp)
            sub = os.path.join(tmp, "plans")
            os.makedirs(sub)
            st = hud.build_state({"workspace": {"current_dir": sub}}, cfg, tmp)
            self.assertEqual(st["brain"]["files"], ["plans"])

    def test_brain_goes_on_line_three_and_counts_extras(self):
        state = dict(hud.DEMO_STATE, brain={"files": ["plans/a.md", "sessions/hud-2026.md"]})
        out = hud.render(hud.demo_data(), make_cfg(layout="rows"), state)
        lines = out.split("\n")
        self.assertEqual(len(lines), 3)
        self.assertIn("sessions/hud-2026", lines[2])
        self.assertIn("+1", lines[2])

    def test_plain_icons_label_the_brain_segment(self):
        state = dict(hud.DEMO_STATE, brain={"files": ["a/b.md"]})
        out = hud.render(hud.demo_data(), make_cfg(icons="plain"), state)
        self.assertIn("brain a/b", out)


class ProjectTests(unittest.TestCase):
    def make_repo(self, base, name):
        root = os.path.join(base, name)
        os.makedirs(os.path.join(root, ".git"))
        os.makedirs(os.path.join(root, "src"))
        return root

    def transcript(self, base, *file_paths):
        path = os.path.join(base, "s.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(tool_use_line("Read", file_path=p) for p in file_paths) + "\n")
        return path

    def state(self, base, cwd, *file_paths, **cfg_over):
        cfg = make_cfg(**cfg_over)
        data = {"transcript_path": self.transcript(base, *file_paths), "workspace": {"current_dir": cwd}}
        return hud.build_state(data, cfg, os.path.join(base, "cfg"))

    def test_home_folder_session_finds_the_project_from_the_newest_touched_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            old, new = self.make_repo(tmp, "old-app"), self.make_repo(tmp, "new-app")
            st = self.state(tmp, os.path.expanduser("~"),
                            os.path.join(old, "src", "a.py"), os.path.join(new, "src", "b.py"))
            self.assertEqual(st["project"]["name"], "new-app")

    def test_cwd_repo_beats_touched_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            here, other = self.make_repo(tmp, "here"), self.make_repo(tmp, "other")
            st = self.state(tmp, here, os.path.join(other, "src", "x.py"))
            self.assertEqual(st["project"]["name"], "here")

    def test_brain_and_config_folders_never_count_as_the_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            work, brain = self.make_repo(tmp, "work"), self.make_repo(tmp, "brain")
            config = self.make_repo(os.path.join(tmp, "cfg"), "plugins") if os.makedirs(os.path.join(tmp, "cfg")) is None else None
            st = self.state(tmp, os.path.expanduser("~"),
                            os.path.join(work, "src", "a.py"),
                            os.path.join(brain, "src", "page.md"),
                            os.path.join(config, "src", "c.py"),
                            brain_path=brain)
            self.assertEqual(st["project"]["name"], "work")

    def test_scratch_folders_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = self.make_repo(tmp, "work")
            scratch = self.make_repo(os.path.join(tmp, "scratchpad"), "tmpjob") if os.makedirs(os.path.join(tmp, "scratchpad")) is None else None
            st = self.state(tmp, os.path.expanduser("~"),
                            os.path.join(work, "src", "a.py"), os.path.join(scratch, "src", "t.py"))
            self.assertEqual(st["project"]["name"], "work")

    def test_plain_folder_shows_its_name_and_home_shows_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            plain = os.path.join(tmp, "notes")
            os.makedirs(plain)
            self.assertEqual(self.state(tmp, plain)["project"], {"name": "notes", "git": None})
            self.assertIsNone(self.state(tmp, os.path.expanduser("~"))["project"])

    def test_where_is_hidden_without_a_project(self):
        out = hud.render(hud.demo_data(), make_cfg(), dict(hud.DEMO_STATE, project=None))
        self.assertNotIn("my-app", out)

    def test_files_beat_folders_in_the_brain_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "s.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(tool_use_line("Read", file_path="C:/Notes/brain/sessions/page.md") + "\n")
                f.write(tool_use_line("Bash", command="ls C:/Notes/brain/sessions") + "\n")
            self.assertEqual(hud.brain_touches(path, "C:/Notes/brain", 1 << 20), ["sessions/page.md"])

    def test_brain_label_shrinks_to_the_room_left_and_hides_when_there_is_none(self):
        state = dict(hud.DEMO_STATE, brain={"files": ["sessions/a-very-long-page-name-for-this-test.md"]})
        roomy = hud.render(hud.demo_data(), make_cfg(max_width=140), state).split("\n")[1]
        self.assertIn("sessions/a-very-long-page-name-for-this-test", roomy)
        wide = hud.render(hud.demo_data(), make_cfg(max_width=100), state).split("\n")[1]
        self.assertIn("sessions/a-very", wide)
        self.assertIn("…", wide)
        self.assertLessEqual(hud.vis_len(wide), 100)
        tight = hud.render(hud.demo_data(), make_cfg(max_width=78), state).split("\n")[1]
        self.assertLessEqual(hud.vis_len(tight), 78)
        none = hud.render(hud.demo_data(), make_cfg(max_width=70), state).split("\n")[1]
        self.assertNotIn("sessions/", none)


class StateTests(unittest.TestCase):
    def test_build_state_tracks_time_and_survives_missing_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "s.jsonl")
            t0 = datetime.now(timezone.utc) - timedelta(minutes=30)
            write_transcript(tp, [iso(t0), iso(t0 + timedelta(minutes=4))])
            data = {"transcript_path": tp, "workspace": {"current_dir": tmp}}
            st = hud.build_state(data, make_cfg(), tmp)
            self.assertAlmostEqual(st["session"], 4.0, places=2)
            self.assertAlmostEqual(st["today"], 4.0, places=2)
            self.assertTrue(os.path.exists(os.path.join(tmp, "hud-state", "active.json")))

    def test_config_dir_comes_from_transcript_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "projects", "proj", "abc.jsonl")
            old = os.environ.pop("CLAUDE_CONFIG_DIR", None)
            try:
                self.assertEqual(os.path.normpath(hud.config_dir({"transcript_path": tp})), os.path.normpath(tmp))
            finally:
                if old is not None:
                    os.environ["CLAUDE_CONFIG_DIR"] = old


if __name__ == "__main__":
    unittest.main()
