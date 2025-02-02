import httpx
from bs4 import BeautifulSoup
import re

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

def search_anime(query="Evangelion"):
  print(f"Ricercando {query}...")
  response = generate_client().get(WEBSITE+"/search?keyword=" + query)
  if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')

    items = soup.find_all('div', class_='item')

    filtered_items = [item for item in items if query.lower() in item.text.lower()]

    anime_data = []
    for item in filtered_items:
      title_italian = item.find('a', class_='name').text.strip()
      jtitle = item.find('a', class_='name')['data-jtitle']
      image_url = item.find('img')['src']
      link = WEBSITE + item.find('a', class_='name')['href']
      
      anime_data.append({
        'jap_title': title_italian,
        'it_title': jtitle,
        'image_url': image_url,
        'link': link
      })
    if len(anime_data) == 0:
      return None
    return anime_data
  else:
    return None