#!/usr/bin/env bash
#
# Fase 3 -- Las cuatro demostraciones que exige la consigna (punto 5.2).
#
#   1. Tres o mas replicas en estado Running simultaneamente
#   2. El trafico se reparte entre replicas distintas
#   3. Autorreparacion: se elimina un pod y Kubernetes lo repone
#   4. Escalado: se cambia el numero de replicas y se ve el efecto
#
# Todo queda guardado en evidencia/evidencia_kubernetes.txt para adjuntarlo al
# informe. Igual conviene sacar capturas de pantalla mientras corre.
#
# Uso:  ./scripts/05_pruebas_kubernetes.sh

set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGISTRO="$RAIZ/evidencia/evidencia_kubernetes.txt"
SERVICIO="http://localhost:30080"
ETIQUETA="app=tc-usdt-api"
DESPLIEGUE="tc-usdt-api"

mkdir -p "$RAIZ/evidencia"

# Escribe en pantalla y en el archivo de evidencia al mismo tiempo.
registrar() { echo -e "$@" | tee -a "$REGISTRO"; }
ejecutar()  { registrar "\$ $*"; "$@" 2>&1 | tee -a "$REGISTRO"; }

: > "$REGISTRO"
registrar "==============================================================="
registrar " EVIDENCIA FASE 3 - KUBERNETES"
registrar " Fecha: $(date '+%Y-%m-%d %H:%M:%S')"
registrar " Cluster: $(kubectl config current-context)"
registrar "==============================================================="

# --- Comprobacion previa -------------------------------------------------
if ! kubectl get deployment "$DESPLIEGUE" >/dev/null 2>&1; then
  registrar "\nERROR: no existe el deployment '$DESPLIEGUE'."
  registrar "Aplica primero los manifiestos:"
  registrar "    kubectl apply -f k8s/deployment.yaml"
  registrar "    kubectl apply -f k8s/service.yaml"
  exit 1
fi

registrar "\nEsperando a que las replicas esten listas..."
kubectl wait --for=condition=available --timeout=180s "deployment/$DESPLIEGUE" 2>&1 | tee -a "$REGISTRO"

# --- 1) Replicas en Running ----------------------------------------------
registrar "\n\n---------------------------------------------------------------"
registrar " DEMOSTRACION 1 - Tres o mas replicas en Running simultaneamente"
registrar "---------------------------------------------------------------"
ejecutar kubectl get pods -l "$ETIQUETA" -o wide

