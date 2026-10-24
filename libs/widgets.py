"""Widget riutilizzabili dell'interfaccia (badge, gruppi di pulsanti, copertine, dialog)."""

import sys
import tkinter
from io import BytesIO

import customtkinter
from PIL import Image, ImageDraw, ImageOps, ImageTk, UnidentifiedImageError

from . import theme as t


def set_window_icon(window, path="icons/icon.ico"):
  """Imposta l'icona della finestra; su Linux il formato .ico non è supportato da iconbitmap."""
  if sys.platform.startswith("win"):
    def apply():
      try:
        window.iconbitmap(path)
      except tkinter.TclError:
        pass
    # CustomTkinter imposta la sua icona dopo 200 ms: la mia va applicata dopo
    window.after(250, apply)
    return
  try:
    photo = ImageTk.PhotoImage(Image.open(path), master=window)
    window.wm_iconphoto(False, photo)
    window._window_icon = photo
  except (OSError, tkinter.TclError):
    pass


def primary_button(master, text, command=None, image=None, height=44, **kwargs):
  return customtkinter.CTkButton(master, text=text, command=command, image=image, compound="left", height=height,
                                 corner_radius=height // 2, fg_color=t.ACCENT, hover_color=t.ACCENT_HOVER,
                                 text_color=t.ON_ACCENT, text_color_disabled=t.ON_ACCENT_DISABLED,
                                 font=t.font(15, True), **kwargs)


def secondary_button(master, text, command=None, image=None, height=44, **kwargs):
  return customtkinter.CTkButton(master, text=text, command=command, image=image, compound="left", height=height,
                                 corner_radius=height // 2, fg_color="transparent", hover_color=t.SURFACE_2,
                                 border_width=1, border_color=t.BORDER_STRONG, text_color=t.TEXT,
                                 text_color_disabled=t.TEXT_MUTED, font=t.font(15, True), **kwargs)


def set_primary_enabled(button, enabled):
  button.configure(state="normal" if enabled else "disabled", fg_color=t.ACCENT if enabled else t.ACCENT_DISABLED)


def link_button(master, text, command=None, size=14):
  return customtkinter.CTkButton(master, text=text, command=command, fg_color="transparent", hover_color=t.SURFACE,
                                 text_color=t.ACCENT_SOFT, font=t.font(size, True), width=0, height=28)


class Badge(customtkinter.CTkFrame):
  """Etichetta piccola, opzionalmente con bandierina (es. DUB ITA con il tricolore)."""

  STYLES = {
    "dub": (t.DUB_BG, t.ACCENT_SOFT),
    "neutral": (t.NEUTRAL_BG, t.TEXT),
    "owned": (t.OWNED_BG, t.OWNED_FG),
  }

  def __init__(self, master, text, style="neutral", flag=None):
    bg, fg = self.STYLES[style]
    super().__init__(master, fg_color=bg, corner_radius=6)
    if flag:
      customtkinter.CTkLabel(self, text="", image=t.flag(flag, 10), width=15, height=10).pack(side="left", padx=(7, 0), pady=3)
    customtkinter.CTkLabel(self, text=text, text_color=fg, font=t.font(11, True), height=18).pack(side="left", padx=(5 if flag else 8, 8), pady=2)


def language_badge_spec(dub):
  """Badge della lingua: entrambe le versioni sono in italiano (audio o sottotitoli), quindi hanno il tricolore."""
  return ("DUB ITA", "dub", "it") if dub else ("SUB ITA", "neutral", "it")


def language_badge(master, dub):
  text, style, country = language_badge_spec(dub)
  return Badge(master, text, style, flag=country)


