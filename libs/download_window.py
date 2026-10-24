"""Finestra di download di una serie: informazioni, scelta degli episodi e avanzamento."""

import os
import time
from io import BytesIO
from threading import Event, Thread

import customtkinter
import httpx
import requests
from PIL import Image, UnidentifiedImageError

from . import theme as t
from .downloader import (AnimeNotAvailable, AnimeNotFound, DownloadCancelled, DownloadError, download_file_multithread,
                         get_anime_info, get_episodes, resolve_episode_link)
from .settings import settings
from .stats import stats
from .utils import (anime_folder_name, episode_value, fetch_image_data, format_elapsed, format_episode_number, format_eta,
                    format_number, format_size, generate_client, library_entries, open_folder, run_on_ui,
                    sanitize_filename, with_session_retry)
from .widgets import (Badge, ConfirmDialog, Cover, language_badge, link_button, primary_button, secondary_button,
                      set_primary_enabled, set_window_icon)

CONTENT_WIDTH = 592
STORY_PREVIEW_LENGTH = 220


def _range_text(value):
  """Valore di un episodio da mostrare nei campi da/a: 12.0 -> '12', 5.5 -> '5.5'."""
  return str(int(value)) if value == int(value) else str(value)


def _shorten(text, length):
  return text if len(text) <= length else text[:length - 1].rstrip() + "…"


def _short_path(path, length=44):
  """Percorso da mostrare: se è lungo si tiene la parte finale, la più utile (es. '…/downloads/Titolo(2023)')."""
  path = path.replace("\\", "/")
  return path if len(path) <= length else "…" + path[-(length - 1):]


