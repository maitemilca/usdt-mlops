#!/usr/bin/env bash
# Paso 1.1 — Crear el entorno e instalar dependencias.
#
# Uso:
#   ./scripts/01_preparar_entorno.sh
#
# Crea un entorno virtual en .venv/ e instala las 13 dependencias fijadas
# por versión exacta en requirements.txt. Fijar las versiones (y no usar
# rangos) es lo que garantiza que el entorno de desarrollo y el de la
# imagen de Docker sean idénticos.
set -euo pipefail

cd "$(dirname "$0")/.."   # ubicarse en la raíz del repo, sin importar desde dónde se llame

PYTHON_BIN="python3"
if command -v py >/dev/null 2>&1; then
  # Windows con el launcher py: evita el Python 3.14 por defecto, que da
  # problemas de compatibilidad con estas librerías.
  PYTHON_BIN="py -3.12"
fi

if [ ! -d ".venv" ]; then
  echo ">> Creando entorno virtual en .venv/"
  $PYTHON_BIN -m venv .venv
else
  echo ">> .venv/ ya existe, reutilizando"
fi

if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
else
  # shellcheck disable=SC1091
  source .venv/Scripts/activate   # Windows (Git Bash)
fi

echo ">> Instalando dependencias (requirements.txt)"
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo ">> Verificando la instalacion"
python - <<'PYEOF'
import importlib
paquetes = ["mlflow", "sklearn", "xgboost", "pandas"]
nombres_pip = {"sklearn": "scikit-learn"}
versiones = []
for p in paquetes:
    mod = importlib.import_module(p)
    nombre = nombres_pip.get(p, p)
    versiones.append(f"{nombre} {mod.__version__}")
print("   " + " | ".join(versiones))
PYEOF

echo ">> Entorno listo. Activalo con:  source .venv/bin/activate"
