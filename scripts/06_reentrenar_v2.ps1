# Paso 6 (Windows) -- Cierre del ciclo de vida.
#
# El monitor del paso 4 detecto deriva sostenida. La respuesta correcta es
# reentrenar incorporando los datos nuevos y registrar una version nueva.
#
# Se usa --sin-alias a proposito: la version 2 queda registrada pero NO
# desplegada. Promover una version es una decision explicita, no un efecto
# secundario de entrenar. El alias se mueve despues, a mano, en el paso 8 de
# la guia.
#
# Uso:
#   .\scripts\06_reentrenar_v2.ps1

$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

$python = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "No existe .venv\. Corre primero .\scripts\01_preparar_entorno.ps1"
}

$nota = "Reentrenamiento disparado por el monitor de concept drift: la " +
        "exactitud balanceada cayo por debajo del azar dos meses seguidos " +
        "tras la flexibilizacion cambiaria del BCB. Incluye los datos " +
        "posteriores al cambio de regimen."

Set-Location src
& $python train.py --hasta 2026-07-31 --nota $nota --sin-alias
