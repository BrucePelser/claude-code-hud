import json
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
import hud  # noqa: E402
from icons import design  # noqa: E402


class ShippedFilesTests(unittest.TestCase):
    def test_example_config_lists_every_default_except_the_lines(self):
        with open(os.path.join(ROOT, "hud.config.example.json"), encoding="utf-8") as f:
            example = json.load(f)
        defaults = {k: v for k, v in hud.DEFAULTS.items() if k not in ("line1", "line2", "line3")}
        self.assertEqual(example, defaults)

    def test_every_icon_has_an_svg_file(self):
        for name in design.ICONS:
            path = os.path.join(ROOT, "icons", "svg", name + ".svg")
            self.assertTrue(os.path.exists(path), path)

    def test_every_custom_role_points_at_a_real_glyph_and_colour(self):
        for role, (glyph, color) in hud.CUSTOM_ROLES.items():
            self.assertIn(glyph, hud.GLYPHS, role)
            self.assertIn(color, hud.DEFAULTS["icon_colors"], role)

    def test_all_layout_segments_exist(self):
        for layout in hud.LAYOUTS.values():
            for names in layout.values():
                for name in names:
                    self.assertIn(name, hud.SEGMENTS)

    def test_font_has_a_glyph_for_every_icon(self):
        try:
            from fontTools.ttLib import TTFont
        except ImportError:
            self.skipTest("fonttools not installed")
        font = TTFont(os.path.join(ROOT, "fonts", "ClaudeHudIcons.ttf"))
        cmap = font.getBestCmap()
        for name, codepoint in design.CODEPOINTS.items():
            self.assertEqual(cmap.get(codepoint), name)


if __name__ == "__main__":
    unittest.main()
