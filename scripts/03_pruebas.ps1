# Paso 3 (Windows) -- Bateria de pruebas automatizadas del detector de deriva.
#
# Todas deben pasar: comprueban que el detector es confiable antes de usarlo
# como puerta en el paso 4.
#
# Uso:
#   .\scripts\03_pruebas.ps1

$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

$python = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "No existe .venv\. Corre primero .\scripts\01_preparar_entorno.ps1"
}

& $python -W ignore -m pytest tests\ -v
