# Paso 4 (Windows) -- Fase 6: corre los monitores de deriva y guarda la
# evidencia en evidencia\evidencia_deriva.txt.
#
# Estos monitores son PUERTAS: terminan con codigo de salida 0 (verde) o 1
# (rojo). Por eso $ErrorActionPreference NO se pone en "Stop": un codigo 1
# aqui no es un error del script, es el resultado que se quiere demostrar.
#
# Uso:
#   .\scripts\04_monitores_deriva.ps1

Set-Location (Join-Path $PSScriptRoot "..")

$raiz = Get-Location
$python = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "No existe .venv\. Corre primero .\scripts\01_preparar_entorno.ps1"
    exit 1
}

$registro = Join-Path $raiz "evidencia\evidencia_deriva.txt"
New-Item -ItemType Directory -Force -Path (Join-Path $raiz "evidencia") | Out-Null
"" | Set-Content -Path $registro -Encoding utf8

Set-Location (Join-Path $raiz "src")

function Correr($titulo, $argumentos) {
    $encabezado = @(
        ""
        "###############################################################"
        "# $titulo"
        "# > python $($argumentos -join ' ')"
        "###############################################################"
    )
    $encabezado | Tee-Object -FilePath $registro -Append | Write-Host

    & $python -W ignore @argumentos 2>&1 | Tee-Object -FilePath $registro -Append | Write-Host
    $codigo = $LASTEXITCODE

    $estado = if ($codigo -eq 0) { "VERDE" } else { "ROJO" }
    ">>> codigo de salida: $codigo  ($estado)" |
        Tee-Object -FilePath $registro -Append | Write-Host
}

Correr "6.1 DATA DRIFT - control (debe dar VERDE, salida 0)" `
       @("monitor_data_drift.py", "--escenario", "control")

Correr "6.1 DATA DRIFT - post flexibilizacion (debe dar ROJO, salida 1)" `
       @("monitor_data_drift.py", "--escenario", "post_flex")

Correr "6.1 DATA DRIFT - deriva inyectada (debe dar ROJO, salida 1)" `
       @("monitor_data_drift.py", "--escenario", "sintetico")

Correr "6.1 DATA DRIFT - reporte completo" `
       @("monitor_data_drift.py", "--escenario", "todos")

Correr "6.2 CONCEPT DRIFT - holdout real" `
       @("monitor_concept_drift.py")

Correr "6.2 CONCEPT DRIFT - control sintetico" `
       @("monitor_concept_drift.py", "--escenario", "sintetico")

Set-Location $raiz
Write-Host ""
Write-Host "Evidencia guardada en evidencia\evidencia_deriva.txt"
Write-Host "Graficos en resultados\data_drift.png y resultados\concept_drift.png"
