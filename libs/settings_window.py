"""Finestra delle impostazioni: vista dei risultati, lingua dei titoli, connessioni e cartella dei download."""

import os
import tkinter
import tkinter.filedialog

import customtkinter

from . import theme as t
from .settings import settings
from .widgets import ToggleGroup, primary_button, secondary_button, set_window_icon


class SettingsDialog(customtkinter.CTkToplevel):
  def __init__(self, parent, on_saved=None):
    super().__init__(parent)
    self.on_saved = on_saved
    self.title("Impostazioni")
    self.configure(fg_color=t.SURFACE)
    self.resizable(False, False)
    self.transient(parent)
    set_window_icon(self)
    self.protocol("WM_DELETE_WINDOW", self.destroy)
    self.bind("<Escape>", lambda event: self.destroy())

    body = customtkinter.CTkFrame(self, fg_color="transparent")
    body.pack(padx=28, pady=24, fill="both", expand=True)
    customtkinter.CTkLabel(body, text="Impostazioni", font=t.font(22, True), text_color=t.TEXT).pack(anchor="w", pady=(0, 8))

    self.view_toggle = ToggleGroup(self.section(body, "Vista dei risultati", "Puoi cambiarla anche sopra i risultati."),
                                   [("list", "Lista", t.icon("list", t.TEXT, 16)), ("grid", "Griglia", t.icon("grid", t.TEXT, 16))],
                                   settings.get("view_mode"))
    self.view_toggle.pack(anchor="w")

    self.language_toggle = ToggleGroup(self.section(body, "Lingua dei titoli", "La ricerca trova l'anime con entrambi i titoli."),
                                       [("it", "Italiano", t.flag("it")), ("jp", "Giapponese", t.flag("jp"))],
                                       settings.get("title_language"))
    self.language_toggle.pack(anchor="w")

    self.threads_var = customtkinter.StringVar(value=str(settings.get("threads")))
    threads_section = self.section(body, "Connessioni per episodio",
                                   "Più connessioni scaricano più in fretta, ma alcuni server limitano le richieste.")
    customtkinter.CTkOptionMenu(threads_section, variable=self.threads_var, values=[str(i) for i in range(1, 13)],
                                width=80, height=36, corner_radius=8, fg_color=t.SURFACE_2, button_color=t.SURFACE_2,
                                button_hover_color=t.SELECTED, text_color=t.TEXT, font=t.font(14, True),
                                dropdown_font=t.font(13)).pack(anchor="w")

    folder_section = self.section(body, "Cartella dei download", "Ogni serie viene salvata in una sottocartella 'Titolo(Anno)'.")
    folder_row = customtkinter.CTkFrame(folder_section, fg_color="transparent")
    folder_row.pack(anchor="w", fill="x")
    self.folder_entry = customtkinter.CTkEntry(folder_row, width=330, height=36, corner_radius=8, border_width=1,
                                               border_color=t.NEUTRAL_BG, fg_color=t.SURFACE_2, text_color=t.TEXT,
                                               font=t.font(13))
    self.folder_entry.insert(0, settings.get("download_dir"))
    self.folder_entry.pack(side="left")
    secondary_button(folder_row, "Sfoglia…", command=self.browse, height=36, width=0).pack(side="left", padx=(10, 0))

    self.error_label = customtkinter.CTkLabel(body, text="", font=t.font(13), text_color=t.DANGER_FG)
    self.error_label.pack(anchor="w", pady=(12, 0))

    footer = customtkinter.CTkFrame(body, fg_color="transparent")
    footer.pack(anchor="e", pady=(8, 0))
    secondary_button(footer, "Annulla", command=self.destroy).pack(side="left", padx=(0, 12))
    primary_button(footer, "Salva", command=self.save).pack(side="left")

  def section(self, master, title, hint):
    frame = customtkinter.CTkFrame(master, fg_color="transparent")
    frame.pack(anchor="w", fill="x", pady=(14, 0))
    customtkinter.CTkLabel(frame, text=title, font=t.font(14, True), text_color=t.TEXT, height=20).pack(anchor="w")
    customtkinter.CTkLabel(frame, text=hint, font=t.font(12), text_color=t.TEXT_MUTED, height=18).pack(anchor="w", pady=(0, 6))
    return frame

  def browse(self):
    current = self.folder_entry.get().strip()
    folder = tkinter.filedialog.askdirectory(parent=self, initialdir=current if os.path.isdir(current) else os.getcwd(),
                                             title="Scegli la cartella dei download")
    if folder:
      self.folder_entry.delete(0, "end")
      self.folder_entry.insert(0, folder)

  def save(self):
    folder = self.folder_entry.get().strip()
    if not folder:
      self.error_label.configure(text="Scegli una cartella per i download.")
      return
    settings.update(view_mode=self.view_toggle.value, title_language=self.language_toggle.value,
                    threads=int(self.threads_var.get()), download_dir=folder)
    if self.on_saved:
      self.on_saved()
    self.destroy()

  def _grab(self):
    try:
      self.lift()
      self.focus_force()
      self.grab_set()
    except tkinter.TclError:
      self.after(100, self._grab)

  def show(self):
    self.after(50, self._grab)
