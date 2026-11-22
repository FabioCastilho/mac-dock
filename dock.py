#!/usr/bin/env python3
"""mac-dock: dock estilo macOS em GTK4 + layer-shell (KDE Plasma / Wayland).

Ampliação com física de mola, bounce ao abrir, brilho na cor do ícone, apps abertos
(via script do KWin), menu do botão direito, arrastar para reordenar, lixeira,
esconder automático e lançador de apps. Config: ~/.config/mac-dock/config.json.

Uso:  python3 dock.py            # roda o dock (2ª execução abre os ajustes)
      python3 dock.py --png X    # renderiza uma imagem de teste e sai
"""
import copy
import json
import math
import os
import shlex
import subprocess
import sys
import time


def _preload_layer_shell():
    """gtk4-layer-shell precisa ser carregado antes do libwayland-client: re-executa
    o programa com LD_PRELOAD (sem isso o dock vira uma janela comum no meio da tela)."""
    if "libgtk4-layer-shell" in os.environ.get("LD_PRELOAD", ""):
        return
    for d in ("/usr/lib", "/usr/lib64", "/usr/lib/x86_64-linux-gnu"):
        path = os.path.join(d, "libgtk4-layer-shell.so")
        if os.path.exists(path):
            old = os.environ.get("LD_PRELOAD")
            os.environ["LD_PRELOAD"] = path + (":" + old if old else "")
            os.execv(sys.executable, [sys.executable] + sys.argv)


if __name__ == "__main__":
    _preload_layer_shell()

# A biblioteca já foi carregada neste processo; os apps que o dock abrir não devem herdá-la
# (ela quebra apps como a Steam: "libgtk-4.so.1 not found").
_LP = [p for p in os.environ.get("LD_PRELOAD", "").split(":")
       if p and "libgtk4-layer-shell" not in p]
if _LP:
    os.environ["LD_PRELOAD"] = ":".join(_LP)
else:
    os.environ.pop("LD_PRELOAD", None)

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Pango", "1.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import (Adw, Gdk, GdkPixbuf, Gio, GLib, Graphene, Gsk, Gtk,  # noqa: E402
                           Pango)

try:
    gi.require_version("Gtk4LayerShell", "1.0")
    from gi.repository import Gtk4LayerShell as LayerShell  # noqa: E402
except (ValueError, ImportError):
    LayerShell = None

try:
    import cairo
except ImportError:
    cairo = None

APP_ID = "io.github.fabio.MacDock"
CONFIG_PATH = os.path.expanduser("~/.config/mac-dock/config.json")
DEFAULTS = {
    "pinned": [
        "org.kde.dolphin.desktop",
        "brave-origin.desktop",
        "steam.desktop",
        "org.kde.konsole.desktop",
        "systemsettings.desktop",
    ],
    "icon_size": 52,       # tamanho em repouso (px)
    "max_scale": 1.85,     # ampliação máxima do ícone sob o mouse
    "spread": 78,          # raio da ampliação (px)
    "gap": 8,              # espaço entre ícones
    "padding": 12,         # margem interna do dock
    "margin_bottom": 8,    # distância da borda inferior
    "radius": 22,
    "monitor": "",         # conector (ex.: "HDMI-A-1"); vazio = deixa o compositor escolher
    "bounce_seconds": 10,  # tempo máximo de bounce esperando o app abrir
    "theme": "escuro",
    "bg_intensity": 1.0,   # multiplica a opacidade do fundo do tema
    "show_labels": True,
    "show_dots": True,
    "blur": True,          # desfoque do fundo pelo KWin
    "reserve_space": True, # janelas maximizadas não cobrem o dock
    "autohide": False,     # esconde o dock quando o mouse sai (borda de baixo traz de volta)
    "show_launcher": True, # botão de menu iniciar (lançador de apps) no começo do dock
    "show_running": True,  # mostra apps abertos que não estão fixados
    "show_trash": True,    # lixeira no fim do dock
    "glow": True,          # brilho sob o ícone na cor dominante dele
    "spring": True,        # ampliação com física de mola (leve oscilação)
    "launcher_icon": "",   # imagem do botão de menu; vazio = fruta do projeto; "grid" = grade
    "mode": "Padrão",      # modo ativo (conjunto de apps do dock)
    "modes": [],           # [{"name", "pinned": [...], "triggers": [...]}]; criados na 1ª vez
    "auto_modes": True,    # troca de modo sozinha quando um app "gatilho" fica ativo
    "badges": True,        # contador de notificações no ícone do app
    "music_pulse": True,   # ícone do app que está tocando música anima
    "reflection": False,   # reflexo suave embaixo dos ícones
    "rich_dots": True,     # indicador mostra nº de janelas e pede atenção em laranja
    "big_menu": True,      # mais ações no menu do botão direito
    "file_drop": True,     # soltar arquivos num ícone abre no app; na lixeira, apaga
    "progress": True,      # barra de progresso e contador no ícone (Unity LauncherEntry)
    "theme_follow": "off", # "kde": segue o claro/escuro do KDE usando theme_light/theme_dark
    "theme_light": "claro",
    "theme_dark": "escuro",
    "accent_auto": False,  # usa a cor de destaque do KDE no indicador e na borda
}

# modos sugeridos na primeira execução (só entram os apps instalados)
SEED_MODES = [
    ("Jogos", ["steam.desktop", "com.heroicgameslauncher.hgl.desktop", "net.lutris.Lutris.desktop",
               "discord.desktop", "org.kde.dolphin.desktop", "brave-origin.desktop"]),
    ("Dev", ["org.kde.konsole.desktop", "code.desktop", "dev.zed.Zed.desktop",
             "org.kde.kate.desktop", "org.kde.dolphin.desktop", "brave-origin.desktop"]),
    ("Criação", ["krita.desktop", "org.kde.krita.desktop", "blender.desktop", "gimp.desktop",
                 "org.inkscape.Inkscape.desktop", "org.godotengine.Godot.desktop",
                 "com.obsproject.Studio.desktop", "org.kde.dolphin.desktop"]),
]

DEFAULT_LAUNCHER_ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "assets", "launcher.png")


def desktop_info(desktop_id):
    """Gio.DesktopAppInfo ou None (o binding lança TypeError quando o .desktop não existe)."""
    try:
        return Gio.DesktopAppInfo.new(desktop_id)
    except TypeError:
        return None


def load_launcher_texture(setting):
    """Textura do botão de menu iniciar (reduzida p/ ficar nítida), ou None p/ a grade."""
    if setting == "grid":
        return None
    path = os.path.expanduser(setting) if setting else DEFAULT_LAUNCHER_ICON
    try:
        pb = GdkPixbuf.Pixbuf.new_from_file(path)
        k = 256 / max(pb.get_width(), pb.get_height())
        if k < 1:
            pb = pb.scale_simple(max(1, int(pb.get_width() * k)), max(1, int(pb.get_height() * k)),
                                 GdkPixbuf.InterpType.HYPER)
        return Gdk.Texture.new_for_pixbuf(pb)
    except GLib.Error:
        return None

