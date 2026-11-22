"""Traduções do mac-dock. O texto original (português) é a chave; sem tradução, volta o próprio texto.

Uso:  from i18n import _, set_language, translate_tree
      set_language("auto" | "pt" | "en" | "es")
"""
import locale
import os

LANGS = ("pt", "en", "es")
LANG_NAMES = {"pt": "Português", "en": "English", "es": "Español"}
_lang = "pt"

# pt -> (en, es)
TABLE = {
    # ---- dock: menu e rótulos
    "Aplicativos": ("Applications", "Aplicaciones"),
    "Lixeira": ("Trash", "Papelera"),
    "Abrir": ("Open", "Abrir"),
    "Abrir nova janela": ("Open new window", "Abrir nueva ventana"),
    "Janelas": ("Windows", "Ventanas"),
    "Fechar todas as janelas": ("Close all windows", "Cerrar todas las ventanas"),
    "Minimizar todas as janelas": ("Minimize all windows", "Minimizar todas las ventanas"),
    "Mover para o começo": ("Move to the start", "Mover al principio"),
    "Mover para o fim": ("Move to the end", "Mover al final"),
    "Remover do dock": ("Remove from dock", "Quitar del dock"),
    "Manter no dock": ("Keep in dock", "Mantener en el dock"),
    "Abrir lixeira": ("Open trash", "Abrir papelera"),
    "Esvaziar lixeira": ("Empty trash", "Vaciar papelera"),
    "Ajustes do dock…": ("Dock settings…", "Ajustes del dock…"),
    "Modo: ": ("Mode: ", "Modo: "),
    "Buscar": ("Search", "Buscar"),
    "Padrão": ("Default", "Predeterminado"),
    # ---- temas
    "Escuro": ("Dark", "Oscuro"),
    "Claro": ("Light", "Claro"),
    "Oceano": ("Ocean", "Océano"),
    "Floresta": ("Forest", "Bosque"),
    "Sakura": ("Sakura", "Sakura"),
    "Vidro (estilo Apple)": ("Glass (Apple style)", "Cristal (estilo Apple)"),
    "Grafite": ("Graphite", "Grafito"),
    "Meia-noite": ("Midnight", "Medianoche"),
    # ---- ajustes: estrutura
    "Ajustes do Dock": ("Dock Settings", "Ajustes del Dock"),
    "Recursos": ("Features", "Funciones"),
    "Ajustes": ("Settings", "Ajustes"),
    "Ativar": ("Enable", "Activar"),
    "Em desenvolvimento": ("In development", "En desarrollo"),
    "Aparência": ("Appearance", "Apariencia"),
    "Tela": ("Screen", "Pantalla"),
    "Ícones e ampliação": ("Icons and magnification", "Iconos y ampliación"),
    "Comportamento": ("Behavior", "Comportamiento"),
    "Restaurar padrões": ("Restore defaults", "Restaurar valores"),
    # ---- ajustes: modos e apps
    "Apps do dock (modo atual)": ("Dock apps (current mode)", "Apps del dock (modo actual)"),
    "Ordem, adição e remoção dos apps fixos do modo ativo.":
        ("Order, adding and removing pinned apps of the active mode.",
         "Orden, alta y baja de las apps fijas del modo activo."),
    "Gatilhos do modo atual": ("Triggers of the current mode", "Disparadores del modo actual"),
    "Quando um destes apps ficar ativo, o dock troca para este modo sozinho (e volta quando eles fecharem).":
        ("When one of these apps becomes active, the dock switches to this mode by itself (and goes back when they close).",
         "Cuando una de estas apps se activa, el dock cambia a este modo solo (y vuelve al cerrarse)."),
    "Adicionar gatilho": ("Add trigger", "Añadir disparador"),
    "Adicionar app": ("Add app", "Añadir app"),
    "Escolha na lista e clique em +": ("Pick from the list and click +", "Elige de la lista y pulsa +"),
    "Adicionar": ("Add", "Añadir"),
    "Remover": ("Remove", "Quitar"),
    "Subir": ("Move up", "Subir"),
    "Descer": ("Move down", "Bajar"),
    "não encontrado": ("not found", "no encontrado"),
    "Modos": ("Modes", "Modos"),
    "Conjuntos de apps do dock (Jogos, Dev…). Troque pelo botão direito no dock ou deixe a troca automática cuidar disso.":
        ("Sets of dock apps (Games, Dev…). Switch with the right button on the dock or let automatic switching handle it.",
         "Conjuntos de apps del dock (Juegos, Dev…). Cambia con el botón derecho o deja que el cambio automático se encargue."),
    "Troca automática": ("Automatic switching", "Cambio automático"),
    "Muda de modo quando um app gatilho fica ativo": ("Changes mode when a trigger app becomes active",
                                                       "Cambia de modo cuando una app disparadora se activa"),
    "Modo atual": ("Current mode", "Modo actual"),
    "Nome do modo": ("Mode name", "Nombre del modo"),
    "Gerenciar modos": ("Manage modes", "Gestionar modos"),
    "Novo (copia o atual)": ("New (copies the current)", "Nuevo (copia el actual)"),
    "Excluir este": ("Delete this", "Eliminar este"),
    "Novo modo ": ("New mode ", "Nuevo modo "),
    # ---- ajustes: recursos
    "Progresso e contadores": ("Progress and counters", "Progreso y contadores"),
    "Downloads e tarefas de apps como o Brave e a Steam mostram uma barra no ícone, e o número de itens pendentes vira um contador.":
        ("Downloads and tasks from apps like Brave and Steam show a bar on the icon, and the number of pending items becomes a counter.",
         "Las descargas y tareas de apps como Brave y Steam muestran una barra en el icono, y el número de pendientes pasa a ser un contador."),
    "Indicador de janelas": ("Window indicator", "Indicador de ventanas"),
    "O pontinho embaixo do ícone mostra quantas janelas o app tem (até 3) e fica laranja e pulsando quando o app pede atenção.":
        ("The dot under the icon shows how many windows the app has (up to 3) and turns orange and pulses when the app needs attention.",
         "El punto bajo el icono muestra cuántas ventanas tiene la app (hasta 3) y se vuelve naranja y pulsa cuando la app pide atención."),
    "Reflexo dos ícones": ("Icon reflection", "Reflejo de los iconos"),
    "Um reflexo suave embaixo de cada ícone, como no macOS clássico. Só nos docks de baixo e de cima.":
        ("A soft reflection under each icon, like classic macOS. Only for bottom and top docks.",
         "Un reflejo suave bajo cada icono, como en el macOS clásico. Solo en los docks inferior y superior."),
    "Arrastar arquivos para os ícones": ("Drag files onto icons", "Arrastrar archivos a los iconos"),
    "Solte um arquivo sobre um app para abri-lo com ele, ou sobre a lixeira para movê-lo para ela.":
        ("Drop a file on an app to open it with it, or on the trash to move it there.",
         "Suelta un archivo sobre una app para abrirlo con ella, o sobre la papelera para moverlo allí."),
    "Menu de contexto maior": ("Bigger context menu", "Menú contextual ampliado"),
    "O botão direito ganha ações extras: minimizar todas as janelas e mover o app para o começo ou o fim do dock.":
        ("The right button gets extra actions: minimize all windows and move the app to the start or end of the dock.",
         "El botón derecho gana acciones extra: minimizar todas las ventanas y mover la app al principio o al final del dock."),
    "Pré-visualização de janelas": ("Window previews", "Vista previa de ventanas"),
    "Passar o mouse sobre um app aberto mostra miniaturas das janelas. Sem permissão do KWin, mostra o ícone e o título.":
        ("Hovering an open app shows thumbnails of its windows. Without KWin permission it shows the icon and title.",
         "Al pasar el ratón sobre una app abierta se ven miniaturas de sus ventanas. Sin permiso de KWin, muestra el icono y el título."),
    "Esconder inteligente": ("Smart hide", "Ocultar inteligente"),
    "O dock só recolhe quando uma janela estiver tapando. Combine com \"Reservar espaço\" desligado.":
        ("The dock only hides when a window covers it. Works best with \"Reserve space\" off.",
         "El dock solo se oculta cuando una ventana lo tapa. Funciona mejor con \"Reservar espacio\" desactivado."),
    "Posição do dock": ("Dock position", "Posición del dock"),
    "Em qual borda da tela o dock fica.": ("Which screen edge the dock sits on.",
                                           "En qué borde de la pantalla está el dock."),
    "Embaixo": ("Bottom", "Abajo"),
    "Em cima": ("Top", "Arriba"),
    "Esquerda": ("Left", "Izquierda"),
    "Direita": ("Right", "Derecha"),
    "Borda": ("Edge", "Borde"),
    "Multi-monitor": ("Multi-monitor", "Multimonitor"),
    "Um dock por monitor, com os apps de cada tela.": ("One dock per monitor, with each screen's apps.",
                                                       "Un dock por monitor, con las apps de cada pantalla."),
    "Idioma": ("Language", "Idioma"),
    "Idioma da interface do dock e dos ajustes.": ("Language of the dock and settings interface.",
                                                   "Idioma de la interfaz del dock y los ajustes."),
    "Automático (do sistema)": ("Automatic (from system)", "Automático (del sistema)"),
    "Seguir o claro/escuro do KDE": ("Follow KDE light/dark", "Seguir claro/oscuro de KDE"),
    "Troca entre os dois temas abaixo sozinho": ("Switches between the two themes below by itself",
                                                  "Cambia entre los dos temas de abajo solo"),
    "Pinta o indicador e a borda com ela": ("Paints the indicator and border with it",
                                            "Pinta el indicador y el borde con él"),
    "Usar a cor de destaque do KDE": ("Use the KDE accent color", "Usar el color de acento de KDE"),
    "Temas e cor automática": ("Themes and automatic color", "Temas y color automático"),
    "Mais temas prontos e a opção de acompanhar o modo claro/escuro e a cor de destaque do KDE.":
        ("More built-in themes and the option to follow KDE's light/dark mode and accent color.",
         "Más temas incluidos y la opción de seguir el modo claro/oscuro y el color de acento de KDE."),
    "Tema no modo claro": ("Theme in light mode", "Tema en modo claro"),
    "Usado quando o KDE está claro": ("Used when KDE is light", "Se usa cuando KDE está en claro"),
    "Tema no modo escuro": ("Theme in dark mode", "Tema en modo oscuro"),
    "Usado quando o KDE está escuro": ("Used when KDE is dark", "Se usa cuando KDE está en oscuro"),
    "Copiar comando": ("Copy command", "Copiar comando"),
    "Instalar no sistema": ("Install on the system", "Instalar en el sistema"),
    "Na pasta do projeto, rode ./install.sh: ele confere as dependências e liga o início automático com a sessão.":
        ("In the project folder, run ./install.sh: it checks dependencies and enables autostart with the session.",
         "En la carpeta del proyecto, ejecuta ./install.sh: comprueba las dependencias y activa el inicio automático."),
    "Instalador": ("Installer", "Instalador"),
    # ---- ajustes: aparência
    "Cores do fundo, borda e rótulo": ("Background, border and label colors", "Colores de fondo, borde y etiqueta"),
    "Tema": ("Theme", "Tema"),
    "Intensidade do fundo": ("Background intensity", "Intensidad del fondo"),
    "Quanto o fundo do dock é opaco (1 = padrão do tema)": ("How opaque the dock background is (1 = theme default)",
                                                             "Qué tan opaco es el fondo del dock (1 = el del tema)"),
    "Arredondamento": ("Corner radius", "Redondeo"),
    "Raio dos cantos, em pixels": ("Corner radius, in pixels", "Radio de las esquinas, en píxeles"),
    "Desfoque do fundo (blur)": ("Background blur", "Desenfoque del fondo (blur)"),
    "O KWin desfoca o que está atrás do dock": ("KWin blurs what is behind the dock",
                                                "KWin desenfoca lo que hay detrás del dock"),
    "Botão de menu iniciar": ("Start menu button", "Botón de menú de inicio"),
    "Ícone de grade no começo do dock que abre o lançador": ("Grid icon at the start of the dock that opens the launcher",
                                                              "Icono de cuadrícula al inicio del dock que abre el lanzador"),
    "Contador de notificações": ("Notification counter", "Contador de notificaciones"),
    "Bolinha vermelha com o número de notificações do app": ("Red badge with the app's notification count",
                                                              "Globo rojo con el número de notificaciones de la app"),
    "Animação de música": ("Music animation", "Animación de música"),
    "O ícone do app que toca música pulsa e mostra um equalizador": ("The icon of the app playing music pulses and shows an equalizer",
                                                                      "El icono de la app que reproduce música pulsa y muestra un ecualizador"),
    "Brilho na cor do ícone": ("Icon-colored glow", "Brillo del color del icono"),
    "Luz suave sob o ícone, na cor dominante dele": ("Soft light under the icon, in its dominant color",
                                                      "Luz suave bajo el icono, en su color dominante"),
    "Ampliação com mola": ("Spring magnification", "Ampliación con muelle"),
    "O ícone oscila de leve ao crescer e voltar": ("The icon wobbles slightly when growing and returning",
                                                   "El icono oscila un poco al crecer y volver"),
    "Mostrar apps abertos": ("Show open apps", "Mostrar apps abiertas"),
    "Apps abertos que não estão fixados aparecem no dock": ("Open apps that are not pinned appear in the dock",
                                                             "Las apps abiertas que no están fijadas aparecen en el dock"),
    "Ícone da lixeira no fim do dock": ("Trash icon at the end of the dock", "Icono de la papelera al final del dock"),
    "Mostrar nome do app": ("Show app name", "Mostrar nombre de la app"),
    "Rótulo acima do ícone sob o mouse": ("Label above the icon under the mouse", "Etiqueta sobre el icono bajo el ratón"),
    "Indicador de app aberto": ("Open app indicator", "Indicador de app abierta"),
    "Pontinho embaixo do ícone": ("Small dot under the icon", "Punto bajo el icono"),
    "Ícone do menu iniciar": ("Start menu icon", "Icono del menú de inicio"),
    "Imagem PNG do botão de menu (a fruta é o padrão)": ("PNG image of the menu button (the fruit is the default)",
                                                          "Imagen PNG del botón de menú (la fruta es la predeterminada)"),
    "Escolher imagem…": ("Choose image…", "Elegir imagen…"),
    "Voltar para a fruta": ("Back to the fruit", "Volver a la fruta"),
    "Grade": ("Grid", "Cuadrícula"),
    "Usar o ícone de grade colorida": ("Use the colorful grid icon", "Usar el icono de cuadrícula de colores"),
    "Escolher ícone do menu iniciar": ("Choose start menu icon", "Elegir icono del menú de inicio"),
    "Imagens": ("Images", "Imágenes"),
    # ---- ajustes: tela, ícones, comportamento
    "Automático (o sistema escolhe)": ("Automatic (system chooses)", "Automático (lo elige el sistema)"),
    "Em qual tela o dock aparece": ("Which screen the dock appears on", "En qué pantalla aparece el dock"),
    "Monitor": ("Monitor", "Monitor"),
    "Esconder automaticamente": ("Hide automatically", "Ocultar automáticamente"),
    "O dock some quando o mouse sai; encoste o mouse na borda de baixo para ele voltar":
        ("The dock hides when the mouse leaves; touch the screen edge to bring it back",
         "El dock se oculta al salir el ratón; toca el borde de la pantalla para que vuelva"),
    "Reservar espaço": ("Reserve space", "Reservar espacio"),
    "Janelas maximizadas ficam acima do dock, sem cobri-lo": ("Maximized windows stay above the dock without covering it",
                                                               "Las ventanas maximizadas quedan sobre el dock sin cubrirlo"),
    "Distância da borda": ("Distance from the edge", "Distancia al borde"),
    "Espaço entre o dock e a parte de baixo da tela (px)": ("Space between the dock and the screen edge (px)",
                                                            "Espacio entre el dock y el borde de la pantalla (px)"),
    "Tamanho dos ícones": ("Icon size", "Tamaño de los iconos"),
    "Em repouso, em pixels": ("At rest, in pixels", "En reposo, en píxeles"),
    "Ampliação máxima": ("Maximum magnification", "Ampliación máxima"),
    "Quanto o ícone sob o mouse cresce (1 = sem zoom)": ("How much the icon under the mouse grows (1 = no zoom)",
                                                          "Cuánto crece el icono bajo el ratón (1 = sin zoom)"),
    "Alcance da ampliação": ("Magnification reach", "Alcance de la ampliación"),
    "Quantos ícones vizinhos crescem junto (px)": ("How many neighboring icons grow along (px)",
                                                    "Cuántos iconos vecinos crecen a la vez (px)"),
    "Espaço entre ícones": ("Space between icons", "Espacio entre iconos"),
    "Em pixels": ("In pixels", "En píxeles"),
    "Margem interna": ("Inner margin", "Margen interno"),
    "Folga entre os ícones e a borda do dock (px)": ("Gap between the icons and the dock edge (px)",
                                                      "Holgura entre los iconos y el borde del dock (px)"),
    "Duração máxima do bounce": ("Maximum bounce duration", "Duración máxima del rebote"),
    "Segundos pulando enquanto o app abre": ("Seconds bouncing while the app opens", "Segundos saltando mientras la app abre"),
    # ---- ilustrações
    "Baixando 65%": ("Downloading 65%", "Descargando 65%"),
    "1, 2 ou 3 janelas · laranja = pede atenção": ("1, 2 or 3 windows · orange = needs attention",
                                                    "1, 2 o 3 ventanas · naranja = pide atención"),
    "segue o KDE": ("follows KDE", "sigue a KDE"),
    "janela cobre o dock: ele recolhe": ("a window covers the dock: it hides", "una ventana tapa el dock: se oculta"),
    "Minimizar todas": ("Minimize all", "Minimizar todas"),
    "dependências ...... ok": ("dependencies ..... ok", "dependencias ...... ok"),
    "autostart ......... ok": ("autostart ......... ok", "autoinicio ........ ok"),
    "pronto": ("done", "listo"),
    "Reabra os ajustes para aplicar o idioma por inteiro.": ("Reopen settings to apply the language fully.",
                                                              "Reabre los ajustes para aplicar el idioma por completo."),
}


def resolve(setting):
    """"auto" usa o idioma do sistema; qualquer valor desconhecido vira português."""
    if setting in LANGS:
        return setting
    code = (os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG")
            or (locale.getlocale()[0] or ""))
    code = code.lower()
    for lang in ("pt", "es", "en"):
        if code.startswith(lang):
            return lang
    return "en" if code and not code.startswith("c") and not code.startswith("posix") else "pt"


def set_language(setting):
    global _lang
    _lang = resolve(setting)
    return _lang


def current():
    return _lang


def _(text):
    """Traduz `text` (português) para o idioma atual."""
    if _lang == "pt":
        return text
    row = TABLE.get(text)
    if row is None:
        return text
    return row[0] if _lang == "en" else row[1]


def translate_tree(widget):
    """Traduz os textos (Gtk.Label, inclusive os de dentro de linhas do libadwaita) de uma janela."""
    from gi.repository import Gtk
    if _lang == "pt":
        return
    stack = [widget]
    while stack:
        w = stack.pop()
        if isinstance(w, Gtk.Label):
            txt = w.get_label()
            if txt in TABLE:
                w.set_label(_(txt))
        child = w.get_first_child()
        while child is not None:
            stack.append(child)
            child = child.get_next_sibling()
