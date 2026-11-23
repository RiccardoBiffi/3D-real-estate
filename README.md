# Case in 3D

Catalogo immobiliare di Trieste e dintorni con 90 schede. «Pubblicato» indica che una fonte online permette di identificare la casa. «Archiviato» indica che l’ultimo controllo non ha confermato una scheda dello stesso immobile. La consultabilità di un annuncio e la disponibilità commerciale possono divergere.

## Avvio locale

Servire soltanto la cartella `dist`:

    python3 -m http.server 8765 --bind 127.0.0.1 --directory dist

Il catalogo pubblico è `dist/data/catalog.json`. Non occorrono database, account o servizi di scrittura. I modelli sono HTML autonomi e funzionano offline con WebGL. La pagina del catalogo richiede un server HTTP per leggere il JSON.

## Navigazione e copertura

Ricerca testuale e filtri per località, disponibilità e presenza del modello. Un solo modello viene caricato alla volta; le viste derivano dal numero effettivo di livelli. I collegamenti storici `#aurisina` e `#muggia` restano validi. Comandi e informazioni sono esterni alla scena.

La raccolta del 23 novembre 2026 comprende 70 modelli rigenerati. Si possono esplorare i piani di 56 immobili e gli esterni documentati di altri 14. Ogni scheda raccoglie le fotografie, le tavole utilizzate, le parti omesse e i confronti con la geometria. Le dimensioni prive di quota e il mobilio sono stime. [Consulta la raccolta di foto e planimetrie](dist/ricostruzioni/2026-11-23/index.html).

## Aggiornamento e verifica

Gli script in `scripts` importano messaggi identificati da ID e hash completo, preservano lo storico prezzi, distinguono annunci assenti da errori temporanei e generano il catalogo in modo atomico. Un modello diventa visibile soltanto con QA statico/browser, confronto geometrico e una seconda revisione delle fonti riferiti al medesimo hash HTML. Questa seconda lettura può essere svolta dallo stesso esecutore e non implica una verifica umana indipendente. La pubblicazione non è dedotta dalla sola presenza della casa nella chat o da una pagina indicizzata.

    python3 scripts/test-catalog-workflow.py
    python3 scripts/validate-catalog.py dist/data/catalog.json --dist dist --work work --baseline-commit 1b6c0bc244eba8409e893df35e39f47049864381 --expected 90

Le prove browser usano Chromium desktop/mobile emulato con rendering software. Non equivalgono a prove su dispositivi fisici. I metadati di inizio/fine includono eventuali interruzioni della lavorazione, non misurano le sole ore attive.

## Pubblicazione

Usare il progetto Sites indicato in `.openai/hosting.json`, mantenendo il sito pubblico. Prima di pubblicare: validare il catalogo, generare `out` con `scripts/stage-release.py` includendo soltanto HTML approvati, creare un archivio dal commit effettivamente inviato al repository Sites, salvare e distribuire quella versione e confrontare i file serviti con quelli verificati. Un errore di pubblicazione non sostituisce il riferimento all’ultima versione valida.

Il completamento del popolamento iniziale e l’attivazione dell’aggiornamento del lunedì sono tracciati nei file privati di gestione del lavoro; non sono implicitamente attestati da questo README.

## Modelli e pubblicazione

Il catalogo del 15 novembre 2026 deriva dalla versione 14 di Sites, integrata su GitHub con un merge che conserva le due cronologie. I modelli nuovi aggiornano solo il campo del modello nelle schede pubblicate. Ogni modello approvato ha un HTML autonomo e verificato offline. Le note della scheda indicano quali parti sono rappresentate e quali volumi mancano.

Lo script `integrate-reviewed-models.py` verifica gli hash degli artefatti e richiede un esito di QA e revisione indipendente per i nuovi modelli. `stage-release.py --baseline-commit <SHA completo>` conserva i modelli identici alla versione distribuita e prepara la cartella pubblica `out`. La raccolta pubblica include le tavole, le fotografie e gli esiti delle verifiche elencati nel suo indice.
