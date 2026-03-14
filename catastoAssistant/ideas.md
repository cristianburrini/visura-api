



Sottomissione massiva di visure.

Costruire una API per gestire una sottomissione massiva di visure.
L'API supportera 3 scenari di richieste:
1) richiesta massiva di visure immobili in una data lista di particelle. 
2) richiesta massive di visure degli intestatari di una data lista di subalterni. 
3) richiesta massiva di visure immobili e contestualmente la visura di tutti gli intestatari associati agli immobili risultanti dalla prima operazione. 

IL sistema modellera la richiesta come una schedulazione di targets di visure (particelle o subalterni) in una coda, implementanto come nuova tabella SCHEDULED_VISURES. 

L'API garantira che non ci siano processing inutili:
1) target duplicati nella coda non verranno inseriti
2) non venga schedulata una nuova visura  per i target per cui si hanno gia i risultanti in cache (sia visura immobili che visura intestati)

Un background job si occupera di processare la coda di target sottomettendo la corretta tipologia di richiesta di visura per ciascun target.

Il background job effettuera il polling della richiesta e quando la visura sara pronta e salvata in cache, la togliera dalla coda per passare alla prossima. 
In questo modo lo stato di avanzamento della sottomissione massiva sara sempre presente nel db e sopravvivera a riavvii del servizio.

Il background job schedulera  fino a X visure in parallelo (parametro di ambiente configurabile) dalla coda (marcando il loro stato processing = "submitted"), evitando di sovraccaricare il portale SISTER. 

In caso di errore durante la visura, il target verra rimosso dalla coda e lo stato di processing sara "error", per permettere eventualy retry. (che dovra essere fatto manualmente con una update sql sullo stato del target da error a pending)
In caso di successo, la particella verra rimossa dalla coda e lo stato di processing sara "done".

La coda implementata nella tabella SCHEDULED_VISURES avra una riga per target (particella o subalterno) cosicche sia facilmente alterabile via sql per permettere di aggiungere, rimuovere, riprovare o modificare targets in corso d'opera. 

Le entries nella  coda avranno anche timestamps per permettere di identificare quando i target sono stati inseriti e rimossi dalla coda e quindi monitorare la velocita del sistema. 

Nota: al riavvio, il background job deve risottomettere tutte i target correntemente marcati "submitted" nella coda. (la sottomissione di visura interrotta dovrebbe essere un operazione idempotente e permettere un automatico resume del processo in caso di crash/shutdown).

Testing da effettuare in locale senza docker containers: 
1) Implementa unit tests per la logica di business e per il background job. 
2) Implementa integration test per la persistenza e gestione della coda. 
2) fai il mock del componente visure-api e testa le API contro un db di test caricato con i vari scenari.  

Quando tutti i test passano, puoi procedere con il deployment sui container docker (che va effettuato in modo gracefull facendo il down dal compose file dell'MCP Server (lasciando a docker di fare il down di tutti i suoi componenti) e poi facendo il rebuild e up dello stesso compose file, per evitare di corrompere lo stato della sessione SISTER gestita dalla API core).



Arricchimento
Integrare l'estrazione della data di nascita e sesso dal codice fiscale, usando libreria reverse-codice fiscale. Arricchire il DB con queste informazioni. 

Velocizzare lo scraping. 
Caricare un report standardizzato dei necrologi sul comune richiesto (ottenuto tramite agente). Caricare nel DB il necrologio ed usarlo per individuare eventuali immobili intestati ai defunti = predirre la successione. 
 
Sorgente del catalogo
 il DB contiene la struttura gerarchica dei regioni, province, comuni,  fogli, particelle cosi da supportare scrape automatizzate su larga scala
** I dati vengono caricati da file csv o parquet all'avvio del servizio. Idealmente vengono presi in automatico da questo repo. https://github.com/ondata/dati_catastali/tree/main
Ecco lo script di estrazione di dati csv da un solo file di GML di quel repo.  
echo '"Codice Comune","Codice Sezione","Numero Foglio","Flags","Particella"' 
grep -h "<CP:CadastralParcel" *.gml | sed -n -E 's/.*gml:id="CadastralParcel\.IT\.AGE\.PLA\.([[:upper:]][[:digit:]]{3})([_A-Z])([[:digit:]]{4})([[:digit:]]{2})\.([[:digit:]]+)".*/\1,\2,\3,\4,\5/p' | sort -u