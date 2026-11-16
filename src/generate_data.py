"""Generatore di dati sintetici per il PW 21 (startup di servizi on-demand).

Produce 4 file CSV in data/: clienti, fornitori, operatori, richieste.
Tutti i dati sono inventati: nessuna informazione personale.
Con un seed fisso il risultato e' sempre lo stesso (riproducibile).

Uso:
    python src/generate_data.py [--seed 42] [--dirty 0.03]

--dirty e' la percentuale di righe "sporche" (formati incoerenti, duplicati,
valori mancanti) inserite apposta per dare un senso alla fase di pulizia dell'ETL.
"""
import argparse
import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

N_CLIENTI, N_FORNITORI, N_OPERATORI, N_RICHIESTE = 400, 300, 350, 600
START, END = date(2025, 1, 1), date(2025, 12, 31)

ZONE = ["Nord", "Sud", "Est", "Ovest", "Centro"]
PESO_ZONE = [0.26, 0.16, 0.18, 0.14, 0.26]

# categoria -> (prezzo medio EUR, durata media min, soglia SLA min)
CATEGORIE = {
    "Idraulica":       (95, 70, 90),
    "Elettricista":    (85, 60, 80),
    "Pulizie":         (60, 120, 150),
    "Trasloco":        (210, 240, 300),
    "Giardinaggio":    (75, 110, 140),
    "Assistenza IT":   (70, 45, 60),
}
PESO_CATEGORIE = [0.18, 0.17, 0.25, 0.08, 0.12, 0.20]

TIPI_ATTIVITA = ["Intervento a domicilio", "Consulenza da remoto", "Ispezione", "Consegna e montaggio"]
PREFISSI = {
    "Idraulica": ["Idro", "Aqua", "Tubi"], "Elettricista": ["Volt", "Elettro", "Lumen"],
    "Pulizie": ["Pulito", "Splendor", "Casa"], "Trasloco": ["Mover", "Trasporti", "Scatola"],
    "Giardinaggio": ["Verde", "Flora", "Orto"], "Assistenza IT": ["Byte", "Tech", "Net"],
}
SUFFISSI = ["Service", "Pro", "Team", "Express", "Solutions", "Group"]

STATI_OK = "completata"
STATO_RITARDO = "completata in ritardo"
STATO_ANN = "annullata"


