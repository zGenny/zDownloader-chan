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

def fetch_image(self, url):
  response = requests.get(url)
  if response.status_code == 200:
    return customtkinter.CTkImage(light_image=Image.open(BytesIO(response.content)),
                    dark_image=Image.open(BytesIO(response.content)),
                    size=(100, 150))
  return None

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


def download_file_multithread(url, output_file, num_threads=5, update_ui_callback=None):
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
    if update_ui_callback:
      update_ui_callback(percentage, downloaded, file_size, speed, remaining_time)
    time.sleep(0.02)

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
  if update_ui_callback:
    update_ui_callback(100, file_size, file_size, speed, 0)  # Final update to 100%

  print(f"\nDownload completato. File salvato in: {output_file}")

import re
import customtkinter
import requests
from PIL import Image, ImageTk
from io import BytesIO

def get_anime_info(name, jname):
  s = generate_client()
  response = s.post("https://www.animeworld.so/api/search/v2?", params = {"keyword": name}, follow_redirects=True)
  data = response.json()
  data = data["animes"]
  for anime in data:
    print(anime["name"], anime["jtitle"])
    if anime["name"] == jname or anime["jtitle"] == name:
      return anime
  return None

class DownloadPopup(customtkinter.CTkToplevel):
  def __init__(self, parent, anime):
    super().__init__(parent)
    self.after(201, lambda :self.iconbitmap('icons/icon.ico'))
    self.resizable(False, False)
    self.attributes("-topmost", True)
    self.it_title  = anime["it_title"]
    self.jap_title = anime["jap_title"]
    self.image_url = anime["image_url"]
    self.link      = anime["link"]
    anime_parsed = get_anime_info(self.it_title, self.jap_title)
    # Setting delle varie vars di anime
    self.studio = anime_parsed["studio"]
    self.rilascio = anime_parsed["release"]
    self.episodi = int(anime_parsed["episodes"]) if anime_parsed["episodes"] != "??" else -1
    self.durata = anime_parsed["durationEpisodes"]
    self.anno = anime_parsed["year"]
    self.tipo = anime_parsed["animeTypeName"]
    self.voto_mal = anime_parsed["malVote"]
    self.visualizzazioni = anime_parsed["totViews"]
    self.doppiaggio = 'Sub ITA' if anime_parsed["dub"] == '0' else 'Dub ITA'
    self.storia = anime_parsed["story"]
    self.title(f"Download di {self.it_title}")
    self.setup_ui()
  
  def setup_ui(self):
    frame = customtkinter.CTkFrame(self)
    frame.pack(padx=10, pady=10, fill="both", expand=True)

    img = fetch_image(self, self.image_url)

    img_label = customtkinter.CTkLabel(frame, image=img, text="")
    img_label.grid(row=0, column=0, rowspan=6, padx=10, pady=10)

    info_text = f"""
    Titolo: {self.it_title}
    Titolo Originale: {self.jap_title}
    Studio: {self.studio}
    Rilascio: {self.rilascio}
    Episodi: {self.episodi}
    Durata: {self.durata}
    Anno: {self.anno}
    Tipo: {self.tipo}
    Voto MAL: {self.voto_mal}
    Visualizzazioni: {self.visualizzazioni}
    Doppiaggio: {self.doppiaggio}
    """

    info_label = customtkinter.CTkLabel(frame, text=info_text, justify="left", anchor="w")
    info_label.grid(row=0, column=1, sticky="w", padx=10, pady=10)

    story_label = customtkinter.CTkLabel(frame, text="Trama:", font=("Arial", 12, "bold"))
    story_label.grid(row=6, column=0, columnspan=1, sticky="w", padx=10, pady=(10, 0))

    story_text = customtkinter.CTkTextbox(frame, width=550, height=80, wrap="word")
    story_text.insert("1.0", self.storia)
    story_text.configure(state="disabled")
    story_text.grid(row=7, column=0, columnspan=3, padx=5, pady=5)
    self.progress_label = customtkinter.CTkLabel(frame, text="Episodio scaricato: 0 di 0", font=("Arial", 12))
    self.progress_label.grid(row=8, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 0))

    self.progress_bar = customtkinter.CTkProgressBar(frame, width=550, height=15)
    self.progress_bar.grid(row=9, column=0, columnspan=3, padx=10, pady=5)
    self.progress_bar.set(0)

    self.episode_progress_label = customtkinter.CTkLabel(frame, text="Progresso episodio: -\nVelocità: -\nTempo rimanente: -\nScaricato 0MB di 0MB", justify="left", font=("Arial", 12))
    self.episode_progress_label.grid(row=10, column=0,columnspan=2,rowspan=3, sticky="w", padx=5, pady=(10, 0))

    self.episode_progress_bar = customtkinter.CTkProgressBar(frame, width=550, height=15)
    self.episode_progress_bar.grid(row=14, column=0, columnspan=3, pady=5)
    self.episode_progress_bar.set(0)

    self.download_button = customtkinter.CTkButton(frame, text="Scarica Episodi", command=self.start_download)
    self.download_button.grid(row=15, column=1, sticky="w", pady=10)

  def start_download(self):
    self.progress_label.configure(text=f"Episodio scaricato: 0 di {self.episodi}")
    self.download_episodes_thread = Thread(target=self.download_episodes, args=(self.link, self.it_title))
    self.download_episodes_thread.start()
    self.download_button.configure(state="disabled", text="Download in corso...")

  def get_episodes(self, link):
    session = generate_client()
    response = session.get(link, follow_redirects=True)
    soup = BeautifulSoup(response.text, 'html.parser')
    episodes = []
    if response.status_code == 200:
      for episode in soup.find_all('li', class_='episode'):
        link_tag = episode.find('a')
        if link_tag:
          href = link_tag.get('href')
          full_link = WEBSITE + href
          response = session.get(full_link, follow_redirects=True)
          if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            link_tag = soup.find('a', id="alternativeDownloadLink")
            if link_tag:
              link = link_tag.get('href')
              episodes.append(link)
    return set(episodes)
  
  def download_episodes(self, link, name, episode_number=0):
    episodes = self.get_episodes(link)
    for episode_link in episodes:
      episode_output = f"./downloads/{name}/{int(episode_number) + 1:02}.mp4"
      print(f"Downloading {name} episode {episode_number} from {episode_link}")
      download_file_multithread(episode_link, episode_output, 8, self.update_episode_progress)
      episode_number += 1
      self.update_progress(episode_number)
    print("Download completato")

  def update_progress(self, episode_number):
    self.progress_label.configure(text=f"Episodio scaricato: {episode_number} di {self.episodi}")
    self.progress_bar.set(episode_number / self.episodi)
    if episode_number == self.episodi:
      self.download_button.configure(text="Download completato", state="disabled")
  
  def update_episode_progress(self, percentage, downloaded, file_size, speed, remaining_time):
    self.episode_progress_label.configure(text=f"Progresso episodio: {percentage:.0f}%\nVelocità: {speed / (1024 * 1024):.2f} MB/s\nTempo rimanente: {remaining_time:.2f} s\nScaricato {downloaded / (1024 * 1024):.2f} MB di {file_size / (1024 * 1024):.2f} MB")
    self.episode_progress_bar.set(percentage / 100)