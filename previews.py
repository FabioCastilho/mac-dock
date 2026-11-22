"""Pré-visualização de janelas: miniaturas ao passar o mouse sobre um app aberto.

As imagens vêm do KWin (org.kde.KWin.ScreenShot2). O KWin só atende aplicativos que declaram
`X-KDE-DBUS-Restricted-Interfaces=org.kde.KWin.ScreenShot2` no .desktop (o install.sh cria
esse arquivo). Sem a autorização, ou para janelas minimizadas, o cartão mostra o ícone do app
e o título da janela, e continua funcionando para focar a janela.
"""
import os
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

DEST = "org.kde.KWin"
PATH = "/org/kde/KWin/ScreenShot2"
IFACE = "org.kde.KWin.ScreenShot2"
THUMB_W, THUMB_H = 190, 118

# QImage::Format -> formato de memória do GDK
QIMAGE_FORMATS = {
    4: Gdk.MemoryFormat.B8G8R8X8,                 # RGB32
    5: Gdk.MemoryFormat.B8G8R8A8,                 # ARGB32
    6: Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED,   # ARGB32_Premultiplied
    17: Gdk.MemoryFormat.R8G8B8A8,                # RGBA8888
    18: Gdk.MemoryFormat.R8G8B8A8_PREMULTIPLIED,  # RGBA8888_Premultiplied
}


def capture(handle=None, timeout_ms=4000):
    """Captura uma janela (id do KWin) ou, sem `handle`, a janela ativa.
    Devolve (largura, altura, stride, formato_qimage, bytes). Levanta GLib.Error, OSError
    ou ValueError se o KWin recusar ou devolver algo que não entendemos."""
    r, w = os.pipe()
    chunks = []

    def reader():
        with os.fdopen(r, "rb", closefd=True) as f:
            while True:
                part = f.read(65536)
                if not part:
                    break
                chunks.append(part)

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    fdl = Gio.UnixFDList.new()
    idx = fdl.append(w)
    os.close(w)
    opts = {"include-decoration": GLib.Variant("b", True),
            "include-cursor": GLib.Variant("b", False)}
    try:
        conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        if handle:
            params = GLib.Variant("(sa{sv}h)", (handle, opts, idx))
            method = "CaptureWindow"
        else:
            params = GLib.Variant("(a{sv}h)", (opts, idx))
            method = "CaptureActiveWindow"
        reply, _ = conn.call_with_unix_fd_list_sync(
            DEST, PATH, IFACE, method, params, GLib.VariantType("(a{sv})"),
            Gio.DBusCallFlags.NONE, timeout_ms, fdl, None)
    finally:
        for fd in fdl.steal_fds():     # sem isso o leitor nunca vê o fim do arquivo
            os.close(fd)
    t.join(timeout_ms / 1000)
    info = reply.unpack()[0]
    width, height, stride, fmt = (int(info.get(k, 0)) for k in ("width", "height", "stride", "format"))
    data = b"".join(chunks)
    if not (width and height and stride) or len(data) < stride * height or fmt not in QIMAGE_FORMATS:
        raise ValueError(f"imagem inesperada: {width}x{height} formato {fmt}")
    return width, height, stride, fmt, data[:stride * height]


def to_texture(shot):
    width, height, stride, fmt, data = shot
    return Gdk.MemoryTexture.new(width, height, QIMAGE_FORMATS[fmt], GLib.Bytes.new(data), stride)


class WindowPreview:
    """Popover com um cartão (miniatura + título) por janela do app."""

    def __init__(self, view, focus_cb):
        self.view = view
        self.focus_cb = focus_cb         # focus_cb(id_da_janela)
        self.pop = None
        self.item = None
        self.inside = False
        self._failed = 0                 # falhas seguidas: para de insistir se o KWin recusa

    @property
    def is_open(self):
        return self.pop is not None

    def close(self):
        pop, self.pop, self.item, self.inside = self.pop, None, None, False
        if pop is not None:
            pop.popdown()
            GLib.idle_add(pop.unparent)

    def open(self, item, anchor_screen, position):
        """anchor_screen: (x, y) na tela do ponto logo acima (ou ao lado) do ícone."""
        self.close()
        pop = Gtk.Popover()
        pop.set_autohide(False)
        pop.set_has_arrow(False)
        pop.add_css_class("mac-dock-preview")
        pop.set_parent(self.view)
        pop.set_position({"bottom": Gtk.PositionType.TOP, "top": Gtk.PositionType.BOTTOM,
                          "left": Gtk.PositionType.RIGHT, "right": Gtk.PositionType.LEFT}[position])
        target = Gdk.Rectangle()
        target.x, target.y, target.width, target.height = int(anchor_screen[0]), int(anchor_screen[1]), 1, 1
        pop.set_pointing_to(target)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if position in ("left", "right")
                      else Gtk.Orientation.HORIZONTAL, spacing=8)
        for m in ("start", "end", "top", "bottom"):
            getattr(box, f"set_margin_{m}")(8)
        for win in item.windows[:6]:
            box.append(self._card(item, win))
        pop.set_child(box)
        motion = Gtk.EventControllerMotion()
        motion.connect("enter", lambda *_a: setattr(self, "inside", True))
        motion.connect("leave", lambda *_a: setattr(self, "inside", False))
        pop.add_controller(motion)
        self.pop, self.item = pop, item
        pop.popup()

    def _card(self, item, win):
        pic = Gtk.Picture()
        pic.set_size_request(THUMB_W, THUMB_H)
        pic.set_content_fit(Gtk.ContentFit.CONTAIN)
        pic.set_can_shrink(True)
        if item.paintable is not None:
            pic.set_paintable(item.paintable)
        title = Gtk.Label(label=(win.get("title") or item.name)[:60])
        title.set_ellipsize(3)           # fim do texto
        title.set_max_width_chars(24)
        title.set_xalign(0.5)
        if win.get("att"):
            title.add_css_class("warning")
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        col.append(pic)
        col.append(title)
        btn = Gtk.Button()
        btn.add_css_class("flat")
        btn.set_child(col)
        btn.connect("clicked", lambda _b, w=win: (self.focus_cb(w["id"]), self.close()))
        if not win.get("min") and self._failed < 3:
            self._load(pic, win["id"])
        return btn

    def _load(self, pic, win_id):
        def work():
            try:
                shot = capture(win_id)
            except (GLib.Error, OSError, ValueError) as e:
                GLib.idle_add(self._failed_once, getattr(e, "message", str(e)))
                return
            GLib.idle_add(self._show, pic, shot)

        threading.Thread(target=work, daemon=True).start()

    def _show(self, pic, shot):
        self._failed = 0
        try:
            pic.set_paintable(to_texture(shot))
        except (GLib.Error, TypeError):
            pass
        return False

    def _failed_once(self, msg):
        self._failed += 1
        if self._failed == 1:
            print(f"[mac-dock] sem miniaturas (usando ícones): {msg}", file=sys.stderr)
        return False
