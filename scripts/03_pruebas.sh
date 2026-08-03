#!/usr/bin/env bash
# Paso 3 -- Ejecuta la bateria de pruebas automatizadas del detector de deriva.
# Todas deben pasar: comprueban que el detector es confiable antes de usarlo
# como puerta en el paso 4.
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"
exec .venv/bin/python -W ignore -m pytest tests/ -v
