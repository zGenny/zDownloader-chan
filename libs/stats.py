"""
Statistiche dei download (episodi e dati scaricati), salvate in stats.json nella cartella del progetto.

Il conteggio è cumulativo: non diminuisce se si cancellano o spostano gli episodi dalla libreria.
"""

import json
import threading
from datetime import date
from pathlib import Path

STATS_PATH = Path(__file__).resolve().parent.parent / "stats.json"


class Stats:
  def __init__(self, path=STATS_PATH):
    self._path = path
    self._lock = threading.Lock()  # i download aggiornano il conteggio dai loro thread
    self._values = None

  def _load(self, library):
    """Legge le statistiche; restituisce True se sono state create ora a partire dalla libreria."""
    if self._values is not None:
      return False
    try:
      with open(self._path, encoding="utf-8") as f:
        stored = json.load(f)
      self._values = {
        "episodes": int(stored.get("episodes", 0)),
        "bytes": int(stored.get("bytes", 0)),
        "since": stored.get("since") or date.today().isoformat(),
      }
      return False
    except (FileNotFoundError, ValueError, TypeError, OSError):
      # Primo avvio con le statistiche: si parte da quanto c'è già in libreria, non da zero
      self._values = {
        "episodes": sum(entry["episodes"] for entry in library),
        "bytes": sum(entry["size"] for entry in library),
        "since": date.today().isoformat(),
      }
      self._save()
      return True

  def _save(self):
    try:
      with open(self._path, "w", encoding="utf-8") as f:
        json.dump(self._values, f, indent=2)
    except OSError as e:
      print(f"Errore nel salvataggio delle statistiche: {e}")

  def totals(self, library):
    """Episodi e byte scaricati in tutto, più la data di inizio del conteggio."""
    with self._lock:
      self._load(library)
      return dict(self._values)

  def record_episode(self, size, library_loader):
    """Conta un episodio appena scaricato; library_loader serve solo se le statistiche non sono ancora state lette."""
    with self._lock:
      # Se le statistiche nascono ora dalla libreria, questo episodio (già su disco) è già contato
      if self._values is None and self._load(library_loader()):
        return
      self._values["episodes"] += 1
      self._values["bytes"] += size
      self._save()


stats = Stats()
