# Server MCP Visura

Questa directory contiene il server Model Context Protocol (MCP) per Visura API. Permette agli agenti AI di interagire con il sistema catastale italiano (SISTER) in modo strutturato.

## Indice
- [Produzione (Docker)](#produzione-docker)
- [Sviluppo (Locale)](#sviluppo-locale)
- [Test](#test)
- [Esempi di Utilizzo](docs/mcp_examples.md)

---

## Produzione (Docker)

L'utilizzo di Docker è il modo raccomandato per eseguire il sistema in produzione. Il server MCP è un'immagine standalone leggera (`python:3.11-slim`).

### Avvio con Docker Compose
Eseguire i comandi dalla cartella `visura_mcp/`:

#### 1. API + MCP (Sistema completo)
Per avviare entrambi i servizi:
```bash
docker-compose up -d
```

#### 2. Solo MCP
Se la Visura API è già in esecuzione altrove (es. su un altro server):
```bash
docker-compose up -d visure-mcp
```

### Configurazione Connessione
In Docker, il server MCP si connette all'API tramite la variabile `VISURA_API_URL` definita nel file `docker-compose.yaml`:

- **Default**: `http://visure-api:8000` (risolve l'IP del container API nella stessa rete).
- **Custom**: Modifica la variabile nel `docker-compose.yaml` se l'API ha un indirizzo diverso.

**Endpoint**: `http://localhost:8001/mcp`

---

## Sviluppo (Locale)

Configurazione per lo sviluppo o test rapido senza Docker.

### 1. Installazione
Dalla cartella `visura_mcp/`:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configurazione Connessione
Prima di avviare il server, esporta l'indirizzo della tua istanza di Visura API:

```bash
# Se l'API gira localmente su porta 8000
export VISURA_API_URL=http://localhost:8000

# Oppure se l'API è in cloud/remoto
export VISURA_API_URL=https://tua-api-visure.com
```

### 3. Avvio del Server
Puoi avviare il server in modalità **Stdio** (comunicazione diretta) o **SSE** (HTTP):

**Modalità Stdio (Default per debugging):**
```bash
python server.py
```

**Modalità SSE (Via FastMCP CLI):**
```bash
fastmcp run server.py --transport streamable-http --port 8001
```

---

## Test

### MCP Inspector
Per testare tool e risorse durante lo sviluppo:
```bash
./scripts/test_mcp.sh
```
Questo avvierà l'interfaccia di test ufficiale per verificare il comportamento del server.

---

### Strumenti Disponibili
L'MCP espone diversi strumenti per gli agenti:
- **Visura**: `avvia_ricerca_immobili_o_terreni`, `avvia_ricerca_intestatari`, `recupera_risultati_ricerca`.
- **Catalogo**: `mcp_visure_search_comune`, `mcp_visure_list_parcels`, `mcp_visure_reload_catalog`.
- **Utility**: `mcp_visure_get_health`.

Vedi [Esempi di Utilizzo](docs/mcp_examples.md) per i dettagli.
