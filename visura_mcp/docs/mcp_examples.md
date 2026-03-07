# Esempi di Utilizzo MCP Visura

Questa guida mostra come richiedere visure catastali tramite il server MCP Visura, con prompts di esempio e tracce complete delle interazioni.

> Tutti gli esempi usano: **Foglio 135, Particella 161, Comune di LUCCA (LU)**

---

## Caso 1 — Ricerca Terreni (flusso a fase singola)

Per i terreni, una sola chiamata avvia la ricerca **e** recupera gli intestatari automaticamente.

### Prompt dell'utente
> _"Chi sono i proprietari del terreno al foglio 135, particella 161 di Lucca?"_

### Flusso MCP

**Step 1 — Avvia la ricerca**

Tool: `avvia_ricerca_immobili_o_terreni`
```json
{
  "provincia": "Lucca",
  "comune": "LUCCA",
  "foglio": "135",
  "particella": "161",
  "tipo_catasto": "T"
}
```

Risposta:
```
Visura requested successfully. Request IDs: req_T_1741370400000. Status: queued.
```

**Step 2 — Polling del risultato**

Tool: `richiedi_stato_ricerca`
```json
{
  "request_id": "req_T_1741370400000"
}
```

Risposta (in elaborazione):
```json
{ "status": "processing" }
```

Risposta (completata):
```json
{
  "request_id": "req_T_1741370400000",
  "tipo_catasto": "T",
  "status": "completed",
  "data": {
    "immobili": [
      {
        "Foglio": "135",
        "Particella": "161",
        "Sub": null,
        "Qualità": "SEMINATIVO",
        "Classe": "3",
        "Ettari": "0",
        "Are": "15",
        "Centiare": "80",
        "Reddito Dominicale": "4,35",
        "Reddito Agrario": "2,81"
      }
    ],
    "results": [
      {
        "immobile": { "Foglio": "135", "Particella": "161" },
        "intestati": [
          {
            "Nominativo o denominazione": "BIANCHI MARIO",
            "Codice fiscale": "BNCMRA60A01G628Z",
            "Titolarità": "Proprietà per 1/2"
          },
          {
            "Nominativo o denominazione": "BIANCHI ANNA",
            "Codice fiscale": "BNCNNA63D50G628Z",
            "Titolarità": "Proprietà per 1/2"
          }
        ]
      }
    ],
    "total_results": 1
  }
}
```

### Risposta all'utente (esempio)
> _"Il terreno (seminativo, classe 3, 15 are e 80 centiare) è di proprietà al 50% ciascuno di Mario Bianchi e Anna Bianchi."_

---

## Caso 2 — Ricerca Fabbricati con intestatari (flusso a due fasi)

Per i fabbricati, la Fase 1 restituisce la lista degli immobili. Per ottenere i proprietari di un subalterno specifico serve la Fase 2.

### Prompt dell'utente
> _"Voglio sapere chi possiede il subalterno 4 nel fabbricato a foglio 135, particella 161 di Lucca."_

### Flusso MCP

**Step 1 — Avvia la ricerca fabbricati**

Tool: `avvia_ricerca_immobili_o_terreni`
```json
{
  "provincia": "Lucca",
  "comune": "LUCCA",
  "foglio": "135",
  "particella": "161",
  "tipo_catasto": "F"
}
```

Risposta:
```
Visura requested successfully. Request IDs: req_F_1741370400001. Status: queued.
```

**Step 2 — Recupera la lista degli immobili (polling)**

Tool: `richiedi_stato_ricerca`
```json
{ "request_id": "req_F_1741370400001" }
```

