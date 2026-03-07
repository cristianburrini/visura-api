# Server MCP Visura

Questa directory contiene il server Model Context Protocol (MCP) per Visura API. Permette agli agenti AI di interagire con il sistema catastale italiano (SISTER) in modo strutturato e documentato.

## Funzionalità
- **Tool**: Esegue visure, recupera risultati e cerca intestatari di immobili.
- **Risorse**: Documentazione di alta qualità, incluse specifiche OpenAPI e workflow Arazzo per orchestrazioni complesse.
- **Prompt**: Prompt predefiniti per aiutare gli agenti a iniziare correttamente.

## Installazione
1. Installa le dipendenze:
   ```bash
   pip install -r requirements.txt
   ```
2. Configura l'ambiente:
   Assicurati che `VISURA_API_URL` sia impostato sull'indirizzo della tua istanza di `visura-api` in esecuzione.

## Avvio del Server
Puoi eseguire il server in modalità stdio (per uso locale) o in modalità SSE (per uso remoto).

### Modalità Stdio
```bash
python server.py
```

### Modalità SSE (Remoto)
Usa la configurazione Docker con `APP_MODE=MCP`. Vedi le istruzioni Docker sotto.

## Integrazione Docker
Il servizio può essere eseguito interamente tramite Docker. Per avviare solo il server MCP:

```bash
docker-compose run -e APP_MODE=MCP -p 8001:8001 visura-api
```

Oppure, per avviare sia l'API che il server MCP:

```bash
docker-compose up
```

In modalità MCP, il server sarà accessibile via SSE su `http://localhost:8001/mcp/sse`.

## Test
Usa lo script fornito:
```bash
./scripts/test_mcp.sh
```
Questo avvierà l'MCP Inspector per testare i tool e le risorse.
