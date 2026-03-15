import pytest
import os
from bs4 import BeautifulSoup
from utils import parse_table, is_session_expired, is_no_results_found

SNAPSHOT_DIR = "tests/snapshots"

def test_parse_intestati_from_snapshot():
    snapshot_path = os.path.join(SNAPSHOT_DIR, "fabbricati_intestati.html")
    
    with open(snapshot_path, "r", encoding="utf-8") as f:
        html_content = f.read()
        
    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table", class_="listaIsp4")
    assert table is not None
    
    data = parse_table(str(table))
    assert len(data) > 0
    first_row = data[0]
    
    assert "STEFANINI ITALO" in first_row["Nominativo o denominazione"]
    assert "STFTLI63S21E715M" == first_row["Codice fiscale"]
    assert "Proprieta'" in first_row["Titolarità"]
    assert "1/1" in first_row["Quota"]

def test_parse_terreni_results_from_snapshot():
    snapshot_path = os.path.join(SNAPSHOT_DIR, "terreni_lista_immobili.html")
    
    with open(snapshot_path, "r", encoding="utf-8") as f:
        html_content = f.read()
        
    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table", class_="listaIsp4")
    assert table is not None
    
    data = parse_table(str(table))
    assert len(data) == 1
    row = data[0]
    
    assert row["Foglio"] == "135"
    assert row["Particella"] == "161"
    assert "ENTE URBANO" in row["Qualità"]
    assert row["are"] == "13"
    assert row["ca"] == "40"
    assert row["Partita"] == "0000001"

def test_no_results_found_logic():
    # TEST THE ACTUAL LOGIC from utils.py
    snapshot_path = os.path.join(SNAPSHOT_DIR, "nessuna_corrispondenza.html")
    
    with open(snapshot_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # We test the function extracted in utils.py
    assert is_no_results_found(html_content) is True

def test_session_expired_logic():
    # TEST THE ACTUAL LOGIC from utils.py
    snapshot_path = os.path.join(SNAPSHOT_DIR, "sessione_scaduta.html")
    
    with open(snapshot_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # We test the function extracted in utils.py
    assert is_session_expired(html_content) is True

def test_large_result_set_snapshot():
    snapshot_path = os.path.join(SNAPSHOT_DIR, "fabbricati_lista_immobili.html")
    
    with open(snapshot_path, "r", encoding="utf-8") as f:
        html_content = f.read()
        
    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table", class_="listaIsp4")
    assert table is not None
    
    data = parse_table(str(table))
    assert len(data) == 14
    
    sub_12_row = next((r for r in data if r.get("Sub") == "12"), None)
    assert sub_12_row is not None
    assert "VIA PESCIATINA n. 564" in sub_12_row["Indirizzo"]
    assert "1931,55" in sub_12_row["Rendita"]

def test_visura_flow_simulation():
    # Simulates a sequence of parsing
    results_path = os.path.join(SNAPSHOT_DIR, "fabbricati_risultati_per_flow.html")
    intestati_path = os.path.join(SNAPSHOT_DIR, "fabbricati_intestati.html")
    
    # 1. Parse Results
    with open(results_path, "r", encoding="utf-8") as f:
        html_results = f.read()
    data_results = parse_table(html_results)
    assert len(data_results) > 0
    
    # 2. Parse Intestati
    with open(intestati_path, "r", encoding="utf-8") as f:
        html_intestati = f.read()
    data_intestati = parse_table(html_intestati)
    
    assert len(data_intestati) > 0
    assert "STEFANINI ITALO" in data_intestati[0]["Nominativo o denominazione"]

def test_parse_table_generic():
    html = """
    <table>
        <thead>
            <tr><th>Header 1</th><th>Header 2</th></tr>
        </thead>
        <tbody>
            <tr><td>Val 1</td><td>Val 2</td></tr>
        </tbody>
    </table>
    """
    data = parse_table(html)
    assert len(data) == 1
    assert data[0]["Header 1"] == "Val 1"
    assert data[0]["Header 2"] == "Val 2"
