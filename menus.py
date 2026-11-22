"""Menu do botão direito como Gtk.Popover simples.

O Gtk.PopoverMenu limita a altura e põe barra de rolagem quando o menu é grande (o do dock
fica grande com as ações extras). Aqui o menu usa a altura que precisar. Aceita o mesmo
Gio.Menu (seções, itens com ação e submenus) que o dock já monta.
"""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, Gtk  # noqa: E402

_CSS = b"""
.mac-dock-menu button { min-height: 0; padding: 5px 10px; border-radius: 6px; }
.mac-dock-menu button:focus:not(:focus-visible) { outline: none; }
"""
_css_ready = False


def _ensure_css():
    global _css_ready
    if _css_ready:
        return
    prov = Gtk.CssProvider()
    prov.load_from_data(_CSS)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    _css_ready = True


def _label(model, i, attr="label"):
    v = model.get_item_attribute_value(i, attr, None)
    return v.get_string() if v is not None else ""


def _entry(text, indent=False):
    btn = Gtk.Button()
    btn.add_css_class("flat")
    lab = Gtk.Label(label=text, xalign=0)
    lab.set_ellipsize(3)
    lab.set_max_width_chars(38)
    if indent:
        lab.set_margin_start(14)
    btn.set_child(lab)
    return btn


def popover_from_model(model, group, on_done):
    """Popover com os itens de `model`; `group` executa as ações ("dock.aN").
    on_done() é chamado depois que um item é acionado."""
    _ensure_css()
    pop = Gtk.Popover()
    pop.set_has_arrow(False)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
    box.add_css_class("mac-dock-menu")
    for m in ("start", "end", "top", "bottom"):
        getattr(box, f"set_margin_{m}")(6)
    pop.set_child(box)

    def run(action):
        name = action.split(".", 1)[-1]
        pop.popdown()
        group.activate_action(name, None)
        on_done()

    def fill(target, mdl, indent=False):
        first = True
        for i in range(mdl.get_n_items()):
            section = mdl.get_item_link(i, "section")
            sub = mdl.get_item_link(i, "submenu")
            if section is not None:
                if not first and section.get_n_items():
                    sep = Gtk.Separator()
                    sep.set_margin_top(4)
                    sep.set_margin_bottom(4)
                    target.append(sep)
                title = _label(mdl, i)
                if title:
                    h = Gtk.Label(label=title, xalign=0)
                    h.add_css_class("dim-label")
                    h.add_css_class("heading")
                    h.set_margin_start(10)
                    h.set_margin_top(4)
                    h.set_margin_bottom(2)
                    target.append(h)
                fill(target, section, indent)
                first = False
            elif sub is not None:
                head = _entry(_label(mdl, i) + "  ›", indent)
                rev = Gtk.Revealer()
                inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                rev.set_child(inner)
                fill(inner, sub, True)
                head.connect("clicked", lambda _b, r=rev: r.set_reveal_child(not r.get_reveal_child()))
                target.append(head)
                target.append(rev)
                first = False
            else:
                action = mdl.get_item_attribute_value(i, "action", None)
                btn = _entry(_label(mdl, i), indent)
                if action is not None:
                    btn.connect("clicked", lambda _b, a=action.get_string(): run(a))
                target.append(btn)
                first = False

    fill(box, model)
    return pop
