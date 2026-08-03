#!/usr/bin/env bash
# Paso 6 -- Cierre del ciclo de vida.
#
# El monitor del paso 4 detecto deriva sostenida. La respuesta correcta es
# reentrenar incorporando los datos nuevos y registrar una version nueva.
#
# Se usa --sin-alias a proposito: la version 2 queda registrada pero NO
# desplegada. Promover una version es una decision explicita, no un efecto
# secundario de entrenar. El alias se mueve despues, a mano, en el paso 7 de
# la guia.
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ/src"
exec ../.venv/bin/python train.py \
  --hasta 2026-07-31 \
  --nota "Reentrenamiento disparado por el monitor de concept drift: la exactitud balanceada cayo por debajo del azar dos meses seguidos tras la flexibilizacion cambiaria del BCB. Incluye los datos posteriores al cambio de regimen." \
  --sin-alias
