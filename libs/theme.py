"""
Colori, font e icone dell'interfaccia.

Le icone e le bandiere vengono disegnate con PIL a risoluzione doppia, così non servono
file immagine aggiuntivi e restano nitide anche con lo scaling di Windows.
"""

import math
import os
from functools import lru_cache

import customtkinter
from PIL import Image, ImageDraw, ImageFont

# Colori (derivati dal tema MoonLight)
BG = "#1E1F20"
SURFACE = "#262729"
SURFACE_2 = "#343638"
BORDER = "#3A3D40"
BORDER_STRONG = "#565B5E"
SELECTED = "#4A4D50"
SKELETON = "#3A3D40"
SKELETON_DIM = "#333537"
TEXT = "#DCE4EE"
TEXT_STRONG = "#F9F9FA"
TEXT_SOFT = "#B4BBC2"
TEXT_MUTED = "#979DA2"
ACCENT = "#FF6505"
ACCENT_HOVER = "#CC5500"
ACCENT_SOFT = "#FF8C42"
ACCENT_DISABLED = "#6B3A1C"
ON_ACCENT = "#111111"
ON_ACCENT_DISABLED = "#F2D2BD"
DUB_BG = "#3A2A1F"
NEUTRAL_BG = "#3E454A"
OWNED_BG = "#2E2A22"
OWNED_BORDER = "#5A4A2A"
OWNED_FG = "#FFC266"
DANGER_FG = "#FF9A8A"
DANGER_BORDER = "#8A3A2E"
DANGER_BG = "#2A2422"

FONT_FAMILY = "Nunito"
FONTS_DIR = "fonts"


def load_fonts():
  """Registra i font inclusi nel progetto; va chiamata prima di creare la finestra."""
  if not os.path.isdir(FONTS_DIR):
    return
  for name in os.listdir(FONTS_DIR):
    if name.lower().endswith(".ttf"):
      customtkinter.FontManager.load_font(os.path.join(FONTS_DIR, name))


@lru_cache(maxsize=None)
def font(size, bold=False):
  return customtkinter.CTkFont(family=FONT_FAMILY, size=size, weight="bold" if bold else "normal")


# Icone

SCALE = 4  # disegno a risoluzione maggiore e poi riduco, per avere i bordi sfumati


def _canvas(size):
  image = Image.new("RGBA", (size * SCALE, size * SCALE), (0, 0, 0, 0))
  return image, ImageDraw.Draw(image)


def _finish(image, size):
  return image.resize((size * 2, size * 2), Image.LANCZOS)


def _draw_search(draw, s, color, w):
  r = s * 0.3
  cx = cy = s * 0.42
  draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=w)
  draw.line((cx + r * 0.72, cy + r * 0.72, s * 0.86, s * 0.86), fill=color, width=w)


def _draw_gear(draw, s, color, w):
  c = s / 2
  for i in range(8):
    angle = i * math.pi / 4
    x1, y1 = c + math.cos(angle) * s * 0.26, c + math.sin(angle) * s * 0.26
    x2, y2 = c + math.cos(angle) * s * 0.44, c + math.sin(angle) * s * 0.44
    draw.line((x1, y1, x2, y2), fill=color, width=int(w * 1.6))
  r = s * 0.3
  draw.ellipse((c - r, c - r, c + r, c + r), outline=color, width=w)
  r = s * 0.11
  draw.ellipse((c - r, c - r, c + r, c + r), outline=color, width=w)


def _draw_list(draw, s, color, w):
  for y in (0.25, 0.5, 0.75):
    draw.ellipse((s * 0.12, s * y - w, s * 0.12 + 2 * w, s * y + w), fill=color)
    draw.line((s * 0.34, s * y, s * 0.88, s * y), fill=color, width=w)


def _draw_grid(draw, s, color, w):
  for x in (0.14, 0.56):
    for y in (0.14, 0.56):
      draw.rounded_rectangle((s * x, s * y, s * (x + 0.3), s * (y + 0.3)), radius=s * 0.06, outline=color, width=w)


def _draw_folder(draw, s, color, w):
  draw.line([(s * 0.1, s * 0.78), (s * 0.1, s * 0.22), (s * 0.38, s * 0.22), (s * 0.48, s * 0.34),
             (s * 0.9, s * 0.34), (s * 0.9, s * 0.78), (s * 0.1, s * 0.78)], fill=color, width=w, joint="curve")


