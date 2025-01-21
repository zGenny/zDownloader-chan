import httpx
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