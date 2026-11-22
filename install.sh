#!/usr/bin/env bash
# Instala o mac-dock para o usuário atual: confere as dependências e liga o início
# automático com a sessão. Uso:  ./install.sh [--dry-run] [--uninstall]
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/mac-dock.desktop"
DRY=0; UNINSTALL=0
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --uninstall) UNINSTALL=1 ;;
    -h|--help) sed -n '2,3p' "$0"; exit 0 ;;
    *) echo "opção desconhecida: $a" >&2; exit 2 ;;
  esac
done

run() { if [ "$DRY" = 1 ]; then echo "[simulação] $*"; else "$@"; fi; }

if [ "$UNINSTALL" = 1 ]; then
  run rm -f "$DESKTOP"
  echo "Início automático removido. (Seus ajustes em ~/.config/mac-dock continuam lá.)"
  exit 0
fi

ok() { printf '  %-34s ok\n' "$1"; }
falta() { printf '  %-34s FALTA  (%s)\n' "$1" "$2"; MISSING=1; }
MISSING=0
echo "Conferindo dependências..."
command -v python3 >/dev/null && ok "python3" || falta "python3" "instale o python"
python3 - <<'PY' 2>/dev/null && ok "PyGObject, GTK 4, libadwaita" || falta "PyGObject, GTK 4, libadwaita" "pacman -S python-gobject gtk4 libadwaita"
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw
PY
python3 -c 'import gi; gi.require_version("Gtk4LayerShell","1.0")' 2>/dev/null \
  && ok "gtk4-layer-shell" || falta "gtk4-layer-shell" "pacman -S gtk4-layer-shell"
command -v gdbus >/dev/null && ok "gdbus (fala com o KWin)" || falta "gdbus" "pacman -S glib2"
[ "${XDG_CURRENT_DESKTOP:-}" = "KDE" ] && ok "KDE Plasma" \
  || echo "  aviso: não detectei o KDE (XDG_CURRENT_DESKTOP=${XDG_CURRENT_DESKTOP:-vazio}); o dock é feito para o Plasma/Wayland."

if [ "$MISSING" = 1 ]; then
  echo "Instale o que falta e rode de novo." >&2
  [ "$DRY" = 1 ] || exit 1
fi

run mkdir -p "$(dirname "$DESKTOP")"
if [ "$DRY" = 1 ]; then
  echo "[simulação] escreveria $DESKTOP apontando para $DIR/dock.py"
else
  cat > "$DESKTOP" <<DESK
[Desktop Entry]
Type=Application
Name=mac-dock
Comment=Dock estilo macOS para o KDE Plasma
Exec=/usr/bin/python3 $DIR/dock.py
X-GNOME-Autostart-enabled=true
DESK
fi
echo "Pronto. O dock inicia sozinho na próxima sessão. Para testar agora:  python3 $DIR/dock.py"
