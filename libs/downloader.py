import os
import shutil
import time
from threading import Event, Thread

import requests
from bs4 import BeautifulSoup

from .config import config
from .utils import generate_client

REQUEST_TIMEOUT = 30
CHUNK_RETRIES = 3


class DownloadError(Exception):
  pass


class DownloadCancelled(Exception):
  pass


class AnimeNotFound(Exception):
  pass


class AnimeNotAvailable(Exception):
  pass


def probe_range_support(url):
  """
  Verifica se il server supporta le richieste Range.

  Returns:
      tuple: (supporta_range, dimensione_file) - la dimensione è 0 se sconosciuta
  """
  with requests.get(url, headers={'Range': 'bytes=0-0'}, stream=True, timeout=REQUEST_TIMEOUT) as response:
    response.raise_for_status()
    content_range = response.headers.get('Content-Range', '')
    if response.status_code == 206 and '/' in content_range:
      total = content_range.rsplit('/', 1)[1]
      if total.isdigit():
        return True, int(total)
    return False, int(response.headers.get('Content-Length', 0))


def download_chunk(url, start, end, chunk_path, chunk_num, progress_dict, errors, cancel_event):
  headers = {'Range': f'bytes={start}-{end}'}
  expected = end - start + 1

  for attempt in range(1, CHUNK_RETRIES + 1):
    progress_dict[chunk_num] = 0
    try:
      with requests.get(url, headers=headers, stream=True, timeout=REQUEST_TIMEOUT) as response:
        # Un 200 significherebbe che il server ha ignorato il Range e sta inviando il file intero
        if response.status_code != 206:
          raise DownloadError(f"risposta {response.status_code} invece di 206")
        total_downloaded = 0
        with open(chunk_path, "wb") as f:
          for data in response.iter_content(chunk_size=8192):
            if cancel_event.is_set():
              return
            f.write(data)
            total_downloaded += len(data)
            progress_dict[chunk_num] = total_downloaded
      if total_downloaded != expected:
        raise DownloadError(f"blocco incompleto ({total_downloaded} di {expected} byte)")
      return
    except (requests.RequestException, DownloadError, OSError) as e:
      print(f"Blocco {chunk_num}, tentativo {attempt}/{CHUNK_RETRIES} fallito: {e}")
      if attempt == CHUNK_RETRIES or cancel_event.is_set():
        errors[chunk_num] = str(e)


def download_file_single(url, output_file, update_ui_callback=None, cancel_event=None):
  """Scarica un file con una sola connessione (server senza supporto Range)."""
  start_time = time.time()
  downloaded = 0
  with requests.get(url, stream=True, timeout=REQUEST_TIMEOUT) as response:
    response.raise_for_status()
    file_size = int(response.headers.get('Content-Length', 0))
    last_update = 0
    with open(output_file, "wb") as f:
      for data in response.iter_content(chunk_size=8192):
        if cancel_event and cancel_event.is_set():
          raise DownloadCancelled()
        f.write(data)
        downloaded += len(data)
        now = time.time()
        if update_ui_callback and now - last_update > 0.1:
          last_update = now
          speed = downloaded / (now - start_time) if now > start_time else 0
          percentage = (downloaded / file_size) * 100 if file_size else 0
          remaining_time = (file_size - downloaded) / speed if speed > 0 and file_size else float('inf')
          update_ui_callback(percentage, downloaded, file_size, speed, remaining_time)
  if file_size and downloaded != file_size:
    raise DownloadError(f"file incompleto ({downloaded} di {file_size} byte)")
  return downloaded


