import httpx
import re
from .config import config


def generate_client():
  """
  Genera e configura un client httpx con headers e cookie/token CSRF.
  
  Utilizza la configurazione centralizzata per base_url e user_agent.
  
  Returns:
      httpx.Client: Client HTTP configurato
  """
  session = httpx.Client()

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