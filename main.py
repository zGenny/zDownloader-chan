import os
import threading
from concurrent.futures import ThreadPoolExecutor

import customtkinter
import httpx

from libs import theme as t
from libs.download_window import DownloadPopup
from libs.searcher import SERIES_TYPE, get_anime_details, search_anime
from libs.settings import settings
from libs.settings_window import SettingsDialog
from libs.stats import stats
from libs.strings import ANGRY_GIRL
from libs.utils import (downloaded_titles, fetch_image_data, format_number, format_size, library_entries, open_folder,
                        run_on_ui, sanitize_filename, with_session_retry)
from libs.widgets import (Badge, Chip, ConfirmDialog, Cover, ToggleGroup, language_badge, language_badge_spec, link_button,
                          primary_button, set_primary_enabled, set_window_icon)

APP_NAME = "zDownloader-chan"
GRID_COLUMNS = 5
LIST_COVER = (64, 92)
GRID_COVER = (168, 240)
INITIAL_ITEMS = 8  # risultati creati subito; gli altri arrivano in sottofondo
TYPE_FILTERS = [("all", "Tutti", None), ("series", "Serie TV", None), ("movie", "Film", None), ("other", "Altro", None)]


def matches_type(anime, type_filter):
  if type_filter == "series":
    return anime["type"] == SERIES_TYPE
  if type_filter == "movie":
    return anime["type"] == "Film"
  if type_filter == "other":
    return anime["type"] not in (SERIES_TYPE, "Film")
  return True


def _shorten(text, length):
  return text if len(text) <= length else text[:length - 1].rstrip() + "…"