# fundo, borda, rótulo (fundo/texto) e ponto de app aberto: (r, g, b, a)
THEMES = {
    "escuro": {"nome": "Escuro", "bg": (0.10, 0.10, 0.12, 0.55), "border": (1, 1, 1, 0.22),
               "label_bg": (0.10, 0.10, 0.12, 0.80), "label_fg": (1, 1, 1, 0.95),
               "dot": (1, 1, 1, 0.85)},
    "oceano": {"nome": "Oceano", "bg": (0.04, 0.14, 0.24, 0.62), "border": (0.55, 0.85, 1.0, 0.35),
               "label_bg": (0.04, 0.14, 0.24, 0.90), "label_fg": (0.9, 0.97, 1, 0.97),
               "dot": (0.55, 0.9, 1, 0.95)},
    "floresta": {"nome": "Floresta", "bg": (0.07, 0.15, 0.11, 0.62), "border": (0.6, 0.95, 0.7, 0.30),
                 "label_bg": (0.07, 0.15, 0.11, 0.90), "label_fg": (0.92, 1, 0.94, 0.97),
                 "dot": (0.6, 0.95, 0.7, 0.95)},
    "sakura": {"nome": "Sakura", "bg": (0.97, 0.88, 0.92, 0.50), "border": (1, 1, 1, 0.70),
               "label_bg": (0.35, 0.14, 0.24, 0.90), "label_fg": (1, 0.94, 0.97, 0.97),
               "dot": (0.85, 0.3, 0.5, 0.95)},
    "claro": {"nome": "Claro", "bg": (1, 1, 1, 0.45), "border": (1, 1, 1, 0.70),
              "label_bg": (1, 1, 1, 0.88), "label_fg": (0.1, 0.1, 0.12, 0.95),
              "dot": (0.1, 0.1, 0.12, 0.75)},
    "apple": {"nome": "Vidro (estilo Apple)", "bg": (0.92, 0.93, 0.97, 0.28),
              "border": (1, 1, 1, 0.50), "label_bg": (0.16, 0.16, 0.18, 0.85),
              "label_fg": (1, 1, 1, 0.95), "dot": (1, 1, 1, 0.9)},
    "grafite": {"nome": "Grafite", "bg": (0.18, 0.18, 0.20, 0.88), "border": (1, 1, 1, 0.12),
                "label_bg": (0.08, 0.08, 0.09, 0.90), "label_fg": (1, 1, 1, 0.95),
                "dot": (0.75, 0.75, 0.8, 0.9)},
    "meia-noite": {"nome": "Meia-noite", "bg": (0.04, 0.05, 0.14, 0.70),
                   "border": (0.45, 0.55, 1.0, 0.38), "label_bg": (0.04, 0.05, 0.14, 0.88),
                   "label_fg": (0.85, 0.9, 1, 0.95), "dot": (0.55, 0.7, 1.0, 0.95)},
}

SEP_W = 14          # largura do separador
SPRING_K = 300.0    # rigidez da mola da ampliação
SPRING_C = 22.0     # amortecimento (menor = mais balanço)


def ensure_modes(cfg):
    """Garante a lista de modos e mantém cfg['pinned'] igual ao conjunto do modo ativo."""
    modes = cfg.get("modes") or []
    if not modes:
        modes = [{"name": "Padrão", "pinned": list(cfg["pinned"]), "triggers": []}]
        for name, cands in SEED_MODES:
            apps = [d for d in dict.fromkeys(cands) if desktop_info(d)]
            if len(apps) >= 3:
                modes.append({"name": name, "pinned": apps, "triggers": []})
        cfg["mode"] = "Padrão"
    for m in modes:
        m.setdefault("pinned", [])
        m.setdefault("triggers", [])
    cfg["modes"] = modes
    if cfg.get("mode") not in [m["name"] for m in modes]:
        cfg["mode"] = modes[0]["name"]
    cfg["pinned"] = list(next(m for m in modes if m["name"] == cfg["mode"])["pinned"])
    return cfg


def load_config():
    cfg = copy.deepcopy(DEFAULTS)
    try:
        with open(CONFIG_PATH) as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return ensure_modes(cfg)


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CONFIG_PATH)


def rgba(r, g, b, a):
    c = Gdk.RGBA()
    c.red, c.green, c.blue, c.alpha = r, g, b, a
    return c


def rect(x, y, w, h):
    return Graphene.Rect().init(x, y, w, h)


def stop(offset, color):
    s = Gsk.ColorStop()
    s.offset = offset
    s.color = color
    return s


# ---------------------------------------------------------------- KWin

def _kwin_call(method, *args, obj="/Scripting"):
    return subprocess.run(
        ["gdbus", "call", "--session", "--dest", "org.kde.KWin", "--object-path", obj,
         "--method", method, *args], capture_output=True, text=True, timeout=3).stdout


def kwin_eval(js, name="mac-dock-cmd"):
    """Roda um script curto no KWin (Wayland não tem wmctrl/xdotool)."""
    path = os.path.join(GLib.get_user_runtime_dir(), name + ".js")
    with open(path, "w") as f:
        f.write(js)
    try:
        _kwin_call("org.kde.kwin.Scripting.unloadScript", name)
        out = _kwin_call("org.kde.kwin.Scripting.loadScript", path, name)
        sid = "".join(ch for ch in out if ch.isdigit())
        if sid:
            _kwin_call("org.kde.kwin.Script.run", obj=f"/Scripting/Script{sid}")
        return bool(sid)
    except (OSError, subprocess.TimeoutExpired):
        return False


def kwin_window_cmd(win_id, action):
    """action: focus | minimize | close"""
    body = {
        "focus": "if (w.minimized) w.minimized=false; workspace.activeWindow=w;",
        "minimize": "w.minimized=true;",
        "close": "w.closeWindow();",
    }[action]
    name = "mac-dock-cmd"
    kwin_eval('const id="%s"; for (const w of workspace.windowList()) '
              'if (String(w.internalId)===id) { %s break; }' % (win_id, body), name)
    GLib.timeout_add(800, lambda: (_kwin_call("org.kde.kwin.Scripting.unloadScript", name), False)[1])


FEED_JS = r"""
const SVC="%(svc)s", PATH="%(path)s", IFACE="%(iface)s";
function snap() {
  const out = [];
  for (const w of workspace.windowList()) {
    if (!w.normalWindow || w.skipTaskbar) continue;
    out.push({id: String(w.internalId), app: String(w.desktopFileName || ""),
              cls: String(w.resourceClass || ""), title: String(w.caption || ""),
              active: w === workspace.activeWindow, min: !!w.minimized, pid: w.pid, att: !!w.demandsAttention});
  }
  callDBus(SVC, PATH, IFACE, "Update", JSON.stringify(out));
}
function hook(w) {
  if (w.captionChanged) w.captionChanged.connect(snap);
  if (w.minimizedChanged) w.minimizedChanged.connect(snap);
  if (w.demandsAttentionChanged) w.demandsAttentionChanged.connect(snap);
}
for (const w of workspace.windowList()) hook(w);
workspace.windowAdded.connect(function(w) { hook(w); snap(); });
workspace.windowRemoved.connect(snap);
workspace.windowActivated.connect(snap);
snap();
"""


class KWinFeed:
    """Recebe do KWin (script + D-Bus) a lista de janelas abertas, em tempo real."""
    OBJ_PATH = "/io/github/fabio/MacDock/Windows"
    IFACE = "io.github.fabio.MacDock.Windows"
    XML = ("<node><interface name='%s'><method name='Update'>"
           "<arg type='s' name='json' direction='in'/></method></interface></node>" % IFACE)
    NAME = "mac-dock-feed"

    def __init__(self, app, on_change):
        self.app, self.on_change = app, on_change
        self.ok = False

    def start(self):
        conn = self.app.get_dbus_connection()
        if conn is None:
            return
        info = Gio.DBusNodeInfo.new_for_xml(self.XML)
        try:
            conn.register_object(self.OBJ_PATH, info.interfaces[0], self._on_call, None, None)
        except GLib.Error as e:
            print("feed D-Bus:", e, file=sys.stderr)
            return
        js = FEED_JS % {"svc": APP_ID, "path": self.OBJ_PATH, "iface": self.IFACE}
        self.ok = kwin_eval(js, self.NAME)

    def _on_call(self, _conn, _sender, _path, _iface, method, params, invocation):
        if method == "Update":
            try:
                wins = json.loads(params.unpack()[0])
            except (ValueError, IndexError):
                wins = []
            wins = [w for w in wins
                    if APP_ID.lower() not in (w.get("app", "").lower(), w.get("cls", "").lower())]
            self.ok = True
            self.on_change(wins)
        invocation.return_value(None)

    def stop(self):
        try:
            _kwin_call("org.kde.kwin.Scripting.unloadScript", self.NAME)
        except (OSError, subprocess.TimeoutExpired):
            pass


# ---------------------------------------------------------------- itens

