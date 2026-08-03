# Paso 5 (Windows) -- Fase 3: las cuatro demostraciones que exige la consigna
# (punto 5.2).
#
#   1. Tres o mas replicas en estado Running simultaneamente
#   2. El trafico se reparte entre replicas distintas
#   3. Autorreparacion: se elimina un pod y Kubernetes lo repone
#   4. Escalado: se cambia el numero de replicas y se ve el efecto
#
# Todo queda en evidencia\evidencia_kubernetes.txt. Igual conviene sacar
# capturas de pantalla mientras corre.
#
# Uso:
#   .\scripts\05_pruebas_kubernetes.ps1
#
# Si PowerShell bloquea la ejecucion, corre una vez en esa terminal:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

Set-Location (Join-Path $PSScriptRoot "..")

$raiz      = Get-Location
$registro  = Join-Path $raiz "evidencia\evidencia_kubernetes.txt"
$servicio  = "http://localhost:30080"
$etiqueta  = "app=tc-usdt-api"
$despliegue = "tc-usdt-api"

New-Item -ItemType Directory -Force -Path (Join-Path $raiz "evidencia") | Out-Null
"" | Set-Content -Path $registro -Encoding utf8

function Registrar($texto) {
    $texto | Tee-Object -FilePath $registro -Append | Write-Host
}

function Ejecutar($comando) {
    Registrar "> $comando"
    Invoke-Expression $comando 2>&1 | Tee-Object -FilePath $registro -Append | Write-Host
}

Registrar "==============================================================="
Registrar " EVIDENCIA FASE 3 - KUBERNETES"
Registrar " Fecha: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Registrar " Cluster: $(kubectl config current-context)"
Registrar "==============================================================="

# --- Comprobacion previa -------------------------------------------------
kubectl get deployment $despliegue *> $null
if ($LASTEXITCODE -ne 0) {
    Registrar ""
    Registrar "ERROR: no existe el deployment '$despliegue'."
    Registrar "Aplica primero los manifiestos:"
    Registrar "    kubectl apply -f k8s\deployment.yaml"
    Registrar "    kubectl apply -f k8s\service.yaml"
    exit 1
}

Registrar ""
Registrar "Esperando a que las replicas esten listas..."
Ejecutar "kubectl wait --for=condition=available --timeout=180s deployment/$despliegue"

# --- 1) Replicas en Running ----------------------------------------------
Registrar ""
Registrar "---------------------------------------------------------------"
Registrar " DEMOSTRACION 1 - Tres o mas replicas en Running simultaneamente"
Registrar "---------------------------------------------------------------"
Ejecutar "kubectl get pods -l $etiqueta -o wide"

$enEjecucion = @(kubectl get pods -l $etiqueta --field-selector=status.phase=Running --no-headers).Count
Registrar ""
Registrar "Pods en Running: $enEjecucion"
if ($enEjecucion -ge 3) {
    Registrar "RESULTADO: OK - hay $enEjecucion replicas corriendo a la vez."
} else {
    Registrar "RESULTADO: FALLO - se esperaban al menos 3, hay $enEjecucion."
}

# --- 2) Balanceo de carga ------------------------------------------------
Registrar ""
Registrar "---------------------------------------------------------------"
Registrar " DEMOSTRACION 2 - El Service reparte el trafico entre replicas"
Registrar "---------------------------------------------------------------"
Registrar "Cada respuesta trae el campo served_by_pod, que es el hostname del"
Registrar "contenedor. En Kubernetes ese hostname es el nombre del pod."
Registrar ""

$respuestas = @()
foreach ($i in 1..20) {
    try {
        $r = Invoke-RestMethod -Uri "$servicio/health" -TimeoutSec 5
        $pod = $r.served_by_pod
    } catch {
        $pod = "SIN_RESPUESTA"
    }
    $respuestas += $pod
    Registrar ("  peticion {0,2} -> {1}" -f $i, $pod)
}

Registrar ""
Registrar "Reparto de las 20 peticiones:"
$respuestas | Group-Object | Sort-Object Count -Descending | ForEach-Object {
    Registrar "  $($_.Name) : $($_.Count) peticiones"
}
$distintos = ($respuestas | Where-Object { $_ -ne "SIN_RESPUESTA" } | Sort-Object -Unique).Count