class ModemChanApp:
  def __init__(self):
    t.load_fonts()
    customtkinter.set_appearance_mode("dark")
    customtkinter.set_default_color_theme("theme/MoonLight.json")
    self.root = customtkinter.CTk(fg_color=t.BG)
    self.root.title(APP_NAME)
    self.root.geometry("1080x720")
    self.root.minsize(940, 620)
    set_window_icon(self.root)

    # Incrementato a ogni ricerca, serve a scartare i risultati di ricerche ormai superate
    self.search_id = 0
    self.query = ""
    self.results = []
    self.images = {}    # indice del risultato -> byte della copertina (None se non disponibile)
    self.details = {}   # indice del risultato -> anno, stato e voto
    self.reset_item_widgets()
    self.type_filter = "all"
    self.dub_only = False
    self.view = "home"
    self.skeletons = []
    self.pulse_job = None
    self.executor = ThreadPoolExecutor(max_workers=6)

    self.root.grid_columnconfigure(0, weight=1)
    self.root.grid_rowconfigure(2, weight=1)
    self.build_header()
    self.loading_bar = customtkinter.CTkProgressBar(self.root, mode="indeterminate", height=3, corner_radius=0,
                                                    progress_color=t.ACCENT, fg_color=t.BG)
    self.loading_bar.grid(row=1, column=0, sticky="ew")
    self.loading_bar.grid_remove()
    self.content = customtkinter.CTkScrollableFrame(self.root, fg_color=t.BG, corner_radius=0,
                                                    scrollbar_button_color=t.SELECTED,
                                                    scrollbar_button_hover_color=t.BORDER_STRONG)
    self.content.grid(row=2, column=0, sticky="nsew")
    self.content.grid_columnconfigure(0, weight=1)

    self.root.bind("<Control-f>", self.focus_search)
    self.root.bind("<Control-F>", self.focus_search)
    self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    self.show_home()
    self.search_entry.focus()
    self.root.mainloop()

  # Intestazione

  def build_header(self):
    header = customtkinter.CTkFrame(self.root, fg_color=t.SURFACE, corner_radius=0)
    header.grid(row=0, column=0, sticky="ew")
    header.grid_columnconfigure(1, weight=1)

    logo = customtkinter.CTkFrame(header, fg_color="transparent", cursor="hand2")
    logo.grid(row=0, column=0, padx=(24, 16), pady=16)
    for text, color in (("z", t.ACCENT), ("Downloader-chan", t.TEXT)):
      label = customtkinter.CTkLabel(logo, text=text, font=t.font(22, True), text_color=color, cursor="hand2")
      label.pack(side="left")
      label.bind("<Button-1>", lambda event: self.show_home())

    self.search_box = customtkinter.CTkFrame(header, fg_color=t.SURFACE_2, corner_radius=22, border_width=1,
                                             border_color=t.BORDER_STRONG, height=44)
    self.search_box.grid(row=0, column=1, sticky="ew", pady=16)
    customtkinter.CTkLabel(self.search_box, text="", image=t.icon("search", t.TEXT_MUTED, 18), width=18).pack(side="left", padx=(14, 4))
    customtkinter.CTkLabel(self.search_box, text="Ctrl F", font=t.font(12), text_color=t.TEXT_MUTED, height=22).pack(side="right", padx=(6, 16))
    self.search_entry = customtkinter.CTkEntry(self.search_box, placeholder_text="Cerca un anime… es. Evangelion",
                                               border_width=0, fg_color=t.SURFACE_2, text_color=t.TEXT,
                                               placeholder_text_color=t.TEXT_MUTED, font=t.font(16, True), height=38)
    self.search_entry.pack(side="left", fill="x", expand=True, pady=2)
    self.search_entry.bind("<Return>", self.search)
    self.search_entry.bind("<Escape>", self.clear_search)
    self.search_entry.bind("<FocusIn>", lambda event: self.search_box.configure(border_color=t.ACCENT))
    self.search_entry.bind("<FocusOut>", lambda event: self.search_box.configure(border_color=t.BORDER_STRONG))

    self.search_button = primary_button(header, "Cerca", command=self.search, width=96)
    self.search_button.grid(row=0, column=2, padx=(12, 12))

    self.language_toggle = ToggleGroup(header, [("it", "Italiano", t.flag("it")), ("jp", "Giapponese", t.flag("jp"))],
                                       settings.get("title_language"), command=self.on_language_changed)
    self.language_toggle.grid(row=0, column=3)

    customtkinter.CTkButton(header, text="", image=t.icon("gear", t.TEXT, 20), width=44, height=44, corner_radius=22,
                            fg_color="transparent", hover_color=t.SURFACE_2, border_width=1, border_color=t.NEUTRAL_BG,
                            command=self.open_settings).grid(row=0, column=4, padx=(12, 24))
    customtkinter.CTkFrame(header, fg_color=t.BORDER, height=1, corner_radius=0).grid(row=1, column=0, columnspan=5, sticky="ew")

  def focus_search(self, event=None):
    self.search_entry.focus_set()
    self.search_entry.select_range(0, "end")
    return "break"

  def clear_search(self, event=None):
    self.search_entry.delete(0, "end")
    self.show_home()
    return "break"

  # Area dei contenuti

  def clear_content(self):
    self.stop_pulse()
    for widget in self.content.winfo_children():
      widget.destroy()
    self.reset_item_widgets()
    self.content._parent_canvas.yview_moveto(0)

  def page(self, pady=32):
    page = customtkinter.CTkFrame(self.content, fg_color="transparent")
    page.grid(row=0, column=0, sticky="nsew", padx=40, pady=pady)
    page.grid_columnconfigure(0, weight=1)
    return page

  def show_home(self):
    self.search_id += 1
    self.stop_loading()
    self.view = "home"
    self.clear_content()
    page = self.page()

    welcome = customtkinter.CTkFrame(page, fg_color=t.SURFACE, border_width=1, border_color=t.BORDER, corner_radius=16)
    welcome.grid(row=0, column=0, sticky="ew")
    welcome.grid_columnconfigure(1, weight=1)
    customtkinter.CTkLabel(welcome, text="z", font=t.font(44, True), text_color=t.ACCENT, width=88, height=88,
                           fg_color=t.DUB_BG, corner_radius=44).grid(row=0, column=0, rowspan=2, padx=28, pady=24)
    customtkinter.CTkLabel(welcome, text="Ciao senpai! Cosa guardiamo oggi?", font=t.font(26, True), text_color=t.TEXT,
                           anchor="w").grid(row=0, column=1, sticky="sw", padx=(0, 28), pady=(24, 0))
    customtkinter.CTkLabel(welcome, text="Cerca un anime per titolo italiano o giapponese, poi scarica tutta la serie "
                                         "o solo gli episodi che ti servono.",
                           font=t.font(15), text_color=t.TEXT_SOFT, wraplength=720, justify="left",
                           anchor="w").grid(row=1, column=1, sticky="nw", padx=(0, 28), pady=(4, 24))

    entries = library_entries(settings.get("download_dir"))
    self.stats_row(page, entries).grid(row=1, column=0, sticky="ew", pady=(20, 0))
    heading = customtkinter.CTkFrame(page, fg_color="transparent")
    heading.grid(row=2, column=0, sticky="ew", pady=(32, 14))
    customtkinter.CTkLabel(heading, text="La tua libreria", font=t.font(18, True), text_color=t.TEXT).pack(side="left")
    if entries:
      count = "1 serie" if len(entries) == 1 else f"{len(entries)} serie"
      customtkinter.CTkLabel(heading, text=f" · {count}", font=t.font(18), text_color=t.TEXT_MUTED).pack(side="left")
    link_button(heading, "Apri cartella dei download", command=lambda: open_folder(settings.get("download_dir"))).pack(side="right")

    if not entries:
      customtkinter.CTkLabel(page, text="Qui compariranno le serie che scarichi.", font=t.font(14),
                             text_color=t.TEXT_MUTED).grid(row=3, column=0, sticky="w")
      return
    grid = customtkinter.CTkFrame(page, fg_color="transparent")
    grid.grid(row=3, column=0, sticky="ew")
    for column in range(GRID_COLUMNS):
      grid.grid_columnconfigure(column, weight=1, uniform="library")
    for index, entry in enumerate(entries):
      self.library_card(grid, entry).grid(row=index // GRID_COLUMNS, column=index % GRID_COLUMNS, sticky="nw", pady=(0, 24))

  def stats_row(self, master, entries):
    """Contatori dei download: totali di sempre (stats.json) e stato attuale della libreria."""
    totals = stats.totals(entries)
    since = "-".join(reversed(totals["since"].split("-")))  # 2026-10-24 -> 24-10-2026
    tiles = [
      (format_number(totals["episodes"]), "episodi scaricati", f"dal {since}"),
      (format_size(totals["bytes"]) if totals["bytes"] else "0 GB", "dati scaricati", f"dal {since}"),
      (format_number(len(entries)), "serie in libreria", "nella cartella dei download"),
      (format_size(sum(entry["size"] for entry in entries)) if entries else "0 GB", "spazio occupato",
       "dagli episodi in libreria"),
    ]
    row = customtkinter.CTkFrame(master, fg_color="transparent")
    for column, (value, label, hint) in enumerate(tiles):
      row.grid_columnconfigure(column, weight=1, uniform="stats")
      tile = customtkinter.CTkFrame(row, fg_color=t.SURFACE, border_width=1, border_color=t.BORDER, corner_radius=14)
      tile.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0 if column == len(tiles) - 1 else 8))
      customtkinter.CTkLabel(tile, text=value, font=t.font(26, True), text_color=t.ACCENT_SOFT if column < 2 else t.TEXT,
                             anchor="w").pack(anchor="w", padx=18, pady=(14, 0))
      customtkinter.CTkLabel(tile, text=label, font=t.font(14, True), text_color=t.TEXT, anchor="w",
                             height=20).pack(anchor="w", padx=18)
      customtkinter.CTkLabel(tile, text=hint, font=t.font(12), text_color=t.TEXT_MUTED, anchor="w",
                             height=18).pack(anchor="w", padx=18, pady=(0, 14))
    return row

  def library_card(self, master, entry):
    # Senza width il CTkFrame chiede 200 px e la copertina (168 px) resterebbe centrata, disallineata dal testo
    card = customtkinter.CTkFrame(master, fg_color="transparent", width=GRID_COVER[0], height=1)
    poster = None
    if entry["poster"]:
      try:
        with open(entry["poster"], "rb") as f:
          poster = f.read()
      except OSError:
        poster = None
    cover = Cover(card, *GRID_COVER, radius=12, cursor="hand2")
    cover.set_image(poster)
    cover.pack()
    title = customtkinter.CTkLabel(card, text=_shorten(entry["title"], 60), font=t.font(14, True), text_color=t.TEXT,
                                   wraplength=GRID_COVER[0], justify="left", anchor="w", cursor="hand2")
    title.pack(anchor="w", pady=(8, 0))
    parts = [entry["year"]] if entry["year"] and entry["year"] != "ND" else []
    parts += ["1 episodio" if entry["episodes"] == 1 else f"{entry['episodes']} episodi", format_size(entry["size"])]
    customtkinter.CTkLabel(card, text=" · ".join(parts), font=t.font(12), text_color=t.TEXT_MUTED,
                           anchor="w").pack(anchor="w")
    for widget in (cover, title):
      widget.bind("<Button-1>", lambda event, path=entry["path"]: open_folder(path))
    return card

  # Ricerca

  def search(self, event=None):
    text = self.search_entry.get().strip()
    if text == "":
      return "break"
    self.search_id += 1
    search_id = self.search_id
    self.query = text
    self.results = []
    self.images = {}
    self.details = {}
    self.show_searching(text)

    def background_search():
      try:
        results, client = with_session_retry(lambda session: search_anime(query=text, client=session))
      except httpx.HTTPError as e:
        print(f"Errore durante la ricerca: {e}")
        run_on_ui(self.root, lambda: self.show_message(search_id, "Non riesco a contattare il sito, senpai!"))
        return
      run_on_ui(self.root, lambda: self.show_results(search_id, results or []))
      # Copertine e dettagli arrivano dopo, in parallelo, e aggiornano i risultati già mostrati
      for index, result in enumerate(results or []):
        self.executor.submit(self.load_cover, search_id, index, result["image_url"])
        if result["tooltip"]:
          self.executor.submit(self.load_details, search_id, index, result["tooltip"], client)

    threading.Thread(target=background_search, daemon=True).start()
    return "break"

  def load_cover(self, search_id, index, url):
    if search_id != self.search_id:
      return
    data = fetch_image_data(url)
    run_on_ui(self.root, lambda: self.on_cover_loaded(search_id, index, data))

  def load_details(self, search_id, index, url, client):
    if search_id != self.search_id:
      return
    try:
      details = get_anime_details(url, client)
    except httpx.HTTPError:
      details = {}
    run_on_ui(self.root, lambda: self.on_details_loaded(search_id, index, details))

  def on_cover_loaded(self, search_id, index, data):
    if search_id != self.search_id:
      return
    self.images[index] = data
    for covers in self.cover_widgets.values():
      cover = covers.get(index)
      if cover is not None and cover.winfo_exists():
        cover.set_image(data)

  def on_details_loaded(self, search_id, index, details):
    if search_id != self.search_id:
      return
    self.details[index] = details
    for view, labels in self.meta_labels.items():
      label = labels.get(index)
      if label is not None and label.winfo_exists():
        label.configure(text=self.meta_text(index, view))

  def meta_text(self, index, view):
    details = self.details.get(index)
    parts = [self.results[index]["type"]] if view == "grid" else []
    if details is None:
      return " · ".join(parts + ["…"])
    if details.get("year"):
      parts.append(details["year"])
    if details.get("state"):
      parts.append(details["state"])
    if details.get("rating"):
      parts.append(f"★ {details['rating']}")
    return " · ".join(parts)

  def show_searching(self, text):
    self.view = "searching"
    self.clear_content()
    self.loading_bar.grid()
    self.loading_bar.start()
    self.search_button.configure(text="Cerco…")
    set_primary_enabled(self.search_button, False)
    page = self.page(pady=20)
    customtkinter.CTkLabel(page, text=f"Cerco “{text}” su AnimeWorld…", font=t.font(15), text_color=t.TEXT_SOFT,
                           anchor="w").grid(row=0, column=0, sticky="w", pady=(0, 12))
    skeleton_area = customtkinter.CTkFrame(page, fg_color="transparent")
    skeleton_area.grid(row=1, column=0, sticky="ew")
    self.skeletons = []

    def block(master, width, height, radius=8):
      widget = customtkinter.CTkFrame(master, width=width, height=height, corner_radius=radius, fg_color=t.SKELETON)
      self.skeletons.append(widget)
      return widget

    if settings.get("view_mode") == "grid":
      for column in range(GRID_COLUMNS):
        skeleton_area.grid_columnconfigure(column, weight=1, uniform="skeleton")
        card = customtkinter.CTkFrame(skeleton_area, fg_color="transparent", width=GRID_COVER[0], height=1)
        card.grid(row=0, column=column, sticky="nw")
        block(card, *GRID_COVER, radius=12).pack()
        block(card, 140, 14, radius=7).pack(anchor="w", pady=(10, 6))
        block(card, 90, 12, radius=6).pack(anchor="w")
    else:
      skeleton_area.grid_columnconfigure(0, weight=1)
      for row, width in enumerate((340, 420, 280, 380)):
        frame = customtkinter.CTkFrame(skeleton_area, fg_color=t.SURFACE, corner_radius=14, border_width=1, border_color=t.BORDER)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        frame.grid_columnconfigure(1, weight=1)
        block(frame, *LIST_COVER).grid(row=0, column=0, rowspan=3, padx=(12, 20), pady=12)
        block(frame, width, 16).grid(row=0, column=1, sticky="sw", pady=(18, 0))
        block(frame, 180, 12, radius=6).grid(row=1, column=1, sticky="w", pady=8)
        block(frame, 150, 20, radius=10).grid(row=2, column=1, sticky="nw", pady=(0, 18))
        block(frame, 120, 40, radius=20).grid(row=0, column=2, rowspan=3, padx=16)
    self.pulse(False)

  def pulse(self, dim):
    """Fa 'respirare' i segnaposto mentre la ricerca è in corso."""
    for widget in self.skeletons:
      if widget.winfo_exists():
        widget.configure(fg_color=t.SKELETON_DIM if dim else t.SKELETON)
    self.pulse_job = self.root.after(650, lambda: self.pulse(not dim))

  def stop_pulse(self):
    if self.pulse_job is not None:
      self.root.after_cancel(self.pulse_job)
      self.pulse_job = None
    self.skeletons = []

  def stop_loading(self):
    self.loading_bar.stop()
    self.loading_bar.grid_remove()
    self.search_button.configure(text="Cerca")
    set_primary_enabled(self.search_button, True)

  def show_message(self, search_id, message):
    if search_id != self.search_id:
      return
    self.stop_loading()
    self.view = "message"
    self.clear_content()
    page = self.page()
    customtkinter.CTkLabel(page, text=message, font=t.font(18, True), text_color=t.TEXT).grid(row=0, column=0)
    customtkinter.CTkLabel(page, text=ANGRY_GIRL, font=customtkinter.CTkFont(size=7), text_color=t.TEXT_SOFT,
                           justify="left").grid(row=1, column=0, pady=(12, 0))

  # Risultati

  def show_results(self, search_id, results):
    if search_id != self.search_id:
      return
    if not results:
      self.show_message(search_id, f"Hai scritto bene? Non ho trovato nulla con “{self.query}”, senpai!")
      return
    self.stop_loading()
    self.view = "results"
    self.results = results
    self.clear_content()
    page = self.page(pady=20)

    toolbar = customtkinter.CTkFrame(page, fg_color="transparent")
    toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 14))
    self.count_label = customtkinter.CTkLabel(toolbar, text="", font=t.font(15), text_color=t.TEXT_SOFT)
    self.count_label.pack(side="left")
    self.view_toggle = ToggleGroup(toolbar, [("list", "", t.icon("list", t.TEXT, 18)), ("grid", "", t.icon("grid", t.TEXT, 18))],
                                   settings.get("view_mode"), command=self.on_view_changed, height=30)
    self.view_toggle.pack(side="right")
    Chip(toolbar, "Solo DUB ITA", image=t.flag("it"), command=self.on_dub_filter_changed,
         selected=self.dub_only).pack(side="right", padx=(0, 16))
    ToggleGroup(toolbar, TYPE_FILTERS, self.type_filter, command=self.on_type_filter_changed, height=26,
                font_size=12).pack(side="right", padx=(0, 10))

    self.items_frame = customtkinter.CTkFrame(page, fg_color="transparent")
    self.items_frame.grid(row=1, column=0, sticky="ew")
    self.items_frame.grid_columnconfigure(0, weight=1)
    self.render_items(build_limit=INITIAL_ITEMS)
    self.prebuild_items()

  def prebuild_items(self):
    """
    Crea in sottofondo, pochi alla volta, i widget non ancora visibili (l'altra vista e i risultati
    nascosti dai filtri), così anche il primo cambio di vista o di filtro è immediato.
    """
    item_widgets = self.item_widgets
    owned = downloaded_titles(settings.get("download_dir"))
    # Prima i risultati della vista corrente, nell'ordine in cui compaiono, poi l'altra vista
    current = settings.get("view_mode")
    views = (current, "grid" if current == "list" else "list")
    pending = [(view, index) for view in views for index in range(len(self.results))]

    def step():
      # Se nel frattempo i risultati sono stati ricreati (nuova ricerca, lingua, libreria) mi fermo
      if self.item_widgets is not item_widgets or not self.items_frame.winfo_exists():
        return
      built_current = False
      built = 0
      while pending and built < 2:
        view, index = pending.pop(0)
        if index not in item_widgets[view]:
          builder = self.grid_card if view == "grid" else self.list_row
          item_widgets[view][index] = builder(self.view_frame(view), index, owned)
          built += 1
          built_current = built_current or view == settings.get("view_mode")
      if built_current:
        self.render_items(build_limit=0)
      if pending:
        self.root.after(15, step)

    self.root.after(50, step)

  def reset_item_widgets(self):
    """
    Dimentica i widget dei risultati già creati.

    Righe della lista e schede della griglia vengono create una sola volta per ricerca e poi
    solo mostrate o nascoste: creare widget con CustomTkinter è lento, cambiare vista o filtro no.
    """
    self.view_frames = {}
    self.item_widgets = {"list": {}, "grid": {}}
    self.cover_widgets = {"list": {}, "grid": {}}
    self.meta_labels = {"list": {}, "grid": {}}
    self.empty_label = None

  def rebuild_items(self):
    """Ricrea i risultati da zero (serve quando cambiano i titoli o lo stato 'In libreria')."""
    for widget in self.items_frame.winfo_children():
      widget.destroy()
    self.reset_item_widgets()
    self.render_items()
    self.prebuild_items()

  def view_frame(self, view):
    frame = self.view_frames.get(view)
    if frame is None:
      frame = customtkinter.CTkFrame(self.items_frame, fg_color="transparent")
      if view == "grid":
        for column in range(GRID_COLUMNS):
          frame.grid_columnconfigure(column, weight=1, uniform="cards")
      else:
        frame.grid_columnconfigure(0, weight=1)
      self.view_frames[view] = frame
    return frame

  def render_items(self, build_limit=None):
    """
    Mostra i risultati della vista corrente che passano i filtri.

    build_limit limita quanti widget mancanti creare subito (None = tutti); gli altri
    li aggiunge prebuild_items in sottofondo.
    """
    view = settings.get("view_mode")
    visible = [index for index, anime in enumerate(self.results)
               if matches_type(anime, self.type_filter) and (anime["dub"] or not self.dub_only)]
    count = "1 risultato" if len(visible) == 1 else f"{len(visible)} risultati"
    filtered = f" (su {len(self.results)})" if len(visible) != len(self.results) else ""
    self.count_label.configure(text=f"{count} per “{self.query}”{filtered}")

    for other_view, frame in self.view_frames.items():
      if other_view != view:
        frame.grid_remove()
    if self.empty_label is None:
      self.empty_label = customtkinter.CTkLabel(self.items_frame, text="Nessun risultato con questi filtri.",
                                                font=t.font(15), text_color=t.TEXT_MUTED)
    if not visible:
      self.view_frame(view).grid_remove()
      self.empty_label.grid(row=1, column=0, sticky="w", pady=20)
      return
    self.empty_label.grid_remove()

    frame = self.view_frame(view)
    frame.grid(row=0, column=0, sticky="ew")
    widgets = self.item_widgets[view]
    owned = None
    for index in visible:
      if index not in widgets:
        if build_limit is not None:
          if build_limit <= 0:
            break
          build_limit -= 1
        if owned is None:
          owned = downloaded_titles(settings.get("download_dir"))
        widgets[index] = (self.grid_card if view == "grid" else self.list_row)(frame, index, owned)
    shown = set(visible)
    for index, widget in widgets.items():
      if index not in shown:
        widget.grid_remove()
    # Si mostrano in ordine fino al primo non ancora creato, così non restano buchi nella lista
    for position, index in enumerate(visible):
      if index not in widgets:
        break
      if view == "grid":
        widgets[index].grid(row=position // GRID_COLUMNS, column=position % GRID_COLUMNS, sticky="nw", pady=(0, 24))
      else:
        widgets[index].grid(row=position, column=0, sticky="ew", pady=(0, 12))

  def titles(self, anime):
    """Titolo principale e alternativo, secondo la lingua scelta."""
    if settings.get("title_language") == "it":
      main, other = anime["it_title"], anime["jap_title"]
    else:
      main, other = anime["jap_title"], anime["it_title"]
    return main, (other if other != main else "")

  def make_cover(self, master, index, view, size, radius, badge=None):
    cover = Cover(master, *size, radius=radius, badge=badge, cursor="hand2")
    if index in self.images:
      cover.set_image(self.images[index])
    cover.bind("<Button-1>", lambda event: self.open_download(index))
    self.cover_widgets[view][index] = cover
    return cover

  def action_button(self, master, index, owned, **kwargs):
    if sanitize_filename(self.results[index]["it_title"]) in owned:
      # La serie è già in libreria: si può comunque riaprire per scaricare gli episodi mancanti
      return customtkinter.CTkButton(master, text="In libreria", image=t.icon("check", t.OWNED_FG, 16), compound="left",
                                     fg_color=t.OWNED_BG, hover_color="#3A3428", border_width=1, border_color=t.OWNED_BORDER,
                                     text_color=t.OWNED_FG, font=t.font(14, True), corner_radius=kwargs.get("height", 40) // 2,
                                     command=lambda: self.open_download(index), **kwargs)
    return primary_button(master, "Scarica", image=t.icon("download", t.ON_ACCENT, 16),
                          command=lambda: self.open_download(index), **kwargs)

  def list_row(self, master, index, owned):
    anime = self.results[index]
    title, other_title = self.titles(anime)
    row = customtkinter.CTkFrame(master, fg_color=t.SURFACE, corner_radius=14, border_width=1, border_color=t.BORDER)
    row.grid_columnconfigure(1, weight=1)
    self.make_cover(row, index, "list", LIST_COVER, 8).grid(row=0, column=0, padx=(12, 20), pady=12)

    text = customtkinter.CTkFrame(row, fg_color="transparent")
    text.grid(row=0, column=1, sticky="ew")
    title_label = customtkinter.CTkLabel(text, text=title, font=t.font(17, True), text_color=t.TEXT, wraplength=560,
                                         justify="left", anchor="w", cursor="hand2")
    title_label.pack(anchor="w")
    title_label.bind("<Button-1>", lambda event: self.open_download(index))
    if other_title:
      customtkinter.CTkLabel(text, text=other_title, font=t.font(13), text_color=t.TEXT_MUTED, wraplength=560,
                             justify="left", anchor="w", height=18).pack(anchor="w")
    line = customtkinter.CTkFrame(text, fg_color="transparent")
    line.pack(anchor="w", pady=(6, 0))
    language_badge(line, anime["dub"]).pack(side="left", padx=(0, 6))
    Badge(line, anime["type"]).pack(side="left", padx=(0, 10))
    meta = customtkinter.CTkLabel(line, text=self.meta_text(index, "list"), font=t.font(13), text_color=t.TEXT_SOFT, height=20)
    meta.pack(side="left")
    self.meta_labels["list"][index] = meta

    self.action_button(row, index, owned, height=40, width=130).grid(row=0, column=2, padx=(12, 16))
    return row

  def grid_card(self, master, index, owned):
    anime = self.results[index]
    title, _ = self.titles(anime)
    card = customtkinter.CTkFrame(master, fg_color="transparent", width=GRID_COVER[0], height=1)
    cover = self.make_cover(card, index, "grid", GRID_COVER, 12, badge=language_badge_spec(anime["dub"]))
    cover.pack()
    title_label = customtkinter.CTkLabel(card, text=_shorten(title, 56), font=t.font(14, True), text_color=t.TEXT,
                                         wraplength=GRID_COVER[0], justify="left", anchor="w", cursor="hand2")
    title_label.pack(anchor="w", pady=(8, 0))
    title_label.bind("<Button-1>", lambda event: self.open_download(index))
    meta = customtkinter.CTkLabel(card, text=self.meta_text(index, "grid"), font=t.font(12), text_color=t.TEXT_MUTED,
                                  wraplength=GRID_COVER[0], justify="left", anchor="w", height=18)
    meta.pack(anchor="w")
    self.meta_labels["grid"][index] = meta
    self.action_button(card, index, owned, height=36, width=GRID_COVER[0]).pack(pady=(8, 0))
    return card

  def on_type_filter_changed(self, value):
    self.type_filter = value
    self.render_items()

  def on_dub_filter_changed(self, selected):
    self.dub_only = selected
    self.render_items()

  def on_view_changed(self, value):
    settings.update(view_mode=value)
    self.render_items()

  def on_language_changed(self, value):
    settings.update(title_language=value)
    if self.view == "results":
      self.rebuild_items()

  # Finestre secondarie

  def open_download(self, index):
    DownloadPopup(self.root, self.results[index], image_data=self.images.get(index), on_finished=self.on_library_changed)

  def on_library_changed(self):
    if self.view == "home":
      self.show_home()
    elif self.view == "results":
      self.rebuild_items()

  def open_settings(self):
    SettingsDialog(self.root, on_saved=self.on_settings_saved).show()

  def on_settings_saved(self):
    self.language_toggle.set(settings.get("title_language"))
    if self.view == "results":
      self.view_toggle.set(settings.get("view_mode"))
      self.rebuild_items()
    elif self.view == "home":
      self.show_home()

  def on_close(self):
    downloading = [popup for popup in DownloadPopup.active if popup.downloading]
    if downloading:
      if len(downloading) == 1:
        message = "C'è un download in corso. Se chiudi ora verrà interrotto; gli episodi già scaricati restano nella cartella."
      else:
        message = (f"Ci sono {len(downloading)} download in corso. Se chiudi ora verranno interrotti; "
                   "gli episodi già scaricati restano nella cartella.")
      if not ConfirmDialog(self.root, "Download in corso", message, "Interrompi e chiudi", "Continua i download").show():
        return
      for popup in downloading:
        popup.cancel_event.set()
    self.executor.shutdown(wait=False, cancel_futures=True)
    self.root.destroy()


if __name__ == "__main__":
  if not os.path.exists(settings.get("download_dir")):
    os.makedirs(settings.get("download_dir"))
  ModemChanApp()
