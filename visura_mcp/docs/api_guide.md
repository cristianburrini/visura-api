# Guida Visura API & SISTER per Agenti

Questa guida aiuta a capire come funziona il sistema catastale italiano (SISTER) e come utilizzare efficacemente i tool di Visura API.

## Concetti Base

### Identificativi Catastali
- **Provincia**: La provincia amministrativa (es. ROMA, MILANO). Solitamente 2 o 4 caratteri o il nome completo.
- **Comune**: Il comune specifico.
- **Foglio**: Una porzione del territorio comunale. Sempre richiesto.
- **Particella**: Una specifica porzione di terreno o il perimetro esterno di un edificio. Sempre richiesto.
- **Subalterno**: Richiesto per i **Fabbricati** per identificare uno specifico appartamento o ufficio. NON usato per i **Terreni**.
- **Sezione**: Alcuni comuni sono divisi in sezioni (es. 'A', 'B'). Usa se nota, altrimenti ometti.

### Tipi di Ricerca
1. **Terreni (T)**: Ricerca per terreni. Restituisce i proprietari (intestati) direttamente nel risultato della visura.
2. **Fabbricati (F)**: Ricerca per edifici. Se cerchi una particella con molti subalterni, potresti ricevere una lista di immobili. Dovrai quindi usare `avvia_ricerca_intestatari` con un `subalterno` specifico per ottenere i proprietari.

## Flusso Operativo
1. **Ricerca Iniziale**: Usa `avvia_ricerca_immobili_o_terreni` con `tipo_catasto=None` se non sei sicuro di cercare terreni o fabbricati.
2. **Verifica Stato**: Usa `recupera_risultati_ricerca` per attendere passivamente il risultato, o `richiedi_stato_ricerca` per un controllo veloce.
3. **Analisi Risultati**:
   - Se `tipo_catasto='T'`, solitamente hai già tutte le informazioni.
   - Se `tipo_catasto='F'`, verifica se è necessario un `subalterno` specifico.
4. **Ricerca Intestati**: Se mancano i proprietari per un'unità immobiliare, usa `avvia_ricerca_intestatari`.

## Errori Comuni
- **Nomi Province**: Assicurati di usare il nome standard italiano.
- **Timeout Sessione**: Il sistema potrebbe impiegare alcuni minuti per processare le visure. Richiama sempre iterativamente `recupera_risultati_ricerca` se ricevi timeout.

## Catalog & Validazione

Il sistema include un catalogo statico di comuni, fogli e particelle per migliorare la precisione delle ricerche.

### Ricerca Comuni
Usa `mcp_visure_search_comune` per trovare il **Codice Catastale** corretto di un comune. Questo codice è fondamentale per l'accuratezza della visura.

### Validazione Input
Le richieste inviate a `avvia_ricerca_immobili_o_terreni` vengono validate automaticamente contro il catalogo:
- Se il comune non esiste: Errore 400.
- Se il foglio o la particella non sono censiti per quel comune: Errore 400.

Usa `mcp_visure_list_parcels` per verificare quali fogli e particelle sono validi per un determinato comune prima di avviare una ricerca costosa sul portale SISTER.