Risposta (completata):
```json
{
  "request_id": "req_F_1741370400001",
  "tipo_catasto": "F",
  "status": "completed",
  "data": {
    "immobili": [
      {
        "Foglio": "135", "Particella": "161", "Sub": "1",
        "Categoria": "A/2", "Classe": "4", "Consistenza": "6",
        "Rendita": "412,35", "Indirizzo": "VIA DEI BORGHI 12", "Partita": "43210"
      },
      {
        "Foglio": "135", "Particella": "161", "Sub": "2",
        "Categoria": "C/6", "Classe": "0", "Consistenza": "18",
        "Rendita": "28,40", "Indirizzo": "VIA DEI BORGHI 12", "Partita": "43210"
      },
      {
        "Foglio": "135", "Particella": "161", "Sub": "4",
        "Categoria": "A/3", "Classe": "3", "Consistenza": "4.5",
        "Rendita": "258,22", "Indirizzo": "VIA DEI BORGHI 12 INT.4", "Partita": "43211"
      }
    ],
    "total_results": 3
  }
}
```

**Step 3 — Richiesta intestatari del subalterno 4**

Tool: `avvia_ricerca_intestatari`
```json
{
  "provincia": "Lucca",
  "comune": "LUCCA",
  "foglio": "135",
  "particella": "161",
  "tipo_catasto": "F",
  "subalterno": "4"
}
```

Risposta:
```
Intestati search requested. Request ID: intestati_F_4_1741370400002. Status: queued.
```

**Step 4 — Polling intestatari**

Tool: `richiedi_stato_ricerca`
```json
{ "request_id": "intestati_F_4_1741370400002" }
```

Risposta (completata):
```json
{
  "request_id": "intestati_F_4_1741370400002",
  "status": "completed",
  "data": {
    "immobile": { "Foglio": "135", "Particella": "161", "Sub": "4" },
    "intestati": [
      {
        "Nominativo o denominazione": "ROSSI GIUSEPPE",
        "Codice fiscale": "RSSGPP75M10E715E",
        "Titolarità": "Proprietà per 1/1"
      }
    ],
    "total_intestati": 1
  }
}
```

### Risposta all'utente (esempio)
> _"Il subalterno 4 (appartamento A/3, 4.5 vani, rendita €258,22 in Via dei Borghi 12 int.4) è di proprietà esclusiva di Giuseppe Rossi."_

---

## Caso 3 — Ricerca Completa (Terreni + Fabbricati)

Omettendo `tipo_catasto`, il server avvia entrambe le ricerche in serie e restituisce due `request_id`.

### Prompt dell'utente
> _"Cerca tutti gli immobili al foglio 135, particella 161 di Lucca, sia terreni che fabbricati."_

### Flusso MCP

**Step 1 — Avvia entrambe le ricerche**

Tool: `avvia_ricerca_immobili_o_terreni`
```json
{
  "provincia": "Lucca",
  "comune": "LUCCA",
  "foglio": "135",
  "particella": "161"
}
```

Risposta:
```
Visura requested successfully. Request IDs: req_T_1741370400010, req_F_1741370400011. Status: queued.
```

**Step 2 — Polling di entrambi i risultati**

Tool: `richiedi_stato_ricerca` × 2 (un chiamata per ID):
- `req_T_1741370400010` → risultato terreni (come Caso 1)
- `req_F_1741370400011` → risultato fabbricati (come Caso 2, Fase 1)

Poi, per ogni subalterno di interesse, si prosegue con `avvia_ricerca_intestatari` come nel Caso 2.

### Note sul flusso
- Il polling va ripetuto ogni 5–10 secondi finché `status != "processing"`.
- In caso di coda lunga, `GET /health` mostra il numero di richieste in attesa.

---

## Gestione Errori Comuni

| Situazione | Risposta API | Come gestire |
|---|---|---|
| Particella non trovata | `status: completed`, `data.error: "NESSUNA CORRISPONDENZA TROVATA"` | Informare l'utente e verificare i dati |
| Partita "Soppressa" | Immobile incluso senza intestati | Normale per unità non più attive |
| API non raggiungibile | `Error: Connection refused` | Verificare che il servizio API sia attivo e autenticato |
| Richiesta ancora in coda | `status: processing` | Riprovare tra qualche secondo |
