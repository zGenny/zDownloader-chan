import httpx
from bs4 import BeautifulSoup
import re
from .config import config
from .utils import generate_client

def search_anime(query="Evangelion"):
  print(f"Ricercando {query}...")
  # Utilizza l'endpoint di ricerca HTML dalla configurazione centralizzata
  html_endpoint = config.get_html_endpoint()
  response = generate_client().get(html_endpoint + "?keyword=" + query)
  if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')

    items = soup.find_all('div', class_='item')

    filtered_items = [item for item in items if query.lower() in str(item).lower()]

    anime_data = []
    for item in filtered_items:
      title_italian = item.find('a', class_='name').text.strip()
      jtitle = item.find('a', class_='name')['data-jtitle']
      image_url = item.find('img')['src']
      # Utilizza get_full_url() dalla configurazione per costruire l'URL completo
      href = item.find('a', class_='name')['href']
      link = config.get_full_url(href)
      
      anime_data.append({
        'jap_title': jtitle,
        'it_title': title_italian,
        'image_url': image_url,
        'link': link
      })
    if len(anime_data) == 0:
      return None
    return anime_data
  else:
    return None