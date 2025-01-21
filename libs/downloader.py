import os
from bs4 import BeautifulSoup
import requests
from threading import Thread
import time

import httpx

WEBSITE = "https://www.animeworld.so"

def generate_client():
  session = httpx.Client()

  headers = { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36" }

  session.headers.update(headers)
  csrf_token = re.compile(br'<meta.*?id="csrf-token"\s*?content="(.*?)">')
  cookie = re.compile(br'document\.cookie\s*?=\s*?"(.+?)=(.+?)(\s*?;\s*?path=.+?)?"\s*?;')

  for _ in range(2):
    res = session.get(WEBSITE, follow_redirects=True)

    m = cookie.search(res.content)
    if m:
      session.cookies.update({m.group(1).decode('utf-8'): m.group(2).decode('utf-8')})
      continue

    m = csrf_token.search(res.content)
    if m:
      session.headers.update({'csrf-token': m.group(1).decode('utf-8')})
      break
  return session


def download_chunk(url, start, end, chunk_num, output_folder, progress_dict):
  headers = {'Range': f'bytes={start}-{end}'}
  response = requests.get(url, headers=headers, stream=True)
  chunk_path = os.path.join(output_folder, f"chunk_{chunk_num}.tmp")
  
  total_downloaded = 0
  with open(chunk_path, "wb") as f:
    for data in response.iter_content(chunk_size=8192):
      f.write(data)
      total_downloaded += len(data)
      progress_dict[chunk_num] = total_downloaded


def download_file_multithread(url, output_file, num_threads=13):
  """
    ## Scarica un file utilizzando download multithread.

    Args:
        url (str): URL del file da scaricare.
        output_file (str): Percorso dove salvare il file scaricato.
        num_threads (int): Numero di thread da utilizzare.

    Returns:
        None
    """
  response = requests.head(url)
  if 'Content-Length' not in response.headers:
    print("Il server non supporta il download parziale (Range).")
    return

  file_size = int(response.headers['Content-Length'])
  chunk_size = file_size // num_threads
  output_folder = os.path.dirname(output_file)
  os.makedirs(output_folder, exist_ok=True)

  # Dizionario per tracciare i progressi di ogni thread
  progress_dict = {i: 0 for i in range(num_threads)}
  threads = []

  start_time = time.time()

  for i in range(num_threads):
    start = i * chunk_size
    end = (start + chunk_size - 1) if i < num_threads - 1 else file_size - 1
    thread = Thread(target=download_chunk, args=(url, start, end, i, output_folder, progress_dict))
    threads.append(thread)
    thread.start()

  while any(thread.is_alive() for thread in threads):
    downloaded = sum(progress_dict.values())
    elapsed_time = time.time() - start_time
    speed = downloaded / elapsed_time if elapsed_time > 0 else 0
    percentage = (downloaded / file_size) * 100
    remaining_time = (file_size - downloaded) / speed if speed > 0 else float('inf')

    print(f"\rScaricato: {percentage:.2f}% | Velocità: {speed / 1024:.2f} KB/s | Tempo rimanente: {remaining_time:.2f} s", end="")

  print("\n")

  for thread in threads:
    thread.join()

  # Combina tutti i chunk in un unico file
  with open(output_file, "wb") as output:
    for i in range(num_threads):
      chunk_path = os.path.join(output_folder, f"chunk_{i}.tmp")
      with open(chunk_path, "rb") as chunk:
          output.write(chunk.read())
      os.remove(chunk_path)

  print(f"\nDownload completato. File salvato in: {output_file}")

import re

def download_episodes(link, name, episode_number=1):
  print(f"Downloading {name} episode {episode_number} from {link}")
  response = generate_client().get(link, follow_redirects=True)
  print(response)
  if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')
    link_tag = soup.find('a', id="alternativeDownloadLink")
    if link_tag:
      link = link_tag.get('href')
      print(f"Link trovato: {link}")
      while True:
        if requests.head(link).status_code != 200:
          break
        download_file_multithread(link, "./downloads/"+name+"/"+str(episode_number)+".mp4")
        episode_number += 1
        link = re.sub(r"_(\d+)_", lambda m: f"_{int(m.group(1)) + 1:02}_", link)
    else:
      print("Nessun link trovato contenente 'Download subito'.")
      print(link_tag)
  else:
    print("Errore durante il download.")

