-- Interrogazioni SQL sugli indicatori principali (nessun filtro: tutto il periodo).
-- Esecuzione:  sqlite3 warehouse.db < sql/queries.sql
-- Le stesse query, con i filtri aggiunti nella clausola WHERE, sono usate dalla dashboard.

.headers on
.mode column

-- 1. Numero di richieste gestite (annullate escluse) e annullate
SELECT SUM(is_annullata = 0) AS richieste_gestite,
       SUM(is_annullata = 1) AS richieste_annullate,
       ROUND(100.0 * SUM(is_annullata) / COUNT(*), 1) AS pct_annullate
FROM fact_richieste;

-- 2. Incassi totali (EUR)
SELECT ROUND(SUM(importo), 2) AS incassi_totali
FROM fact_richieste WHERE is_annullata = 0;

-- 3. Tempo medio di erogazione (minuti), sulle richieste con tempo noto
SELECT ROUND(AVG(tempo_erogazione_min), 1) AS tempo_medio_min
FROM fact_richieste WHERE is_annullata = 0 AND tempo_erogazione_min IS NOT NULL;

-- 4. Clienti attivi e % di clienti che tornano a richiedere il servizio
--    (tornano = almeno 2 richieste gestite nel periodo)
WITH per_cliente AS (
    SELECT cliente_key, COUNT(*) AS n
    FROM fact_richieste WHERE is_annullata = 0
    GROUP BY cliente_key
)
SELECT COUNT(*) AS clienti_attivi,
       SUM(n >= 2) AS clienti_ricorrenti,
       ROUND(100.0 * SUM(n >= 2) / COUNT(*), 1) AS pct_clienti_che_tornano
FROM per_cliente;

-- 5. Incassi per zona (zona del cliente)
SELECT c.zona, COUNT(*) AS richieste, ROUND(SUM(f.importo), 2) AS incassi
FROM fact_richieste f JOIN dim_cliente c USING (cliente_key)
WHERE f.is_annullata = 0
GROUP BY c.zona ORDER BY incassi DESC;

-- 6. Richieste e incassi per categoria di servizio
SELECT fo.categoria_servizio, COUNT(*) AS richieste, ROUND(SUM(f.importo), 2) AS incassi,
       ROUND(AVG(f.tempo_erogazione_min), 1) AS tempo_medio_min
FROM fact_richieste f JOIN dim_fornitore fo USING (fornitore_key)
WHERE f.is_annullata = 0
GROUP BY fo.categoria_servizio ORDER BY incassi DESC;

-- 7. Top 5 fornitori per incassi
SELECT fo.fornitore_id, fo.nome, fo.categoria_servizio, ROUND(SUM(f.importo), 2) AS incassi
FROM fact_richieste f JOIN dim_fornitore fo USING (fornitore_key)
WHERE f.is_annullata = 0
GROUP BY fo.fornitore_key ORDER BY incassi DESC LIMIT 5;

-- 8. Andamento mensile delle richieste
SELECT t.anno, t.mese, t.nome_mese, COUNT(*) AS richieste, ROUND(SUM(f.importo), 2) AS incassi
FROM fact_richieste f JOIN dim_tempo t USING (tempo_key)
WHERE f.is_annullata = 0
GROUP BY t.anno, t.mese ORDER BY t.anno, t.mese;

-- 9. Percentuale di richieste in ritardo per categoria
SELECT fo.categoria_servizio,
       ROUND(100.0 * SUM(f.is_ritardo) / COUNT(*), 1) AS pct_ritardo
FROM fact_richieste f JOIN dim_fornitore fo USING (fornitore_key)
WHERE f.is_annullata = 0
GROUP BY fo.categoria_servizio ORDER BY pct_ritardo DESC;

-- 10. Richieste per giorno della settimana e fascia oraria
SELECT t.nome_giorno, f.ora, COUNT(*) AS richieste
FROM fact_richieste f JOIN dim_tempo t USING (tempo_key)
WHERE f.is_annullata = 0
GROUP BY t.giorno_settimana, f.ora ORDER BY t.giorno_settimana, f.ora;