class Item:
    """kind: launcher | app | sep | trash"""

    def __init__(self, kind, key, info=None, pinned=False, name=None):
        self.kind, self.key, self.info, self.pinned = kind, key, info, pinned
        self.name = name or (info.get_display_name() if info else key)
        self.paintable = None
        self.color = None            # cor dominante do ícone (r, g, b)
        self.windows = []
        self.proc_running = False
        self.bounce_start = None
        self.badge = 0
        self.progress = None         # 0..1 (Unity LauncherEntry) ou None
        self.count = 0
        self.music = False           # está tocando mídia (MPRIS)
        self.pulse = 0.0
        self.scale = 1.0             # ampliação atual (mola)
        self.vel = 0.0
        self.x = self.w = 0.0
        self.off = 0.0               # deslocamento animado ao reordenar
        self.match_keys = self._match_keys()
        self.exe = self._exe_name()

    @property
    def running(self):
        return bool(self.windows) or self.proc_running

    @property
    def active(self):
        return any(w.get("active") for w in self.windows)

    @property
    def attention(self):
        return any(w.get("att") for w in self.windows)

    @property
    def desktop_id(self):
        return self.info.get_id() if self.info else None

    def _exe_name(self):
        if self.info is None:
            return ""
        cmd = self.info.get_commandline() or ""
        try:
            parts = shlex.split(cmd)
        except ValueError:
            parts = cmd.split()
        parts = [p for p in parts if "=" not in p.split("/")[0] and p != "env"]
        return os.path.basename(parts[0]) if parts else ""

    def _match_keys(self):
        keys = set()
        if self.info is not None:
            keys.add((self.info.get_id() or "").removesuffix(".desktop").lower())
            wm = self.info.get_startup_wm_class()
            if wm:
                keys.add(wm.lower())
        elif self.kind == "app":
            keys.add(self.key.lower())
        keys.discard("")
        return keys

    def matches(self, win):
        return bool(self.match_keys) and (
            win.get("app", "").removesuffix(".desktop").lower() in self.match_keys
            or win.get("cls", "").lower() in self.match_keys)


def find_app_info(win):
    """Procura o .desktop de uma janela que não está fixada."""
    app = win.get("app", "").removesuffix(".desktop")
    cls = win.get("cls", "")
    for cand in (app, app.lower(), cls, cls.lower()):
        if cand:
            info = desktop_info(cand + ".desktop")
            if info:
                return info
    want = {app.lower(), cls.lower()} - {""}
    for info in Gio.AppInfo.get_all():
        wm = info.get_startup_wm_class() if hasattr(info, "get_startup_wm_class") else None
        if wm and wm.lower() in want:
            return info
    return None


def keys_match(keys, item):
    """True se algum dos nomes (app/desktop-entry/player) corresponde ao item do dock."""
    names = set(item.match_keys) | {item.name.lower()}
    for k in keys:
        if not k:
            continue
        if k in names:
            return True
        if len(k) >= 4 and any(len(n) >= 4 and (k in n or n in k) for n in names):
            return True
    return False