class ToggleGroup(customtkinter.CTkFrame):
  """Pulsanti mutuamente esclusivi a forma di pillola (es. Italiano | Giapponese)."""

  def __init__(self, master, options, value, command=None, height=36, font_size=13):
    # Un raggio pari a metà altezza, con il bordo, lascia angoli scuri: lo tengo appena sotto
    super().__init__(master, fg_color=t.SURFACE_2, corner_radius=height // 2 + 2, border_width=1, border_color=t.NEUTRAL_BG)
    self._command = command
    self._buttons = {}
    for column, (option_value, text, image) in enumerate(options):
      button = customtkinter.CTkButton(self, text=text, image=image, compound="left", height=height,
                                       width=height if not text else 0, corner_radius=height // 2,
                                       font=t.font(font_size, True), border_spacing=6 if text else 0,
                                       command=lambda v=option_value: self._on_click(v))
      button.grid(row=0, column=column, padx=(4 if column == 0 else 0, 4), pady=4)
      self._buttons[option_value] = button
    self.set(value)

  def set(self, value):
    self.value = value
    for option_value, button in self._buttons.items():
      selected = option_value == value
      button.configure(fg_color=t.SELECTED if selected else "transparent", hover_color=t.SELECTED,
                       text_color=t.TEXT_STRONG if selected else t.TEXT_MUTED)

  def _on_click(self, value):
    if value != self.value:
      self.set(value)
      if self._command:
        self._command(value)


class Chip(customtkinter.CTkButton):
  """Filtro attivabile (es. 'Solo DUB ITA')."""

  def __init__(self, master, text, command=None, image=None, selected=False):
    super().__init__(master, text=text, image=image, compound="left", height=30, width=0, corner_radius=15,
                     border_width=1, font=t.font(13, True), command=self._toggle)
    self._on_change = command
    self.set_selected(selected)

  def set_selected(self, selected):
    self.selected = selected
    self.configure(fg_color=t.DUB_BG if selected else "transparent", hover_color=t.SURFACE_2,
                   border_color=t.ACCENT if selected else t.NEUTRAL_BG,
                   text_color=t.ACCENT_SOFT if selected else t.TEXT_SOFT)

  def _toggle(self):
    self.set_selected(not self.selected)
    if self._on_change:
      self._on_change(self.selected)


def _rounded(image, radius):
  mask = Image.new("L", image.size, 0)
  ImageDraw.Draw(mask).rounded_rectangle((0, 0, image.size[0] - 1, image.size[1] - 1), radius=radius, fill=255)
  image = image.convert("RGBA")
  image.putalpha(mask)
  return image


class Cover(customtkinter.CTkLabel):
  """
  Copertina con segnaposto grigio finché l'immagine non arriva.

  badge (testo, stile, bandiera) mostra un Badge nell'angolo in alto a sinistra: sul segnaposto
  è un widget, sopra l'immagine viene disegnato dentro l'immagine stessa per avere angoli trasparenti.
  """

  BADGE_OFFSET = 8

  def __init__(self, master, width, height, radius=8, image_data=None, badge=None, **kwargs):
    super().__init__(master, text="", width=width, height=height, fg_color=t.SKELETON, corner_radius=radius, **kwargs)
    self._cover_size = (width, height)
    self._cover_radius = radius
    self._cover_image = None
    self._badge = badge
    self._badge_widget = None
    if badge:
      text, style, country = badge
      self._badge_widget = Badge(self, text, style, flag=country)
      self._badge_widget.place(x=self.BADGE_OFFSET, y=self.BADGE_OFFSET)
    if image_data is not None:
      self.set_image(image_data)

  def set_image(self, data):
    image = None
    if data:
      try:
        image = Image.open(BytesIO(data))
        image = ImageOps.fit(image.convert("RGB"), (self._cover_size[0] * 2, self._cover_size[1] * 2), Image.LANCZOS)
        image = _rounded(image, self._cover_radius * 2)
      except (UnidentifiedImageError, OSError):
        image = None
    if image is None:
      self.configure(text="Nessuna\ncopertina", text_color=t.TEXT_MUTED, font=t.font(11, True))
      return
    if self._badge:
      text, style, country = self._badge
      bg, fg = Badge.STYLES[style]
      image.alpha_composite(t.badge_image(text, bg, fg, country, scale=2), (self.BADGE_OFFSET * 2, self.BADGE_OFFSET * 2))
      if self._badge_widget is not None:
        self._badge_widget.destroy()
        self._badge_widget = None
    self._cover_image = customtkinter.CTkImage(image, size=self._cover_size)
    # Gli angoli sono già nell'immagine; con corner_radius il CTkLabel aggiungerebbe un margine laterale
    self.configure(image=self._cover_image, fg_color="transparent", text="", corner_radius=0)


class ConfirmDialog(customtkinter.CTkToplevel):
  """Dialog modale di conferma; show() restituisce True se l'utente conferma."""

  def __init__(self, parent, title, message, confirm_text, cancel_text):
    super().__init__(parent)
    self.result = False
    self.title(title)
    self.configure(fg_color=t.SURFACE)
    self.resizable(False, False)
    self.transient(parent.winfo_toplevel())

    body = customtkinter.CTkFrame(self, fg_color="transparent")
    body.pack(padx=28, pady=28, fill="both", expand=True)
    icon_circle = customtkinter.CTkLabel(body, text="", image=t.icon("warning", t.ACCENT_SOFT, 24), width=48, height=48,
                                         fg_color=t.DUB_BG, corner_radius=24)
    icon_circle.pack(anchor="w")
    customtkinter.CTkLabel(body, text=title, font=t.font(20, True), text_color=t.TEXT, anchor="w").pack(anchor="w", pady=(14, 6))
    customtkinter.CTkLabel(body, text=message, font=t.font(14), text_color=t.TEXT_SOFT, justify="left", anchor="w",
                           wraplength=400).pack(anchor="w")

    buttons = customtkinter.CTkFrame(body, fg_color="transparent")
    buttons.pack(anchor="e", pady=(22, 0))
    customtkinter.CTkButton(buttons, text=confirm_text, command=self._confirm, height=44, corner_radius=22,
                            fg_color="transparent", hover_color=t.DANGER_BG, border_width=1, border_color=t.DANGER_BORDER,
                            text_color=t.DANGER_FG, font=t.font(14, True)).pack(side="left", padx=(0, 10))
    cancel = primary_button(buttons, cancel_text, command=self._cancel)
    cancel.pack(side="left")

    self.protocol("WM_DELETE_WINDOW", self._cancel)
    self.bind("<Escape>", lambda event: self._cancel())

  def _confirm(self):
    self.result = True
    self.destroy()

  def _cancel(self):
    self.result = False
    self.destroy()

  def _grab(self):
    try:
      self.lift()
      self.focus_force()
      self.grab_set()
    except tkinter.TclError:
      # La finestra non è ancora visibile: riprovo tra poco
      self.after(100, self._grab)

  def show(self):
    self.after(50, self._grab)
    self.wait_window()
    return self.result
