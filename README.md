# Case in 3D

Catalogo immobiliare pubblico statico in italiano. La ricerca contiene 60 immobili distinti e 22 modelli approvati; ogni scheda distingue i dati dell’annuncio, le verifiche di disponibilità e lo stato della ricostruzione. Non sono pubblicati la trascrizione privata della chat o i file di lavoro.

## Avvio locale

Servire soltanto la cartella `dist`:

    python3 -m http.server 8765 --bind 127.0.0.1 --directory dist

Il catalogo pubblico è `dist/data/catalog.json`. Non occorrono database, account o servizi di scrittura. I modelli approvati sono HTML autonomi con Three.js incorporato e funzionano offline con WebGL. La pagina del catalogo richiede un server HTTP per leggere il JSON.

## Navigazione e copertura

Ricerca testuale e filtri per località, disponibilità e presenza del modello. Un solo modello viene caricato alla volta; le viste derivano dal numero effettivo di livelli. I collegamenti storici `#aurisina` e `#muggia` restano validi. Comandi e informazioni sono esterni alla scena.

I modelli parziali riportano nella scheda e sopra la scena l’elenco dei volumi presenti nell’annuncio ma non renderizzati. Le parti documentate dalle piante sono ricalcate senza specchiatura o deformazione indipendente degli assi; le dimensioni non quotate, gli arredi e il contesto sono stime dichiarate. Gli ambienti non documentati non vengono inventati. Destinazioni catastali e abitabilità non sono certificate dal modello.

## Aggiornamento e verifica

Gli script in `scripts` importano messaggi identificati da ID e hash completo, preservano lo storico prezzi, distinguono annunci assenti da errori temporanei e generano il catalogo in modo atomico. Un modello diventa visibile soltanto con QA statico/browser, confronto geometrico e una seconda revisione delle fonti riferiti al medesimo hash HTML. Questa seconda lettura può essere svolta dallo stesso esecutore e non implica una verifica umana indipendente. La disponibilità non è dedotta dalla sola presenza della casa nella chat o da una pagina indicizzata.

    python3 scripts/test-catalog-workflow.py
    python3 scripts/validate-catalog.py dist/data/catalog.json --dist dist --work ../work --expected 60

Le prove browser usano Chromium desktop/mobile emulato con rendering software. Non equivalgono a prove su dispositivi fisici. I metadati di inizio/fine includono eventuali interruzioni della lavorazione, non misurano le sole ore attive.

## Pubblicazione

Usare il progetto Sites indicato in `.openai/hosting.json`, mantenendo il sito pubblico. Prima di pubblicare: validare il catalogo, generare `out` con `scripts/stage-release.py` includendo soltanto HTML approvati, creare un archivio dal commit effettivamente inviato al repository Sites, salvare e distribuire quella versione e confrontare i file serviti con quelli verificati. Un errore di pubblicazione non sostituisce il riferimento all’ultima versione valida.

Il completamento del popolamento iniziale e l’attivazione dell’aggiornamento del lunedì sono tracciati nei file privati di gestione del lavoro; non sono implicitamente attestati da questo README.
