"""
Modulo di configurazione centralizzato per l'applicazione.

Questo modulo gestisce la configurazione dell'applicazione leggendo da:
1. File di configurazione (config.json)
2. Variabili d'ambiente (per override)

Fornisce metodi per:
- Leggere la configurazione
- Aggiornare valori a runtime
- Salvare la configurazione su file
"""

import os
import json
from pathlib import Path


class ConfigManager:
  """Gestisce la configurazione centralizzata dell'applicazione."""
  
  _instance = None
  _config = None
  _config_path = None
  
  def __new__(cls):
    """Implementa il pattern Singleton per garantire una sola istanza."""
    if cls._instance is None:
      cls._instance = super(ConfigManager, cls).__new__(cls)
      cls._instance._initialize()
    return cls._instance
  
  def _initialize(self):
    """Inizializza il gestore di configurazione."""
    # Determina il percorso del file di configurazione (nella root del progetto)
    self._config_path = Path(__file__).parent / "config.json"
    
    # Carica la configurazione dal file
    self._load_config()
    
    # Applica override da variabili d'ambiente
    self._apply_env_overrides()
  
  def _load_config(self):
    """Carica la configurazione dal file JSON."""
    try:
      with open(self._config_path, 'r', encoding='utf-8') as f:
        self._config = json.load(f)
    except FileNotFoundError:
      print(f"Avvertenza: File di configurazione non trovato in {self._config_path}")
      self._config = self._get_default_config()
      self._save_config()
    except json.JSONDecodeError as e:
      print(f"Errore: Il file di configurazione non è un JSON valido: {e}")
      self._config = self._get_default_config()
    except PermissionError:
      print(f"Errore: Permessi insufficienti per leggere il file di configurazione")
      self._config = self._get_default_config()
    except Exception as e:
      print(f"Errore inatteso durante il caricamento della configurazione: {e}")
      self._config = self._get_default_config()
  
  def _apply_env_overrides(self):
    """Applica override da variabili d'ambiente."""
    # Override del base_url
    if os.getenv('ANIMEWORLD_BASE_URL'):
      self._config['base_url'] = os.getenv('ANIMEWORLD_BASE_URL')
    
    # Override del user_agent
    if os.getenv('ANIMEWORLD_USER_AGENT'):
      self._config['headers']['user_agent'] = os.getenv('ANIMEWORLD_USER_AGENT')
  
  def _get_default_config(self):
    """Restituisce la configurazione di default."""
    return {
      "base_url": "https://www.animeworld.ac",
      "endpoints": {
        "html_endpoint": "/search",
        "api_endpoint": "/api/search/v2"
      },
      "headers": {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
      }
    }
  
  def _save_config(self):
    """Salva la configurazione corrente sul file JSON."""
    try:
      with open(self._config_path, 'w', encoding='utf-8') as f:
        json.dump(self._config, f, indent=2, ensure_ascii=False)
    except IOError as e:
      print(f"Errore nel salvataggio della configurazione: {e}")
  
  def get_base_url(self):
    """Restituisce l'URL base dell'applicazione."""
    return self._config.get('base_url', '').rstrip('/')
  
  def get_api_endpoint(self):
    """
    Restituisce l'URL completo dell'endpoint API JSON (/api/search/v2).
    
    Returns:
        str: URL completo dell'endpoint API
    """
    endpoint_path = self._config.get('endpoints', {}).get('api_endpoint', '')
    return self.get_base_url() + endpoint_path
  
  def get_html_endpoint(self):
    """
    Restituisce l'URL completo dell'endpoint HTML (/search).
    
    Returns:
        str: URL completo dell'endpoint HTML
    """
    endpoint_path = self._config.get('endpoints', {}).get('html_endpoint', '')
    return self.get_base_url() + endpoint_path
  
  def get_user_agent(self):
    """Restituisce lo User-Agent da usare nelle richieste HTTP."""
    return self._config.get('headers', {}).get('user_agent', '')
  
  def get_full_url(self, path):
    """
    Restituisce l'URL completo concatenando base_url con il percorso.
    
    Args:
        path (str): Percorso relativo (es. '/search?keyword=evangelion')
    
    Returns:
        str: URL completo
    """
    base = self.get_base_url()
    if path.startswith('/'):
      return base + path
    return base + '/' + path
  
  def update_base_url(self, new_url, persist=True):
    """
    Aggiorna l'URL base della configurazione.
    
    Args:
        new_url (str): Nuovo URL base
        persist (bool): Se True, salva la modifica su file
        
    Raises:
        ValueError: Se l'URL non è valido
    """
    if not new_url or not isinstance(new_url, str):
      raise ValueError("L'URL base deve essere una stringa non vuota")
    
    if not new_url.startswith(('http://', 'https://')):
      raise ValueError("L'URL base deve iniziare con http:// o https://")
    
    self._config['base_url'] = new_url.rstrip('/')
    if persist:
      self._save_config()
  
  def update_api_endpoint(self, new_path, persist=True):
    """
    Aggiorna l'endpoint API (/api/search/v2).
    
    Args:
        new_path (str): Nuovo percorso dell'endpoint (es. '/api/search/v3')
        persist (bool): Se True, salva la modifica su file
        
    Raises:
        ValueError: Se il percorso non è valido
    """
    if not new_path or not isinstance(new_path, str):
      raise ValueError("Il percorso dell'endpoint API deve essere una stringa non vuota")
    
    if not new_path.startswith('/'):
      raise ValueError("Il percorso dell'endpoint API deve iniziare con /")
    
    if 'endpoints' not in self._config:
      self._config['endpoints'] = {}
    
    self._config['endpoints']['api_endpoint'] = new_path
    if persist:
      self._save_config()
  
  def update_html_endpoint(self, new_path, persist=True):
    """
    Aggiorna l'endpoint HTML (/search).
    
    Args:
        new_path (str): Nuovo percorso dell'endpoint (es. '/search/v2')
        persist (bool): Se True, salva la modifica su file
        
    Raises:
        ValueError: Se il percorso non è valido
    """
    if not new_path or not isinstance(new_path, str):
      raise ValueError("Il percorso dell'endpoint HTML deve essere una stringa non vuota")
    
    if not new_path.startswith('/'):
      raise ValueError("Il percorso dell'endpoint HTML deve iniziare con /")
    
    if 'endpoints' not in self._config:
      self._config['endpoints'] = {}
    
    self._config['endpoints']['html_endpoint'] = new_path
    if persist:
      self._save_config()
  
  def update_user_agent(self, new_user_agent, persist=True):
    """
    Aggiorna lo User-Agent.
    
    Args:
        new_user_agent (str): Nuovo User-Agent
        persist (bool): Se True, salva la modifica su file
        
    Raises:
        ValueError: Se lo User-Agent non è valido
    """
    if not new_user_agent or not isinstance(new_user_agent, str):
      raise ValueError("Lo User-Agent deve essere una stringa non vuota")
    
    if 'headers' not in self._config:
      self._config['headers'] = {}
    
    self._config['headers']['user_agent'] = new_user_agent
    if persist:
      self._save_config()
  
  def get_all_config(self):
    """Restituisce l'intera configurazione."""
    return self._config.copy()
  
  def reload(self):
    """Ricarica la configurazione dal file."""
    self._load_config()
    self._apply_env_overrides()


# Istanza singleton globale della configurazione
config = ConfigManager()