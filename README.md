# mac-dock

Dock estilo macOS para **KDE Plasma (Wayland)**, em Python + GTK4 + layer-shell.

- Ampliação dos ícones com física de mola e bounce ao abrir apps
- Apps abertos detectados via script do KWin, com indicador
- Menu do botão direito (ações do app, janelas, fixar/remover), arrastar para reordenar, lixeira
- Esconder automático, vidro com blur do KWin, temas Escuro, Claro, Vidro (estilo Apple), Grafite e Meia-noite
- Lançador de apps em tela cheia (estilo Launchpad)
- Janela de ajustes (libadwaita); configuração em `~/.config/mac-dock/config.json`

## Requisitos

Python 3, GTK 4, libadwaita, PyGObject, [gtk4-layer-shell](https://github.com/wmww/gtk4-layer-shell), KDE Plasma 6 em Wayland.

No Arch/CachyOS: `sudo pacman -S gtk4 libadwaita python-gobject gtk4-layer-shell`

## Uso

```
python3 dock.py          # roda o dock (rodar de novo abre os ajustes)
python3 dock.py --png X  # renderiza uma imagem de teste e sai
```

Para iniciar com a sessão, copie um `.desktop` com `Exec=python3 /caminho/para/dock.py` para `~/.config/autostart/`.

O botão de menu usa `assets/launcher.png` se existir; sem ele, mostra uma grade. Use `launcher_icon` nos ajustes para escolher outra imagem.

## Licença

[MIT](LICENSE): use, modifique e distribua à vontade.