class DownloadPopup(customtkinter.CTkToplevel):
  # Popup con un download in corso, usato dalla finestra principale per chiedere conferma alla chiusura
  active = set()

  def __init__(self, parent, anime, image_data=None, on_finished=None):
    super().__init__(parent)
    self.anime = anime
    self.it_title = anime["it_title"]
    self.jap_title = anime["jap_title"]
    self.link = anime["link"]
    self.image_data = image_data
    self.on_finished = on_finished
    self.downloading = False
    self.cancel_event = Event()
    self.episodes = None        # coppie (numero, id); None se la lista non è stata letta
    self.episodes_error = None  # perché non ci sono episodi (pagina inesistente, non ancora disponibile)
    self.last_failed = []
    self.current_episode = None

    self.title(f"Download di {self.it_title}")
    self.configure(fg_color=t.BG)
    self.resizable(False, False)
    self.transient(parent)
    set_window_icon(self)
    self.protocol("WM_DELETE_WINDOW", self.on_close)
    self.bind("<Escape>", lambda event: self.on_close())

    # Le informazioni vengono caricate in background per non bloccare l'interfaccia
    self.loading = customtkinter.CTkFrame(self, fg_color="transparent")
    self.loading.pack(padx=160, pady=110)
    customtkinter.CTkLabel(self.loading, text="Caricamento informazioni…", font=t.font(15, True), text_color=t.TEXT_SOFT).pack()
    loading_bar = customtkinter.CTkProgressBar(self.loading, mode="indeterminate", width=240, height=4,
                                               progress_color=t.ACCENT, fg_color=t.SKELETON)
    loading_bar.pack(pady=(12, 0))
    loading_bar.start()
    self.after(100, self._bring_to_front)
    Thread(target=self.load_info, daemon=True).start()

  def _bring_to_front(self):
    self.lift()
    self.focus_force()

  # Caricamento

  def load_episodes(self, client=None):
    """Restituisce (episodi, errore); episodi è None se il sito non risponde."""
    try:
      episodes, _ = with_session_retry(lambda session: get_episodes(self.link, session), client)
      return episodes, None
    except AnimeNotFound:
      return [], "Questa pagina non esiste più sul sito: prova a cercare di nuovo l'anime."
    except AnimeNotAvailable:
      return [], "Questo anime non è ancora disponibile sul sito: riprova più avanti."
    except httpx.HTTPError as e:
      print(f"Errore nel recupero degli episodi: {e}")
      return None, None

  def load_info(self):
    info, client = None, None
    try:
      info, client = with_session_retry(lambda session: get_anime_info(self.it_title, self.jap_title, session))
    except httpx.HTTPError as e:
      print(f"Impossibile recuperare le informazioni di {self.it_title}: {e}")
    episodes, error = self.load_episodes(client)
    image_data = self.image_data or fetch_image_data(self.anime["image_url"])
    run_on_ui(self, lambda: self.on_info_loaded(info or {}, image_data, episodes, error))

  def reload_episodes(self):
    self.show_message("Ricarico la lista degli episodi…")
    set_primary_enabled(self.primary_button, False)

    def background():
      episodes, error = self.load_episodes()
      run_on_ui(self, lambda: self.on_episodes_loaded(episodes, error))

    Thread(target=background, daemon=True).start()

  def episode_bounds(self):
    """Primo e ultimo valore numerico degli episodi (per i campi da/a)."""
    values = [value for value in (episode_value(number) for number, _ in self.episodes or []) if value is not None]
    return (min(values), max(values)) if values else (None, None)

  def reset_range(self):
    first, last = self.episode_bounds()
    if first is None:
      return
    for entry, value in ((self.from_entry, first), (self.to_entry, last)):
      entry.delete(0, "end")
      entry.insert(0, _range_text(value))

  def on_episodes_loaded(self, episodes, error):
    self.episodes = episodes
    self.episodes_error = error
    self.reset_range()
    self.show_ready()

  def on_info_loaded(self, info, image_data, episodes, error):
    self.image_data = image_data
    self.episodes = episodes
    self.episodes_error = error
    self.year = info.get("year")
    self.dub = self.anime["dub"] if "dub" in self.anime else str(info.get("dub")) == "1"
    self.folder = os.path.join(settings.get("download_dir"), anime_folder_name(self.it_title, self.year))
    self.loading.destroy()
    self.build_ui(info)
    self.show_ready()

  # Costruzione dell'interfaccia

  def build_ui(self, info):
    body = customtkinter.CTkFrame(self, fg_color="transparent")
    body.pack(padx=24, pady=24, fill="both", expand=True)
    body.grid_columnconfigure(0, weight=1)

    self.build_header(body, info).grid(row=0, column=0, sticky="ew")
    self.build_story(body, info.get("story")).grid(row=1, column=0, sticky="ew", pady=(20, 0))
    self.options_card = self.build_options(body)
    self.options_card.grid(row=2, column=0, sticky="ew", pady=(20, 0))
    self.progress_box = self.build_progress(body)
    self.progress_box.grid(row=3, column=0, sticky="ew", pady=(20, 0))
    self.done_card = self.build_done_card(body)
    self.done_card.grid(row=4, column=0, sticky="ew", pady=(20, 0))
    self.error_box = self.build_error_box(body)
    self.error_box.grid(row=5, column=0, sticky="ew", pady=(14, 0))

    self.message_label = customtkinter.CTkLabel(body, text="", font=t.font(13), text_color=t.TEXT_MUTED,
                                                wraplength=CONTENT_WIDTH, justify="left", anchor="w")
    self.message_label.grid(row=6, column=0, sticky="ew", pady=(14, 0))

    footer = customtkinter.CTkFrame(body, fg_color="transparent")
    footer.grid(row=7, column=0, sticky="e", pady=(16, 0))
    self.secondary_button = secondary_button(footer, "Chiudi", command=self.on_close)
    self.secondary_button.pack(side="left", padx=(0, 12))
    self.primary_button = primary_button(footer, "Scarica", command=self.start_download)
    self.primary_button.pack(side="left")

  def build_header(self, master, info):
    header = customtkinter.CTkFrame(master, fg_color="transparent")
    Cover(header, 104, 150, radius=10, image_data=self.image_data).grid(row=0, column=0, sticky="n")

    right = customtkinter.CTkFrame(header, fg_color="transparent")
    right.grid(row=0, column=1, sticky="nw", padx=(20, 0))
    customtkinter.CTkLabel(right, text=self.it_title, font=t.font(22, True), text_color=t.TEXT, wraplength=460,
                           justify="left", anchor="w").pack(anchor="w")
    if self.jap_title != self.it_title:
      customtkinter.CTkLabel(right, text=self.jap_title, font=t.font(13), text_color=t.TEXT_MUTED, wraplength=460,
                             justify="left", anchor="w").pack(anchor="w")

    badges = customtkinter.CTkFrame(right, fg_color="transparent")
    badges.pack(anchor="w", pady=(8, 8))
    language_badge(badges, self.dub).pack(side="left", padx=(0, 6))
    Badge(badges, self.anime.get("type") or info.get("animeTypeName") or "Anime").pack(side="left", padx=(0, 6))
    if info.get("malVote"):
      Badge(badges, f"MAL {info['malVote']}").pack(side="left")

    episodes = info.get("episodes") or "??"
    duration = info.get("durationEpisodes")
    language = "Doppiato in italiano" if self.dub else "Sottotitolato in italiano"
    rows = [
      ("Studio", _shorten(info.get("studio") or "N/D", 26)),
      ("Anno", self.year or "N/D"),
      ("Uscita", info.get("release") or "N/D"),
      ("Episodi", f"{episodes} × {duration} min" if duration and duration != "??" else episodes),
      ("Visualizzazioni", format_number(info["totViews"]) if info.get("totViews") is not None else "N/D"),
      ("Lingua", language),
    ]
    grid = customtkinter.CTkFrame(right, fg_color="transparent")
    grid.pack(anchor="w")
    for index, (key, value) in enumerate(rows):
      cell = customtkinter.CTkFrame(grid, fg_color="transparent")
      cell.grid(row=index // 2, column=index % 2, sticky="w", padx=(0, 18), pady=1)
      customtkinter.CTkLabel(cell, text=key, font=t.font(13), text_color=t.TEXT_MUTED, height=20).pack(side="left")
      value_label = customtkinter.CTkLabel(cell, text=value, font=t.font(13, True), text_color=t.TEXT, height=20)
      if key == "Lingua":
        value_label.configure(image=t.flag("it", 10), compound="right", text=f"{value} ")
      value_label.pack(side="left", padx=(6, 0))
    return header

  def build_story(self, master, story):
    frame = customtkinter.CTkFrame(master, fg_color="transparent")
    self.story = (story or "Trama non disponibile.").strip()
    self.story_expanded = False
    customtkinter.CTkLabel(frame, text="Trama", font=t.font(14, True), text_color=t.TEXT, height=20).pack(anchor="w")
    self.story_label = customtkinter.CTkLabel(frame, text=_shorten(self.story, STORY_PREVIEW_LENGTH), font=t.font(13),
                                              text_color=t.TEXT_SOFT, wraplength=CONTENT_WIDTH, justify="left", anchor="w")
    self.story_label.pack(anchor="w", pady=(4, 0))
    if len(self.story) > STORY_PREVIEW_LENGTH:
      self.story_button = link_button(frame, "Mostra tutto", command=self.toggle_story, size=13)
      self.story_button.pack(anchor="w")
    return frame

  def toggle_story(self):
    self.story_expanded = not self.story_expanded
    self.story_label.configure(text=self.story if self.story_expanded else _shorten(self.story, STORY_PREVIEW_LENGTH))
    self.story_button.configure(text="Mostra meno" if self.story_expanded else "Mostra tutto")

  def _field(self, master, column, label):
    field = customtkinter.CTkFrame(master, fg_color="transparent")
    field.grid(row=0, column=column, sticky="w", padx=(0, 12))
    customtkinter.CTkLabel(field, text=label, font=t.font(12, True), text_color=t.TEXT_MUTED, height=18).pack(anchor="w")
    return field

  def _episode_entry(self, master, value):
    entry = customtkinter.CTkEntry(master, width=72, height=36, corner_radius=8, border_width=1, border_color=t.NEUTRAL_BG,
                                   fg_color=t.SURFACE_2, text_color=t.TEXT, font=t.font(14, True), justify="center")
    entry.insert(0, value)
    entry.bind("<KeyRelease>", lambda event: self.update_primary_label())
    entry.bind("<Return>", lambda event: self.start_download())
    entry.pack(anchor="w", pady=(4, 0))
    return entry

  def build_options(self, master):
    card = customtkinter.CTkFrame(master, fg_color=t.SURFACE, border_width=1, border_color=t.BORDER, corner_radius=14)
    row = customtkinter.CTkFrame(card, fg_color="transparent")
    row.pack(fill="x", padx=16, pady=(14, 6))
    row.grid_columnconfigure(3, weight=1)

    self.from_entry = self._episode_entry(self._field(row, 0, "Da episodio"), "")
    self.to_entry = self._episode_entry(self._field(row, 1, "A episodio"), "")
    self.reset_range()

    self.threads_var = customtkinter.StringVar(value=str(settings.get("threads")))
    self.threads_menu = customtkinter.CTkOptionMenu(self._field(row, 2, "Connessioni"), variable=self.threads_var,
                                                    values=[str(i) for i in range(1, 13)], width=80, height=36,
                                                    corner_radius=8, fg_color=t.SURFACE_2, button_color=t.SURFACE_2,
                                                    button_hover_color=t.SELECTED, text_color=t.TEXT,
                                                    font=t.font(14, True), dropdown_font=t.font(13))
    self.threads_menu.pack(anchor="w", pady=(4, 0))

    destination = self._field(row, 3, "Salva in")
    destination.grid_configure(sticky="ew", padx=0)
    customtkinter.CTkLabel(destination, text=_short_path(self.folder), font=t.font(13),
                           text_color=t.TEXT_SOFT, height=36, anchor="w").pack(anchor="w", pady=(4, 0))

    self.options_hint = customtkinter.CTkLabel(card, text="", font=t.font(12), text_color=t.TEXT_MUTED, anchor="w")
    self.options_hint.pack(anchor="w", padx=16, pady=(0, 12))
    return card

  def build_progress(self, master):
    box = customtkinter.CTkFrame(master, fg_color="transparent")
    box.grid_columnconfigure(0, weight=1)

    def heading(row, title, pady=0):
      line = customtkinter.CTkFrame(box, fg_color="transparent")
      line.grid(row=row, column=0, sticky="ew", pady=pady)
      title_label = customtkinter.CTkLabel(line, text=title, font=t.font(14, True), text_color=t.TEXT, height=20)
      title_label.pack(side="left")
      detail = customtkinter.CTkLabel(line, text="", font=t.font(14), text_color=t.TEXT_SOFT, height=20)
      detail.pack(side="right")
      return title_label, detail

    def bar(row, color):
      progress = customtkinter.CTkProgressBar(box, height=10, corner_radius=5, progress_color=color, fg_color=t.SKELETON)
      progress.grid(row=row, column=0, sticky="ew", pady=(6, 0))
      progress.set(0)
      return progress

    _, self.series_detail = heading(0, "Serie")
    self.series_bar = bar(1, t.ACCENT)
    self.episode_title, self.episode_detail = heading(2, "Episodio", pady=(14, 0))
    self.episode_bar = bar(3, t.ACCENT_SOFT)
    self.episode_size = customtkinter.CTkLabel(box, text="", font=t.font(12), text_color=t.TEXT_MUTED, height=18, anchor="w")
    self.episode_size.grid(row=4, column=0, sticky="w", pady=(4, 0))
    return box

  def build_done_card(self, master):
    card = customtkinter.CTkFrame(master, fg_color=t.SURFACE, border_width=1, border_color=t.BORDER, corner_radius=16)
    self.done_icon = customtkinter.CTkLabel(card, text="", image=t.check_badge(64), width=64, height=64)
    self.done_icon.pack(pady=(28, 10))
    self.done_title = customtkinter.CTkLabel(card, text="Download completato!", font=t.font(22, True), text_color=t.TEXT)
    self.done_title.pack()
    self.done_summary = customtkinter.CTkLabel(card, text="", font=t.font(15), text_color=t.TEXT_SOFT)
    self.done_summary.pack(pady=(4, 0))
    done_bar = customtkinter.CTkProgressBar(card, height=10, corner_radius=5, progress_color=t.ACCENT, fg_color=t.SKELETON)
    done_bar.pack(fill="x", padx=24, pady=(14, 28))
    done_bar.set(1)
    return card

  def build_error_box(self, master):
    box = customtkinter.CTkFrame(master, fg_color=t.DANGER_BG, border_width=1, border_color=t.DANGER_BORDER, corner_radius=12)
    customtkinter.CTkLabel(box, text="", image=t.icon("warning", t.DANGER_FG, 18), width=18).pack(side="left", padx=(16, 10), pady=12)
    self.error_label = customtkinter.CTkLabel(box, text="", font=t.font(14), text_color=t.TEXT, anchor="w")
    self.error_label.pack(side="left", fill="x", expand=True)
    link_button(box, "Riprova questi", command=self.retry_failed).pack(side="right", padx=(0, 10))
    return box

  # Stati della finestra

  def show_message(self, message, error=False):
    self.message_label.configure(text=message, text_color=t.DANGER_FG if error else t.TEXT_MUTED)
    if message:
      self.message_label.grid()
    else:
      self.message_label.grid_remove()

  def set_options_enabled(self, enabled):
    state = "normal" if enabled else "disabled"
    for widget in (self.from_entry, self.to_entry, self.threads_menu):
      widget.configure(state=state)

  def selected_episodes(self):
    """Episodi (numero, id) compresi tra i valori dei campi da/a, secondo i numeri del sito; None se non valido."""
    try:
      first = float(self.from_entry.get().replace(",", "."))
      last = float(self.to_entry.get().replace(",", "."))
    except ValueError:
      return None
    if not self.episodes or first > last:
      return None
    selection = [(number, episode_id) for number, episode_id in self.episodes
                 if (value := episode_value(number)) is not None and first <= value <= last]
    return selection or None

  def update_primary_label(self):
    if self.downloading or not self.episodes:
      return
    selection = self.selected_episodes()
    for entry in (self.from_entry, self.to_entry):
      entry.configure(border_color=t.NEUTRAL_BG if selection else t.DANGER_BORDER)
    if selection:
      count = len(selection)
      self.primary_button.configure(text="Scarica 1 episodio" if count == 1 else f"Scarica {count} episodi")
    else:
      self.primary_button.configure(text="Scarica")
    set_primary_enabled(self.primary_button, selection is not None)

  def show_ready(self, message="", error=False):
    self.options_card.grid()
    self.progress_box.grid_remove()
    self.done_card.grid_remove()
    self.error_box.grid_remove()
    self.set_options_enabled(True)
    self.secondary_button.configure(text="Chiudi", command=self.on_close, state="normal")
    self.primary_button.configure(image=t.icon("download", t.ON_ACCENT, 18))

    if self.episodes is None:
      self.options_hint.configure(text="Lista degli episodi non disponibile")
      self.primary_button.configure(text="Riprova", command=self.reload_episodes, image=None)
      set_primary_enabled(self.primary_button, True)
      self.show_message(message or "Non riesco a leggere la lista degli episodi dal sito.", error=True)
      return
    if not self.episodes:
      self.options_hint.configure(text="Nessun episodio disponibile")
      self.primary_button.configure(text="Scarica")
      set_primary_enabled(self.primary_button, False)
      self.show_message(message or self.episodes_error or "Il sito non elenca episodi per questo anime.", error=True)
      return

    total = len(self.episodes)
    first, last = self.episode_bounds()
    span = f" (dal {_range_text(first)} al {_range_text(last)})" if first is not None else ""
    self.options_hint.configure(text=f"{total} episodi disponibili{span} · quelli già scaricati vengono saltati")
    self.primary_button.configure(command=self.start_download)
    self.update_primary_label()
    self.show_message(message, error)

  def show_downloading(self, total):
    self.options_card.grid()
    self.progress_box.grid()
    self.done_card.grid_remove()
    self.error_box.grid_remove()
    self.set_options_enabled(False)
    self.secondary_button.configure(text="Annulla", command=self.cancel_download, state="normal")
    self.primary_button.configure(text="Download in corso…", image=None)
    set_primary_enabled(self.primary_button, False)
    self.series_bar.set(0)
    self.series_detail.configure(text=f"0 di {total} episodi")
    self.episode_title.configure(text="Episodio")
    self.episode_detail.configure(text="")
    self.episode_bar.set(0)
    self.episode_size.configure(text="")
    self.show_message("")

  def show_finished(self, done, total_bytes, elapsed, failed):
    self.options_card.grid_remove()
    self.progress_box.grid_remove()
    self.done_card.grid()
    if failed:
      self.done_icon.configure(image=t.icon("warning", t.DANGER_FG, 48))
      self.done_title.configure(text="Download completato con errori" if done else "Download non riuscito")
      self.error_label.configure(text=f"Episodi non scaricati: {', '.join(map(str, failed))}")
      self.error_box.grid()
    else:
      self.done_icon.configure(image=t.check_badge(64))
      self.done_title.configure(text="Download completato!")
      self.error_box.grid_remove()
    episodes = "1 episodio" if done == 1 else f"{done} episodi"
    self.done_summary.configure(text=f"{episodes} · {format_size(total_bytes)} · in {format_elapsed(elapsed)}")
    self.show_message(f"Salvato in {_short_path(self.folder, 70)}")
    self.secondary_button.configure(text="Chiudi", command=self.on_close, state="normal")
    self.primary_button.configure(text="Apri cartella", image=t.icon("folder", t.ON_ACCENT, 18),
                                  command=lambda: open_folder(self.folder))
    set_primary_enabled(self.primary_button, True)

  # Download

  def set_downloading(self, downloading):
    self.downloading = downloading
    if downloading:
      DownloadPopup.active.add(self)
    else:
      DownloadPopup.active.discard(self)

  def start_download(self, selection=None):
    if self.downloading or not self.episodes:
      return
    if selection is None:
      selection = self.selected_episodes()
      if selection is None:
        first, last = self.episode_bounds()
        self.show_message(f"Scegli un intervallo di episodi tra {_range_text(first)} e {_range_text(last)}.", error=True)
        return
    num_threads = int(self.threads_var.get())
    self.cancel_event = Event()
    self.set_downloading(True)
    self.show_downloading(len(selection))
    Thread(target=self.download_episodes, args=(selection, num_threads, self.cancel_event)).start()

  def retry_failed(self):
    selection = [(number, episode_id) for number, episode_id in self.episodes if number in self.last_failed]
    self.start_download(selection)

  def cancel_download(self):
    self.cancel_event.set()
    self.secondary_button.configure(text="Annullamento…", state="disabled")

  def save_poster(self, folder):
    """Salva la copertina nella cartella della serie (la usano la libreria e i media server)."""
    path = os.path.join(folder, "poster.jpg")
    if not self.image_data or os.path.exists(path):
      return
    try:
      Image.open(BytesIO(self.image_data)).convert("RGB").save(path, "JPEG", quality=90)
    except (UnidentifiedImageError, OSError) as e:
      print(f"Impossibile salvare la copertina: {e}")

  def download_episodes(self, selection, num_threads, cancel_event):
    total = len(selection)
    start_time = time.time()
    failed = []
    try:
      os.makedirs(self.folder, exist_ok=True)
      self.save_poster(self.folder)
      client = generate_client()
    except (httpx.HTTPError, OSError) as e:
      print(f"Impossibile avviare il download: {e}")
      run_on_ui(self, lambda: self.on_download_stopped("Impossibile avviare il download, controlla la connessione.", error=True))
      return

    file_prefix = f"{sanitize_filename(self.it_title)} ({sanitize_filename(self.year)})"
    on_episode_progress = lambda *args: run_on_ui(self, lambda: self.update_episode_progress(*args))
    outputs = []
    for position, (number, episode_id) in enumerate(selection, start=1):
      output = os.path.join(self.folder, f"{file_prefix} - e{format_episode_number(number)}.mp4")
      outputs.append(output)
      run_on_ui(self, lambda n=number: self.start_episode(n))
      # I file vengono rinominati in .mp4 solo a download completato, quindi se esiste è integro
      if not os.path.exists(output):
        link = None
        for attempt in range(2):
          try:
            link = resolve_episode_link(episode_id, client)
          except httpx.HTTPError as e:
            print(f"Errore nel recupero del link dell'episodio {number}: {e}")
          if link or attempt == 1:
            break
          # Nei download lunghi i cookie della sessione possono scadere: ne creo una nuova e riprovo
          try:
            client = generate_client()
          except httpx.HTTPError:
            break
        if not link:
          failed.append(number)
        else:
          print(f"Downloading {self.it_title} episode {number} from {link}")
          try:
            download_file_multithread(link, output, num_threads, on_episode_progress, cancel_event)
            stats.record_episode(os.path.getsize(output), lambda: library_entries(settings.get("download_dir")))
          except DownloadCancelled:
            completed = position - 1 - len(failed)
            message = f"Download annullato ({completed} episodi completati). Gli episodi già scaricati verranno saltati."
            run_on_ui(self, lambda: self.on_download_stopped(message))
            return
          except (requests.RequestException, DownloadError, OSError) as e:
            print(f"Errore nel download dell'episodio {number}: {e}")
            failed.append(number)
      run_on_ui(self, lambda p=position: self.update_series_progress(p, total))

    total_bytes = sum(os.path.getsize(path) for path in outputs if os.path.exists(path))
    elapsed = time.time() - start_time
    print("Download completato" if not failed else f"Episodi non scaricati: {failed}")
    run_on_ui(self, lambda: self.on_download_finished(total - len(failed), total_bytes, elapsed, failed))

  def on_download_stopped(self, message, error=False):
    self.set_downloading(False)
    self.show_ready(message, error)
    if self.on_finished:
      self.on_finished()

  def on_download_finished(self, done, total_bytes, elapsed, failed):
    self.set_downloading(False)
    self.last_failed = failed
    self.show_finished(done, total_bytes, elapsed, failed)
    if self.on_finished:
      self.on_finished()

  def start_episode(self, number):
    self.current_episode = number
    self.episode_title.configure(text=f"Episodio {number}")
    self.episode_detail.configure(text="preparazione…")
    self.episode_bar.set(0)
    self.episode_size.configure(text="")

  def update_series_progress(self, done, total):
    self.series_detail.configure(text=f"{done} di {total} episodi")
    self.series_bar.set(done / total)

  def update_episode_progress(self, percentage, downloaded, file_size, speed, remaining_time):
    speed_text = f"{speed / (1024 * 1024):.1f}".replace(".", ",")
    self.episode_detail.configure(text=f"{percentage:.0f}% · {speed_text} MB/s · {format_eta(remaining_time)} rimanenti")
    self.episode_bar.set(percentage / 100)
    if file_size:
      self.episode_size.configure(text=f"{format_size(downloaded)} di {format_size(file_size)}")

  def on_close(self):
    if self.downloading:
      episode = f"l'episodio {self.current_episode}" if self.current_episode else "l'episodio in corso"
      confirmed = ConfirmDialog(self, "Il download è ancora in corso",
                                f"Se chiudi ora, {episode} verrà interrotto e il file parziale eliminato. "
                                "Gli episodi già scaricati restano nella cartella.",
                                "Interrompi e chiudi", "Continua il download").show()
      if not confirmed:
        return
      self.cancel_event.set()
      self.set_downloading(False)
    self.destroy()
