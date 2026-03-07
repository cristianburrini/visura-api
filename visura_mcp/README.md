# Server MCP Visura

Questa directory contiene il server Model Context Protocol (MCP) per Visura API. Permette agli agenti AI di interagire con il sistema catastale italiano (SISTER) in modo strutturato e documentato.

## Funzionalità
- **Tool**: Esegue visure, recupera risultati e cerca intestatari di immobili.
- **Risorse**: Documentazione di alta qualità, incluse specifiche OpenAPI e workflow Arazzo per orchestrazioni complesse.
- **Prompt**: Prompt predefiniti per aiutare gli agenti a iniziare correttamente.

## Integrazione Docker
Il servizio può essere eseguito interamente tramite Docker. 

### Avvio di un container docker che espone sia l'API che il server MCP
Se si vuole esporre il servizio ad automatizioni tradizionali ed ad agenti AI contemporaneamente, si può avviare un container docker che espone sia l'API (porta 8000) che il server MCP (porta 8001):

```bash
docker-compose up
```
L'MCP server sarà accessibile via SSE su `http://localhost:8001/mcp/sse`.


### Avvio del server MCP 
Il server MCP può essere avviato in modalità remota (SSE) senza esporre l'API pubblicamente. In questa modalita l'MCP server accede ad una instanza privata e colocata dell'API. 

```bash
docker-compose run -e APP_MODE=MCP visura-api
```
Per cambiare la porta del server MCP:

```bash
docker-compose run -e APP_MODE=MCP -p 8001:<target_port> visura-api
```


## Sviluppo in locale (senza Docker)
### Installazione 
1. Installa le dipendenze:
   ```bash
   pip install -r requirements.txt
   ```
2. Configura l'ambiente:
   Assicurati che `VISURA_API_URL` sia impostato sull'indirizzo della tua istanza di `visura-api` in esecuzione.

### Avvio del Server
Puoi eseguire il server in modalità stdio (per uso locale) o in modalità SSE (per uso remoto).

### Modalità Stdio
```bash
python server.py
```

### Modalità SSE (Remoto)
Usa la configurazione Docker con `APP_MODE=MCP`. Vedi le istruzioni Docker sotto.

### MCP Inspector Test
Usa lo script fornito:
```bash
./scripts/test_mcp.sh
```
Questo avvierà l'MCP Inspector per testare i tool e le risorse.


