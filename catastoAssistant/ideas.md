
1) il DB contiene la struttura gerarchica dei regioni, province, comuni,  fogli, particelle cosi da supportare scrape automatizzate su larga scala
** I dati vengono caricati da file csv o parquet all'avvio del servizio. Idealmente vengono presi in automatico da questo repo. https://github.com/ondata/dati_catastali/tree/main
Ecco lo script di estrazione di dati csv da un solo file di GML di quel repo.  
echo '"Codice Comune","Codice Sezione","Numero Foglio","Flags","Particella"' 
grep -h "<CP:CadastralParcel" *.gml | sed -n -E 's/.*gml:id="CadastralParcel\.IT\.AGE\.PLA\.([[:upper:]][[:digit:]]{3})([_A-Z])([[:digit:]]{4})([[:digit:]]{2})\.([[:digit:]]+)".*/\1,\2,\3,\4,\5/p' | sort -u

2) il proxy potrebbe non cachare bene le richieste perche la query string cambia spesso. Introdurre una normalizzazione della query string prima di cachare. 
ex: tutte le stringe in uppercase? rimuovere spazi? 

3) l'api core ha un bug dove la sigla della provincia TR viene sempre scambiata per Trapani. Aggiungere un flag per forzare la ricerca esatta (default false) per aumentare l'affidabilita dell'API. 
Vedere se e' possibile risolvere il prolema validando l'input dell'utente contro le infor del catasto nel DB per effettuare una migliore normalizzazione (non e' detto che il catasto sia allineato a SISTER -> Magari meglio fare il fetch delle info del comune da SISTER e validarle. Forse e' il caso di fare un mapping fra dati catasto e nomi sister ?)


costruire una API per orchestrare la ricerca gerarchia di un intero comune o foglio.   


integrare l'estrazione della data di nascita e sesso dal codice fiscale, usando libreria reverse-codice fiscale. Arricchire il DB con queste informazioni. 
Velocizzare lo scraping. 
Caricare un report standardizzato dei necrologi sul comune richiesto (ottenuto tramite agente). Caricare nel DB il necrologio ed usarlo per individuare eventuali immobili intestati ai defunti = predirre la successione. 
 