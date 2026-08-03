#!/usr/bin/env bash
# Paso 4 -- Fase 6: corre los monitores de deriva y guarda la evidencia.
#
# Estos monitores son PUERTAS: terminan en 0 (verde) o 1 (rojo). Por eso el
# script NO usa `set -e`: un codigo 1 aqui no es un error del script, es el
# resultado que se quiere demostrar.
set -uo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$RAIZ/evidencia"
REGISTRO="$RAIZ/evidencia/evidencia_deriva.txt"
cd "$RAIZ/src"
PY="../.venv/bin/python -W ignore"

: > "$REGISTRO"
correr() {
  local titulo="$1"; shift
  {
    echo ""
    echo "###############################################################"
    echo "# $titulo"
    echo "# \$ $*"
    echo "###############################################################"
  } | tee -a "$REGISTRO"
  $PY "$@" 2>&1 | tee -a "$REGISTRO"
  local codigo=${PIPESTATUS[0]}
  echo "" | tee -a "$REGISTRO"
  echo ">>> codigo de salida: $codigo  ($([ "$codigo" -eq 0 ] && echo VERDE || echo ROJO))" | tee -a "$REGISTRO"
  return 0
}

correr "6.1 DATA DRIFT - control (debe dar VERDE, salida 0)"  monitor_data_drift.py --escenario control
correr "6.1 DATA DRIFT - post flexibilizacion (debe dar ROJO, salida 1)" monitor_data_drift.py --escenario post_flex
correr "6.1 DATA DRIFT - deriva inyectada (debe dar ROJO, salida 1)" monitor_data_drift.py --escenario sintetico
correr "6.1 DATA DRIFT - reporte completo" monitor_data_drift.py --escenario todos
correr "6.2 CONCEPT DRIFT - holdout real" monitor_concept_drift.py
correr "6.2 CONCEPT DRIFT - control sintetico" monitor_concept_drift.py --escenario sintetico

echo ""
echo "Evidencia guardada en evidencia/evidencia_deriva.txt"
echo "Graficos en resultados/data_drift.png y resultados/concept_drift.png"
