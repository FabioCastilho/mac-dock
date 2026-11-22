"""Testes da lógica do mac-dock que não precisam de uma janela real."""
import ast
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import dock  # noqa: E402
import i18n  # noqa: E402


class FakeView:
    """Só o necessário para usar os métodos de mapeamento de DockView."""
    def __init__(self, position):
        self.cfg = dict(dock.DEFAULTS, position=position)
        self.cfg["pinned"] = []

    logical_size = lambda self: (700, 200)  # noqa: E731
    position = property(lambda self: self.cfg["position"])
    _xf = dock.DockView._xf
    to_screen = dock.DockView.to_screen
    to_logical = dock.DockView.to_logical
    lin_to_logical = dock.DockView.lin_to_logical
    screen_rect = dock.DockView.screen_rect


class PositionMapping(unittest.TestCase):
    def test_round_trip(self):
        for pos in dock.POSITIONS:
            v = FakeView(pos)
            for x, y in ((0, 0), (123.5, 45.25), (699, 199)):
                lx, ly = v.to_logical(*v.to_screen(x, y))
                self.assertAlmostEqual(lx, x, msg=pos)
                self.assertAlmostEqual(ly, y, msg=pos)

    def test_edge_side(self):
        # o "fundo" lógico (y = altura) fica na borda certa da tela
        self.assertEqual(FakeView("bottom").to_screen(10, 200), (10, 200))
        self.assertEqual(FakeView("top").to_screen(10, 200), (10, 0))
        self.assertEqual(FakeView("left").to_screen(10, 200)[0], 0)
        self.assertEqual(FakeView("right").to_screen(10, 200)[0], 200)

    def test_rect_swaps_size_on_vertical(self):
        _x, _y, w, h = FakeView("left").screen_rect(0, 0, 300, 50)
        self.assertEqual((w, h), (50, 300))


class SmartHide(unittest.TestCase):
    RECT = (300, 1000, 600, 80)

    def test_cover(self):
        w = [{"geo": [0, 0, 1920, 1080], "vis": True, "out": "DP-1"}]
        self.assertTrue(dock.windows_cover(w, "DP-1", self.RECT))
        self.assertFalse(dock.windows_cover(w, "HDMI-A-1", self.RECT))      # outra tela

    def test_no_cover(self):
        up = [{"geo": [0, 0, 1920, 900], "vis": True}]
        self.assertFalse(dock.windows_cover(up, "", self.RECT))
        hidden = [{"geo": [0, 0, 1920, 1080], "vis": True, "min": True}]
        self.assertFalse(dock.windows_cover(hidden, "", self.RECT))
        other_desktop = [{"geo": [0, 0, 1920, 1080], "vis": False}]
        self.assertFalse(dock.windows_cover(other_desktop, "", self.RECT))


class Translations(unittest.TestCase):
    def test_every_entry_has_en_and_es(self):
        for key, row in i18n.TABLE.items():
            self.assertEqual(len(row), 2, key)
            self.assertTrue(all(row), key)

    def test_translate(self):
        i18n.set_language("en")
        self.assertEqual(i18n._("Lixeira"), "Trash")
        i18n.set_language("es")
        self.assertEqual(i18n._("Lixeira"), "Papelera")
        i18n.set_language("pt")
        self.assertEqual(i18n._("Lixeira"), "Lixeira")
        self.assertEqual(i18n._("texto sem tradução"), "texto sem tradução")

    def test_resolve(self):
        self.assertEqual(i18n.resolve("en"), "en")
        self.assertEqual(i18n.resolve("xx") in i18n.LANGS, True)

    def test_literals_passed_to_underscore_are_in_table(self):
        """Todo texto fixo que o código manda para _() tem tradução."""
        missing = []
        for name in ("dock.py", "settings.py", "launcher.py"):
            tree = ast.parse(open(os.path.join(ROOT, name), encoding="utf-8").read())
            for n in ast.walk(tree):
                if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_"
                        and n.args and isinstance(n.args[0], ast.Constant)
                        and isinstance(n.args[0].value, str)):
                    if n.args[0].value not in i18n.TABLE:
                        missing.append((name, n.args[0].value))
        self.assertEqual(missing, [])

    def test_theme_names_translated(self):
        for t in dock.THEMES.values():
            self.assertIn(t["nome"], i18n.TABLE, t["nome"])


class ConfigAndFiles(unittest.TestCase):
    def test_new_defaults(self):
        for key in ("position", "multi_monitor", "window_preview", "smart_hide", "language",
                    "reflection", "rich_dots", "big_menu", "file_drop", "progress"):
            self.assertIn(key, dock.DEFAULTS)
        self.assertIn(dock.DEFAULTS["position"], dock.POSITIONS)

    def test_installer_syntax(self):
        r = subprocess.run(["bash", "-n", os.path.join(ROOT, "install.sh")], capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_installer_dry_run_changes_nothing(self):
        home = os.path.join(os.environ.get("TMPDIR", "/tmp"), "mac-dock-test-home")
        os.makedirs(home, exist_ok=True)
        r = subprocess.run(["bash", os.path.join(ROOT, "install.sh"), "--dry-run"],
                           capture_output=True, text=True, env=dict(os.environ, HOME=home,
                                                                    XDG_CONFIG_HOME=home + "/c",
                                                                    XDG_DATA_HOME=home + "/d"))
        self.assertFalse(os.path.exists(home + "/c/autostart/mac-dock.desktop"))
        self.assertIn("simulação", r.stdout)


class LauncherEntryParsing(unittest.TestCase):
    def test_progress_and_count(self):
        v = dock.DockView.__new__(dock.DockView)
        v.entries = {}
        v.apply_badges = lambda: None
        dock.DockView.set_entry(v, "brave-browser", {"progress-visible": True, "progress": 0.5,
                                                     "count-visible": True, "count": 3})
        self.assertEqual(v.entries["brave-browser"], {"progress": 0.5, "count": 3})
        dock.DockView.set_entry(v, "brave-browser", {"progress-visible": False, "count-visible": False})
        self.assertNotIn("brave-browser", v.entries)


if __name__ == "__main__":
    unittest.main()
