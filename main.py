from libs.downloader import download_episodes
from libs.searcher import search_anime
import customtkinter
from PIL import Image, ImageTk
import requests
from io import BytesIO

NOME_APP = "Modem-Chan"

icon_search = customtkinter.CTkImage(light_image=Image.open("icons/Search.ico"),
                                  dark_image=Image.open("icons/Search.ico"),
                                  size=(30, 30))

website = "https://www.animeworld.so/"


def send_modem():
    print("Sending modem...")
    # Aggiungi la logica per l'invio del modem qui

import threading

def fetch_image(url):
    response = requests.get(url)
    if response.status_code == 200:
        return Image.open(BytesIO(response.content))
    return None

def search():
  for widget in scrollable_frame.winfo_children():
    widget.destroy()
  def background_search():
    text = ricerca.get("0.0", "end").strip()
    results = search_anime(query=text)

    for i, result in enumerate(results):
      image = fetch_image(result["image_url"])
      if image:
        image = image.resize((100, 150))
        image_tk = ImageTk.PhotoImage(image)

        image_label = customtkinter.CTkLabel(scrollable_frame, image=image_tk, text="")
        image_label.image = image_tk
        image_label.grid(row=i, column=0, padx=5, pady=5)

      title_label = customtkinter.CTkLabel(scrollable_frame, text=result["title_italian"], font=("Air", 18), wraplength=300)
      title_label.grid(row=i, column=1, pady=5)

      download_button = customtkinter.CTkButton(scrollable_frame, text="Download",
                                                command=lambda link=result["link"], title= result["title_italian"]: download_episodes_func(link, title))
      download_button.grid(row=i, column=2, padx=5, pady=5)
  
  threading.Thread(target=background_search).start()

def download_episodes_func(link, name):
  threading.Thread(target=download_episodes, args=(link, name)).start()

# Crea la finestra principale
customtkinter.set_appearance_mode("dark")
app = customtkinter.CTk()
app.title(NOME_APP)
app.geometry("1080x720")

# Frame scrollabile
scrollable_frame = customtkinter.CTkScrollableFrame(app, width=800, height=400)
scrollable_frame.grid(row=3, column=0, padx=10, pady=10, columnspan=2, sticky="nsew")

# Elementi
ricerca = customtkinter.CTkTextbox(app, height=50, width=500, font=("Consolas", 25))
ricerca.bind("<Return>", lambda event: search())
button_ricerca = customtkinter.CTkButton(app, height=40, width=40, image=icon_search, command=search, text="")
button_invio_modem = customtkinter.CTkButton(app, text="Invio Modem", command=send_modem)
titolo = customtkinter.CTkLabel(app, text=NOME_APP, font=("Consolas", 25))
sottoTitolo = customtkinter.CTkLabel(app, text="Search by name:", font=("Consolas", 15))

# Layout
titolo.grid(row=0, column=0, padx=10, pady=10)
sottoTitolo.grid(row=1, column=0)
button_ricerca.grid(row=2, column=1, padx=10, pady=10)
ricerca.grid(row=2, column=0, padx=10, pady=10)

# Configura la griglia della finestra principale
app.grid_rowconfigure(0, weight=0)
app.grid_rowconfigure(1, weight=0)
app.grid_rowconfigure(2, weight=0)
app.grid_rowconfigure(3, weight=1)  # 1 per far prendere spazio
app.grid_columnconfigure(0, weight=1)
app.grid_columnconfigure(1, weight=0)

# Configura la larghezza delle colonne nella scrollable_frame
scrollable_frame.grid_columnconfigure(0,weight=1)   # Colonna immagine
scrollable_frame.grid_columnconfigure(1, weight=3)  # Colonna titolo
scrollable_frame.grid_columnconfigure(2, weight=1)  # Colonna pulsante

# Configura l'altezza delle righe
scrollable_frame.grid_rowconfigure(0, weight=1)
scrollable_frame.grid_rowconfigure(1, weight=3)
scrollable_frame.grid_rowconfigure(2, weight=3)

# Avvia l'applicazione
app.mainloop()
