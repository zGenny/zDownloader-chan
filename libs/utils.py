import math
import os
import platform
import re
import subprocess
import sys
import tkinter

import httpx
import requests
from .config import config

# Caratteri non ammessi nei nomi di file/cartelle (Windows è il più restrittivo)
INVALID_PATH_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def generate_client():
  """
  Genera e configura un client httpx con headers e cookie/token CSRF.
  
  Utilizza la configurazione centralizzata per base_url e user_agent.
  
  Returns:
      httpx.Client: Client HTTP configurato
  """
  session = httpx.Client(timeout=30)

  headers = {"User-Agent": config.get_user_agent()}

  session.headers.update(headers)
  csrf_token = re.compile(br'<meta.*?id="csrf-token"\s*?content="(.*?)">')
  cookie = re.compile(br'document\.cookie\s*?=\s*?"(.+?)=(.+?)(\s*?;\s*?path=.+?)?"\s*?;')

  # Ottiene l'URL base dalla configurazione centralizzata
  base_url = config.get_base_url()

  for _ in range(2):
    res = session.get(base_url, follow_redirects=True)

    m = cookie.search(res.content)
    if m:
      session.cookies.update({m.group(1).decode('utf-8'): m.group(2).decode('utf-8')})
      continue

    m = csrf_token.search(res.content)
    if m:
      session.headers.update({'csrf-token': m.group(1).decode('utf-8')})
      break
  return session


def sanitize_filename(name, fallback="ND"):
  """Rimuove i caratteri non validi per un nome di file/cartella."""
  if name is None:
    return fallback
  cleaned = INVALID_PATH_CHARS.sub('', str(name))
  cleaned = re.sub(r'\s+', ' ', cleaned).strip().rstrip('. ')
  return cleaned or fallback


def anime_folder_name(name, year):
  """Nome della cartella in cui viene salvata una serie: 'Titolo(Anno)'."""
  return f"{sanitize_filename(name)}({sanitize_filename(year)})"


def with_session_retry(func, client=None):
  """
  Esegue func(client); se fallisce per un errore di rete crea una nuova sessione e riprova una volta.

  I cookie anti-bot del sito scadono: durante le operazioni lunghe una sessione nuova risolve.

  Returns:
      tuple: (risultato, client usato), così il chiamante può continuare con la sessione buona
  """
  client = client or generate_client()
  try:
    return func(client), client
  except httpx.HTTPError as e:
    print(f"Errore di rete ({e}), riprovo con una nuova sessione")
    client = generate_client()
    return func(client), client


def episode_value(number):
  """Valore numerico di un episodio del sito ('12' -> 12, '5.5' -> 5.5, '268-269' -> 268), None se manca."""
  match = re.match(r'\s*(\d+(?:[.,]\d+)?)', str(number))
  return float(match.group(1).replace(",", ".")) if match else None


def format_episode_number(number):
  """Numero di episodio per il nome del file, con almeno due cifre: '1' -> '01', '5.5' -> '05.5'."""
  match = re.match(r'^(\d+)(.*)$', str(number))
  if not match:
    return sanitize_filename(number)
  return f"{int(match.group(1)):02}{sanitize_filename(match.group(2), fallback='')}"


def split_folder_name(folder):
  """Divide 'Titolo(Anno)' in (titolo, anno); l'anno è '' se manca."""
  match = re.match(r'^(.*)\(([^()]*)\)$', folder)
  return (match.group(1), match.group(2)) if match else (folder, "")


def downloaded_titles(downloads_dir="downloads"):
  """Restituisce i titoli (sanificati, senza anno) delle serie già presenti nella cartella dei download."""
  if not os.path.isdir(downloads_dir):
    return set()
  return {split_folder_name(folder)[0] for folder in os.listdir(downloads_dir)}


