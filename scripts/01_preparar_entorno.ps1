
# Paso 1.1 (Windows) — Crear el entorno e instalar dependencias.
#
# Uso:
#   .\scripts\01_preparar_entorno.ps1
#
# Crea un entorno virtual en .venv\ e instala las 12 dependencias fijadas
# por version exacta en requirements.txt. Fijar las versiones (y no usar
# rangos) es lo que garantiza que tu entorno y el de la imagen de Docker
# sean identicos.
#
# streamlit NO esta aca: vive aparte en ui\requirements.txt. Es a proposito.
# La consigna pide que la interfaz consuma la API real desplegada en
# Kubernetes y no un proceso local, y mantener sus dependencias separadas es
# lo que garantiza que la interfaz no pueda importar el modelo ni las
# librerias de modelado aunque quisiera. Para la interfaz:
#   python -m pip install -r ui\requirements.txt
 
$ErrorActionPreference = "Stop"
 
# Ubicarse en la raiz del repo sin importar desde donde se llame el script
Set-Location (Join-Path $PSScriptRoot "..")
 
if (-not (Test-Path ".venv")) {
    Write-Host ">> Creando entorno virtual en .venv\"
    py -3.12 -m venv .venv
} else {
    Write-Host ">> .venv\ ya existe, reutilizando"
}
 
Write-Host ">> Activando entorno"
& .\.venv\Scripts\Activate.ps1
 
Write-Host ">> Instalando dependencias (requirements.txt)"
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q
 
Write-Host ">> Verificando la instalacion"
python -c "import mlflow, sklearn, xgboost, pandas as pd; print(f'   mlflow {mlflow.__version__} | scikit-learn {sklearn.__version__} | xgboost {xgboost.__version__} | pandas {pd.__version__}')"
 
Write-Host ">> Entorno listo. Activalo en cada terminal nueva con:  .\.venv\Scripts\Activate.ps1"