def dominant_color(texture):
    """Cor dominante (ponderada por saturação) de uma textura pequena."""
    w, h = texture.get_width(), texture.get_height()
    stride = w * 4
    buf = bytearray(stride * h)
    texture.download(buf, stride)
    sr = sg = sb = tw = 0.0
    for i in range(0, len(buf), 4):
        b, g, r, a = buf[i], buf[i + 1], buf[i + 2], buf[i + 3]
        if a < 160:
            continue
        r, g, b = min(255, r * 255 // a), min(255, g * 255 // a), min(255, b * 255 // a)
        mx, mn = max(r, g, b), min(r, g, b)
        sat = (mx - mn) / (mx or 1)
        wgt = sat * sat * (mx / 255) + 0.02
        sr, sg, sb, tw = sr + r * wgt, sg + g * wgt, sb + b * wgt, tw + wgt
    if tw <= 0:
        return (0.6, 0.65, 0.8)
    r, g, b = sr / tw / 255, sg / tw / 255, sb / tw / 255
    mx = max(r, g, b) or 1
    return tuple(min(1.0, v / mx * 0.95 + 0.03) for v in (r, g, b))


# ---------------------------------------------------------------- widget

class DockView(Gtk.Widget):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.items = []
        self.windows = []
        self.feed_ok = False
        self.mouse_x = None
        self.smooth_x = 0.0
        self.act = 0.0              # 0 = repouso, 1 = ampliado
        self.hover = -1
        self.hide_t = 0.0           # 0 = visível, 1 = escondido (autohide)
        self.last_active = time.monotonic()
        self.menu_open = False
        self.drag = None            # estado do arrastar
        self.press = None
        self.trash_full = False
        self._launcher_setting = None
        self._launcher_tex = None
        self._sync_key = None
        self.pending = []            # uma entrada (conjunto de nomes) por notificação não lida
        self.playing_keys = frozenset()
        self.entries = {}            # key do app -> {'progress', 'count'} (Unity LauncherEntry)
        self.kde_dark = None         # preferência de cor do KDE (True = escuro)
        self.kde_accent = None
        self.drop_hover = False
        self._last_region = None
        self._last_frame = None
        self.on_settings = self.on_launcher = self.on_pinned = None
        self.on_mode_menu = None
        self.on_resized = None
        self.glass = self.spacer = None
        self._glass_key = None
        self._glass_css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self._glass_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.sync_items()
        self.set_size_request(*self.window_size())
        self.set_hexpand(False)
        self.set_vexpand(False)

        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)
        drag = Gtk.GestureDrag()
        drag.set_button(1)
        drag.connect("drag-begin", self._drag_begin)
        drag.connect("drag-update", self._drag_update)
        drag.connect("drag-end", self._drag_end)
        self.add_controller(drag)
        right = Gtk.GestureClick()
        right.set_button(3)
        right.connect("pressed", self._on_right)
        self.add_controller(right)
        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("motion", self._drop_motion)
        drop.connect("leave", self._drop_leave)
        drop.connect("drop", self._drop_files)
        self.add_controller(drop)

        self.add_tick_callback(self._tick)
        GLib.timeout_add(1500, self._poll_running)
        GLib.timeout_add(5000, self._poll_trash)
        self._poll_trash()

    # ---------- itens ----------
    def _struct_key(self):
        """O que muda a estrutura do dock (comparado com uma cópia, não com o mesmo dict)."""
        c = self.cfg
        return (tuple(c["pinned"]), c["show_launcher"], c["show_running"], c["show_trash"])

    def sync_items(self):
        """Monta a lista: [lançador] fixados | abertos | [lixeira], reaproveitando os itens."""
        c = self.cfg
        self._sync_key = self._struct_key()
        old = {(it.kind, it.key): it for it in self.items}

        def get(kind, key, **kw):
            return old.get((kind, key)) or Item(kind, key, **kw)

        new = []
        if c["show_launcher"]:
            new.append(get("launcher", "launcher", name="Aplicativos"))
        pinned_items = []
        for did in c["pinned"]:
            info = desktop_info(did)
            if info is None:
                continue
            it = get("app", did, info=info, pinned=True)
            it.pinned = True
            it.windows = []
            pinned_items.append(it)
        new += pinned_items

        extra = {}
        for win in self.windows:
            for it in pinned_items:
                if it.matches(win):
                    it.windows.append(win)
                    break
            else:
                k = (win.get("app") or win.get("cls") or "?").lower()
                extra.setdefault(k, []).append(win)
        running = []
        if c["show_running"]:
            for k, wins in extra.items():
                it = old.get(("app", "run:" + k))
                if it is None:
                    info = find_app_info(wins[0])
                    it = Item("app", "run:" + k, info=info, pinned=False,
                              name=info.get_display_name() if info else (wins[0].get("cls") or k))
                    it.match_keys = {k, wins[0].get("cls", "").lower()} - {""}
                it.pinned = False
                it.windows = wins
                running.append(it)
        if running:
            new.append(get("sep", "sep1"))
            new += running
        if c["show_trash"]:
            new.append(get("sep", "sep2"))
            new.append(get("trash", "trash", name="Lixeira"))
        for it in new:
            if it.windows and it.bounce_start:
                it.bounce_start = None
        self.items = new
        if self.get_realized():
            self._load_icons()
        self._last_region = None
        self.apply_badges()
        self.fit_size()

    def fit_size(self):
        """Mantém view, espaçador e janela do tamanho calculado (a largura muda
        quando apps abrem/fecham; sem isso a janela fica cortada e o menu desalinha)."""
        size = self.window_size()
        if size == getattr(self, "_fit_size", None):
            return
        self._fit_size = size
        self.set_size_request(*size)
        if self.spacer:
            self.spacer.set_size_request(*size)
        if self.on_resized:
            self.on_resized(*size)

    # ---------- notificações e música ----------
    def notify(self, app, entry, replaces_id):
        """Uma notificação nova de `app`. Só o nome do app é guardado, nunca o texto."""
        if replaces_id or app.lower() in ("linux-island", "mac-dock"):
            return                       # atualização de uma notificação já contada
        self.pending.append({n for n in (app.lower(), (entry or "").lower()) if n})
        del self.pending[:-200]
        self.apply_badges()

    def apply_badges(self):
        on = self.cfg["badges"]
        for it in self.items:
            if it.kind != "app":
                it.badge = 0
                continue
            mine = [p for p in self.pending if keys_match(p, it)]
            if it.active and mine:       # o app está em foco: considera lidas
                self.pending = [p for p in self.pending if p not in mine]
                mine = []
            it.badge = min(len(mine), 99) if on else 0
            it.progress, it.count = None, 0
            if self.cfg["progress"]:
                for key, st in self.entries.items():
                    if keys_match({key}, it):
                        it.progress, it.count = st.get("progress"), st.get("count", 0)
                        break
                it.badge = max(it.badge, min(it.count, 99))

    def set_entry(self, key, props):
        """Atualização do protocolo com.canonical.Unity.LauncherEntry (progresso e contador)."""
        st = {}
        if props.get("progress-visible") and isinstance(props.get("progress"), (int, float)):
            st["progress"] = max(0.0, min(1.0, float(props["progress"])))
        if props.get("count-visible") and isinstance(props.get("count"), int):
            st["count"] = max(0, props["count"])
        if st:
            self.entries[key] = st
        else:
            self.entries.pop(key, None)
        self.apply_badges()

    def set_kde(self, dark, accent):
        self.kde_dark, self.kde_accent = dark, accent
        self.queue_draw()

    def set_playing(self, keys):
        self.playing_keys = keys

    def set_windows(self, wins):
        self.windows = wins
        self.feed_ok = True
        if not self.drag:
            self.sync_items()
            self.queue_resize()
        else:
            self.apply_badges()

    def apply_config(self, cfg):
        if self._launcher_setting is not None and cfg["launcher_icon"] != self._launcher_setting:
            for it in self.items:
                if it.kind == "launcher":
                    it.paintable, it.color = None, None
        self.cfg = cfg
        if self._struct_key() != self._sync_key:
            self.sync_items()
        self._fit_size = self.window_size()
        self.set_size_request(*self._fit_size)
        if self.spacer:
            self.spacer.set_size_request(*self._fit_size)
        self._glass_key = None
        self._last_region = None
        self.apply_badges()
        self.queue_resize()
        self.queue_draw()

    def pop_in(self):
        """Animação de troca de modo: os ícones 'brotam' com a mola."""
        for it in self.items:
            if it.kind != "sep":
                it.scale, it.vel = 0.3, 0.0

    def theme(self):
        c = self.cfg
        name = c["theme"]
        if c["theme_follow"] == "kde" and self.kde_dark is not None:
            name = c["theme_dark"] if self.kde_dark else c["theme_light"]
        th = THEMES.get(name, THEMES["escuro"])
        if c["accent_auto"] and self.kde_accent:
            th = dict(th, dot=(*self.kde_accent, 0.95), border=(*self.kde_accent, 0.38))
        return th

    def _load_icons(self):
        theme = Gtk.IconTheme.get_for_display(self.get_display())
        for it in self.items:
            if it.kind == "sep" or it.paintable is not None:
                continue
            if it.kind == "launcher":
                if self._launcher_setting != self.cfg["launcher_icon"]:
                    self._launcher_setting = self.cfg["launcher_icon"]
                    self._launcher_tex = load_launcher_texture(self._launcher_setting)
                it.paintable = self._launcher_tex
                it.color = (0.62, 0.30, 0.95) if self._launcher_tex else (0.45, 0.5, 0.9)
                continue
            if it.kind == "trash":
                icon = Gio.ThemedIcon.new("user-trash-full" if self.trash_full else "user-trash")
            else:
                icon = it.info.get_icon() if it.info else None
                if icon is None:
                    icon = Gio.ThemedIcon.new("application-x-executable")
            it.paintable = theme.lookup_by_gicon(
                icon, 128, self.get_scale_factor(), Gtk.TextDirection.NONE, 0)
            it.color = None

    def _ensure_colors(self):
        """Calcula a cor dominante dos ícones que ainda não têm (uma vez cada)."""
        native = self.get_native()
        renderer = native.get_renderer() if native else None
        if renderer is None:
            return
        for it in self.items:
            if it.color is not None or it.paintable is None:
                continue
            it.color = (0.6, 0.65, 0.8)
            if it.kind == "launcher":
                it.color = (0.62, 0.30, 0.95)
                continue
            try:
                sn = Gtk.Snapshot()
                it.paintable.snapshot(sn, 24, 24)
                node = sn.to_node()
                if node:
                    it.color = dominant_color(renderer.render_texture(node, rect(0, 0, 24, 24)))
            except (TypeError, GLib.Error):
                pass

    # ---------- geometria ----------
    def rest_w(self, it):
        return SEP_W if it.kind == "sep" else self.cfg["icon_size"]

    def _rest_total(self):
        n = len(self.items)
        return sum(self.rest_w(it) for it in self.items) + max(n - 1, 0) * self.cfg["gap"]

    def window_size(self):
        c = self.cfg
        base, M = c["icon_size"], c["max_scale"]
        extra = base * (M - 1) * 2.6
        w = self._rest_total() + 2 * c["padding"] + extra + 60
        h = base * M * 1.12 + 2 * c["padding"] + 60 + c["margin_bottom"]
        return int(w), int(h)

    def _rest_centers(self):
        W, _ = self.window_size()
        x = (W - self._rest_total()) / 2
        out = []
        for it in self.items:
            w = self.rest_w(it)
            out.append(x + w / 2)
            x += w + self.cfg["gap"]
        return out

    def _layout(self):
        """Posiciona os itens a partir das escalas atuais; devolve a largura total."""
        W, _ = self.window_size()
        for it in self.items:
            it.w = self.rest_w(it) * (1.0 if it.kind == "sep" else it.scale)
        total = sum(it.w for it in self.items) + max(len(self.items) - 1, 0) * self.cfg["gap"]
        x = (W - total) / 2
        for it in self.items:
            it.x = x
            x += it.w + self.cfg["gap"]
        return total

    def _hit(self, mx):
        for i, it in enumerate(self.items):
            if it.x - self.cfg["gap"] / 2 <= mx <= it.x + it.w + self.cfg["gap"] / 2:
                return i
        return -1

    # ---------- mouse ----------
    def _on_motion(self, _c, x, _y):
        if self.mouse_x is None:
            self.smooth_x = x
        self.mouse_x = x

    def _on_leave(self, _c):
        if not self.drag:
            self.mouse_x = None

    def _drag_begin(self, _g, x, y):
        i = self._hit(x)
        self.press = {"idx": i, "x": x, "y": y} if i >= 0 else None
        self.drag = None

    def _drag_update(self, _g, dx, dy):
        if not self.press:
            return
        it = self.items[self.press["idx"]]
        if self.drag is None:
            if not (it.kind == "app" and it.pinned) or math.hypot(dx, dy) < 10:
                return
            self.drag = {"item": it, "grab": self.press["x"] - it.x, "remove": False}
        px, py = self.press["x"] + dx, self.press["y"] + dy
        self.drag.update(x=px, y=py, remove=dy < -90)
        self.mouse_x = px
        self._reorder_drag(px)

    def _reorder_drag(self, px):
        it = self.drag["item"]
        before = {id(i): i.x for i in self.items}
        others = [i for i in self.items if i.kind == "app" and i.pinned and i is not it]
        pos = sum(1 for i in others if px > i.x + i.w / 2)
        self.items.remove(it)
        idx = [k for k, i in enumerate(self.items) if i.kind == "app" and i.pinned]
        if idx:
            at = idx[pos] if pos < len(idx) else idx[-1] + 1
        else:
            at = len(self.items)
        self.items.insert(at, it)
        self._layout()
        for i in self.items:
            if i is not it:
                i.off += before.get(id(i), i.x) - i.x

    def _drag_end(self, _g, dx, dy):
        press, drag = self.press, self.drag
        self.press = self.drag = None
        if press is None:
            return
        if drag is None:
            if abs(dx) < 10 and abs(dy) < 10:
                self.activate(self.items[press["idx"]])
            return
        new = [i.info.get_id() for i in self.items
               if i.kind == "app" and i.pinned and not (i is drag["item"] and drag["remove"])]
        self.mouse_x = None
        if self.on_pinned:
            self.on_pinned(new)

    # ---------- ações ----------
    def activate(self, it):
        if it.kind == "launcher":
            if self.on_launcher:
                self.on_launcher()
        elif it.kind == "trash":
            self._open_trash()
        elif it.kind == "app":
            self.pending = [p for p in self.pending if not keys_match(p, it)]
            it.badge = 0
            if it.windows:
                self.focus_item(it)
            elif it.info is not None and not it.running:
                self.launch(it)

    def launch(self, it, action=None):
        ctx = self.get_display().get_app_launch_context()
        try:
            if action:
                it.info.launch_action(action, ctx)
            else:
                it.info.launch([], ctx)
        except GLib.Error as e:
            print("falha ao abrir", it.name, e, file=sys.stderr)
            return
        if not it.windows:
            it.bounce_start = time.monotonic()

    def focus_item(self, it):
        wins = it.windows
        active = [w for w in wins if w.get("active")]
        if active and len(wins) == 1:
            kwin_window_cmd(active[0]["id"], "minimize")      # clicar no ativo minimiza
            return
        nxt = next((w for w in wins if not w.get("active")), wins[0])
        kwin_window_cmd(nxt["id"], "focus")

    def _open_trash(self):
        try:
            Gio.AppInfo.launch_default_for_uri("trash:///", None)
        except GLib.Error:
            pass

    def _poll_trash(self):
        try:
            info = Gio.File.new_for_uri("trash:///").query_info(
                "trash::item-count", Gio.FileQueryInfoFlags.NONE, None)
            full = info.get_attribute_uint32("trash::item-count") > 0
        except GLib.Error:
            full = False
        if full != self.trash_full:
            self.trash_full = full
            for it in self.items:
                if it.kind == "trash":
                    it.paintable = None
            if self.get_realized():
                self._load_icons()
        return True

    def _poll_running(self):
        """Plano B quando o feed do KWin não está disponível: procura pelo nome do processo."""
        if self.feed_ok:
            for it in self.items:
                it.proc_running = False
            return True
        names = set()
        for pid in os.listdir("/proc"):
            if pid.isdigit():
                try:
                    with open(f"/proc/{pid}/comm") as f:
                        names.add(f.read().strip())
                except OSError:
                    pass
        for it in self.items:
            exe = it.exe
            it.proc_running = bool(exe) and any(
                n == exe or (len(exe) > 15 and exe.startswith(n)) for n in names)
            if it.running:
                it.bounce_start = None
        return True

    # ---------- soltar arquivos ----------
    def _drop_target(self, x):
        i = self._hit(x)
        it = self.items[i] if i >= 0 else None
        if it and ((it.kind == "app" and it.info) or it.kind == "trash"):
            return it
        return None

    def _drop_motion(self, _t, x, _y):
        if not self.cfg["file_drop"]:
            return 0
        self.mouse_x = x
        self.drop_hover = True
        return Gdk.DragAction.COPY if self._drop_target(x) else 0

    def _drop_leave(self, _t):
        self.drop_hover = False
        self.mouse_x = None

    def _drop_files(self, _t, value, x, _y):
        self.drop_hover = False
        it = self._drop_target(x)
        files = value.get_files() if value else []
        if not (self.cfg["file_drop"] and it and files):
            return False
        if it.kind == "trash":
            for f in files:
                try:
                    f.trash(None)
                except GLib.Error as e:
                    print("lixeira:", e.message, file=sys.stderr)
            self._poll_trash()
        else:
            try:
                it.info.launch(files, None)
                if not it.running:
                    it.bounce_start = time.monotonic()
            except GLib.Error as e:
                print("abrir arquivo:", e.message, file=sys.stderr)
        return True

    # ---------- menu do botão direito ----------
    def _on_right(self, _g, _n, x, _y):
        i = self._hit(x)
        it = self.items[i] if i >= 0 and self.items[i].kind != "sep" else None
        group = Gio.SimpleActionGroup()
        menu = Gio.Menu()
        counter = [0]

        def add(section, label, cb):
            counter[0] += 1
            name = f"a{counter[0]}"
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", lambda *_a: cb())
            group.add_action(act)
            section.append(label, f"dock.{name}")

        if it and it.kind == "app":
            actions = Gio.Menu()
            if it.info:
                add(actions, "Abrir nova janela" if it.windows else "Abrir", lambda: self.launch(it))
                for a in it.info.list_actions():
                    add(actions, it.info.get_action_name(a), lambda a=a: self.launch(it, a))
            if actions.get_n_items():
                menu.append_section(it.name, actions)
            if it.windows:
                wsec = Gio.Menu()
                for w in it.windows[:8]:
                    add(wsec, (w.get("title") or it.name)[:48],
                        lambda w=w: kwin_window_cmd(w["id"], "focus"))
                menu.append_section("Janelas", wsec)
                csec = Gio.Menu()
                add(csec, "Fechar todas as janelas",
                    lambda: [kwin_window_cmd(w["id"], "close") for w in it.windows])
                menu.append_section(None, csec)
            if self.cfg["big_menu"] and it.windows:
                msec = Gio.Menu()
                add(msec, "Minimizar todas as janelas",
                    lambda: [kwin_window_cmd(w["id"], "minimize") for w in it.windows])
                menu.append_section(None, msec)
            psec = Gio.Menu()
            if self.cfg["big_menu"] and it.pinned and len(self.cfg["pinned"]) > 1:
                add(psec, "Mover para o começo", lambda: self._move_pinned(it, 0))
                add(psec, "Mover para o fim", lambda: self._move_pinned(it, -1))
            if it.pinned:
                add(psec, "Remover do dock", lambda: self._unpin(it))
            elif it.info:
                add(psec, "Manter no dock", lambda: self._pin(it))
            menu.append_section(None, psec)
        elif it and it.kind == "trash":
            tsec = Gio.Menu()
            add(tsec, "Abrir lixeira", self._open_trash)
            add(tsec, "Esvaziar lixeira", lambda: subprocess.Popen(["gio", "trash", "--empty"]))
            menu.append_section(None, tsec)
        if self.on_mode_menu:
            self.on_mode_menu(menu, add)
        ssec = Gio.Menu()
        add(ssec, "Ajustes do dock…", lambda: self.on_settings and self.on_settings())
        menu.append_section(None, ssec)

        pop = Gtk.PopoverMenu.new_from_model(menu)
        self.insert_action_group("dock", group)
        pop.set_parent(self)
        pop.set_position(Gtk.PositionType.TOP)
        pop.set_has_arrow(False)
        H = self.get_height() or self.window_size()[1]
        c = self.cfg
        cx = (it.x + it.w / 2) if it else x
        target = Gdk.Rectangle()          # (os argumentos do construtor são ignorados)
        target.x = int(cx)
        target.y = int(H - c["margin_bottom"] - c["icon_size"] - 2 * c["padding"] - 6)
        target.width = target.height = 1
        pop.set_pointing_to(target)
        self.menu_open = True
        pop.connect("closed", self._menu_closed)
        pop.popup()

    def _menu_closed(self, pop):
        self.menu_open = False
        GLib.idle_add(pop.unparent)

    def _pin(self, it):
        if self.on_pinned and it.desktop_id:
            self.on_pinned(list(self.cfg["pinned"]) + [it.desktop_id])

    def _move_pinned(self, it, where):
        lst = [d for d in self.cfg["pinned"] if d != it.desktop_id]
        lst.insert(0 if where == 0 else len(lst), it.desktop_id)
        if self.on_pinned:
            self.on_pinned(lst)

    def _unpin(self, it):
        if self.on_pinned:
            self.on_pinned([d for d in self.cfg["pinned"] if d != it.desktop_id])

    # ---------- animação ----------
    def _tick(self, _w, clock):
        now_us = clock.get_frame_time()
        dt = 1 / 60 if self._last_frame is None else (now_us - self._last_frame) / 1e6
        self._last_frame = now_us
        dt = max(0.004, min(dt, 0.05))
        c = self.cfg
        now = time.monotonic()
        active = self.mouse_x is not None or self.menu_open or self.drag is not None
        if active:
            self.last_active = now
        hide = c["autohide"] and not active and now - self.last_active > 0.6
        goal = 1.0 if hide else 0.0
        self.hide_t += (goal - self.hide_t) * 0.18
        if abs(goal - self.hide_t) < 0.003:
            self.hide_t = goal

        target = 1.0 if self.mouse_x is not None else 0.0
        self.act += (target - self.act) * 0.22
        if abs(target - self.act) < 0.002:
            self.act = target
        if self.mouse_x is not None:
            self.smooth_x += (self.mouse_x - self.smooth_x) * 0.35

        self._step_springs(dt)
        for it in self.items:
            it.music = (c["music_pulse"] and it.kind == "app" and bool(self.playing_keys)
                        and keys_match(self.playing_keys, it))
            if it.bounce_start and now - it.bounce_start > c["bounce_seconds"]:
                it.bounce_start = None
            it.off *= 0.72
            if abs(it.off) < 0.2:
                it.off = 0.0
        self._layout()
        self.hover = self._hit(self.mouse_x) if self.mouse_x is not None else -1
        self._ensure_colors()
        self._update_input_region()
        self._update_glass()
        self.queue_draw()
        return GLib.SOURCE_CONTINUE

    def _step_springs(self, dt):
        c = self.cfg
        M, sigma = c["max_scale"], c["spread"]
        for it, cx in zip(self.items, self._rest_centers()):
            if it.kind == "sep":
                continue
            d = (cx - self.smooth_x) / sigma
            target = 1 + (M - 1) * self.act * math.exp(-d * d)
            if self.drag and self.drag["item"] is it:
                target = max(target, 1.15)
            if c["spring"]:
                for _ in range(2):
                    acc = SPRING_K * (target - it.scale) - SPRING_C * it.vel
                    it.vel += acc * dt / 2
                    it.scale += it.vel * dt / 2
                it.scale = max(0.85, it.scale)
            else:
                it.scale, it.vel = target, 0.0

    def _update_input_region(self):
        """Fora do dock os cliques passam para as janelas de baixo."""
        if cairo is None:
            return
        native = self.get_native()
        surface = native.get_surface() if native else None
        if surface is None:
            return
        c = self.cfg
        W, H = self.window_size()
        total = self._layout()
        pill_h = c["icon_size"] + 2 * c["padding"] + c["margin_bottom"]
        hovering = self.act > 0.01 or self.drag is not None
        rest = self._rest_total()
        if self.drag:                       # arrastando: região grande, para puxar p/ cima
            x0, w, h = 0, W, H
        elif c["autohide"] and self.hide_t > 0.5 and not hovering:
            x0, w, h = int((W - rest) / 2 - c["padding"] - 60), int(rest + 2 * c["padding"] + 120), 3
        elif hovering or self.menu_open:
            x0, w = int((W - total) / 2 - 20), int(total + 40)
            y0 = H - c["max_scale"] * c["icon_size"] * 1.12 - 2 * c["padding"] - 30
            h = H - int(y0)
        else:
            x0, w = int((W - rest) / 2 - c["padding"]), int(rest + 2 * c["padding"])
            h = int(pill_h)
        key = (x0, w, h)
        if key == self._last_region:
            return
        self._last_region = key
        surface.set_input_region(cairo.Region(cairo.RectangleInt(x0, H - h, w, h)))

    def _update_glass(self):
        """A caixa 'glass' acompanha o dock; o GTK pede o blur ao KWin por ela (CSS)."""
        if self.glass is None:
            return
        c = self.cfg
        total = self._layout()
        w = int(round(total + 2 * c["padding"]))
        h = int(c["icon_size"] + 2 * c["padding"])
        off = int(round(self.hide_t * (h + c["margin_bottom"] + 6)))
        key = (w, h, c["radius"], bool(c["blur"]), off)
        if key == self._glass_key:
            return
        if not self._glass_key or self._glass_key[2] != c["radius"]:
            self._glass_css.load_from_string(
                ".glass { background: rgba(0,0,0,0.01); border-radius: %dpx; "
                "backdrop-filter: blur(24px); }" % c["radius"])
        self._glass_key = key
        self.glass.set_size_request(w, h)
        self.glass.set_margin_top(self.window_size()[1] - c["margin_bottom"] - h + off)
        self.glass.set_visible(bool(c["blur"]) and self.hide_t < 0.97)

    # ---------- desenho ----------
    def do_snapshot(self, snapshot):
        c = self.cfg
        W, H = self.window_size()
        total = self._layout()
        pad, base, mb = c["padding"], c["icon_size"], c["margin_bottom"]
        pill_w, pill_h = total + 2 * pad, base + 2 * pad
        px, py = (W - pill_w) / 2, H - mb - pill_h
        th = self.theme()
        snapshot.save()
        snapshot.translate(Graphene.Point().init(0, self.hide_t * (pill_h + mb + 6)))

        bgr, bgg, bgb, bga = th["bg"]
        bga = min(1.0, bga * c["bg_intensity"])
        rr = Gsk.RoundedRect()
        rr.init_from_rect(rect(px, py, pill_w, pill_h), c["radius"])
        snapshot.push_rounded_clip(rr)
        snapshot.append_color(rgba(bgr, bgg, bgb, bga), rect(px, py, pill_w, pill_h))
        snapshot.pop()
        snapshot.append_border(rr, [1, 1, 1, 1], [rgba(*th["border"])] * 4)

        now = time.monotonic()
        base_y = H - mb - pad
        dragged = self.drag["item"] if self.drag else None
        order = [i for i in self.items if i is not dragged] + ([dragged] if dragged else [])
        for it in order:
            x, size = it.x + it.off, it.w
            if it.kind == "sep":
                snapshot.append_color(rgba(*th["border"]),
                                      rect(x + size / 2 - 0.5, base_y - base * 0.8, 1, base * 0.8))
                continue
            y = base_y - size
            if it.bounce_start:
                y -= abs(math.sin(math.pi * (now - it.bounce_start) / 0.5)) * base * 0.55
            if it.pulse > 0.01:
                y -= it.pulse * base * 0.08
            if it is dragged:
                x = self.drag["x"] - self.drag["grab"]
                y = self.drag["y"] - size / 2 - 6
            self._draw_glow(snapshot, it, x, base_y, size)
            snapshot.push_opacity(0.55 if it is dragged and self.drag["remove"] else 1.0)
            if it.kind == "launcher" and it.paintable is None:
                self._draw_launcher_icon(snapshot, x, y, size)
            elif it.paintable:
                snapshot.save()
                snapshot.translate(Graphene.Point().init(x, y))
                it.paintable.snapshot(snapshot, size, size)
                snapshot.restore()
            snapshot.pop()
            if c["reflection"] and it.paintable and it is not dragged:
                self._draw_reflection(snapshot, it, x, base_y, size, pad + mb)
            if it.running and c["show_dots"] and it.kind == "app" and it is not dragged:
                self._draw_dots(snapshot, it, x, size, H - mb - 8, th, now)
            if it.progress is not None and it is not dragged:
                self._draw_progress(snapshot, x, y, size, it.progress)
            if it.music and it is not dragged:
                self._draw_equalizer(snapshot, x, y, size, now)
            if it.badge:
                self._draw_badge(snapshot, x + size - 6, y + 2, it.badge)

        if self.drag and self.drag["remove"]:
            self._draw_label(snapshot, self.drag["x"], self.drag["y"] - base - 14, "Remover do dock", th)
        elif c["show_labels"] and self.hover >= 0 and self.act > 0.3 and not self.drag:
            it = self.items[self.hover]
            if it.kind != "sep":
                self._draw_label(snapshot, it.x + it.w / 2, base_y - it.w - 14, it.name, th)
        snapshot.restore()

    def _draw_dots(self, snapshot, it, x, size, y, th, now):
        c = self.cfg
        d = 6 if it.active else 5
        col = rgba(*th["dot"])
        if c["glow"] and it.color:
            col = rgba(*it.color, 0.95)
        n = 1
        if c["rich_dots"]:
            n = max(1, min(len(it.windows), 3))
            if it.attention:
                col = rgba(1.0, 0.62, 0.12, 0.55 + 0.45 * abs(math.sin(now * 4)))
        step = d + 3
        x0 = x + size / 2 - (n * d + (n - 1) * 3) / 2
        for k in range(n):
            snapshot.append_color(col, rect(x0 + k * step, y, d, d))

    def _draw_progress(self, snapshot, x, y, size, frac):
        w, h = size * 0.76, max(4.0, size * 0.09)
        bx, by = x + size * 0.12, y + size * 0.80
        rr = Gsk.RoundedRect()
        rr.init_from_rect(rect(bx, by, w, h), h / 2)
        snapshot.push_rounded_clip(rr)
        snapshot.append_color(rgba(0, 0, 0, 0.60), rect(bx, by, w, h))
        snapshot.append_color(rgba(0.35, 0.65, 1.0, 1), rect(bx, by, w * frac, h))
        snapshot.pop()

    def _draw_reflection(self, snapshot, it, x, base_y, size, room):
        rh = min(size * 0.40, room)
        if rh < 4:
            return
        area = rect(x, base_y + 1, size, rh)
        snapshot.push_clip(area)
        snapshot.push_mask(Gsk.MaskMode.ALPHA)
        snapshot.append_linear_gradient(
            area, Graphene.Point().init(x, base_y), Graphene.Point().init(x, base_y + rh),
            [stop(0.0, rgba(1, 1, 1, 0.30)), stop(1.0, rgba(1, 1, 1, 0.0))])
        snapshot.pop()
        snapshot.save()
        snapshot.translate(Graphene.Point().init(x, base_y + 1))
        snapshot.scale(1, -1)
        snapshot.translate(Graphene.Point().init(0, -size))
        it.paintable.snapshot(snapshot, size, size)
        snapshot.restore()
        snapshot.pop()   # máscara
        snapshot.pop()   # clip

    def _draw_glow(self, snapshot, it, x, base_y, size):
        c = self.cfg
        if not c["glow"] or it.color is None or it.kind == "sep":
            return
        k = (it.scale - 1) / max(c["max_scale"] - 1, 0.01)
        a = max(0.0, min(1.0, k)) * 0.55 + (0.10 if it.active else 0.0)
        if it.music:
            a = max(a, 0.22 + 0.14 * math.sin(time.monotonic() * 5.0))
        if a < 0.02:
            return
        cx, cy = x + size / 2, base_y - size * 0.35
        hr, vr = size * 0.95, size * 0.8
        snapshot.append_radial_gradient(
            rect(cx - hr, cy - vr, hr * 2, vr * 2), Graphene.Point().init(cx, cy), hr, vr, 0.0, 1.0,
            [stop(0.0, rgba(*it.color, a)), stop(1.0, rgba(*it.color, 0.0))])

    def _draw_equalizer(self, snapshot, x, y, size, now):
        bw, gap = max(2.0, size * 0.055), max(1.5, size * 0.035)
        w, h = 3 * bw + 2 * gap + size * 0.14, size * 0.26
        bx, by = x + size * 0.04, y + size * 0.04
        rr = Gsk.RoundedRect()
        rr.init_from_rect(rect(bx, by, w, h), h * 0.3)
        snapshot.push_rounded_clip(rr)
        snapshot.append_color(rgba(0, 0, 0, 0.55), rect(bx, by, w, h))
        snapshot.pop()
        for i in range(3):
            bh = (h - size * 0.08) * (0.30 + 0.70 * abs(math.sin(now * (4.2 + i * 1.9) + i * 1.3)))
            snapshot.append_color(rgba(1, 1, 1, 0.92),
                                  rect(bx + size * 0.07 + i * (bw + gap), by + h - size * 0.04 - bh, bw, bh))

    def _draw_badge(self, snapshot, cx, cy, n):
        layout = self.create_pango_layout(str(n) if n < 100 else "99+")
        layout.set_font_description(Pango.FontDescription("Noto Sans Bold 9"))
        tw, th_ = layout.get_pixel_size()
        w, h = max(tw + 10, 18), 18
        rr = Gsk.RoundedRect()
        rr.init_from_rect(rect(cx - w / 2, cy - h / 2, w, h), h / 2)
        snapshot.push_rounded_clip(rr)
        snapshot.append_color(rgba(0.95, 0.22, 0.25, 1), rect(cx - w / 2, cy - h / 2, w, h))
        snapshot.pop()
        snapshot.save()
        snapshot.translate(Graphene.Point().init(cx - tw / 2, cy - th_ / 2))
        snapshot.append_layout(layout, rgba(1, 1, 1, 1))
        snapshot.restore()

    def _draw_label(self, snapshot, cx, bottom, text, th):
        layout = self.create_pango_layout(text)
        layout.set_font_description(Pango.FontDescription("Noto Sans 11"))
        text_w, text_h = layout.get_pixel_size()
        lw, lh = text_w + 22, text_h + 12
        lx, ly = cx - lw / 2, bottom - lh
        lr = Gsk.RoundedRect()
        lr.init_from_rect(rect(lx, ly, lw, lh), lh / 2)
        snapshot.push_rounded_clip(lr)
        snapshot.append_color(rgba(*th["label_bg"]), rect(lx, ly, lw, lh))
        snapshot.pop()
        snapshot.save()
        snapshot.translate(Graphene.Point().init(lx + 11, ly + 6))
        snapshot.append_layout(layout, rgba(*th["label_fg"]))
        snapshot.restore()

    def _draw_launcher_icon(self, snapshot, x, y, size):
        rr = Gsk.RoundedRect()
        rr.init_from_rect(rect(x, y, size, size), size * 0.225)
        snapshot.push_rounded_clip(rr)
        snapshot.append_color(rgba(0.20, 0.22, 0.30, 1), rect(x, y, size, size))
        snapshot.append_color(rgba(1, 1, 1, 0.10), rect(x, y, size, size / 2))
        snapshot.pop()
        cell, gap = size * 0.18, size * 0.09
        x0 = x + (size - (3 * cell + 2 * gap)) / 2
        y0 = y + (size - (3 * cell + 2 * gap)) / 2
        colors = [(1, .42, .42), (1, .72, .3), (.98, .9, .35), (.45, .85, .5),
                  (.35, .75, .95), (.55, .55, 1), (.85, .5, .95), (1, .55, .75), (.9, .9, .95)]
        for n, col in enumerate(colors):
            cx, cy = x0 + (n % 3) * (cell + gap), y0 + (n // 3) * (cell + gap)
            dr = Gsk.RoundedRect()
            dr.init_from_rect(rect(cx, cy, cell, cell), cell / 2)
            snapshot.push_rounded_clip(dr)
            snapshot.append_color(rgba(*col, 1), rect(cx, cy, cell, cell))
            snapshot.pop()

    def do_realize(self):
        Gtk.Widget.do_realize(self)
        self._load_icons()


# ---------------------------------------------------------------- janela / app

CSS = b"window.mac-dock, window.mac-dock > * { background: transparent; }"


def find_monitor(connector):
    mons = Gdk.Display.get_default().get_monitors()
    for i in range(mons.get_n_items()):
        m = mons.get_item(i)
        if connector and m.get_connector() == connector:
            return m
    return None


def place_window(win, cfg):
    """Posição no layer-shell: borda, espaço reservado e monitor."""
    LayerShell.set_margin(win, LayerShell.Edge.BOTTOM, 0)   # a margem é desenhada por dentro
    zone = cfg["icon_size"] + 2 * cfg["padding"] + cfg["margin_bottom"]
    LayerShell.set_exclusive_zone(
        win, zone if cfg["reserve_space"] and not cfg["autohide"] else 0)
    LayerShell.set_monitor(win, find_monitor(cfg.get("monitor")))


def make_window(app, cfg, layer=True):
    win = Gtk.ApplicationWindow(application=app)
    win.add_css_class("mac-dock")
    win.set_decorated(False)
    view = DockView(cfg)
    overlay = Gtk.Overlay()
    view.spacer = Gtk.Box()
    view.spacer.set_size_request(*view.window_size())
    overlay.set_child(view.spacer)
    view.glass = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.START)
    view.glass.add_css_class("glass")
    overlay.add_overlay(view.glass)
    overlay.add_overlay(view)
    win.set_child(overlay)
    prov = Gtk.CssProvider()
    prov.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    if layer and LayerShell and LayerShell.is_supported():
        LayerShell.init_for_window(win)
        LayerShell.set_namespace(win, "mac-dock")
        LayerShell.set_layer(win, LayerShell.Layer.TOP)
        LayerShell.set_anchor(win, LayerShell.Edge.BOTTOM, True)
        LayerShell.set_keyboard_mode(win, LayerShell.KeyboardMode.NONE)
        place_window(win, cfg)
    return win, view


