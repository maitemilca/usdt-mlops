# Paso 2 (Windows) -- Fase 1: entrena, registra los experimentos en MLflow y
# publica la version 1 del modelo con el alias 'champion'.
#
# Uso:
#   .\scripts\02_entrenar.ps1
#   .\scripts\02_entrenar.ps1 --hasta 2026-07-31 --sin-alias

$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

# Se invoca el python del entorno virtual directamente, sin activarlo: asi el
# script funciona igual desde una terminal donde el entorno no este activo.
$python = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "No existe .venv\. Corre primero .\scripts\01_preparar_entorno.ps1"
}

Set-Location src
& $python train.py @args