Registrar ""
Registrar "Pods distintos que respondieron: $distintos"
if ($distintos -ge 2) {
    Registrar "RESULTADO: OK - el trafico se reparte entre $distintos pods."
} else {
    Registrar "RESULTADO: revisar - respondio un solo pod."
    Registrar "Causa habitual: se esta usando 'kubectl port-forward', que abre"
    Registrar "un tunel a un unico pod. Hay que consultar el NodePort ($servicio)."
}

# --- 3) Autorreparacion --------------------------------------------------
Registrar ""
Registrar "---------------------------------------------------------------"
Registrar " DEMOSTRACION 3 - Autorreparacion al eliminar un pod"
Registrar "---------------------------------------------------------------"
Registrar "Estado antes de eliminar:"
Ejecutar "kubectl get pods -l $etiqueta"

$victima = kubectl get pods -l $etiqueta -o jsonpath="{.items[0].metadata.name}"
Registrar ""
Registrar "Eliminando el pod: $victima"
Ejecutar "kubectl delete pod $victima --wait=false"

Registrar ""
Registrar "Inmediatamente despues (el viejo en Terminating, el nuevo creandose):"
Start-Sleep -Seconds 3
Ejecutar "kubectl get pods -l $etiqueta"

Registrar ""
Registrar "El servicio sigue respondiendo durante el reemplazo:"
foreach ($i in 1..5) {
    try {
        $r = Invoke-RestMethod -Uri "$servicio/health" -TimeoutSec 5
        Registrar "  intento $i -> $($r | ConvertTo-Json -Compress)"
    } catch {
        Registrar "  intento $i -> sin respuesta"
    }
    Start-Sleep -Seconds 2
}

Registrar ""
Registrar "Esperando a que el reemplazo este listo..."
Ejecutar "kubectl wait --for=condition=available --timeout=180s deployment/$despliegue"
Registrar ""
Registrar "Estado final (el pod eliminado ya no esta; hay uno nuevo con otro nombre):"
Ejecutar "kubectl get pods -l $etiqueta -o wide"

$final = @(kubectl get pods -l $etiqueta --field-selector=status.phase=Running --no-headers).Count
Registrar ""
if ($final -ge 3) {
    Registrar "RESULTADO: OK - Kubernetes repuso el pod y volvio a $final replicas."
} else {
    Registrar "RESULTADO: revisar - quedaron $final replicas."
}

# --- 4) Escalado ---------------------------------------------------------
Registrar ""
Registrar "---------------------------------------------------------------"
Registrar " DEMOSTRACION 4 - Escalado del numero de replicas"
Registrar "---------------------------------------------------------------"
Registrar "Escalando de 3 a 5 replicas:"
Ejecutar "kubectl scale deployment $despliegue --replicas=5"
kubectl wait --for=condition=available --timeout=180s deployment/$despliegue *> $null
Start-Sleep -Seconds 5
Ejecutar "kubectl get pods -l $etiqueta -o wide"
Registrar "Replicas ahora: $(@(kubectl get pods -l $etiqueta --field-selector=status.phase=Running --no-headers).Count)"

Registrar ""
Registrar "Volviendo a 3 replicas:"
Ejecutar "kubectl scale deployment $despliegue --replicas=3"
Start-Sleep -Seconds 8
Ejecutar "kubectl get pods -l $etiqueta -o wide"
Registrar "Replicas ahora: $(@(kubectl get pods -l $etiqueta --field-selector=status.phase=Running --no-headers).Count)"

# --- Trazabilidad del modelo servido -------------------------------------
Registrar ""
Registrar "---------------------------------------------------------------"
Registrar " EXTRA - Que modelo esta sirviendo el cluster"
Registrar "---------------------------------------------------------------"
Registrar "> curl $servicio/model-info"
try {
    $info = Invoke-RestMethod -Uri "$servicio/model-info" -TimeoutSec 5
    Registrar ($info | ConvertTo-Json)
} catch {
    Registrar "sin respuesta"
}
Registrar ""
Registrar "Esta version y este run_id tienen que coincidir con los de"
Registrar "MODELO_DESPLEGADO.md y con lo que se ve en la interfaz de MLflow."

Registrar ""
Registrar "==============================================================="
Registrar " Evidencia guardada en: evidencia\evidencia_kubernetes.txt"
Registrar "==============================================================="
