"""ETL: Estrazione (CSV) -> Trasformazione (pulizia) -> Caricamento (SQLite a stella).

Uso:
    python src/etl.py
Legge data/*.csv, ricrea warehouse.db e stampa un report di qualita' dei dati.
"""
from pathlib import Path
import sqlite3

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB = ROOT / "warehouse.db"
SCHEMA = ROOT / "sql" / "schema.sql"

ZONE_OK = {"nord", "sud", "est", "ovest", "centro"}
STATI_OK = {"completata", "completata in ritardo", "annullata"}
GIORNI = ["Lunedi", "Martedi", "Mercoledi", "Giovedi", "Venerdi", "Sabato", "Domenica"]
MESI = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto",
        "Settembre", "Ottobre", "Novembre", "Dicembre"]

report = []


def log(msg):
    report.append(msg)
    print(msg)


# ---------------------------------------------------------------- EXTRACT
def extract():
    return {n: pd.read_csv(DATA / f"{n}.csv", dtype=str) for n in
            ["clienti", "fornitori", "operatori", "richieste"]}


# ---------------------------------------------------------------- TRANSFORM
def pulisci_testo(s):
    return s.str.strip()


def tx_zona(s):
    z = s.str.strip().str.lower()
    ko = ~z.isin(ZONE_OK)
    if ko.any():
        raise ValueError(f"Zone non valide: {s[ko].unique()}")
    return z.str.capitalize()


def dedup(df, chiave, nome):
    n0 = len(df)
    df = df.drop_duplicates(subset=chiave, keep="first")
    log(f"[{nome}] duplicati rimossi: {n0 - len(df)}")
    return df


def tx_clienti(df):
    df = df.copy()
    df["cliente_id"] = pulisci_testo(df["cliente_id"])
    df["zona"] = tx_zona(df["zona"])
    # accetta sia AAAA-MM-GG sia GG/MM/AAAA
    d1 = pd.to_datetime(df["data_iscrizione"], format="%Y-%m-%d", errors="coerce")
    d2 = pd.to_datetime(df["data_iscrizione"], format="%d/%m/%Y", errors="coerce")
    df["data_iscrizione"] = d1.fillna(d2)
    nulle = df["data_iscrizione"].isna().sum()
    log(f"[clienti] date normalizzate in formato ISO; non interpretabili: {nulle}")
    df = df.dropna(subset=["data_iscrizione"])
    df["data_iscrizione"] = df["data_iscrizione"].dt.strftime("%Y-%m-%d")
    return dedup(df, ["cliente_id"], "clienti")


def tx_fornitori(df):
    df = df.copy()
    df["fornitore_id"] = pulisci_testo(df["fornitore_id"])
    df["nome"] = pulisci_testo(df["nome"])
    df["categoria_servizio"] = pulisci_testo(df["categoria_servizio"]).str.capitalize()
    df.loc[df["categoria_servizio"] == "Assistenza it", "categoria_servizio"] = "Assistenza IT"
    df["zona"] = tx_zona(df["zona"])
    return dedup(df, ["fornitore_id"], "fornitori")


def tx_operatori(df):
    df = df.copy()
    df["operatore_id"] = pulisci_testo(df["operatore_id"])
    df["zona"] = tx_zona(df["zona"])
    df["tipo_attivita"] = pulisci_testo(df["tipo_attivita"])
    return dedup(df, ["operatore_id"], "operatori")


def tx_richieste(df, cli, forn, ope):
    df = df.copy()
    for c in ["richiesta_id", "cliente_id", "fornitore_id", "operatore_id"]:
        df[c] = pulisci_testo(df[c])
    df["stato"] = df["stato"].str.strip().str.lower()
    ko = ~df["stato"].isin(STATI_OK)
    if ko.any():
        raise ValueError(f"Stati non validi: {df.loc[ko, 'stato'].unique()}")
    df["importo"] = pd.to_numeric(df["importo"].str.replace(",", ".", regex=False), errors="raise")
    df["tempo_erogazione_min"] = pd.to_numeric(df["tempo_erogazione_min"], errors="coerce")
    df["data_ora"] = pd.to_datetime(df["data_ora"], format="%Y-%m-%d %H:%M")
    df = dedup(df, ["richiesta_id"], "richieste")

    # integrita' referenziale: scarta richieste con chiavi inesistenti nelle dimensioni
    ok = (df["cliente_id"].isin(cli["cliente_id"]) & df["fornitore_id"].isin(forn["fornitore_id"])
          & df["operatore_id"].isin(ope["operatore_id"]))
    log(f"[richieste] scartate per chiave esterna inesistente: {(~ok).sum()}")
    scartate = DATA / "richieste_scartate.csv"
    scartate.unlink(missing_ok=True)
    if (~ok).any():
        df[~ok].to_csv(scartate, index=False)
    df = df[ok].copy()

    # regole di coerenza di business
    ann = df["stato"] == "annullata"
    df.loc[ann, ["importo", "tempo_erogazione_min"]] = [0.0, pd.NA]
    mancanti = (~ann & df["tempo_erogazione_min"].isna()).sum()
    log(f"[richieste] completate senza tempo di erogazione (lasciate NULL, escluse dalla media): {mancanti}")
    df["is_annullata"] = ann.astype(int)
    df["is_ritardo"] = (df["stato"] == "completata in ritardo").astype(int)
    return df


