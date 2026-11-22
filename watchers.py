"""Observadores do barramento de sessão para o dock (mesmo padrão da linux-island).

NotifyWatcher: conta notificações novas por app. Só guarda de qual app veio; o texto
               delas nunca é lido nem salvo (pode ser privado).
MprisWatcher:  descobre quais players de mídia (Spotify, navegadores, mpv…) tocam agora.
"""
from gi.repository import Gio, GLib

NOTIFY_RULE = "type='method_call',interface='org.freedesktop.Notifications',member='Notify'"
MPRIS_PREFIX = "org.mpris.MediaPlayer2."
MPRIS_PATH = "/org/mpris/MediaPlayer2"


class NotifyWatcher:
    """Chama on_notify(app_name, desktop_entry, replaces_id) na thread da UI."""

    def __init__(self, on_notify):
        self.on_notify = on_notify
        self.conn = None
        try:
            addr = Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None)
            flags = (Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
                     | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION)
            self.conn = Gio.DBusConnection.new_for_address_sync(addr, flags, None, None)
            self.conn.add_filter(self._filter)
            self.conn.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus",
                                "org.freedesktop.DBus.Monitoring", "BecomeMonitor",
                                GLib.Variant("(asu)", ([NOTIFY_RULE], 0)), None,
                                Gio.DBusCallFlags.NONE, 3000, None)
        except GLib.Error as e:
            print(f"[mac-dock] não deu para observar notificações: {e.message}")
            self.conn = None

    def _filter(self, _conn, msg, incoming):
        # roda numa thread do GDBus: extrai só o necessário e passa para a UI
        if not incoming or msg.get_message_type() != Gio.DBusMessageType.METHOD_CALL:
            return msg
        if msg.get_member() == "Notify" and msg.get_body() is not None:
            try:
                app, rid, _icon, _summary, _body, _actions, hints, _t = msg.get_body().unpack()
                entry = hints.get("desktop-entry") if isinstance(hints, dict) else None
                GLib.idle_add(self._deliver, app or "", entry if isinstance(entry, str) else "", rid)
            except (ValueError, TypeError):
                pass
        return None   # monitores não podem responder: consome a chamada

    def _deliver(self, app, entry, rid):
        self.on_notify(app, entry, rid)
        return False


class MprisWatcher:
    """Chama on_change(frozenset de nomes em minúsculas) quando muda quem está tocando."""

    def __init__(self, on_change):
        self.on_change = on_change
        self.conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.players = {}        # bus name -> {"playing": bool, "keys": set}
        self._last = None
        GLib.timeout_add(2000, self._poll)
        self._poll()

    def _poll(self):
        self.conn.call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                       "ListNames", None, GLib.VariantType("(as)"), Gio.DBusCallFlags.NONE,
                       1000, None, self._names)
        return True

    def _names(self, conn, res):
        try:
            names = [n for n in conn.call_finish(res).unpack()[0] if n.startswith(MPRIS_PREFIX)]
        except GLib.Error:
            return
        for gone in set(self.players) - set(names):
            del self.players[gone]
        for n in names:
            short = n[len(MPRIS_PREFIX):].split(".instance")[0].lower()
            st = self.players.setdefault(n, {"playing": False, "keys": {short}})
            self._get(n, "org.mpris.MediaPlayer2.Player", "PlaybackStatus", self._status)
            if len(st["keys"]) == 1:
                self._get(n, "org.mpris.MediaPlayer2", "DesktopEntry", self._entry)
        self._emit()

    def _get(self, name, iface, prop, cb):
        self.conn.call(name, MPRIS_PATH, "org.freedesktop.DBus.Properties", "Get",
                       GLib.Variant("(ss)", (iface, prop)), GLib.VariantType("(v)"),
                       Gio.DBusCallFlags.NONE, 1000, None, cb, name)

    def _status(self, conn, res, name):
        try:
            value = conn.call_finish(res).unpack()[0]
        except GLib.Error:
            return
        if name in self.players:
            self.players[name]["playing"] = (value == "Playing")
            self._emit()

    def _entry(self, conn, res, name):
        try:
            value = conn.call_finish(res).unpack()[0]
        except GLib.Error:
            return
        if name in self.players and value:
            self.players[name]["keys"].add(str(value).removesuffix(".desktop").lower())
            self._emit()

    def _emit(self):
        keys = set()
        for st in self.players.values():
            if st["playing"]:
                keys |= st["keys"]
        keys = frozenset(keys)
        if keys != self._last:
            self._last = keys
            self.on_change(keys)
