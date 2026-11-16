# PW 21 – Analisi dei dati per una startup di servizi on-demand

Prototipo minimale: dati sintetici → ETL → data warehouse a stella (SQLite) → dashboard Streamlit.

## Avvio rapido (macOS / Linux, circa 2 minuti)

```bash
cd pw21
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python src/generate_data.py      # 1. genera i CSV in data/
python src/etl.py                # 2. pulisce e carica warehouse.db
python src/run_queries.py        # 3. (facoltativo) stampa gli indicatori SQL
streamlit run src/dashboard.py   # 4. apre la dashboard su http://localhost:8501
```

Oppure tutto insieme: `bash run_all.sh`.
Su Windows: `.venv\Scripts\activate` al posto di `source .venv/bin/activate`.

## Struttura

| Percorso | Contenuto |
|---|---|
| `src/generate_data.py` | Generatore di dati inventati (seed fisso = riproducibile) |
| `src/etl.py` | Estrazione dai CSV, pulizia/uniformazione, caricamento in SQLite |
| `src/run_queries.py` | Esegue `sql/queries.sql` e stampa i risultati |
| `src/dashboard.py` | Dashboard interattiva Streamlit |
| `sql/schema.sql` | Schema a stella (1 tabella dei fatti + 4 dimensioni) |
| `sql/queries.sql` | Query degli indicatori (richieste, incassi, tempo medio, clienti che tornano, ...) |
| `data/*.csv` | Dati sintetici (clienti, fornitori, operatori, richieste) |
| `warehouse.db` | Data warehouse SQLite |
| `etl_report.txt` | Report di qualità dei dati dell'ultima esecuzione ETL |
| `docs/screenshots/` | Immagini della dashboard per il report |

## Parametri

`python src/generate_data.py --seed 42 --dirty 0.03`

- `--seed`: seme casuale (stesso seme = stessi dati).
- `--dirty`: quota di righe "sporche" inserite apposta (maiuscole/spazi incoerenti, date in formato diverso,
  virgola decimale, duplicati, tempi mancanti, una chiave esterna inesistente). Con `--dirty 0` i dati sono già puliti.

Volumi: 400 clienti, 300 fornitori, 350 operatori, 600 richieste (anno 2025).

## Modello a stella

```
dim_cliente ─┐
dim_fornitore ┼──< fact_richieste >── dim_tempo
dim_operatore ┘
```

Misure nella tabella dei fatti: `importo`, `tempo_erogazione_min`, `is_annullata`, `is_ritardo`.
Le dimensioni usano chiavi surrogate (`*_key`) e mantengono la chiave di business (`*_id`).

## Definizioni degli indicatori

- **Richieste gestite**: richieste non annullate.
- **Incassi**: somma degli importi delle richieste gestite (le annullate valgono 0). La zona è quella del cliente.
- **Tempo medio di erogazione**: media dei minuti sulle richieste gestite con tempo noto.
- **Clienti attivi**: clienti con almeno una richiesta gestita nel periodo/filtri selezionati.
- **Clienti che tornano**: % dei clienti attivi con almeno 2 richieste gestite.
- **In ritardo**: richieste con tempo di erogazione superiore alla soglia di servizio della categoria.

## Regole di pulizia dell'ETL

Trim e uniformazione maiuscole/minuscole di zone, categorie e stati · date in formato ISO ·
virgola decimale → punto · rimozione duplicati per chiave · scarto (con file `data/richieste_scartate.csv`)
delle richieste con cliente/fornitore/operatore inesistente · richieste annullate forzate a importo 0 e tempo NULL ·
tempi mancanti lasciati NULL (esclusi dalla media, non inventati).
