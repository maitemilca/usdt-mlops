#!/usr/bin/env bash
# Paso 1 -- Crea el entorno virtual e instala las dependencias fijadas.
# Se ejecuta una sola vez, salvo que cambie requirements.txt.
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

echo ">> Python del sistema: $(python3 --version)"
if [ ! -d .venv ]; then
  echo ">> Creando entorno virtual en .venv/"
  python3 -m venv .venv
fi

echo ">> Instalando dependencias (puede tardar unos minutos la primera vez)"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

echo ">> Verificando la instalacion"
.venv/bin/python - <<'PY'
import mlflow, sklearn, xgboost, fastapi, scipy, matplotlib, pandas, numpy
print(f"   mlflow {mlflow.__version__} | scikit-learn {sklearn.__version__} | "
      f"xgboost {xgboost.__version__} | pandas {pandas.__version__}")
PY
echo ">> Entorno listo. Activalo con:  source .venv/bin/activate"
