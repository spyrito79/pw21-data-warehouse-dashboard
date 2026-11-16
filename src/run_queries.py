"""Esegue sql/queries.sql sul warehouse e stampa i risultati (alternativa al comando sqlite3)."""
from pathlib import Path
import sqlite3

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
testo = "\n".join(r for r in (ROOT / "sql" / "queries.sql").read_text(encoding="utf-8").splitlines()
                  if not r.startswith("."))
con = sqlite3.connect(ROOT / "warehouse.db")
pd.set_option("display.width", 160)
for blocco in testo.split(";"):
    righe = [r for r in blocco.splitlines() if r.strip()]
    if not any(not r.strip().startswith("--") for r in righe):
        continue
    titolo = next((r for r in righe if r.startswith("--")), "")
    print("\n" + titolo)
    print(pd.read_sql_query(blocco, con).to_string(index=False))