class DockApp(Adw.Application):
    windows = []        # última lista de janelas vinda do KWin

    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.cfg = load_config()
        self.win = self.view = self.settings_win = self.launcher_win = None
        self.feed = None
        self.notify_watcher = self.mpris = self.entries = self.appearance = None
        self._save_id = 0
        self._auto_from = None       # modo anterior, quando a troca foi automática
        self._trig_keys = {}
        self.connect("activate", self._on_activate)
        self.connect("shutdown", self._on_shutdown)

    def _wire(self):
        v = self.view
        v.on_settings = self.open_settings
        v.on_launcher = self.toggle_launcher
        v.on_pinned = lambda lst: self.change(pinned=lst)
        v.on_mode_menu = self._mode_menu
        v.on_resized = lambda w, h: self.win and self.win.set_default_size(w, h)
        if DockApp.windows:
            v.set_windows(DockApp.windows)

    def _on_activate(self, _app):
        if self.win is not None:           # 2ª execução: abre os ajustes
            self.open_settings()
            return
        self.win, self.view = make_window(self, self.cfg)
        self.feed = KWinFeed(self, self._on_windows)
        self._wire()
        self.win.present()
        self.feed.start()
        from watchers import MprisWatcher, NotifyWatcher
        self.notify_watcher = NotifyWatcher(
            lambda app, entry, rid: self.view and self.view.notify(app, entry, rid))
        self.mpris = MprisWatcher(lambda keys: self.view and self.view.set_playing(keys))
        from watchers import AppearanceWatcher, LauncherEntryWatcher
        self.entries = LauncherEntryWatcher(
            lambda key, props: self.view and self.view.set_entry(key, props))
        self.appearance = AppearanceWatcher(
            lambda dark, accent: self.view and self.view.set_kde(dark, accent))

    def _on_windows(self, wins):
        DockApp.windows = wins
        if self.view:
            self.view.set_windows(wins)
        self._auto_mode(wins)

    # ---------- modos ----------
    def mode_entry(self, name=None):
        name = name or self.cfg["mode"]
        return next((m for m in self.cfg["modes"] if m["name"] == name), self.cfg["modes"][0])

    def set_mode(self, name, auto=False):
        c = self.cfg
        if name == c["mode"] or name not in [m["name"] for m in c["modes"]]:
            return
        self.mode_entry()["pinned"] = list(c["pinned"])
        if not auto:
            self._auto_from = None
        self.change(mode=name, pinned=list(self.mode_entry(name)["pinned"]))
        self.view.pop_in()
        if self.settings_win is not None:
            self.settings_win.refresh_modes()

    def _mode_menu(self, menu, add):
        modes = self.cfg["modes"]
        if len(modes) < 2:
            return
        sub = Gio.Menu()
        for m in modes:
            mark = "✓  " if m["name"] == self.cfg["mode"] else "     "
            add(sub, mark + m["name"], lambda n=m["name"]: self.set_mode(n))
        menu.append_submenu("Modo: " + self.cfg["mode"], sub)

    def _trigger_match(self, triggers, win):
        names = {win.get("app", "").removesuffix(".desktop").lower(), win.get("cls", "").lower()}
        names.discard("")
        for did in triggers:
            keys = self._trig_keys.get(did)
            if keys is None:
                keys = {did.removesuffix(".desktop").lower()}
                info = desktop_info(did)
                if info and info.get_startup_wm_class():
                    keys.add(info.get_startup_wm_class().lower())
                self._trig_keys[did] = keys
            if names & keys:
                return True
        return False

    def _auto_mode(self, wins):
        """Entra no modo cujo app gatilho ficou ativo; volta quando ele fecha."""
        c = self.cfg
        if not c["auto_modes"] or len(c["modes"]) < 2 or self.drag_busy():
            return
        cur = self.mode_entry()
        if (self._auto_from and cur["triggers"]
                and not any(self._trigger_match(cur["triggers"], w) for w in wins)):
            back, self._auto_from = self._auto_from, None
            self.set_mode(back, auto=True)
            return
        active = next((w for w in wins if w.get("active")), None)
        if not active or (cur["triggers"] and self._trigger_match(cur["triggers"], active)):
            return
        for m in c["modes"]:
            if m["name"] != c["mode"] and m["triggers"] and self._trigger_match(m["triggers"], active):
                prev = c["mode"]
                self.set_mode(m["name"], auto=True)
                self._auto_from = self._auto_from or prev
                return

    def drag_busy(self):
        return bool(self.view and self.view.drag)

    def reset_config(self):
        new = ensure_modes(copy.deepcopy(DEFAULTS))
        self._auto_from = None
        self.change(**new)
        self.view.pop_in()

    def _on_shutdown(self, _app):
        if self.feed:
            self.feed.stop()

    def toggle_launcher(self):
        from launcher import LauncherWindow
        if self.launcher_win is not None:
            self.launcher_win.close()
            return
        self.launcher_win = LauncherWindow(self)
        self.launcher_win.connect("close-request", self._launcher_closed)
        self.launcher_win.present()

    def _launcher_closed(self, _w):
        self.launcher_win = None
        return False

    def open_settings(self):
        from settings import SettingsWindow
        if self.settings_win is None:
            self.settings_win = SettingsWindow(self)
            self.settings_win.connect("close-request", self._settings_closed)
        self.settings_win.present()

    def _settings_closed(self, _w):
        self.settings_win = None
        return False

    def change(self, **kw):
        """Muda opções, aplica ao vivo e salva (com pequena espera)."""
        old_monitor = self.cfg.get("monitor")
        if "pinned" in kw and "mode" not in kw:       # editar os fixados edita o modo ativo
            self.mode_entry()["pinned"] = list(kw["pinned"])
        self.cfg.update(kw)
        self._trig_keys.clear()
        self.view.apply_config(self.cfg)
        w, h = self.view.window_size()
        self.win.set_default_size(w, h)
        if LayerShell and LayerShell.is_supported():
            if self.cfg.get("monitor") != old_monitor:
                self._recreate_window()
            else:
                place_window(self.win, self.cfg)
        if self._save_id:
            GLib.source_remove(self._save_id)
        self._save_id = GLib.timeout_add(400, self._save)

    def _recreate_window(self):
        """Trocar de monitor: cria a janela nova na tela certa e fecha a antiga."""
        old = self.win
        self.win, self.view = make_window(self, self.cfg)
        self._wire()
        if self.mpris:
            self.view.set_playing(self.mpris._last or frozenset())
        self.win.present()
        old.close()

    def _save(self):
        self._save_id = 0
        try:
            save_config(self.cfg)
        except OSError as e:
            print("falha ao salvar config:", e, file=sys.stderr)
        return False


