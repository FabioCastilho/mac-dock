"""Janela de ajustes do mac-dock (libadwaita). Tudo aplica ao vivo e é salvo."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, Gtk  # noqa: E402

from dock import DEFAULTS, THEMES, desktop_info  # noqa: E402
from illustrations import make_area  # noqa: E402


def _spin(row_title, subtitle, lo, hi, step, value, digits, on_change):
    row = Adw.SpinRow.new_with_range(lo, hi, step)
    row.set_title(row_title)
    row.set_subtitle(subtitle)
    row.set_digits(digits)
    row.set_value(value)
    row.connect("notify::value", lambda r, _p: on_change(r.get_value()))
    return row


def _switch(title, subtitle, active, on_change):
    row = Adw.SwitchRow(title=title, subtitle=subtitle, active=active)
    row.connect("notify::active", lambda r, _p: on_change(r.get_active()))
    return row


def _art_row(name):
    """Linha só com o esboço do recurso (ocupa o topo do grupo)."""
    row = Adw.PreferencesRow()
    row.set_activatable(False)
    row.set_focusable(False)
    row.set_child(make_area(name))
    return row


def _installed_apps():
    return sorted((a for a in Gio.AppInfo.get_all() if a.should_show()),
                  key=lambda a: a.get_display_name().lower())


class AppListEditor:
    """Lista editável de apps (.desktop) dentro de um Adw.PreferencesGroup."""

    def __init__(self, group, get_list, set_list, reorder=True, add_title="Adicionar app"):
        self.group, self.get_list, self.set_list = group, get_list, set_list
        self.reorder, self.add_title = reorder, add_title
        self._rows = []
        self._avail = []
        self.rebuild()

    def rebuild(self):
        for r in self._rows:
            self.group.remove(r)
        self._rows = []
        lst = list(self.get_list())
        for i, did in enumerate(lst):
            info = desktop_info(did)
            row = Adw.ActionRow(title=info.get_display_name() if info else did,
                                subtitle="" if info else "não encontrado")
            if info and info.get_icon():
                img = Gtk.Image.new_from_gicon(info.get_icon())
                img.set_pixel_size(32)
                row.add_prefix(img)
            if self.reorder:
                for icon, delta, tip in (("go-up-symbolic", -1, "Subir"),
                                         ("go-down-symbolic", 1, "Descer")):
                    b = Gtk.Button(icon_name=icon, valign=Gtk.Align.CENTER, tooltip_text=tip)
                    b.add_css_class("flat")
                    b.set_sensitive(0 <= i + delta < len(lst))
                    b.connect("clicked", self._move, i, delta)
                    row.add_suffix(b)
            rm = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER,
                            tooltip_text="Remover")
            rm.add_css_class("flat")
            rm.connect("clicked", self._remove, i)
            row.add_suffix(rm)
            self.group.add(row)
            self._rows.append(row)
        self._rows.append(self._add_row())

    def _add_row(self):
        self._avail = _installed_apps()
        row = Adw.ComboRow(title=self.add_title, subtitle="Escolha na lista e clique em +")
        row.set_model(Gtk.StringList.new([a.get_display_name() for a in self._avail]))
        row.set_enable_search(True)
        row.set_expression(Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
        btn = Gtk.Button(icon_name="list-add-symbolic", valign=Gtk.Align.CENTER,
                         tooltip_text="Adicionar")
        btn.add_css_class("suggested-action")
        btn.connect("clicked", self._add, row)
        row.add_suffix(btn)
        self.group.add(row)
        return row

    def _commit(self, lst):
        self.set_list(lst)
        self.rebuild()

    def _move(self, _b, i, delta):
        lst = list(self.get_list())
        lst[i], lst[i + delta] = lst[i + delta], lst[i]
        self._commit(lst)

    def _remove(self, _b, i):
        lst = list(self.get_list())
        del lst[i]
        self._commit(lst)

    def _add(self, _b, row):
        did = self._avail[row.get_selected()].get_id()
        lst = list(self.get_list())
        if did not in lst:
            lst.append(did)
            self._commit(lst)


class SettingsWindow(Adw.PreferencesWindow):
    def __init__(self, app):
        super().__init__(title="Ajustes do Dock")
        self.app = app
        self.set_default_size(560, 720)
        self.set_search_enabled(False)
        feat = Adw.PreferencesPage(title="Recursos", icon_name="starred-symbolic")
        self.add(feat)
        for grp in self._features():
            feat.add(grp)
        page = Adw.PreferencesPage(title="Ajustes", icon_name="preferences-system-symbolic")
        self.add(page)
        page.add(self._appearance())
        page.add(self._screen())
        page.add(self._icons())
        page.add(self._behavior())
        self._updating = False
        page.add(self._modes_group())
        self.apps_group = Adw.PreferencesGroup(
            title="Apps do dock (modo atual)",
            description="Ordem, adição e remoção dos apps fixos do modo ativo.")
        page.add(self.apps_group)
        self.apps_editor = AppListEditor(
            self.apps_group, lambda: self.cfg["pinned"],
            lambda lst: self.app.change(pinned=lst))
        self.trig_group = Adw.PreferencesGroup(
            title="Gatilhos do modo atual",
            description="Quando um destes apps ficar ativo, o dock troca para este modo "
                        "sozinho (e volta quando eles fecharem).")
        page.add(self.trig_group)
        self.trig_editor = AppListEditor(
            self.trig_group, lambda: self.app.mode_entry()["triggers"], self._set_triggers,
            reorder=False, add_title="Adicionar gatilho")
        page.add(self._reset_group())

    @property
    def cfg(self):
        return self.app.cfg

    # ---------- modos ----------
    def _modes_group(self):
        g = Adw.PreferencesGroup(
            title="Modos",
            description="Conjuntos de apps do dock (Jogos, Dev…). Troque pelo botão direito "
                        "no dock ou deixe a troca automática cuidar disso.")
        g.add(_switch("Troca automática", "Muda de modo quando um app gatilho fica ativo",
                      self.cfg["auto_modes"], lambda v: self.app.change(auto_modes=v)))
        self.mode_combo = Adw.ComboRow(title="Modo atual")
        self.mode_combo.connect("notify::selected", self._on_mode_selected)
        g.add(self.mode_combo)
        self.name_row = Adw.EntryRow(title="Nome do modo")
        self.name_row.set_show_apply_button(True)
        self.name_row.connect("apply", self._rename_mode)
        g.add(self.name_row)
        row = Adw.ActionRow(title="Gerenciar modos")
        new = Gtk.Button(label="Novo (copia o atual)", valign=Gtk.Align.CENTER)
        new.connect("clicked", self._new_mode)
        self.del_btn = Gtk.Button(label="Excluir este", valign=Gtk.Align.CENTER)
        self.del_btn.add_css_class("destructive-action")
        self.del_btn.connect("clicked", self._delete_mode)
        row.add_suffix(self.del_btn)
        row.add_suffix(new)
        g.add(row)
        self._fill_mode_widgets()
        return g

    def _fill_mode_widgets(self):
        self._updating = True
        names = [m["name"] for m in self.cfg["modes"]]
        self.mode_combo.set_model(Gtk.StringList.new(names))
        self.mode_combo.set_selected(names.index(self.cfg["mode"]))
        self.name_row.set_text(self.cfg["mode"])
        self.del_btn.set_sensitive(len(names) > 1)
        self._updating = False

    def refresh_modes(self):
        """Chamado quando o modo muda por fora (menu do dock ou troca automática)."""
        self._fill_mode_widgets()
        self.apps_editor.rebuild()
        self.trig_editor.rebuild()

    def _on_mode_selected(self, row, _p):
        if self._updating:
            return
        names = [m["name"] for m in self.cfg["modes"]]
        sel = row.get_selected()
        if 0 <= sel < len(names):
            self.app.set_mode(names[sel])

    def _rename_mode(self, row):
        new = row.get_text().strip()
        old = self.cfg["mode"]
        if not new or new == old or new in [m["name"] for m in self.cfg["modes"]]:
            row.set_text(old)
            return
        self.app.mode_entry()["name"] = new
        self.app.change(mode=new, modes=self.cfg["modes"])
        self._fill_mode_widgets()

    def _new_mode(self, _b):
        names = {m["name"] for m in self.cfg["modes"]}
        n = 1
        while f"Novo modo {n}" in names:
            n += 1
        cur = self.app.mode_entry()
        self.cfg["modes"].append({"name": f"Novo modo {n}", "pinned": list(self.cfg["pinned"]),
                                  "triggers": []})
        self.app.change(modes=self.cfg["modes"])
        self.app.set_mode(f"Novo modo {n}")

    def _delete_mode(self, _b):
        modes = self.cfg["modes"]
        if len(modes) < 2:
            return
        cur = self.app.mode_entry()
        modes.remove(cur)
        first = modes[0]
        self.app.change(modes=modes, mode=first["name"], pinned=list(first["pinned"]))
        self.app.view.pop_in()
        self.refresh_modes()

    def _set_triggers(self, lst):
        self.app.mode_entry()["triggers"] = list(lst)
        self.app.change(modes=self.cfg["modes"])

    # ---------- recursos (com ilustração) ----------
    def _feature(self, art, title, desc, key=None, soon=False, extra=()):
        """Grupo com esboço do recurso, texto do que ele faz e a chave de liga/desliga."""
        g = Adw.PreferencesGroup(title=title, description=desc)
        g.add(_art_row(art))
        if key:
            row = _switch("Ativar", "", self.cfg[key], lambda v, k=key: self.app.change(**{k: v}))
        else:
            row = Adw.ActionRow(title="Ativar")
        if soon:
            row.set_subtitle("Em desenvolvimento")
            row.set_sensitive(False)
        g.add(row)
        for r in extra:
            g.add(r)
        return g

    def _features(self):
        out = [
            self._feature("progresso", "Progresso e contadores",
                          "Downloads e tarefas de apps como o Brave e a Steam mostram uma barra no "
                          "ícone, e o número de itens pendentes vira um contador.", key="progress"),
            self._feature("indicador", "Indicador de janelas",
                          "O pontinho embaixo do ícone mostra quantas janelas o app tem (até 3) e "
                          "fica laranja e pulsando quando o app pede atenção.", key="rich_dots"),
            self._feature("reflexo", "Reflexo dos ícones",
                          "Um reflexo suave embaixo de cada ícone, como no macOS clássico.",
                          key="reflection"),
            self._feature("arrastar", "Arrastar arquivos para os ícones",
                          "Solte um arquivo sobre um app para abri-lo com ele, ou sobre a lixeira "
                          "para movê-lo para ela.", key="file_drop"),
            self._feature("contexto", "Menu de contexto maior",
                          "O botão direito ganha ações extras: minimizar todas as janelas e mover "
                          "o app para o começo ou o fim do dock.", key="big_menu"),
            self._theme_feature(),
            self._feature("preview", "Pré-visualização de janelas",
                          "Passar o mouse sobre um app aberto mostra miniaturas das janelas.",
                          soon=True),
            self._feature("esconder", "Esconder inteligente",
                          "O dock só recolhe quando uma janela estiver tapando.", soon=True),
            self._feature("posicao", "Posição do dock",
                          "Esquerda, direita ou topo, além de embaixo.", soon=True),
            self._feature("multimon", "Multi-monitor",
                          "Um dock por monitor, com os apps de cada tela.", soon=True),
            self._feature("traducoes", "Idioma", "Interface em inglês e espanhol.", soon=True),
            self._installer_feature(),
        ]
        return out

    def _theme_feature(self):
        keys = list(THEMES)
        names = [THEMES[k]["nome"] for k in keys]

        def combo(title, sub, cfg_key):
            r = Adw.ComboRow(title=title, subtitle=sub)
            r.set_model(Gtk.StringList.new(names))
            cur = self.cfg[cfg_key]
            r.set_selected(keys.index(cur) if cur in keys else 0)
            r.connect("notify::selected",
                      lambda row, _p: self.app.change(**{cfg_key: keys[row.get_selected()]}))
            return r

        follow = _switch("Seguir o claro/escuro do KDE", "Troca entre os dois temas abaixo sozinho",
                         self.cfg["theme_follow"] == "kde",
                         lambda v: self.app.change(theme_follow="kde" if v else "off"))
        accent = _switch("Usar a cor de destaque do KDE", "Pinta o indicador e a borda com ela",
                         self.cfg["accent_auto"], lambda v: self.app.change(accent_auto=v))
        return self._feature(
            "temas", "Temas e cor automática",
            "Mais temas prontos e a opção de acompanhar o modo claro/escuro e a cor de destaque "
            "do KDE.", extra=(follow, combo("Tema no modo claro", "Usado quando o KDE está claro",
                                            "theme_light"),
                              combo("Tema no modo escuro", "Usado quando o KDE está escuro",
                                    "theme_dark"), accent))

    def _installer_feature(self):
        copy = Gtk.Button(label="Copiar comando", valign=Gtk.Align.CENTER)
        row = Adw.ActionRow(title="Instalar no sistema",
                            subtitle="Na pasta do projeto, rode ./install.sh: ele confere as "
                                     "dependências e liga o início automático com a sessão.")
        row.add_suffix(copy)
        copy.connect("clicked", lambda _b: self.get_clipboard().set("./install.sh"))
        g = Adw.PreferencesGroup(title="Instalador")
        g.add(_art_row("instalador"))
        g.add(row)
        return g

    # ---------- grupos ----------
    def _appearance(self):
        g = Adw.PreferencesGroup(title="Aparência")
        keys = list(THEMES)
        combo = Adw.ComboRow(title="Tema", subtitle="Cores do fundo, borda e rótulo")
        combo.set_model(Gtk.StringList.new([THEMES[k]["nome"] for k in keys]))
        cur = self.cfg["theme"]
        combo.set_selected(keys.index(cur) if cur in keys else 0)
        combo.connect("notify::selected",
                      lambda r, _p: self.app.change(theme=keys[r.get_selected()]))
        g.add(combo)
        g.add(_spin("Intensidade do fundo", "Quanto o fundo do dock é opaco (1 = padrão do tema)",
                    0.2, 2.5, 0.1, self.cfg["bg_intensity"], 1,
                    lambda v: self.app.change(bg_intensity=round(v, 2))))
        g.add(_spin("Arredondamento", "Raio dos cantos, em pixels", 0, 40, 1,
                    self.cfg["radius"], 0, lambda v: self.app.change(radius=int(v))))
        g.add(_switch("Desfoque do fundo (blur)", "O KWin desfoca o que está atrás do dock",
                      self.cfg["blur"], lambda v: self.app.change(blur=v)))
        g.add(_switch("Botão de menu iniciar", "Ícone de grade no começo do dock que abre o lançador",
                      self.cfg["show_launcher"], lambda v: self.app.change(show_launcher=v)))
        g.add(_switch("Contador de notificações", "Bolinha vermelha com o número de notificações do app",
                      self.cfg["badges"], lambda v: self.app.change(badges=v)))
        g.add(_switch("Animação de música", "O ícone do app que toca música pulsa e mostra um equalizador",
                      self.cfg["music_pulse"], lambda v: self.app.change(music_pulse=v)))
        g.add(_switch("Brilho na cor do ícone", "Luz suave sob o ícone, na cor dominante dele",
                      self.cfg["glow"], lambda v: self.app.change(glow=v)))
        g.add(_switch("Ampliação com mola", "O ícone oscila de leve ao crescer e voltar",
                      self.cfg["spring"], lambda v: self.app.change(spring=v)))
        g.add(_switch("Mostrar apps abertos", "Apps abertos que não estão fixados aparecem no dock",
                      self.cfg["show_running"], lambda v: self.app.change(show_running=v)))
        g.add(_switch("Lixeira", "Ícone da lixeira no fim do dock",
                      self.cfg["show_trash"], lambda v: self.app.change(show_trash=v)))
        g.add(self._launcher_icon_row())
        g.add(_switch("Mostrar nome do app", "Rótulo acima do ícone sob o mouse",
                      self.cfg["show_labels"], lambda v: self.app.change(show_labels=v)))
        g.add(_switch("Indicador de app aberto", "Pontinho embaixo do ícone",
                      self.cfg["show_dots"], lambda v: self.app.change(show_dots=v)))
        return g

    def _screen(self):
        g = Adw.PreferencesGroup(title="Tela")
        mons = Gdk.Display.get_default().get_monitors()
        conns, labels = [""], ["Automático (o sistema escolhe)"]
        for i in range(mons.get_n_items()):
            m = mons.get_item(i)
            g_ = m.get_geometry()
            conns.append(m.get_connector())
            labels.append(f"{m.get_connector()} — {g_.width}×{g_.height}")
        combo = Adw.ComboRow(title="Monitor", subtitle="Em qual tela o dock aparece")
        combo.set_model(Gtk.StringList.new(labels))
        cur = self.cfg.get("monitor") or ""
        combo.set_selected(conns.index(cur) if cur in conns else 0)
        combo.connect("notify::selected",
                      lambda r, _p: self.app.change(monitor=conns[r.get_selected()]))
        g.add(combo)
        g.add(_switch("Esconder automaticamente", "O dock some quando o mouse sai; encoste o mouse "
                      "na borda de baixo para ele voltar", self.cfg["autohide"],
                      lambda v: self.app.change(autohide=v)))
        g.add(_switch("Reservar espaço", "Janelas maximizadas ficam acima do dock, sem cobri-lo",
                      self.cfg["reserve_space"], lambda v: self.app.change(reserve_space=v)))
        g.add(_spin("Distância da borda", "Espaço entre o dock e a parte de baixo da tela (px)",
                    0, 200, 1, self.cfg["margin_bottom"], 0,
                    lambda v: self.app.change(margin_bottom=int(v))))
        return g

    def _icons(self):
        g = Adw.PreferencesGroup(title="Ícones e ampliação")
        g.add(_spin("Tamanho dos ícones", "Em repouso, em pixels", 32, 96, 2,
                    self.cfg["icon_size"], 0, lambda v: self.app.change(icon_size=int(v))))
        g.add(_spin("Ampliação máxima", "Quanto o ícone sob o mouse cresce (1 = sem zoom)",
                    1.0, 3.0, 0.05, self.cfg["max_scale"], 2,
                    lambda v: self.app.change(max_scale=round(v, 2))))
        g.add(_spin("Alcance da ampliação", "Quantos ícones vizinhos crescem junto (px)",
                    30, 200, 2, self.cfg["spread"], 0,
                    lambda v: self.app.change(spread=int(v))))
        g.add(_spin("Espaço entre ícones", "Em pixels", 0, 30, 1, self.cfg["gap"], 0,
                    lambda v: self.app.change(gap=int(v))))
        g.add(_spin("Margem interna", "Folga entre os ícones e a borda do dock (px)",
                    2, 30, 1, self.cfg["padding"], 0,
                    lambda v: self.app.change(padding=int(v))))
        return g

    def _behavior(self):
        g = Adw.PreferencesGroup(title="Comportamento")
        g.add(_spin("Duração máxima do bounce", "Segundos pulando enquanto o app abre",
                    1, 30, 1, self.cfg["bounce_seconds"], 0,
                    lambda v: self.app.change(bounce_seconds=int(v))))
        return g

    def _reset_group(self):
        g = Adw.PreferencesGroup()
        btn = Gtk.Button(label="Restaurar padrões", halign=Gtk.Align.CENTER)
        btn.add_css_class("destructive-action")
        btn.connect("clicked", self._reset)
        g.add(btn)
        return g

    def _reset(self, _b):
        self.app.reset_config()
        self.close()  # reabrir mostra os valores restaurados

    # ---------- ícone do menu iniciar ----------
    def _launcher_icon_row(self):
        row = Adw.ActionRow(title="Ícone do menu iniciar",
                            subtitle="Imagem PNG do botão de menu (a fruta é o padrão)")
        pick = Gtk.Button(label="Escolher imagem…", valign=Gtk.Align.CENTER)
        pick.connect("clicked", self._pick_icon)
        reset = Gtk.Button(icon_name="edit-undo-symbolic", valign=Gtk.Align.CENTER,
                           tooltip_text="Voltar para a fruta")
        reset.connect("clicked", lambda _b: self.app.change(launcher_icon=""))
        grid = Gtk.Button(label="Grade", valign=Gtk.Align.CENTER,
                          tooltip_text="Usar o ícone de grade colorida")
        grid.connect("clicked", lambda _b: self.app.change(launcher_icon="grid"))
        for b in (grid, reset, pick):
            row.add_suffix(b)
        return row

    def _pick_icon(self, _b):
        dlg = Gtk.FileDialog(title="Escolher ícone do menu iniciar")
        flt = Gtk.FileFilter()
        flt.set_name("Imagens")
        flt.add_mime_type("image/png")
        flt.add_mime_type("image/svg+xml")
        flt.add_mime_type("image/webp")
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(flt)
        dlg.set_filters(store)

        def done(d, res):
            try:
                f = d.open_finish(res)
            except Exception:
                return
            if f and f.get_path():
                self.app.change(launcher_icon=f.get_path())

        dlg.open(self, None, done)
