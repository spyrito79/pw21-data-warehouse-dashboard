#!/usr/bin/env bash
# Esegue l'intera pipeline e avvia la dashboard.
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
python src/generate_data.py
python src/etl.py
streamlit run src/dashboard.py
