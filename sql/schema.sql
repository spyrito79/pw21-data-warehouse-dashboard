-- Data warehouse "a stella" per il PW 21.
-- Una tabella dei fatti (fact_richieste) collegata a 4 dimensioni.

DROP TABLE IF EXISTS fact_richieste;
DROP TABLE IF EXISTS dim_cliente;
DROP TABLE IF EXISTS dim_fornitore;
DROP TABLE IF EXISTS dim_operatore;
DROP TABLE IF EXISTS dim_tempo;

CREATE TABLE dim_cliente (
    cliente_key      INTEGER PRIMARY KEY AUTOINCREMENT,   -- chiave surrogata
    cliente_id       TEXT NOT NULL UNIQUE,                -- chiave di business
    zona             TEXT NOT NULL,
    data_iscrizione  TEXT NOT NULL
);

CREATE TABLE dim_fornitore (
    fornitore_key        INTEGER PRIMARY KEY AUTOINCREMENT,
    fornitore_id         TEXT NOT NULL UNIQUE,
    nome                 TEXT NOT NULL,
    categoria_servizio   TEXT NOT NULL,
    zona                 TEXT NOT NULL
);

CREATE TABLE dim_operatore (
    operatore_key  INTEGER PRIMARY KEY AUTOINCREMENT,
    operatore_id   TEXT NOT NULL UNIQUE,
    zona           TEXT NOT NULL,
    tipo_attivita  TEXT NOT NULL
);

CREATE TABLE dim_tempo (
    tempo_key        INTEGER PRIMARY KEY,                 -- formato AAAAMMGG
    data             TEXT NOT NULL,
    anno             INTEGER NOT NULL,
    trimestre        INTEGER NOT NULL,
    mese             INTEGER NOT NULL,
    nome_mese        TEXT NOT NULL,
    settimana        INTEGER NOT NULL,
    giorno_settimana INTEGER NOT NULL,                    -- 1 = lunedi
    nome_giorno      TEXT NOT NULL,
    is_weekend       INTEGER NOT NULL
);

CREATE TABLE fact_richieste (
    richiesta_id          TEXT PRIMARY KEY,
    cliente_key           INTEGER NOT NULL REFERENCES dim_cliente(cliente_key),
    fornitore_key         INTEGER NOT NULL REFERENCES dim_fornitore(fornitore_key),
    operatore_key         INTEGER NOT NULL REFERENCES dim_operatore(operatore_key),
    tempo_key             INTEGER NOT NULL REFERENCES dim_tempo(tempo_key),
    ora                   INTEGER NOT NULL,               -- ora del giorno 0-23
    importo               REAL    NOT NULL,               -- EUR, 0 se annullata
    tempo_erogazione_min  INTEGER,                        -- NULL se annullata o mancante
    stato                 TEXT NOT NULL,                  -- completata | completata in ritardo | annullata
    is_annullata          INTEGER NOT NULL,
    is_ritardo            INTEGER NOT NULL
);

CREATE INDEX ix_fact_cliente   ON fact_richieste(cliente_key);
CREATE INDEX ix_fact_fornitore ON fact_richieste(fornitore_key);
CREATE INDEX ix_fact_tempo     ON fact_richieste(tempo_key);