EN_EJECUCION=$(kubectl get pods -l "$ETIQUETA" \
  --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
registrar "\nPods en Running: $EN_EJECUCION"
if [ "$EN_EJECUCION" -ge 3 ]; then
  registrar "RESULTADO: OK - hay $EN_EJECUCION replicas corriendo a la vez."
else
  registrar "RESULTADO: FALLO - se esperaban al menos 3, hay $EN_EJECUCION."
fi

# --- 2) Balanceo de carga ------------------------------------------------
registrar "\n\n---------------------------------------------------------------"
registrar " DEMOSTRACION 2 - El Service reparte el trafico entre replicas"
registrar "---------------------------------------------------------------"
registrar "Cada respuesta trae el campo served_by_pod, que es el hostname del"
registrar "contenedor. En Kubernetes ese hostname es el nombre del pod.\n"

TEMPORAL=$(mktemp)
for i in $(seq 1 20); do
  POD=$(curl -s --max-time 5 "$SERVICIO/health" \
        | grep -o '"served_by_pod":"[^"]*"' | cut -d'"' -f4)
  POD=${POD:-SIN_RESPUESTA}
  echo "$POD" >> "$TEMPORAL"
  registrar "  peticion $(printf '%2d' "$i") -> $POD"
done

registrar "\nReparto de las 20 peticiones:"
sort "$TEMPORAL" | uniq -c | sort -rn | while read -r n pod; do
  registrar "  $pod : $n peticiones"
done
DISTINTOS=$(sort -u "$TEMPORAL" | grep -vc SIN_RESPUESTA)
rm -f "$TEMPORAL"

registrar "\nPods distintos que respondieron: $DISTINTOS"
if [ "$DISTINTOS" -ge 2 ]; then
  registrar "RESULTADO: OK - el trafico se reparte entre $DISTINTOS pods."
else
  registrar "RESULTADO: revisar - respondio un solo pod."
  registrar "Causa habitual: se esta usando 'kubectl port-forward', que abre"
  registrar "un tunel a un unico pod. Hay que consultar el NodePort ($SERVICIO)."
fi

# --- 3) Autorreparacion --------------------------------------------------
registrar "\n\n---------------------------------------------------------------"
registrar " DEMOSTRACION 3 - Autorreparacion al eliminar un pod"
registrar "---------------------------------------------------------------"
registrar "Estado antes de eliminar:"
ejecutar kubectl get pods -l "$ETIQUETA"

VICTIMA=$(kubectl get pods -l "$ETIQUETA" -o jsonpath='{.items[0].metadata.name}')
registrar "\nEliminando el pod: $VICTIMA"
kubectl delete pod "$VICTIMA" --wait=false 2>&1 | tee -a "$REGISTRO"

registrar "\nInmediatamente despues (el viejo en Terminating, el nuevo creandose):"
sleep 3
ejecutar kubectl get pods -l "$ETIQUETA"

registrar "\nEl servicio sigue respondiendo durante el reemplazo:"
for i in $(seq 1 5); do
  RESPUESTA=$(curl -s --max-time 5 "$SERVICIO/health" || echo "sin respuesta")
  registrar "  intento $i -> $RESPUESTA"
  sleep 2
done

registrar "\nEsperando a que el reemplazo este listo..."
kubectl wait --for=condition=available --timeout=180s "deployment/$DESPLIEGUE" 2>&1 | tee -a "$REGISTRO"
registrar "\nEstado final (el pod eliminado ya no esta; hay uno nuevo con otro nombre):"
ejecutar kubectl get pods -l "$ETIQUETA" -o wide

FINAL=$(kubectl get pods -l "$ETIQUETA" --field-selector=status.phase=Running --no-headers | wc -l)
if [ "$FINAL" -ge 3 ]; then
  registrar "\nRESULTADO: OK - Kubernetes repuso el pod y volvio a $FINAL replicas."
else
  registrar "\nRESULTADO: revisar - quedaron $FINAL replicas."
fi

# --- 4) Escalado ---------------------------------------------------------
registrar "\n\n---------------------------------------------------------------"
registrar " DEMOSTRACION 4 - Escalado del numero de replicas"
registrar "---------------------------------------------------------------"
registrar "Escalando de 3 a 5 replicas:"
ejecutar kubectl scale deployment "$DESPLIEGUE" --replicas=5
kubectl wait --for=condition=available --timeout=180s "deployment/$DESPLIEGUE" >/dev/null 2>&1
sleep 5
ejecutar kubectl get pods -l "$ETIQUETA" -o wide
registrar "Replicas ahora: $(kubectl get pods -l "$ETIQUETA" --field-selector=status.phase=Running --no-headers | wc -l)"

registrar "\nVolviendo a 3 replicas:"
ejecutar kubectl scale deployment "$DESPLIEGUE" --replicas=3
sleep 8
ejecutar kubectl get pods -l "$ETIQUETA" -o wide
registrar "Replicas ahora: $(kubectl get pods -l "$ETIQUETA" --field-selector=status.phase=Running --no-headers | wc -l)"

# --- Trazabilidad del modelo servido -------------------------------------
registrar "\n\n---------------------------------------------------------------"
registrar " EXTRA - Que modelo esta sirviendo el cluster"
registrar "---------------------------------------------------------------"
registrar "\$ curl $SERVICIO/model-info"
curl -s "$SERVICIO/model-info" | tee -a "$REGISTRO"
registrar "\n\nEsta version y este run_id tienen que coincidir con los de"
registrar "MODELO_DESPLEGADO.md y con lo que se ve en la interfaz de MLflow."

registrar "\n\n==============================================================="
registrar " Evidencia guardada en: evidencia/evidencia_kubernetes.txt"
registrar "==============================================================="
