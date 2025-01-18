from requests import post
from bs4 import BeautifulSoup

def search_anime(website="https://www.animeworld.so", query=""):
  url = f"{website}/search?keyword={query}"
  response = post(url)
  
  if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Trova tutti i div con classe "item"
    items = soup.find_all('div', class_='item')
    
    # Filtra gli items che non contengono la query
    filtered_items = [item for item in items if query.lower() in item.text.lower()]
    
    # Crea una lista di dizionari con le informazioni richieste
    anime_data = []
    for item in filtered_items:
      title_italian = item.find('a', class_='name').text.strip()
      jtitle = item.find('a', class_='name')['data-jtitle']
      image_url = item.find('img')['src']
      link = website + item.find('a', class_='name')['href']
      
      anime_data.append({
        'title_italian': title_italian,
        'jtitle': jtitle,
        'image_url': image_url,
        'link': link
      })
    
    return anime_data
  else:
    return None
