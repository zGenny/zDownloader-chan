from libs.downloader import download_episodes
from libs.searcher import search_anime
from libs.strings import ANGRY_GIRL
import customtkinter
from PIL import Image, ImageTk
import requests
from io import BytesIO
import threading
import os

def anime_in_directory():
  return os.listdir("downloads")

class Popup(customtkinter.CTkToplevel):
  def __init__(self, parent):
    super().__init__(parent)
    self.title("Manda al Modem")
    self.geometry("300x150")
    self.anime = anime_in_directory()
    self.anime_var = {anime: customtkinter.BooleanVar(value=False) for anime in self.anime}

    customtkinter.CTkLabel(self, text="Questo è un popup!").pack(pady=10)
    for anime, var in self.anime_var.items():
      checkbox = customtkinter.CTkCheckBox(self, text=anime, variable=var)
      checkbox.pack(anchor="center")
    def send_to_modem():
      selected_anime = [anime for anime, var in self.anime_var.items() if var.get()]
      print("Sending to modem:", selected_anime)

    customtkinter.CTkButton(self, text="Send to Modem", command=send_to_modem).pack(pady=10)
    customtkinter.CTkButton(self, text="Chiudi", command=self.destroy).pack(pady=10)

class ModemChanApp:
  def __init__(self):
    self.NOME_APP = "Modem-Chan"
    self.website = "https://www.animeworld.so/"
    self.setup_ui()

  def setup_ui(self):
    customtkinter.set_default_color_theme("MoonLight.json")
    self.app = customtkinter.CTk()
    self.app.title(self.NOME_APP)
    self.app.geometry("1080x720")
    self.icon_search = customtkinter.CTkImage(light_image=Image.open("icons/Search.ico"),dark_image=Image.open("icons/Search.ico"),size=(30, 30))
    self.titolo = customtkinter.CTkLabel(self.app, text=self.NOME_APP, font=('Kristen ITC', 25))
    self.sotto_titolo = customtkinter.CTkLabel(self.app, text="Inserisci il nome dell'anime:", font=('Kristen ITC', 15))
    self.ricerca = customtkinter.CTkEntry(self.app, placeholder_text="Evangelion", height=50, width=500, font=('Kristen ITC', 25))
    self.ricerca.bind("<Return>", self.enter_key)
    self.button_ricerca = customtkinter.CTkButton(self.app, height=40, width=40, image=self.icon_search, command=self.search, text="", corner_radius=100)
    self.button_invio_modem = customtkinter.CTkButton(self.app, text="Invio Modem", command=self.send_modem, corner_radius=100, font=('Kristen ITC', 15))

    self.switch_var_titolo = customtkinter.StringVar(value="Alternativo")
    self.title_switch = customtkinter.CTkSwitch(self.app, text="Titoli in Alternativo", font=('Kristen ITC', 15), command=self.switch_title,
                          variable=self.switch_var_titolo, onvalue="Alternativo", offvalue="Giapponese")

    self.titolo.grid(row=0, column=0, padx=10, pady=10)
    self.sotto_titolo.grid(row=1, column=0)
    self.ricerca.grid(row=2, column=0, padx=10)
    self.ricerca.focus()
    self.button_ricerca.grid(row=2, column=1, padx=10, pady=10)
    self.button_invio_modem.grid(row=2, column=2, padx=10, pady=10)
    self.title_switch.grid(row=1, column=2, padx=10, pady=10)

    self.scrollable_frame = customtkinter.CTkScrollableFrame(self.app, width=800, height=400)
    self.scrollable_frame.grid(row=3, column=0, padx=10, pady=10, columnspan=10, sticky="nsew")

    self.app.grid_rowconfigure(0, weight=0)
    self.app.grid_rowconfigure(1, weight=0)
    self.app.grid_rowconfigure(2, weight=0)
    self.app.grid_rowconfigure(3, weight=1)
    self.app.grid_columnconfigure(0, weight=1)
    self.app.grid_columnconfigure(1, weight=0)

    self.scrollable_frame.grid_columnconfigure(0, weight=1)
    self.scrollable_frame.grid_columnconfigure(1, weight=3)
    self.scrollable_frame.grid_columnconfigure(2, weight=1)

    self.scrollable_frame.grid_rowconfigure(0, weight=1)
    self.scrollable_frame.grid_rowconfigure(1, weight=3)
    self.scrollable_frame.grid_rowconfigure(2, weight=3)

    self.app.mainloop()

  def send_modem(self):
    print("Sending modem...")
    popup = Popup(self.app)

  def fetch_image(self, url):
    response = requests.get(url)
    if response.status_code == 200:
      return customtkinter.CTkImage(light_image=Image.open(BytesIO(response.content)),
                      dark_image=Image.open(BytesIO(response.content)),
                      size=(100, 150))
    return None

  def enter_key(self, event):
    self.search()
    return "break"

  

  def search(self):
    for widget in self.scrollable_frame.winfo_children():
      widget.destroy()
    anime_already_downloaded = anime_in_directory()

    def background_search():
      title_type = "it_title" if self.title_switch.get() == "Alternativo" else "jap_title"
      text = self.ricerca.get().strip()
      if text == "":
        return
      results = search_anime(query=text)
      if results is not None:
        for i, result in enumerate(results):
          image_tk = self.fetch_image(result["image_url"])
          if image_tk:
            image_label = customtkinter.CTkLabel(self.scrollable_frame, image=image_tk, text="")
            image_label.image = image_tk
            image_label.grid(row=i, column=0, padx=5, pady=5)

          title_label = customtkinter.CTkLabel(self.scrollable_frame, text=result[title_type], font=("Air", 18), wraplength=300)
          title_label.grid(row=i, column=1, pady=5)

          if result[title_type] in anime_already_downloaded:
            download_button = customtkinter.CTkButton(self.scrollable_frame, text="In libreria", state="disabled", fg_color="#ffaa00", text_color_disabled="#000000")
          else:
            download_button = customtkinter.CTkButton(self.scrollable_frame, text="Download",
                                  command=lambda link=result["link"], title=result[title_type]: self.download_episodes_func(link, title))
          download_button.grid(row=i, column=2, padx=5, pady=5)
      else:
        no_result = f"Hai scritto bene? Non ho trovato nulla con \"{text}\", senpai!\n{ANGRY_GIRL}"
        no_results_label = customtkinter.CTkLabel(self.scrollable_frame, text=no_result, font=("Air", 18))
        no_results_label.grid(row=0, column=0, columnspan=3)

    threading.Thread(target=background_search).start()

  def download_episodes_func(self, link, name):
    threading.Thread(target=download_episodes, args=(link, name)).start()

  def switch_title(self):
    self.title_switch.configure(text=f"Titoli in {self.title_switch.get()}")
    self.search()

if __name__ == "__main__":
  ModemChanApp()