def _draw_check(draw, s, color, w):
  draw.line([(s * 0.2, s * 0.52), (s * 0.42, s * 0.74), (s * 0.82, s * 0.28)], fill=color, width=w, joint="curve")


def _draw_download(draw, s, color, w):
  draw.line((s * 0.5, s * 0.14, s * 0.5, s * 0.64), fill=color, width=w)
  draw.line([(s * 0.28, s * 0.44), (s * 0.5, s * 0.66), (s * 0.72, s * 0.44)], fill=color, width=w, joint="curve")
  draw.line((s * 0.18, s * 0.86, s * 0.82, s * 0.86), fill=color, width=w)


def _draw_warning(draw, s, color, w):
  draw.line([(s * 0.5, s * 0.12), (s * 0.92, s * 0.86), (s * 0.08, s * 0.86), (s * 0.5, s * 0.12)], fill=color, width=w, joint="curve")
  draw.line((s * 0.5, s * 0.4, s * 0.5, s * 0.62), fill=color, width=w)
  draw.ellipse((s * 0.5 - w * 0.7, s * 0.74 - w * 0.7, s * 0.5 + w * 0.7, s * 0.74 + w * 0.7), fill=color)


ICONS = {
  "search": _draw_search,
  "gear": _draw_gear,
  "list": _draw_list,
  "grid": _draw_grid,
  "folder": _draw_folder,
  "check": _draw_check,
  "download": _draw_download,
  "warning": _draw_warning,
}


@lru_cache(maxsize=None)
def icon(name, color=TEXT, size=18, stroke=0.1):
  image, draw = _canvas(size)
  s = size * SCALE
  ICONS[name](draw, s, color, max(2, int(s * stroke)))
  return customtkinter.CTkImage(_finish(image, size), size=(size, size))


def flag_image(country, height):
  """Bandierina 3:2 con angoli arrotondati come immagine PIL alta height pixel: 'it' (Italia) o 'jp' (Giappone)."""
  width = round(height * 1.5)
  w, h = width * SCALE, height * SCALE
  image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
  draw = ImageDraw.Draw(image)
  if country == "it":
    for i, color in enumerate(("#009246", "#F1F2F1", "#CE2B37")):
      draw.rectangle((w * i / 3, 0, w * (i + 1) / 3, h), fill=color)
  else:
    draw.rectangle((0, 0, w, h), fill="#F1F2F1")
    r = h * 0.3
    draw.ellipse((w / 2 - r, h / 2 - r, w / 2 + r, h / 2 + r), fill="#BC002D")
  mask = Image.new("L", (w, h), 0)
  ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=h * 0.18, fill=255)
  image.putalpha(mask)
  return image.resize((width, height), Image.LANCZOS)


@lru_cache(maxsize=None)
def flag(country, height=12):
  return customtkinter.CTkImage(flag_image(country, height * 2), size=(round(height * 1.5), height))


def badge_image(text, bg, fg, country=None, scale=2):
  """
  Badge disegnato come immagine PIL con angoli trasparenti.

  Serve quando il badge sta sopra una copertina: un widget Tk riempirebbe gli angoli
  arrotondati con il colore di sfondo, lasciando un rettangolo visibile.
  """
  try:
    text_font = ImageFont.truetype(os.path.join(FONTS_DIR, "Nunito-Bold.ttf"), 11 * scale)
  except OSError:
    text_font = ImageFont.load_default(11 * scale)
  text_width = text_font.getlength(text)
  left = (7 + 15 + 5) * scale if country else 8 * scale
  width, height = round(left + text_width + 8 * scale), 22 * scale
  image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
  draw = ImageDraw.Draw(image)
  draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=6 * scale, fill=bg)
  if country:
    image.alpha_composite(flag_image(country, 10 * scale), (7 * scale, 6 * scale))
  draw.text((left, height / 2), text, font=text_font, fill=fg, anchor="lm")
  return image


@lru_cache(maxsize=None)
def check_badge(size=64):
  """Cerchio arancione con la spunta, usato nella schermata di download completato."""
  image, draw = _canvas(size)
  s = size * SCALE
  draw.ellipse((0, 0, s - 1, s - 1), fill=ACCENT)
  draw.line([(s * 0.3, s * 0.52), (s * 0.45, s * 0.67), (s * 0.72, s * 0.36)], fill=ON_ACCENT, width=int(s * 0.08), joint="curve")
  return customtkinter.CTkImage(_finish(image, size), size=(size, size))