def costruisci_dim_tempo(date_min, date_max):
    d = pd.DataFrame({"data": pd.date_range(date_min, date_max, freq="D")})
    iso = d["data"].dt.isocalendar()
    out = pd.DataFrame({
        "tempo_key": d["data"].dt.strftime("%Y%m%d").astype(int),
        "data": d["data"].dt.strftime("%Y-%m-%d"),
        "anno": d["data"].dt.year,
        "trimestre": d["data"].dt.quarter,
        "mese": d["data"].dt.month,
        "nome_mese": d["data"].dt.month.map(lambda m: MESI[m - 1]),
        "settimana": iso["week"].astype(int),
        "giorno_settimana": d["data"].dt.dayofweek + 1,
        "nome_giorno": d["data"].dt.dayofweek.map(lambda g: GIORNI[g]),
        "is_weekend": (d["data"].dt.dayofweek >= 5).astype(int),
    })
    return out


# ---------------------------------------------------------------- LOAD
def load(cli, forn, ope, ric):
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA.read_text(encoding="utf-8"))

    cli.to_sql("dim_cliente", con, if_exists="append", index=False)
    forn.to_sql("dim_fornitore", con, if_exists="append", index=False)
    ope.to_sql("dim_operatore", con, if_exists="append", index=False)

    # calendario completo degli anni coperti dai dati (anche i giorni senza richieste)
    tempo = costruisci_dim_tempo(f"{ric['data_ora'].min().year}-01-01", f"{ric['data_ora'].max().year}-12-31")
    tempo.to_sql("dim_tempo", con, if_exists="append", index=False)

    # sostituisce le chiavi di business con le chiavi surrogate delle dimensioni
    k_cli = pd.read_sql("SELECT cliente_key, cliente_id FROM dim_cliente", con)
    k_for = pd.read_sql("SELECT fornitore_key, fornitore_id FROM dim_fornitore", con)
    k_ope = pd.read_sql("SELECT operatore_key, operatore_id FROM dim_operatore", con)
    f = (ric.merge(k_cli, on="cliente_id").merge(k_for, on="fornitore_id").merge(k_ope, on="operatore_id"))
    f["tempo_key"] = f["data_ora"].dt.strftime("%Y%m%d").astype(int)
    f["ora"] = f["data_ora"].dt.hour
    cols = ["richiesta_id", "cliente_key", "fornitore_key", "operatore_key", "tempo_key", "ora",
            "importo", "tempo_erogazione_min", "stato", "is_annullata", "is_ritardo"]
    f[cols].to_sql("fact_richieste", con, if_exists="append", index=False)
    con.commit()

    # controlli finali sull'archivio
    c = con.cursor()
    orfani = c.execute("""SELECT COUNT(*) FROM fact_richieste f
        LEFT JOIN dim_cliente c USING(cliente_key) WHERE c.cliente_key IS NULL""").fetchone()[0]
    assert orfani == 0, "Righe di fatto orfane!"
    for t in ["dim_cliente", "dim_fornitore", "dim_operatore", "dim_tempo", "fact_richieste"]:
        log(f"[load] {t}: {c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]} righe")
    con.close()


def main():
    raw = extract()
    log("[extract] righe lette: " + ", ".join(f"{k}={len(v)}" for k, v in raw.items()))
    cli = tx_clienti(raw["clienti"])
    forn = tx_fornitori(raw["fornitori"])
    ope = tx_operatori(raw["operatori"])
    ric = tx_richieste(raw["richieste"], cli, forn, ope)
    load(cli, forn, ope, ric)
    (ROOT / "etl_report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    log("ETL completato -> warehouse.db")


if __name__ == "__main__":
    main()
