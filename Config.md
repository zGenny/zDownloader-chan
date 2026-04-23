# Configurazione dell'Applicazione

Questo documento descrive come configurare l'applicazione zDownloader-chan.

## Configurazione Rapida

### Modificare l'URL base

Per cambiare l'URL del sito anime:

1. **Modifica del file `libs/config.json`**:
   ```json
   {
     "base_url": "https://www.nuovo-sito-anime.it",
     "endpoints": {
       "html_endpoint": "/search",
       "api_endpoint": "/api/search/v2"
     },
     "headers": {
       "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
     }
   }
   ```

2. **Via variabile d'ambiente** (temporanea):
   ```bash
   # Windows
   set ANIMEWORLD_BASE_URL=https://www.nuovo-sito-anime.it
   python main.py
   
   # Linux/Mac
   export ANIMEWORLD_BASE_URL=https://www.nuovo-sito-anime.it
   python main.py
   ```

3. **Via codice Python** (permanente):
   ```python
   from libs.config import config
   config.update_base_url('https://www.nuovo-sito-anime.it')
   ```

## Configurazione 'Avanzata'


### Principali parametri configurabili:

- **base_url**: URL base del sito anime
- **endpoints.html_endpoint**: Percorso per la ricerca HTML*
- **endpoints.api_endpoint**: Percorso per l'API JSON*
- **headers.user_agent**: User-Agent per le richieste HTTP*

> [!NOTE]
> *: inseriti nel caso vengano applicati cambiamenti anche su questi endpoints.

### Metodi di configurazione (Future use):

- `config.update_base_url(url, persist=True)`
- `config.update_html_endpoint(path, persist=True)`
- `config.update_api_endpoint(path, persist=True)`
- `config.update_user_agent(ua_string, persist=True)`

## File di Configurazione

- **File principale**: `libs/config.json`
- **Modulo Python**: `libs/config.py`

## Note

- Le modifiche con `persist=True` vengono salvate automaticamente su file
- Le variabili d'ambiente hanno priorità sul file di configurazione
- Usare `config.reload()` per ricaricare la configurazione da file