import re

from bs4 import BeautifulSoup
from .config import config
from .utils import generate_client

# Classi usate dal sito nei risultati per indicare il tipo; senza indicazioni è una serie TV
TYPE_NAMES = {"movie": "Film", "special": "Speciale", "ova": "OVA", "ona": "ONA"}
SERIES_TYPE = "Serie TV"


def search_anime(query="Evangelion", client=None):
  """
  Cerca un anime sul sito.

  Returns:
      list: Risultati con titoli, copertina, link, doppiaggio, tipo e URL del tooltip
            (per i dettagli, vedi get_anime_details); None se non c'è nessun risultato
  """
  print(f"Ricercando {query}...")
  client = client or generate_client()
  # Utilizza l'endpoint di ricerca HTML dalla configurazione centralizzata
  html_endpoint = config.get_html_endpoint()
  response = client.get(html_endpoint, params={"keyword": query})
  if response.status_code != 200:
    return None
  soup = BeautifulSoup(response.text, 'html.parser')

  items = soup.find_all('div', class_='item')

  # La pagina contiene anche i suggerimenti della barra laterale: tengo solo quelli pertinenti
  filtered_items = [item for item in items if query.lower() in str(item).lower()]

  anime_data = []
  for item in filtered_items:
    name_tag = item.find('a', class_='name')
    poster = item.find('a', class_='poster')
    status = item.find('div', class_='status')

    anime_type = SERIES_TYPE
    if status:
      for marker in status.find_all('div'):
        css_class = (marker.get('class') or [''])[0]
        if css_class != 'dub':
          anime_type = TYPE_NAMES.get(css_class, marker.get_text(strip=True) or SERIES_TYPE)

    tooltip = poster.get('data-tip') if poster else None
    anime_data.append({
      'jap_title': name_tag['data-jtitle'],
      'it_title': name_tag.text.strip(),
      'image_url': item.find('img')['src'],
      # Utilizza get_full_url() dalla configurazione per costruire l'URL completo
      'link': config.get_full_url(name_tag['href']),
      'dub': bool(status and status.find('div', class_='dub')),
      'type': anime_type,
      'tooltip': config.get_full_url(tooltip) if tooltip else None,
    })
  return anime_data or None


def get_anime_details(tooltip_url, client):
  """
  Legge dal tooltip del sito anno di uscita, stato e voto di un anime.

  Returns:
      dict: {'year', 'state', 'rating'}; i valori mancanti sono None
  """
  response = client.get(tooltip_url)
  if response.status_code != 200:
    return {}
  soup = BeautifulSoup(response.text, 'html.parser')
  meta = {}
  for row in soup.find_all('div', class_='meta'):
    label, value = row.find('label'), row.find('span')
    if label and value:
      meta[label.get_text(strip=True).rstrip(':').lower()] = ' '.join(value.get_text().split())
  year = re.search(r'\d{4}', meta.get('data di uscita', ''))
  rating = meta.get('voto')
  return {
    'year': year.group(0) if year else None,
    'state': meta.get('stato') or None,
    'rating': rating if rating and re.match(r'^\d+([.,]\d+)?$', rating) else None,
  }
