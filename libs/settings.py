"""
Preferenze dell'utente (vista dei risultati, lingua dei titoli, connessioni, cartella dei download).

A differenza di config.json, che descrive il sito, queste impostazioni vengono cambiate
dall'interfaccia e salvate in settings.json nella cartella del progetto.
"""

import json
from pathlib import Path

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "settings.json"

DEFAULTS = {
  "view_mode": "list",        # "list" oppure "grid"
  "title_language": "it",     # "it" oppure "jp"
  "threads": 8,               # connessioni per episodio (1-12)
  "download_dir": "downloads",
}

ALLOWED_VALUES = {
  "view_mode": ("list", "grid"),
  "title_language": ("it", "jp"),
}


class Settings:
  def __init__(self, path=SETTINGS_PATH):
    self._path = path
    self._values = dict(DEFAULTS)
    try:
      with open(path, encoding="utf-8") as f:
        stored = json.load(f)
      for key, value in stored.items():
        if key in DEFAULTS and self._is_valid(key, value):
          self._values[key] = value
    except FileNotFoundError:
      pass
    except (OSError, ValueError) as e:
      print(f"Impostazioni non leggibili, uso i valori predefiniti: {e}")

  @staticmethod
  def _is_valid(key, value):
    if key in ALLOWED_VALUES:
      return value in ALLOWED_VALUES[key]
    if key == "threads":
      return isinstance(value, int) and 1 <= value <= 12
    if key == "download_dir":
      return isinstance(value, str) and value.strip() != ""
    return True

  def get(self, key):
    return self._values[key]

  def update(self, **values):
    for key, value in values.items():
      if key not in DEFAULTS or not self._is_valid(key, value):
        raise ValueError(f"Valore non valido per {key}: {value!r}")
      self._values[key] = value
    self._save()

  def _save(self):
    try:
      with open(self._path, "w", encoding="utf-8") as f:
        json.dump(self._values, f, indent=2, ensure_ascii=False)
    except OSError as e:
      print(f"Errore nel salvataggio delle impostazioni: {e}")


settings = Settings()
