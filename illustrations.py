"""Esboços (cairo) que mostram, na janela de ajustes, o que cada recurso faz.

Cada função desenha numa tela virtual de 240x110; `pal` traz as cores já tiradas do tema
do sistema (claro/escuro): fg (texto), accent, dock (fundo do dock), icon (ícones neutros)
e bg (fundo do esboço).
"""
import math

from i18n import _

W, H = 240.0, 110.0
X0, STEP = 50.0, 30.0


def _rgba(cr, c, a=None):
    cr.set_source_rgba(c[0], c[1], c[2], c[3] if a is None else a)


def _rr(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _fill(cr, color, x, y, w, h, r=0):
    _rr(cr, x, y, w, h, r) if r else cr.rectangle(x, y, w, h)
    _rgba(cr, color)
    cr.fill()


def _text(cr, s, x, y, color, size=9, center=False, bold=False, mono=False):
    cr.select_font_face("monospace" if mono else "sans",
                        0, 1 if bold else 0)
    cr.set_font_size(size)
    if center:
        ext = cr.text_extents(_(s))
        x -= ext.width / 2 + ext.x_bearing
    cr.move_to(x, y)
    _rgba(cr, color)
    cr.show_text(_(s))


def _line(cr, color, pts, width=1.5, dash=None):
    _rgba(cr, color)
    cr.set_line_width(width)
    cr.set_line_cap(1)
    cr.set_dash(dash or [])
    cr.move_to(*pts[0])
    for p in pts[1:]:
        cr.line_to(*p)
    cr.stroke()
    cr.set_dash([])


def _icons(cr, pal, n=5, y=77, hot=None, x0=X0):
    for k in range(n):
        h = hot == k
        _fill(cr, pal["accent"] if h else pal["icon"], x0 + k * STEP, y - (6 if h else 0), 20, 20, 5)


def _dock(cr, pal, n=5, hot=None):
    _fill(cr, pal["dock"], 36, 72, 168, 30, 10)
    _icons(cr, pal, n, 77, hot)


def _window(cr, pal, x, y, w, h, label=""):
    _fill(cr, pal["bg2"], x, y, w, h, 4)
    _fill(cr, pal["dock"], x, y, w, 8, 3)
    if label:
        _text(cr, label, x + 4, y + h - 5, pal["fg2"], 8)


# ---------------------------------------------------------------- recursos

def preview(cr, pal):
    _window(cr, pal, 60, 10, 54, 40, "Brave")
    _window(cr, pal, 120, 10, 54, 40, "Brave")
    _line(cr, pal["icon"], [(117, 54), (117, 68)])
    _dock(cr, pal, 5, hot=1)


def progress(cr, pal):
    _dock(cr, pal)
    _fill(cr, pal["dock"], X0 + 2 * STEP, 62, 20, 5, 2.5)
    _fill(cr, pal["accent"], X0 + 2 * STEP, 62, 13, 5, 2.5)
    cx = X0 + 3 * STEP + 19
    cr.arc(cx, 78, 7, 0, 2 * math.pi)
    _rgba(cr, (0.95, 0.22, 0.25, 1))
    cr.fill()
    _text(cr, "3", cx, 81, (1, 1, 1, 1), 9, center=True, bold=True)
    _text(cr, "Baixando 65%", 120, 40, pal["fg2"], 9, center=True)


def multimon(cr, pal):
    for ox, hot in ((14, False), (126, True)):
        _fill(cr, pal["bg2"], ox, 18, 100, 62, 4)
        _fill(cr, pal["dock"], ox + 16, 66, 68, 10, 4)
        for k in range(4):
            _fill(cr, pal["accent"] if (hot and k == 0) else pal["icon"], ox + 26 + k * 12, 68, 6, 6, 2)
    _fill(cr, pal["dock"], 64, 84, 112, 6, 3)


def posicao(cr, pal):
    _fill(cr, pal["dock"], 14, 12, 30, 86, 10)
    for k in range(4):
        _fill(cr, pal["accent"] if k == 1 else pal["icon"], 19, 18 + k * 21, 20, 20, 5)
    _line(cr, pal["accent"], [(110, 56), (168, 56)], 2)
    _line(cr, pal["accent"], [(158, 46), (170, 56), (158, 66)], 2)
    _fill(cr, pal["dock"], 190, 8, 38, 12, 5)


def reflexo(cr, pal):
    _fill(cr, pal["dock"], 36, 40, 168, 30, 10)
    _icons(cr, pal, 5, 45)
    for k in range(5):
        g = __import__("cairo").LinearGradient(0, 70, 0, 94)
        c = pal["icon"]
        g.add_color_stop_rgba(0, c[0], c[1], c[2], 0.45)
        g.add_color_stop_rgba(1, c[0], c[1], c[2], 0.0)
        _rr(cr, X0 + k * STEP, 71, 20, 24, 5)
        cr.set_source(g)
        cr.fill()


def indicador(cr, pal):
    _dock(cr, pal)
    counts = [0, 1, 2, 3, 1]
    for k, n in enumerate(counts):
        cx = X0 + k * STEP + 10
        for j in range(n):
            attn = k == 3
            col = (1.0, 0.62, 0.12, 1.0) if attn else (pal["accent"] if k == 2 else pal["icon"])
            cr.arc(cx + (j - (n - 1) / 2) * 6, 98, 2, 0, 2 * math.pi)
            _rgba(cr, col)
            cr.fill()
    _text(cr, "1, 2 ou 3 janelas · laranja = pede atenção", 120, 40, pal["fg2"], 8.5, center=True)


def temas(cr, pal):
    for y, bg, fg, name in ((14, (0.10, 0.10, 0.12, 0.9), (1, 1, 1, 1), "Escuro"),
                            (44, (1, 1, 1, 1), (0.2, 0.2, 0.25, 1), "Claro"),
                            (74, (0.04, 0.14, 0.24, 1), (0.9, 0.97, 1, 1), "Oceano")):
        _fill(cr, bg, 36, y, 168, 22, 8)
        cr.arc(52, y + 11, 4, 0, 2 * math.pi)
        _rgba(cr, pal["accent"])
        cr.fill()
        _text(cr, name, 64, y + 14.5, fg, 9, bold=True)
    _text(cr, "segue o KDE", 196, 60, pal["fg2"], 8, center=True)


def esconder(cr, pal):
    _window(cr, pal, 40, 14, 160, 78)
    _fill(cr, pal["dock"], 60, 98, 120, 4, 2)
    _text(cr, "janela cobre o dock: ele recolhe", 120, 56, pal["fg2"], 9, center=True)


def arrastar(cr, pal):
    _dock(cr, pal, 5, hot=4)
    cr.save()
    cr.translate(100, 36)
    cr.rotate(-0.14)
    _fill(cr, pal["bg2"], -11, -14, 22, 28, 3)
    _line(cr, pal["icon"], [(-6, -6), (4, -6)])
    _line(cr, pal["icon"], [(-6, 0), (4, 0)])
    cr.restore()
    cr.set_line_width(2)
    _rgba(cr, pal["accent"])
    cr.set_dash([3, 4])
    cr.move_to(118, 40)
    cr.curve_to(140, 40, 160, 50, X0 + 4 * STEP + 10, 64)
    cr.stroke()
    cr.set_dash([])


def contexto(cr, pal):
    _fill(cr, pal["bg2"], 92, 6, 96, 60, 6)
    for i, t in enumerate(("Minimizar todas", "Mover para o começo", "Mover para o fim", "Remover do dock")):
        _text(cr, t, 100, 20 + i * 13, pal["fg2"], 8.5)
    _dock(cr, pal, 5, hot=2)


def instalador(cr, pal):
    _fill(cr, pal["bg2"], 20, 10, 200, 90, 6)
    for i, (t, ok) in enumerate((("$ ./install.sh", False), ("dependências ...... ok", True),
                                 ("autostart ......... ok", True), ("pronto", False))):
        _text(cr, t, 30, 28 + i * 16, (0.2, 0.7, 0.4, 1) if ok else pal["fg"], 8.5, mono=True)


def traducoes(cr, pal):
    for i, (t, on) in enumerate((("PT", False), ("EN", True), ("ES", False))):
        _fill(cr, pal["accent"] if on else pal["dock"], 30 + i * 65, 40, 50, 28, 14)
        _text(cr, t, 55 + i * 65, 58, (1, 1, 1, 1) if on else pal["fg2"], 10, center=True, bold=True)


DRAWERS = {f.__name__: f for f in (preview, progress, multimon, posicao, reflexo, indicador,
                                   temas, esconder, arrastar, contexto, instalador, traducoes)}
DRAWERS["progresso"] = progress


def make_area(name):
    """Gtk.DrawingArea com o esboço `name`, já nas cores do tema atual."""
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    area = Gtk.DrawingArea()
    area.set_content_height(150)
    area.set_hexpand(True)
    drawer = DRAWERS[name]

    def draw(widget, cr, w, h):
        fg = widget.get_color()
        f = (fg.red, fg.green, fg.blue)
        pal = {
            "fg": (*f, 0.95), "fg2": (*f, 0.65),
            "bg2": (*f, 0.10), "dock": (*f, 0.16), "icon": (*f, 0.45),
            "accent": (0.25, 0.55, 0.98, 1.0),
        }
        k = min(w / W, h / H)
        cr.translate((w - W * k) / 2, (h - H * k) / 2)
        cr.scale(k, k)
        drawer(cr, pal)

    area.set_draw_func(draw)
    return area
