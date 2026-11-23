# Contratto tecnico

Il canvas deve disegnare una scena WebGL navigabile con librerie incorporate. La vista di piano isola solaio e muri bassi. Le viste esterne possono rappresentare prospetti differenti. Esponi lo stato del rendering con `window.__sceneState`, inclusi modalità corrente, contatore dei frame e parametri della camera. Esponi le operazioni realmente implementate con `window.__sceneControls`. Conserva le attribuzioni delle librerie.

## Gate di consegna

Verifica offline la presenza della scena, tutte le viste, i controlli da tastiera, la risposta a puntatore e touch e il ripristino. Controlla le schermate dei piani e le sovrapposizioni sulle fonti separatamente dalla verifica del browser. Registra inizio, fine, limiti e collegamenti alle evidenze.