def download_file_multithread(url, output_file, num_threads=5, update_ui_callback=None, cancel_event=None):
  """
    ## Scarica un file utilizzando download multithread.

    Se il server non supporta le richieste Range il file viene scaricato con una sola connessione.

    Args:
        url (str): URL del file da scaricare.
        output_file (str): Percorso dove salvare il file scaricato.
        num_threads (int): Numero di thread da utilizzare.
        update_ui_callback (callable): Chiamata con (percentuale, scaricati, totale, velocità, tempo rimanente).
        cancel_event (threading.Event): Se impostato, il download viene interrotto.

    Raises:
        DownloadCancelled: se il download viene annullato tramite cancel_event.
        DownloadError, requests.RequestException, OSError: se il download fallisce.
    """
  cancel_event = cancel_event or Event()
  output_folder = os.path.dirname(output_file)
  os.makedirs(output_folder, exist_ok=True)
  part_file = output_file + ".part"
  start_time = time.time()

  supports_range, file_size = probe_range_support(url)
  if not supports_range or file_size == 0:
    print("Il server non supporta il download parziale (Range), uso una sola connessione.")
    try:
      file_size = download_file_single(url, part_file, update_ui_callback, cancel_event)
      os.replace(part_file, output_file)
    finally:
      if os.path.exists(part_file):
        os.remove(part_file)
    if update_ui_callback:
      update_ui_callback(100, file_size, file_size, 0, 0)
    return

  num_threads = max(1, min(num_threads, file_size))
  chunk_size = file_size // num_threads
  base_name = os.path.basename(output_file)
  chunk_paths = [os.path.join(output_folder, f"{base_name}.chunk{i}.tmp") for i in range(num_threads)]

  # Dizionario per tracciare i progressi di ogni thread
  progress_dict = {i: 0 for i in range(num_threads)}
  errors = {}
  threads = []

  for i in range(num_threads):
    start = i * chunk_size
    end = (start + chunk_size - 1) if i < num_threads - 1 else file_size - 1
    thread = Thread(target=download_chunk, args=(url, start, end, chunk_paths[i], i, progress_dict, errors, cancel_event))
    threads.append(thread)
    thread.start()

  speed = 0
  while any(thread.is_alive() for thread in threads):
    downloaded = sum(progress_dict.values())
    elapsed_time = time.time() - start_time
    speed = downloaded / elapsed_time if elapsed_time > 0 else 0
    percentage = (downloaded / file_size) * 100
    remaining_time = (file_size - downloaded) / speed if speed > 0 else float('inf')
    if update_ui_callback:
      update_ui_callback(percentage, downloaded, file_size, speed, remaining_time)
    time.sleep(0.1)

  for thread in threads:
    thread.join()

  try:
    if cancel_event.is_set():
      raise DownloadCancelled()
    if errors:
      raise DownloadError("; ".join(f"blocco {i}: {msg}" for i, msg in sorted(errors.items())))

    # Combina tutti i chunk in un unico file
    with open(part_file, "wb") as output:
      for chunk_path in chunk_paths:
        with open(chunk_path, "rb") as chunk:
          shutil.copyfileobj(chunk, output)
    os.replace(part_file, output_file)
  finally:
    for path in chunk_paths + [part_file]:
      if os.path.exists(path):
        os.remove(path)

  if update_ui_callback:
    update_ui_callback(100, file_size, file_size, speed, 0)  # Final update to 100%

  print(f"\nDownload completato. File salvato in: {output_file}")


def get_anime_info(name, jname, client=None):
  """
  Recupera le informazioni dettagliate di un anime tramite l'API JSON.

  Args:
      name (str): Nome italiano dell'anime
      jname (str): Nome giapponese dell'anime
      client (httpx.Client): Client da riutilizzare; se None ne viene creato uno

  Returns:
      dict: Dizionario con le informazioni dell'anime, None se non trovato
  """
  s = client or generate_client()
  # Utilizza l'endpoint API dalla configurazione centralizzata
  api_endpoint = config.get_api_endpoint()
  response = s.post(api_endpoint, params={"keyword": name}, follow_redirects=True)
  try:
    data = response.json()["animes"]
  except (ValueError, KeyError, TypeError):
    return None
  for anime in data:
    if anime["name"] == jname or anime["jtitle"] == name or anime["name"] == name or anime["jtitle"] == jname:
      return anime

  return None


def get_episodes(link, client=None):
  """
  Legge dalla pagina di un anime i suoi episodi, in ordine.

  Il link diretto al file si ottiene poi con resolve_episode_link: farlo solo per gli
  episodi da scaricare evita centinaia di richieste per le serie lunghe.

  Returns:
      list: Coppie (numero, id). Il numero è quello del sito ed è una stringa, perché può
            partire da 0 o essere composto (es. "5.5", "268-269")

  Raises:
      AnimeNotFound: la pagina non esiste (il sito risponde 200 con "Errore 404")
      AnimeNotAvailable: l'anime è in elenco ma non ha ancora episodi
  """
  client = client or generate_client()
  response = client.get(link, follow_redirects=True)
  response.raise_for_status()
  if 'Errore 404' in response.text:
    raise AnimeNotFound(link)
  soup = BeautifulSoup(response.text, 'html.parser')
  if soup.find('span', class_='servers-tabs') is None:
    raise AnimeNotAvailable(link)

  # Lo stesso episodio compare in più liste (una per server): si tiene il primo
  episodes = {}
  for link_tag in soup.select('li.episode > a'):
    if link_tag.get("data-id"):
      number = link_tag.get("data-episode-num") or str(len(episodes) + 1)
      episodes.setdefault(link_tag.get("data-episode-id"), (number, link_tag.get("data-id")))
  return list(episodes.values())


def resolve_episode_link(episode_id, client):
  """
  Restituisce il link diretto al file di un episodio, None se il sito non lo fornisce.

  La pagina dell'episodio non contiene il link: lo restituisce l'API episode/info (campo "grabber").
  """
  response = client.get(config.get_episode_info_endpoint(), params={"id": episode_id, "alt": "0"}, follow_redirects=True)
  try:
    return response.json().get("grabber") or None
  except ValueError:
    return None

