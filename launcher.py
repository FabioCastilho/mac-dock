"""Lançador de apps estilo Launchpad: tela cheia com blur, busca e grade de ícones."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from dock import LayerShell, find_monitor  # noqa: E402
from i18n import _  # noqa: E402

CSS = b"""
window.launcher { background: rgba(8, 9, 14, 0.50); backdrop-filter: blur(30px); }
window.launcher entry.launcher-search {
    background: rgba(255, 255, 255, 0.14); color: white; border-radius: 12px;
    padding: 8px 14px; min-height: 26px; font-size: 15px; border: 1px solid rgba(255,255,255,0.2);
}
window.launcher flowboxchild { border-radius: 14px; padding: 8px; }
window.launcher flowboxchild:hover { background: rgba(255, 255, 255, 0.12); }
window.launcher flowboxchild:active { background: rgba(255, 255, 255, 0.20); }
window.launcher label.app-name { color: white; font-size: 12px; }
window.launcher scrolledwindow, window.launcher viewport { background: transparent; }
"""

_css_loaded = False


def _load_css():
    global _css_loaded
    if _css_loaded:
        return
    prov = Gtk.CssProvider()
    prov.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
    _css_loaded = True


class LauncherWindow(Gtk.Window):
    def __init__(self, app):
        super().__init__(application=app)
        _load_css()
        self.dock_app = app
        self.add_css_class("launcher")
        self.set_decorated(False)

        if LayerShell and LayerShell.is_supported():
            LayerShell.init_for_window(self)
            LayerShell.set_namespace(self, "mac-dock-launcher")
            LayerShell.set_layer(self, LayerShell.Layer.OVERLAY)
            for edge in (LayerShell.Edge.TOP, LayerShell.Edge.BOTTOM,
                         LayerShell.Edge.LEFT, LayerShell.Edge.RIGHT):
                LayerShell.set_anchor(self, edge, True)
            LayerShell.set_exclusive_zone(self, -1)        # cobre inclusive o dock
            LayerShell.set_keyboard_mode(self, LayerShell.KeyboardMode.EXCLUSIVE)
            LayerShell.set_monitor(self, find_monitor(app.cfg.get("monitor")))
        else:
            self.fullscreen()

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=28)
        root.set_margin_top(70)
        root.set_margin_bottom(130)   # deixa espaço para o dock
        root.set_margin_start(120)
        root.set_margin_end(120)
        self.set_child(root)

        self.search = Gtk.SearchEntry(placeholder_text=_("Buscar"), halign=Gtk.Align.CENTER)
        self.search.add_css_class("launcher-search")
        self.search.set_size_request(380, -1)
        self.search.connect("search-changed", lambda _e: self.flow.invalidate_filter())
        self.search.connect("activate", self._launch_first)
        root.append(self.search)

        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                valign=Gtk.Align.START, halign=Gtk.Align.CENTER)
        self.flow.set_min_children_per_line(4)
        self.flow.set_max_children_per_line(9)
        self.flow.set_column_spacing(14)
        self.flow.set_row_spacing(14)
        self.flow.set_activate_on_single_click(True)
        self.flow.set_filter_func(self._filter)
        self.flow.connect("child-activated", self._on_child)
        scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True,
                                    hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroll.set_child(self.flow)
        root.append(scroll)

        self._apps = []
        apps = sorted((a for a in Gio.AppInfo.get_all() if a.should_show()),
                      key=lambda a: a.get_display_name().lower())
        for info in apps:
            self.flow.append(self._tile(info))
        self._root = root

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        click = Gtk.GestureClick()
        click.connect("released", self._on_click)
        self.add_controller(click)
        GLib.idle_add(self.search.grab_focus)

    def _tile(self, info):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_size_request(104, -1)
        icon = info.get_icon() or Gio.ThemedIcon.new("application-x-executable")
        img = Gtk.Image.new_from_gicon(icon)
        img.set_pixel_size(64)
        box.append(img)
        label = Gtk.Label(label=info.get_display_name(), ellipsize=3, lines=2, wrap=True,
                          max_width_chars=12, justify=Gtk.Justification.CENTER)
        label.add_css_class("app-name")
        box.append(label)
        child = Gtk.FlowBoxChild()
        child.set_child(box)
        child.info = info
        self._apps.append(child)
        return child

    def _filter(self, child):
        q = self.search.get_text().strip().lower()
        if not q:
            return True
        info = child.info
        hay = (info.get_display_name() + " " + (info.get_generic_name() or "") + " "
               + " ".join(getattr(info, "get_keywords", lambda: [])() or [])).lower()
        return q in hay

    def _launch(self, info):
        ctx = self.get_display().get_app_launch_context()
        try:
            info.launch([], ctx)
        except GLib.Error as e:
            print("falha ao abrir", info.get_display_name(), e)
        self.close()

    def _on_child(self, _flow, child):
        self._launch(child.info)

    def _launch_first(self, _entry):
        for child in self._apps:
            if child.get_child_visible() and self._filter(child):
                self._launch(child.info)
                return

    def _on_key(self, _c, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _on_click(self, _g, _n, x, y):
        # clique no fundo (fora da busca e da grade) fecha, como no Launchpad
        picked = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        if picked is self._root or picked is self:
            self.close()
