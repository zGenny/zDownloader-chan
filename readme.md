# zDownloader-chan

[![Download](https://img.shields.io/github/downloads/zGenny/zDownloader-chan/total?label=download&color=FF6505)](https://github.com/zGenny/zDownloader-chan/releases)
[![Ultima release](https://img.shields.io/github/v/release/zGenny/zDownloader-chan?label=release&color=FF6505)](https://github.com/zGenny/zDownloader-chan/releases/latest)

Essendo il sito di AnimeWorld italiano, il readme è scritto in italiano.
zDownloader-chan è un semplice tool per scaricare anime da [AnimeWorld](https://www.animeworld.tv/) sfruttando **più connessioni in parallelo** (multithread) per velocizzare il download.

## Perché?

zDownloader-chan nasce per semplificare il download degli anime da AnimeWorld.
Il programma consente di scaricare **un’intera serie con un solo click**, evitando
la selezione manuale dei singoli episodi.

Grazie alle **connessioni in parallelo**, i download risultano **notevolmente più rapidi**.
L’idea è nata per consentire la visione degli anime sul mio **home server**; in futuro
è prevista anche una funzionalità di **invio automatico della serie direttamente al server**.

## Screenshot

**Schermata principale** — statistiche dei download e libreria con le serie già scaricate
<br>
<img src="photos/screenshot-home.jpg" width="720">

**Risultati della ricerca** — in lista o a griglia, a scelta, con filtri per tipo e "Solo DUB ITA"

| Lista | Griglia |
|:---:|:---:|
| <img src="photos/screenshot-risultati-lista.jpg" width="420"> | <img src="photos/screenshot-risultati-griglia.jpg" width="420"> |

**Download** — scelta degli episodi, avanzamento della serie e del singolo episodio, riepilogo finale

| In corso | Completato |
|:---:|:---:|
| <img src="photos/screenshot-download.jpg" width="400"> | <img src="photos/screenshot-download-completato.jpg" width="400"> |

**Impostazioni**
<br>
<img src="photos/screenshot-impostazioni.jpg" width="340">


## Installazione

Serve **Python 3.11 o successivo**.

1. Clona il repository:
   ```bash
   git clone https://github.com/zGenny/zDownloader-chan.git
   cd zDownloader-chan
   ```

2. Crea un ambiente virtuale Python:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Su Windows: venv\Scripts\activate
   ```

3. Installa le dipendenze:
   ```bash
   pip install -r requirements.txt
   ```

## Utilizzo

Avvia il programma con:
   ```bash
   python3 ./main.py
   ```



### Configurazione

Per configurare l'URL del sito anime o altri parametri, consultare la [documentazione di configurazione](Config.md).

Esempio rapido per cambiare l'URL base:
```bash
# Via variabile d'ambiente (temporanea)
export ANIMEWORLD_BASE_URL=https://www.nuovo-sito-anime.it
python3 ./main.py
```

Oppure modificare il file `libs/config.json`:
```json
{
  "base_url": "https://www.nuovo-sito-anime.it",
  ...
}
```

Si avvierà la GUI del programma, da qui potrai cercare il tuo anime e scaricarlo con il pulsante "Scarica":

- **Risultati in lista o a griglia**, con badge 🇮🇹 DUB ITA / SUB ITA, tipo, anno, stato e voto
- **Filtri** per tipo (Serie TV, Film, Altro) e "Solo DUB ITA"
- **Titoli in italiano o giapponese**, a scelta
- **Scelta degli episodi** da scaricare (da/a) e del numero di connessioni
- **Download annullabile**: gli episodi già scaricati vengono saltati, quindi puoi riprendere in qualsiasi momento
- **Libreria** nella schermata iniziale, con le serie già scaricate e la loro copertina (salvata come `poster.jpg`)
- **Statistiche dei download**: episodi e GB scaricati in tutto, serie in libreria e spazio occupato
- `Ctrl+F` per tornare alla ricerca, `Esc` per svuotarla

Le preferenze (vista, lingua dei titoli, connessioni, cartella dei download) si cambiano dalla finestra
**Impostazioni** (icona dell'ingranaggio) e vengono salvate in `settings.json`.

Le statistiche restano sul tuo PC, in `stats.json`: nessun dato viene inviato. Il conteggio è cumulativo,
quindi non diminuisce se cancelli o sposti degli episodi; al primo avvio parte da quelli già presenti in libreria.

Il font dell'interfaccia è [Nunito](https://github.com/googlefonts/nunito), distribuito con licenza SIL Open Font License (vedi `fonts/OFL.txt`).

## Problemi noti

### Errore di build di Pillow su Fedora ([Pillow build fails (#1)](https://github.com/zGenny/zDownloader-chan/issues/1))

Su alcune versioni di Fedora (es. Fedora 43), Pillow può fallire in fase di build
a causa della mancanza di librerie di sistema.

**Risoluzione:**

Installare le dipendenze necessarie:

```bash
sudo dnf install libjpeg-turbo-devel zlib-devel python3-devel gcc
```
#### In caso di altri problemi, non esitare ad aprire una issue 😃

## Licenza
Questo progetto è distribuito sotto licenza MIT.

## Donazioni
[![PayPal](photos/donate.png)](https://paypal.me/zgenny?country.x=IT&locale.x=it_IT)

---
**Disclaimer:** Questo software è fornito solo a scopo educativo. L'uso improprio potrebbe violare i termini di servizio di AnimeWorld. L'autore non si assume alcuna responsabilità per eventuali violazioni.