def library_entries(downloads_dir="downloads"):
  """Serie scaricate, dalla più recente: titolo, anno, cartella, numero di episodi, dimensione e locandina."""
  if not os.path.isdir(downloads_dir):
    return []
  entries = []
  for folder in os.listdir(downloads_dir):
    path = os.path.join(downloads_dir, folder)
    if not os.path.isdir(path):
      continue
    title, year = split_folder_name(folder)
    videos = [os.path.join(path, name) for name in os.listdir(path) if name.lower().endswith(".mp4")]
    poster = os.path.join(path, "poster.jpg")
    entries.append({
      "title": title,
      "year": year,
      "path": path,
      "episodes": len(videos),
      "size": sum(os.path.getsize(video) for video in videos),
      "poster": poster if os.path.exists(poster) else None,
      "modified": os.path.getmtime(path),
    })
  return sorted(entries, key=lambda entry: entry["modified"], reverse=True)


def is_wsl():
  """True se il programma gira dentro WSL (Linux su Windows)."""
  return "WSL_DISTRO_NAME" in os.environ or "microsoft" in platform.uname().release.lower()


def open_folder(path):
  """Apre una cartella nel gestore file del sistema (su WSL in Esplora file di Windows)."""
  os.makedirs(path, exist_ok=True)
  try:
    if sys.platform.startswith("win"):
      os.startfile(os.path.abspath(path))
    elif sys.platform == "darwin":
      subprocess.Popen(["open", path])
    elif is_wsl():
      # In WSL di solito non c'è un gestore file Linux: si usa Esplora file con il percorso in formato Windows
      windows_path = subprocess.run(["wslpath", "-w", os.path.abspath(path)], capture_output=True, text=True,
                                    check=True).stdout.strip()
      subprocess.Popen(["explorer.exe", windows_path])
    else:
      subprocess.Popen(["xdg-open", path])
  except (OSError, subprocess.CalledProcessError) as e:
    print(f"Impossibile aprire la cartella {path}: {e}")


def format_size(size):
  """Dimensione leggibile in italiano, es. '9,8 GB' o '400 MB'."""
  if size >= 1024 ** 3:
    return f"{size / 1024 ** 3:.1f} GB".replace(".", ",")
  if size >= 1024 ** 2:
    return f"{size / 1024 ** 2:.0f} MB"
  return f"{size / 1024:.0f} KB"


def format_eta(seconds):
  """Tempo rimanente come mm:ss (o h:mm:ss)."""
  if seconds is None or math.isinf(seconds) or math.isnan(seconds):
    return "--:--"
  seconds = int(seconds)
  hours, rest = divmod(seconds, 3600)
  minutes, seconds = divmod(rest, 60)
  return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes:02}:{seconds:02}"


def format_elapsed(seconds):
  """Durata a parole, es. '45 secondi', '21 minuti', '1 h 05 min'."""
  seconds = int(seconds)
  if seconds < 60:
    return "1 secondo" if seconds == 1 else f"{seconds} secondi"
  if seconds < 3600:
    minutes = seconds // 60
    return "1 minuto" if minutes == 1 else f"{minutes} minuti"
  return f"{seconds // 3600} h {seconds % 3600 // 60:02} min"


def format_number(value):
  """Numero con il separatore delle migliaia italiano, es. 745.983."""
  try:
    return f"{int(value):,}".replace(",", ".")
  except (TypeError, ValueError):
    return str(value)


def fetch_image_data(url):
  """Scarica un'immagine e ne restituisce i byte, None in caso di errore."""
  try:
    response = requests.get(url, timeout=15)
  except requests.RequestException:
    return None
  return response.content if response.status_code == 200 else None


def run_on_ui(widget, func):
  """Esegue func nel thread di Tkinter; ignora la chiamata se la finestra è stata chiusa."""
  def safe_call():
    try:
      if widget.winfo_exists():
        func()
    except tkinter.TclError:
      pass
  try:
    widget.after(0, safe_call)
  except (RuntimeError, tkinter.TclError):
    pass
