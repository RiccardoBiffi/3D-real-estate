# Case in 3D

Sito statico in italiano che raccoglie le due pagine HTML fornite:

- Villa Aurisina.
- Muggia - Via Mameli 14/F.

## Avvio

La versione `case-in-3d.html` consegnata separatamente contiene l'intero sito,
i due HTML originali e le anteprime in un solo file. Si può aprire direttamente
in un browser con JavaScript abilitato. Il rendering interattivo richiede WebGL2.

Per questa versione a più file, servire la cartella con un server HTTP statico.
Ad esempio, da una shell nella cartella che contiene `index.html`:

    python -m http.server 8080

Poi aprire `http://localhost:8080`.

## Pubblicazione

Caricare tutti i file, mantenendo la struttura delle sottocartelle, su un hosting
statico. `index.html` è il punto d'ingresso; non servono build, account utente
nell'app, database, chiavi API o dipendenze JavaScript esterne.

Questo archivio non è, da solo, una pubblicazione online. Non è stato generato
un URL pubblico nella sessione di creazione: il comando di deploy del connettore
Vercel non era disponibile e il collegamento Lovable non disponeva del permesso
OAuth `projects:write`. Per riprendere la pubblicazione attraverso Lovable è
necessaria la riautorizzazione del collegamento con il permesso di scrittura.

## Navigazione

- `#panoramica`: pagina iniziale con le due anteprime.
- `#aurisina`: Villa Aurisina, vista esterna.
- `#muggia`: Muggia, vista esterna.
- `#aurisina/2`, `/3`, `/4`: piano superiore, piano terra, cantina.
- `#muggia/2`, `/3`, `/4`: sottotetto, piano rialzato, seminterrato e box.

Il menù rimane visibile su desktop e diventa apribile su telefono. La selezione
di un immobile lo chiude automaticamente. Un solo iframe è caricato alla volta.
Le viste si selezionano tramite pulsanti su desktop o tramite elenco su schermi
stretti. Il pulsante di condivisione copia il collegamento al modello e al livello,
non la posizione personalizzata della camera. Su file locali spiega che occorre
pubblicare il sito per ottenere un collegamento pubblico.

I controlli dei modelli originali restano disponibili: trascinamento, rotellina,
gesti touch, doppio clic/doppio tocco, tasti 1-4, R, T, 0, frecce e +/-.

## Integrità dei modelli

`modelli/aurisina.html` e `modelli/muggia.html` sono copie identiche, byte per byte,
degli allegati ricevuti. Le geometrie, i materiali, i commenti e i metadati originali
non sono stati ricostruiti o modificati. Gli hash SHA-256 sono riportati in
`source-integrity.json`. L'interfaccia esterna usa le API `window.__sceneControls`
e `window.__sceneState` già presenti nei due file.

Le due immagini sotto `assets/` provengono dalle anteprime incorporate negli HTML
originali; sono state soltanto ridimensionate e ricompresse per l'interfaccia.

Le ricostruzioni sono orientative: non costituiscono rilievi, certificazioni,
verifiche delle destinazioni d'uso o dello stato degli immobili.

## Verifiche e limiti

Verificati sintassi JavaScript, integrità SHA-256 dei due originali, dipendenze locali,
caricamento delle pagine nell'iframe, gestione dell'indisponibilità di WebGL,
menù desktop/mobile, finestre di aiuto, schermo intero e layout a 1440, 390 e 320 px.
La selezione delle viste e i relativi collegamenti sono stati verificati con una
API di scena simulata, esclusivamente negli script di test non inclusi nel sito.

Il browser della sessione non disponeva di WebGL2 e bloccava la navigazione HTTP
locale e file. I controlli dell'interfaccia sono quindi stati provati caricando
il contenuto HTML nel browser, non tramite un URL pubblico. Non è stato possibile
verificare visivamente il rendering 3D vivo in tale ambiente. Gli HTML originali
sono invariati. Sono da verificare su dispositivi reali, in particolare Safari/iOS
per i gesti touch e la modalità a schermo intero.