def scrivi(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def genera_clienti(rnd):
    rows = []
    for i in range(1, N_CLIENTI + 1):
        zona = rnd.choices(ZONE, PESO_ZONE)[0]
        iscr = date(2024, 7, 1) + timedelta(days=rnd.randint(0, (END - date(2024, 7, 1)).days - 5))
        rows.append([f"C{i:04d}", zona, iscr.isoformat()])
    return rows


def genera_fornitori(rnd):
    rows = []
    cats = list(CATEGORIE)
    for i in range(1, N_FORNITORI + 1):
        cat = rnd.choices(cats, PESO_CATEGORIE)[0]
        nome = f"{rnd.choice(PREFISSI[cat])} {rnd.choice(SUFFISSI)} {i:03d}"
        rows.append([f"F{i:04d}", nome, cat, rnd.choices(ZONE, PESO_ZONE)[0]])
    return rows


def genera_operatori(rnd):
    return [[f"O{i:04d}", rnd.choices(ZONE, PESO_ZONE)[0], rnd.choice(TIPI_ATTIVITA)]
            for i in range(1, N_OPERATORI + 1)]


def data_ora_realistica(rnd):
    """Giorno e ora con stagionalita': crescita nell'anno, piu' richieste nei feriali,
    picchi la mattina (8-11) e la sera (17-20)."""
    giorni = (END - START).days + 1
    pesi_g = []
    for k in range(giorni):
        d = START + timedelta(days=k)
        crescita = 1 + 0.8 * k / giorni                     # la startup cresce
        sett = {0: 1.1, 1: 1.1, 2: 1.0, 3: 1.0, 4: 1.2, 5: 0.7, 6: 0.45}[d.weekday()]
        stag = 1.25 if d.month in (3, 4, 9, 10) else (0.8 if d.month == 8 else 1.0)
        pesi_g.append(crescita * sett * stag)
    d = START + timedelta(days=rnd.choices(range(giorni), pesi_g)[0])
    pesi_h = {7: 2, 8: 6, 9: 8, 10: 7, 11: 5, 12: 3, 13: 2, 14: 4, 15: 5, 16: 5, 17: 7, 18: 8, 19: 6, 20: 3}
    h = rnd.choices(list(pesi_h), list(pesi_h.values()))[0]
    return datetime(d.year, d.month, d.day, h, rnd.randint(0, 59))


def genera_richieste(rnd, clienti, fornitori, operatori):
    iscr = {c[0]: date.fromisoformat(c[2]) for c in clienti}
    zona_cli = {c[0]: c[1] for c in clienti}
    # alcuni clienti sono "fedeli": peso piu' alto -> piu' richieste ripetute
    peso_cli = {c[0]: (6 if rnd.random() < 0.12 else 1) for c in clienti}
    forn_per_cat = {}
    for f in fornitori:
        forn_per_cat.setdefault(f[2], []).append(f)
    op_per_zona = {}
    for o in operatori:
        op_per_zona.setdefault(o[1], []).append(o)

    rows = []
    for i in range(1, N_RICHIESTE + 1):
        dt = data_ora_realistica(rnd)
        # solo clienti gia' iscritti alla data della richiesta
        elig = [c for c in iscr if iscr[c] <= dt.date()]
        cid = rnd.choices(elig, [peso_cli[c] for c in elig])[0]
        zona = zona_cli[cid]
        cat = rnd.choices(list(CATEGORIE), PESO_CATEGORIE)[0]
        # fornitore: preferenza per la stessa zona del cliente
        cand = [f for f in forn_per_cat[cat] if f[3] == zona] or forn_per_cat[cat]
        forn = rnd.choice(cand if rnd.random() < 0.8 else forn_per_cat[cat])
        op = rnd.choice(op_per_zona.get(zona) or operatori)
        prezzo, durata, sla = CATEGORIE[cat]
        if rnd.random() < 0.09:                              # annullata
            stato, importo, tempo = STATO_ANN, 0.0, ""
        else:
            tempo = max(10, int(rnd.gauss(durata, durata * 0.22)))
            if rnd.random() < 0.17:                          # ritardo
                tempo = int(sla * rnd.uniform(1.05, 1.5))
            stato = STATO_RITARDO if tempo > sla else STATI_OK
            importo = round(max(15, rnd.gauss(prezzo, prezzo * 0.2)) * (1.15 if dt.hour >= 19 else 1), 2)
        rows.append([f"R{i:05d}", cid, forn[0], op[0], dt.strftime("%Y-%m-%d %H:%M"),
                     f"{importo:.2f}", tempo, stato])
    rows.sort(key=lambda r: r[4])
    for n, r in enumerate(rows, 1):                          # id progressivi in ordine di tempo
        r[0] = f"R{n:05d}"
    return rows


def sporca(rnd, clienti, fornitori, operatori, richieste, p):
    """Inserisce errori tipici di dati reali, da correggere nell'ETL."""
    for r in clienti:
        if rnd.random() < p:
            r[1] = rnd.choice([r[1].upper(), r[1].lower(), f" {r[1]} "])
        if rnd.random() < p / 2:
            d = date.fromisoformat(r[2]); r[2] = d.strftime("%d/%m/%Y")
    for r in fornitori:
        if rnd.random() < p:
            r[2] = r[2].lower()
        if rnd.random() < p:
            r[3] = r[3].upper()
    for r in operatori:
        if rnd.random() < p:
            r[1] = r[1].lower()
    for r in richieste:
        if rnd.random() < p:
            r[5] = r[5].replace(".", ",")                    # virgola decimale
        if rnd.random() < p / 2 and r[7] != STATO_ANN:
            r[6] = ""                                        # tempo mancante
        if rnd.random() < p / 2:
            r[7] = r[7].upper()
    # duplicati esatti
    for _ in range(max(2, int(len(richieste) * p / 2))):
        richieste.append(list(rnd.choice(richieste)))
    for _ in range(max(1, int(len(clienti) * p / 2))):
        clienti.append(list(rnd.choice(clienti)))
    # una richiesta con cliente inesistente (violazione di integrita' da scartare)
    richieste.append(["R99999", "C9999", richieste[0][2], richieste[0][3],
                      "2025-06-15 10:00", "80.00", 60, STATI_OK])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dirty", type=float, default=0.03)
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    DATA.mkdir(exist_ok=True)

    clienti = genera_clienti(rnd)
    fornitori = genera_fornitori(rnd)
    operatori = genera_operatori(rnd)
    richieste = genera_richieste(rnd, clienti, fornitori, operatori)
    if a.dirty > 0:
        sporca(rnd, clienti, fornitori, operatori, richieste, a.dirty)

    scrivi(DATA / "clienti.csv", ["cliente_id", "zona", "data_iscrizione"], clienti)
    scrivi(DATA / "fornitori.csv", ["fornitore_id", "nome", "categoria_servizio", "zona"], fornitori)
    scrivi(DATA / "operatori.csv", ["operatore_id", "zona", "tipo_attivita"], operatori)
    scrivi(DATA / "richieste.csv",
           ["richiesta_id", "cliente_id", "fornitore_id", "operatore_id", "data_ora",
            "importo", "tempo_erogazione_min", "stato"], richieste)
    print(f"clienti={len(clienti)} fornitori={len(fornitori)} operatori={len(operatori)} "
          f"richieste={len(richieste)}  (seed={a.seed}, dirty={a.dirty})")


if __name__ == "__main__":
    main()
