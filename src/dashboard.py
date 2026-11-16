"""Dashboard Streamlit per il data warehouse delle richieste.

Avvio:  streamlit run src/dashboard.py
Filtri nella barra laterale: periodo, zona, categoria di servizio.
"""
from pathlib import Path
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

DB = Path(__file__).resolve().parents[1] / "warehouse.db"
ACCENT = "#2F5D8C"
SCALA = ["#E8EEF5", "#9DB7D3", ACCENT, "#1B3A5C"]
GIORNI = ["Lunedi", "Martedi", "Mercoledi", "Giovedi", "Venerdi", "Sabato", "Domenica"]

st.set_page_config(page_title="Analisi richieste", layout="wide")


# ------------------------------------------------------------------ dati
@st.cache_resource
def connessione():
    if not DB.exists():
        st.error("warehouse.db non trovato. Esegui prima:  python src/etl.py")
        st.stop()
    return sqlite3.connect(DB, check_same_thread=False)


def q(sql, params=()):
    return pd.read_sql_query(sql, connessione(), params=params)


# Tutte le query partono da questa join "a stella" e applicano gli stessi filtri.
BASE = """
FROM fact_richieste f
JOIN dim_cliente   c  ON c.cliente_key   = f.cliente_key
JOIN dim_fornitore fo ON fo.fornitore_key = f.fornitore_key
JOIN dim_tempo     t  ON t.tempo_key     = f.tempo_key
WHERE t.data BETWEEN ? AND ?
  AND c.zona IN ({zone})
  AND fo.categoria_servizio IN ({cat})
"""


def costruisci(d1, d2, zone, cat):
    sql = BASE.format(zone=",".join("?" * len(zone)), cat=",".join("?" * len(cat)))
    return sql, [d1, d2, *zone, *cat]


# ------------------------------------------------------------------ filtri
lim = q("SELECT MIN(data) AS a, MAX(data) AS b FROM dim_tempo WHERE tempo_key IN (SELECT tempo_key FROM fact_richieste)").iloc[0]
tutte_zone = q("SELECT DISTINCT zona FROM dim_cliente ORDER BY zona")["zona"].tolist()
tutte_cat = q("SELECT DISTINCT categoria_servizio AS c FROM dim_fornitore ORDER BY c")["c"].tolist()

st.sidebar.header("Filtri")
periodo = st.sidebar.date_input("Periodo", (pd.to_datetime(lim.a), pd.to_datetime(lim.b)),
                                min_value=pd.to_datetime(lim.a), max_value=pd.to_datetime(lim.b))
zone = st.sidebar.multiselect("Zona", tutte_zone, default=tutte_zone)
cat = st.sidebar.multiselect("Categoria di servizio", tutte_cat, default=tutte_cat)

st.title("Analisi delle richieste")
st.caption("Dati sintetici · data warehouse a stella in SQLite")

if len(periodo) != 2 or not zone or not cat:
    st.info("Seleziona un periodo completo (data inizio e fine), almeno una zona e una categoria.")
    st.stop()

sql, par = costruisci(periodo[0].strftime("%Y-%m-%d"), periodo[1].strftime("%Y-%m-%d"), zone, cat)

# ------------------------------------------------------------------ KPI
k = q(f"""SELECT SUM(f.is_annullata = 0) AS gestite, COUNT(*) AS totali,
                 COALESCE(SUM(f.importo), 0) AS incassi,
                 AVG(CASE WHEN f.is_annullata = 0 THEN f.tempo_erogazione_min END) AS tempo,
                 SUM(f.is_ritardo) AS ritardi
          {sql}""", par).iloc[0]
cl = q(f"""SELECT COUNT(*) AS attivi, COALESCE(SUM(n >= 2), 0) AS ricorrenti FROM (
              SELECT f.cliente_key, COUNT(*) AS n {sql} AND f.is_annullata = 0 GROUP BY f.cliente_key)""", par).iloc[0]

if not k.totali:
    st.warning("Nessuna richiesta con i filtri selezionati.")
    st.stop()

gestite = int(k.gestite or 0)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Richieste gestite", f"{gestite:,}".replace(",", "."))
c2.metric("Incassi", f"€ {k.incassi:,.0f}".replace(",", "."))
c3.metric("Tempo medio di erogazione", f"{k.tempo:.0f} min" if pd.notna(k.tempo) else "n.d.")
c4.metric("Clienti attivi", f"{int(cl.attivi):,}".replace(",", "."))
c5.metric("Clienti che tornano", f"{100 * cl.ricorrenti / cl.attivi:.1f}%" if cl.attivi else "n.d.")
st.caption(f"Richieste annullate: {100 * (k.totali - gestite) / k.totali:.1f}% · "
           f"In ritardo sulle gestite: {100 * k.ritardi / gestite:.1f}% · "
           "«Clienti che tornano» = clienti attivi con almeno 2 richieste gestite nel periodo.")