def run_png(path):
    """Modo de teste: janela comum, simula o mouse e salva um PNG."""
    cfg = load_config()
    app = Gtk.Application(application_id="io.github.fabio.MacDockTest")

    def on_activate(app):
        win, view = make_window(app, cfg, layer=False)
        win.present()

        def snap():
            n = len(view.items)
            view.mouse_x = view.smooth_x = view._rest_centers()[min(2, n - 1)] + 10
            view.act = 1.0
            for _ in range(40):
                view._step_springs(1 / 60)
            GLib.timeout_add(300, shot)
            return False

        def shot():
            w, h = view.window_size()
            view.hover = min(2, len(view.items) - 1)
            view._ensure_colors()
            sn = Gtk.Snapshot()
            view._layout()
            view.do_snapshot(sn)
            node = sn.to_node()
            tex = win.get_native().get_renderer().render_texture(node, rect(0, 0, w, h))
            tex.save_to_png(path)
            print("salvo", path)
            app.quit()
            return False

        GLib.timeout_add(600, snap)

    app.connect("activate", on_activate)
    app.run([])


def main():
    if "--png" in sys.argv:
        run_png(sys.argv[sys.argv.index("--png") + 1])
        return
    DockApp().run([sys.argv[0]])


if __name__ == "__main__":
    main()