def stile(fig, h=330):
    fig.update_layout(height=h, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="rgba(0,0,0,0)",
                      showlegend=False)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.2)")
    return fig


# ------------------------------------------------------------------ grafici
st.subheader("Andamento nel tempo")
gran = st.radio("Granularità", ["Mese", "Settimana"], horizontal=True, label_visibility="collapsed")
col = "t.anno * 100 + t.mese" if gran == "Mese" else "t.anno * 100 + t.settimana"
serie = q(f"SELECT {col} AS periodo, COUNT(*) AS richieste {sql} AND f.is_annullata = 0 GROUP BY 1 ORDER BY 1", par)
serie["periodo"] = serie["periodo"].astype(str)
fig = px.line(serie, x="periodo", y="richieste", markers=True, color_discrete_sequence=[ACCENT])
fig.update_xaxes(title=None, type="category")
fig.update_yaxes(title="Richieste")
st.plotly_chart(stile(fig), use_container_width=True)

a, b = st.columns(2)
with a:
    st.subheader("Top 5 fornitori per incassi")
    top = q(f"""SELECT fo.nome AS fornitore, SUM(f.importo) AS incassi {sql} AND f.is_annullata = 0
                GROUP BY fo.fornitore_key ORDER BY incassi DESC LIMIT 5""", par).iloc[::-1]
    fig = px.bar(top, x="incassi", y="fornitore", orientation="h", color_discrete_sequence=[ACCENT])
    fig.update_xaxes(title="Incassi (€)")
    fig.update_yaxes(title=None)
    st.plotly_chart(stile(fig), use_container_width=True)
with b:
    st.subheader("Richieste per zona")
    z = q(f"SELECT c.zona AS zona, COUNT(*) AS richieste, SUM(f.importo) AS incassi {sql} AND f.is_annullata = 0 GROUP BY c.zona ORDER BY richieste DESC", par)
    fig = px.bar(z, x="zona", y="richieste", color_discrete_sequence=[ACCENT], hover_data={"incassi": ":.0f"})
    fig.update_xaxes(title=None)
    fig.update_yaxes(title="Richieste")
    st.plotly_chart(stile(fig), use_container_width=True)

a, b = st.columns(2)
with a:
    st.subheader("Richieste per categoria di servizio")
    cc = q(f"SELECT fo.categoria_servizio AS categoria, COUNT(*) AS richieste {sql} AND f.is_annullata = 0 GROUP BY 1 ORDER BY richieste", par)
    fig = px.bar(cc, x="richieste", y="categoria", orientation="h", color_discrete_sequence=[ACCENT])
    fig.update_xaxes(title="Richieste")
    fig.update_yaxes(title=None)
    st.plotly_chart(stile(fig), use_container_width=True)
with b:
    st.subheader("Incassi per zona")
    fig = px.bar(z.sort_values("incassi"), x="incassi", y="zona", orientation="h", color_discrete_sequence=[ACCENT])
    fig.update_xaxes(title="Incassi (€)")
    fig.update_yaxes(title=None)
    st.plotly_chart(stile(fig), use_container_width=True)

# ------------------------------------------------------------------ analisi di base
st.subheader("Analisi di base")
a, b = st.columns(2)
with a:
    st.markdown("**Quando arrivano le richieste** (giorno × ora)")
    h = q(f"SELECT t.nome_giorno AS giorno, f.ora AS ora, COUNT(*) AS n {sql} AND f.is_annullata = 0 GROUP BY 1, 2", par)
    m = h.pivot(index="giorno", columns="ora", values="n").reindex(GIORNI).fillna(0)
    fig = px.imshow(m, aspect="auto", color_continuous_scale=SCALA, labels=dict(x="Ora", y="", color="Richieste"))
    st.plotly_chart(stile(fig, 300), use_container_width=True)
with b:
    st.markdown("**Richieste in ritardo per categoria** (% sulle gestite)")
    r = q(f"""SELECT fo.categoria_servizio AS categoria, 100.0 * SUM(f.is_ritardo) / COUNT(*) AS pct
              {sql} AND f.is_annullata = 0 GROUP BY 1 ORDER BY pct""", par)
    fig = px.bar(r, x="pct", y="categoria", orientation="h", color_discrete_sequence=[ACCENT])
    fig.update_xaxes(title="% in ritardo")
    fig.update_yaxes(title=None)
    st.plotly_chart(stile(fig, 300), use_container_width=True)
