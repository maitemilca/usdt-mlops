# Guía paso a paso — Proyecto final MLOps

Esta guía te lleva desde una terminal vacía hasta el proyecto completo
funcionando, en orden, sin saltarse nada.

**Cómo usarla:**

- Ejecutá los pasos **en orden**. Cada uno depende del anterior.
- Cada bloque `$` es un comando para copiar y pegar.
- Después de cada comando está **lo que deberías ver**. Si ves otra cosa,
  mirá la sección [Problemas frecuentes](#problemas-frecuentes) al final.
- Los avisos **CAPTURA N** marcan dónde sacar pantalla para el informe. Debajo
  de cada uno hay un texto listo para pegar en el Word, con el mismo formato
  de tus actividades anteriores.
- Al cierre de cada fase hay **preguntas probables de defensa** con su
  respuesta.

**Tiempo estimado:** unas 2 horas la primera vez, incluyendo capturas.

> **Todo lo de esta guía está verificado.** Cada paso se ejecutó de punta a
> punta antes de escribirla —el entrenamiento, los monitores, el
> `docker build`, el despliegue en Kubernetes y las cuatro demostraciones— y
> después se dejó el proyecto en estado limpio. Las salidas que aparecen abajo
> son las reales, no ejemplos inventados: si ves algo distinto, revisá
> [Problemas frecuentes](#problemas-frecuentes).

---

## Si estás en Windows

El proyecto funciona igual en Linux y en Windows. Los comandos de la guía
están en bash; para PowerShell hay un equivalente de cada uno.

**Los seis scripts tienen versión `.ps1`.** Donde la guía diga
`./scripts/02_entrenar.sh`, usá `.\scripts\02_entrenar.ps1`. Hacen exactamente
lo mismo.

Si PowerShell bloquea la ejecución, corré una vez en esa terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

**Tabla de equivalencias** para los comandos sueltos:

| La guía dice (bash) | En PowerShell |
|---|---|
| `./scripts/NN_algo.sh` | `.\scripts\NN_algo.ps1` |
| `source .venv/bin/activate` | `.\.venv\Scripts\Activate.ps1` |
| `free -h` | Administrador de tareas, pestaña Rendimiento |
| `grep -E "patrón" archivo` | `Select-String "patrón" archivo` |
| `cat archivo` | `Get-Content archivo` |
| `xdg-open imagen.png` | `Invoke-Item imagen.png` |
| `curl -s URL` | `Invoke-RestMethod URL` |
| `curl -X POST ... -d @archivo.json` | `Invoke-RestMethod URL -Method Post -ContentType 'application/json' -InFile archivo.json` |
| `python3` | `python` (o `py -3.12`) |

**Lo que NO cambia:** `docker`, `kubectl`, `git`, `mlflow ui` y `streamlit` se
escriben igual en los dos sistemas.

**El bloque de Python del Paso 5.3** usa sintaxis de bash (`<<'PY'`). En
PowerShell, guardá ese código en un archivo `generar_peticion.py` y corrélo
con `python generar_peticion.py > peticion.json`.

---

## Índice

- [Paso 0 — Preparar la máquina](#paso-0--preparar-la-máquina)
- [Paso 1 — Entorno de Python](#paso-1--entorno-de-python)
- [Paso 2 — Fase 1: entrenamiento y MLflow](#paso-2--fase-1-entrenamiento-y-mlflow)
- [Paso 3 — Fase 1: la interfaz de MLflow](#paso-3--fase-1-la-interfaz-de-mlflow)
- [Paso 4 — Fase 6: pruebas y monitores de deriva](#paso-4--fase-6-pruebas-y-monitores-de-deriva)
- [Paso 5 — Fase 2: contenerización](#paso-5--fase-2-contenerización)
- [Paso 6 — Fase 3: Kubernetes](#paso-6--fase-3-kubernetes)
- [Paso 7 — Extra: interfaz web](#paso-7--extra-interfaz-web)
- [Paso 8 — Cerrar el ciclo: versión 2](#paso-8--cerrar-el-ciclo-versión-2)
- [Paso 9 — Repositorio Git](#paso-9--repositorio-git)
- [Paso 10 — Armar la entrega](#paso-10--armar-la-entrega)
- [Problemas frecuentes](#problemas-frecuentes)
- [Preguntas de defensa](#preguntas-de-defensa)

---

## Paso 0 — Preparar la máquina

### 0.1 Liberar memoria

Docker Desktop se lleva unos 2,5 GB por sí solo, y en la Fase 3 vas a levantar
hasta 5 réplicas. Conviene tener espacio antes de empezar.

```bash
free -h          # en Windows: mirá el Administrador de tareas
```

Si en **disponible** ves menos de 4 GB, cerrá pestañas del navegador. Suele ser
la ganancia más grande y más rápida.

Los contenedores de otras materias que estén en `Exited` **no consumen
memoria**, solo disco. Si tenés disco de sobra, no hace falta borrarlos.

Si además Docker Desktop tiene asignada mucha RAM, bajala en
**Settings → Resources** a unos 5 GB: el clúster respira igual y el escritorio
también.

> **Opcional, solo si necesitás recuperar disco.** Ojo: esto borra
> contenedores e imágenes de otras materias que quizá quieras conservar.
> ```bash
> docker container prune      # contenedores parados
> docker image prune -a       # imágenes sin usar
> ```

### 0.2 Verificar Docker

```bash
docker context ls
docker ps
```

Tenés que ver `desktop-linux` marcado con `*` y una tabla de contenedores.

Si sale `permission denied ... /var/run/docker.sock`, el contexto está mal:

```bash
docker context use desktop-linux
```

### 0.3 Verificar Kubernetes

En Docker Desktop: **Settings → Kubernetes → Enable Kubernetes**. Esperá a que
el círculo diga **Running**. Después:

```bash
kubectl config current-context
kubectl get nodes
```

**Deberías ver:**

```
docker-desktop
NAME             STATUS   ROLES           AGE   VERSION
docker-desktop   Ready    control-plane   9d    v1.32.2
```

Lo importante es `STATUS = Ready`.

> **CAPTURA 1** — la salida de `kubectl get nodes` con el nodo en `Ready`.
>
> *Texto para el informe:* «El nodo `docker-desktop` en estado `Ready`
> confirma que el clúster de Kubernetes está operativo y que `kubectl` tiene
> conexión con la API del clúster.»

### 0.4 Obtener el proyecto y ubicarte

Si todavía no lo clonaste:

```bash
git clone https://github.com/maitemilca/usdt-mlops.git
cd usdt-mlops
```

Si ya lo tenés, entrá a la carpeta y traé lo último:

```bash
cd ruta/donde/clonaste/usdt-mlops
git pull
```

Verificá que estás en el lugar correcto:

```bash
ls
```

Tenés que ver `src/`, `k8s/`, `scripts/`, `data/`, `Dockerfile` y
`requirements.txt`.

**Todos los comandos de esta guía se ejecutan desde la raíz del repositorio**,
salvo donde se indique lo contrario. Cuando la guía diga "abrí otra terminal",
lo primero es volver a esta carpeta.

---

## Paso 1 — Entorno de Python

### 1.1 Crear el entorno e instalar dependencias

```bash
./scripts/01_preparar_entorno.sh
```

Tarda unos minutos la primera vez (descarga ~500 MB).

**Deberías ver al final:**

```
>> Verificando la instalacion
   mlflow 3.15.0 | scikit-learn 1.8.0 | xgboost 3.3.0 | pandas 2.3.3
>> Entorno listo. Activalo con:  source .venv/bin/activate
```

### 1.2 Activar el entorno

```bash
source .venv/bin/activate
```

El prompt pasa a empezar con `(.venv)`. **Si abrís una terminal nueva más
adelante, tenés que volver a activarlo.**

> **CAPTURA 2** — la verificación de versiones.
>
> *Texto para el informe:* «Entorno virtual con las 12 dependencias fijadas
> por versión exacta en `requirements.txt`. Fijar las versiones (y no usar
> rangos) es lo que garantiza que el entorno de desarrollo y el de la imagen
> de Docker sean idénticos.»

---

## Paso 2 — Fase 1: entrenamiento y MLflow

### 2.1 Mirar la configuración antes de entrenar

Vale la pena abrir `src/config.py` y ver estas constantes, porque son las que
te van a preguntar:

```bash
grep -E "^(RANDOM_SEED|TRAIN_PROP|FECHA_CORTE_V1|FECHA_FLEXIBILIZACION|REGISTERED_MODEL_NAME|DEPLOYMENT_ALIAS|METRICA_PRINCIPAL)" src/config.py
```

- `RANDOM_SEED = 42` — reproducibilidad
- `TRAIN_PROP = 0.8` — división cronológica 80/20
- `FECHA_CORTE_V1 = "2025-12-11"` — hasta dónde ve datos la versión 1
- `FECHA_FLEXIBILIZACION = "2026-06-29"` — el cambio de régimen del BCB

### 2.2 Entrenar

```bash
./scripts/02_entrenar.sh
```

**Deberías ver** (tarda ~1 minuto):

```
Datos hasta      : 2025-12-11
Dias utilizables : 259  (solo dias con cotizacion real al dia siguiente)
Balance          : 41.7% de dias al alza
Train / Test     : 207 / 52  (division cronologica 80/20)
Variables        : 8 -> ret_1d, ret_3d, ret_7d, vol_7d, ...

-- Baseline --
  [baseline_clase_mayoritaria] exactitud_balanceada_cv=0.5000 | ...
-- logistica --
  [logistica_C_0.05          ] exactitud_balanceada_cv=0.5220 | ...
  ...
-- xgboost --
  [xgboost_cfg2              ] exactitud_balanceada_cv=0.5860 | ...

Mejor por exactitud_balanceada_cv: xgboost_cfg2 (...)  = 0.5860
Registrado 'tc-usdt-bob-direccion' version 1  (run 98f86de4...)
  Alias 'champion' -> version 1
  Ficha escrita en MODELO_DESPLEGADO.md
```

> **CAPTURA 3** — la salida completa del entrenamiento.
>
> *Texto para el informe:* «Diez corridas comparables entre sí: un baseline de
> clase mayoritaria y nueve configuraciones de tres familias distintas
> (logística, Random Forest, XGBoost). Todas comparten división, variables y
> semilla, que es lo que las hace comparables. La ganadora se elige por
> exactitud balanceada en validación walk-forward, nunca mirando el conjunto
> de prueba.»

### 2.3 Ver la ficha del modelo desplegado

```bash
cat MODELO_DESPLEGADO.md
```

Este archivo lo genera `train.py` solo. Contiene el `run_id` exacto: es la
prueba documental que pide el punto 3.3.2 del enunciado.

> **CAPTURA 4** — el contenido de `MODELO_DESPLEGADO.md`.
>
> *Texto para el informe:* «Ficha de trazabilidad generada automáticamente por
> el script de entrenamiento. Vincula la versión desplegada del Model Registry
> con el `run_id` exacto del experimento que la produjo.»

---

## Paso 3 — Fase 1: la interfaz de MLflow

El enunciado dice que esta interfaz **se muestra en vivo durante la
presentación**, así que conviene practicar esta parte.

### 3.1 Levantar la interfaz

En una terminal **aparte** (esta queda ocupada):

```bash
cd ruta/donde/clonaste/usdt-mlops
source .venv/bin/activate
mlflow ui --backend-store-uri "sqlite:///$(pwd)/mlflow_store/mlflow.db" --port 5000
```

Abrí <http://localhost:5000> en el navegador.

> **Ojo con el `--backend-store-uri`.** Si corrés `mlflow ui` a secas, MLflow
> busca una carpeta `mlruns/` que no existe y vas a ver la interfaz vacía. El
> proyecto guarda todo en `mlflow_store/mlflow.db`.

### 3.2 Cambiar a la vista de entrenamiento (importante)

MLflow 3.x abre por defecto en la vista **GenAI**, pensada para proyectos de
modelos de lenguaje. Ahí vas a ver Traces, Sessions, Judges y Prompts, todo
vacío y sin rastro de tus corridas. No es que falten: es la vista equivocada.

Arriba a la izquierda, justo debajo del logo de MLflow, hay un selector:

```
[ GenAI ]  [ Model training ]
              ↑ hacé click acá
```

Hacé click en **Model training**. También funciona **Training runs** en el
menú de la izquierda.

Recién ahí aparece la tabla con las 10 corridas del experimento.

### 3.3 Recorrer lo que te van a pedir

El enunciado (punto 3.4) pide poder hacer cuatro cosas en vivo. Practicalas:

**a) Abrir el experimento y explicar los runs.**
Click en `tc_usdt_bolivia_diario` en la izquierda. Vas a ver las 10 corridas.
Cada run es una configuración de hiperparámetros sobre los mismos datos.

**b) Mostrar las métricas.**
MLflow 3.15 no las muestra por defecto: la tabla arranca solo con Run Name,
Created, Duration y Source. Click en **Columns** (o en *Show more columns*) y
activá `exactitud_balanceada_cv`, `exactitud_balanceada`, `roc_auc` y
`exactitud`.

**c) Ordenar por la métrica principal.**
No se ordena clickeando la cabecera. Usá el desplegable **`Sort: Created`** y
elegí `exactitud_balanceada_cv`, descendente.

Arriba queda `xgboost_cfg2` con 0,5860 y último `baseline_clase_mayoritaria`
con 0,5000.

**d) Filtrar.**
En la barra de búsqueda:

```
metrics.exactitud_balanceada_cv > 0.55
```

Quedan 4 corridas: los tres XGBoost y `bosque_cfg3`. Borrá el filtro para
volver a verlas todas.

**e) Comparar runs.**
Tildá las casillas de `xgboost_cfg2`, `bosque_cfg3` y
`baseline_clase_mayoritaria`, y hacé click en **Compare**. Vas a ver los
hiperparámetros y las métricas lado a lado.

> Este es el momento para explicar la decisión más interesante del proyecto:
> `bosque_cfg3` tiene mejor exactitud en el test (0,705) que el modelo elegido
> (0,641), pero se eligió `xgboost_cfg2` porque ganó en **walk-forward**.
> Elegir mirando el test lo invalidaría como evaluación independiente.

**f) Abrir el Model Registry.**
Pestaña **Models** arriba → `tc-usdt-bob-direccion` → vas a ver la versión 1
con el alias `champion` y la descripción que escribió `train.py`.

### 3.4 Ver los gráficos de un run

Entrá a `xgboost_cfg2` → pestaña **Artifacts** → `evaluacion.png`. Tiene la
matriz de confusión y la curva ROC.

> **CAPTURA 5** — la lista de runs ordenada por la métrica principal.
>
> *Texto para el informe:* «Experimento `tc_usdt_bolivia_diario` con las diez
> corridas ordenadas por exactitud balanceada de validación cruzada. Las nueve
> configuraciones reales superan al baseline de clase mayoritaria (0,500).»

> **CAPTURA 6** — la vista de comparación de 3 runs.
>
> *Texto para el informe:* «Comparación lado a lado. Permite justificar la
> elección del modelo desplegado contrastando hiperparámetros y métricas de
> validación y de prueba.»

> **CAPTURA 7** — el Model Registry con la versión 1 y el alias `champion`.
>
> *Texto para el informe:* «Model Registry con el modelo registrado bajo un
> nombre estable. El alias `champion` marca de forma explícita cuál de las
> versiones es la que consume el servicio en producción.»

> **CAPTURA 8** — el artefacto `evaluacion.png` de la corrida ganadora.
>
> *Texto para el informe:* «Matriz de confusión y curva ROC del modelo
> desplegado, registradas como artefacto del run. Permiten verificar que el
> modelo discrimina y no está prediciendo siempre la misma clase.»

**Dejá esta terminal con MLflow corriendo**, la vas a volver a usar. Para
cortarla, `Ctrl+C`.

---

## Paso 4 — Fase 6: pruebas y monitores de deriva

Hacemos la Fase 6 antes que Docker porque el resultado del monitoreo es lo
que justifica la versión 2 más adelante.

### 4.1 Pruebas automatizadas del detector

```bash
./scripts/03_pruebas.sh
```

**Deberías ver:**

```
tests/test_deteccion_deriva.py::test_ks_no_detecta_deriva_... PASSED
...
============================== 12 passed in 2.21s ==============================
```

> **CAPTURA 9** — las 12 pruebas en verde.
>
> *Texto para el informe:* «Batería de pruebas automatizadas del detector de
> deriva: verifica que KS y PSI se comportan correctamente en casos
> controlados, que el control no produce falsos positivos, que la deriva real
> e inyectada se detectan, y que los datos cumplen sus invariantes (etiquetas
> reales, sin fuga temporal, sin valores faltantes).»

### 4.2 Los monitores como puerta

Esta es la parte que pide el enunciado: **verde con datos del mismo origen,
rojo con datos derivados**. Corré los tres casos uno por uno para verlo.

**Caso verde:**

```bash
cd src
python monitor_data_drift.py --escenario control
echo "Código de salida: $?"
```

**Deberías ver** `VEREDICTO: VERDE (sin deriva)` y `Código de salida: 0`.

**Caso rojo con datos reales:**

```bash
python monitor_data_drift.py --escenario post_flex
echo "Código de salida: $?"
```

**Deberías ver** `VEREDICTO: ROJO (deriva detectada)` y `Código de salida: 1`.

**Caso rojo con deriva inyectada:**

```bash
python monitor_data_drift.py --escenario sintetico
echo "Código de salida: $?"
```

**Deberías ver** `VEREDICTO: ROJO (deriva detectada)` y `Código de salida: 1`.

Y volvés a la raíz del repositorio, porque el paso 4.3 se corre desde ahí:

```bash
cd ..
```

> **CAPTURA 10** — las tres salidas juntas, mostrando código 0 en el control y
> código 1 en los dos casos con deriva.
>
> *Texto para el informe:* «El monitor de data drift no es un reporte
> informativo sino una puerta: termina con código de salida 0 en verde y 1 en
> rojo, de modo que pueda encadenarse en un pipeline y detener un despliegue.
> El control —una mitad aleatoria del propio conjunto de entrenamiento— pasa
> en verde, lo que descarta falsos positivos; los lotes con deriva real e
> inyectada fallan en rojo.»

### 4.3 Reporte completo y concept drift

```bash
./scripts/04_monitores_deriva.sh
```

Corre los seis escenarios y guarda todo en
`evidencia/evidencia_deriva.txt`. Tarda ~2 minutos.

**Lo importante que vas a ver en el concept drift:**

```
mes       n   pct_al_alza   exactitud_balanceada
2025-12   21     0.5714           0.6111
2026-01   31     0.3871           0.4781
2026-02   27     0.3704           0.4706
2026-03   30     0.6333           0.4306
2026-04   30     0.6667           0.6000
2026-05   31     0.4839           0.5458
2026-06   29     0.4138           0.2770   <- mes de la flexibilización
2026-07   30     0.8000           0.5833

ALARMA: se habria disparado en 2026-02.
```

### 4.4 Mirar los gráficos

```bash
xdg-open resultados/concept_drift.png
xdg-open resultados/data_drift.png
```

> **CAPTURA 11** — `resultados/data_drift.png`.
>
> *Texto para el informe:* «Distribución del retorno diario en cada escenario
> contra el baseline de entrenamiento. En el control las dos distribuciones se
> superponen; en los lotes derivados se separan visiblemente.»

> **CAPTURA 12** — `resultados/concept_drift.png`.
>
> *Texto para el informe:* «Degradación temporal del modelo desplegado sobre
> lotes mensuales del holdout real. La línea roja marca el umbral de alarma
> (0,50 = azar) y la línea punteada vertical la flexibilización cambiaria del
> BCB. El peor mes es junio de 2026, el del cambio de régimen.»

> **CAPTURA 13** — la tabla mensual y la línea `ALARMA: se habria disparado en
> 2026-02`.
>
> *Texto para el informe:* «Criterio de reentrenamiento explícito: alarma si
> la exactitud balanceada cae por debajo de 0,50 durante dos meses
> consecutivos. Se eligió 0,50 porque es el valor exacto del azar en esta
> métrica: por debajo, el modelo induce decisiones peores que tirar una
> moneda. Dos meses, porque cada lote tiene unos 25 días con etiqueta y un
> solo mes se mueve varios puntos por azar.»

> **CAPTURA 14** — el barrido del control sintético (0% a 100% de etiquetas
> invertidas).
>
> *Texto para el informe:* «Control positivo del detector de concept drift: se
> invierten las etiquetas de una fracción creciente del conjunto de prueba
> dejando las variables de entrada intactas, de modo que toda degradación sea
> concept drift puro. Con inversión total el detector dispara. Que con el 50%
> no dispare es correcto: con la mitad de las etiquetas invertidas el
> rendimiento real del modelo es el del azar, y el monitor lo está reportando
> con exactitud.»

---

## Paso 5 — Fase 2: contenerización

### 5.1 Entender qué va a pasar

Antes de construir, mirá el `Dockerfile`:

```bash
head -25 Dockerfile
```

La decisión clave: la imagen **copia** el store de MLflow y le reescribe las
rutas, en vez de reentrenar durante el build. Así el modelo que responde en
Kubernetes es el mismo `run_id` que viste en `mlflow ui`. Reentrenar dentro
del build habría generado un run nuevo y roto la trazabilidad.

### 5.2 Construir la imagen

```bash
docker build -t tc-usdt-api:1.0 .
```

Tarda ~5 minutos la primera vez.

> Si al reconstruir ves varios pasos marcados como `CACHED`, Docker está
> reutilizando capas y no vas a ver la salida de la reescritura de rutas. Para
> la captura, forzá un build completo con
> `docker build --no-cache -t tc-usdt-api:1.0 .`

**Deberías ver, cerca del final:**

```
 => [7/7] RUN python src/portar_store.py --db /app/mlflow_store/mlflow.db --nuevo-prefijo /app/mlflow_store
 ...
Prefijo actual : /home/elmarcinho/.../version-elmar/mlflow_store
Prefijo nuevo  : /app/mlflow_store
  experiments.artifact_location: 1 filas
  runs.artifact_uri: 10 filas
  ...
 => exporting to image
 => => naming to docker.io/library/tc-usdt-api:1.0
```

```bash
docker images | grep tc-usdt-api
```

> **CAPTURA 15** — el build terminado, con el paso `[7/9] RUN python
> src/portar_store.py` y el `naming to docker.io/library/tc-usdt-api:1.0`.
>
> *Texto para el informe:* «Construcción de la imagen en nueve pasos. El paso
> 7 es el que hace portable el store de MLflow: la base de datos guarda rutas
> absolutas de artefactos, que no existen dentro del contenedor. Al
> reescribirlas se conserva el `run_id` original, y el modelo que sirve
> peticiones es exactamente el que se muestra en la interfaz de MLflow.»

> **Docker no muestra la salida de los pasos que terminan bien**, así que no
> vas a leer el "21 rutas reescritas" en pantalla. Si querés esa evidencia
> explícita, rehacé el build con `docker build --no-cache --progress=plain -t
> tc-usdt-api:1.0 .` (tarda ~5 minutos).
>
> No hace falta para el informe: la prueba de que la reescritura funcionó es
> la captura 16. Si hubiera fallado, el contenedor no encontraría los
> artefactos y no levantaría.

### 5.3 Probar el contenedor suelto

Antes de Kubernetes, verificá que la imagen funciona sola:

```bash
docker run -d --name prueba-tc -p 8000:8000 tc-usdt-api:1.0
sleep 25
docker logs prueba-tc | tail -5
```

**Deberías ver:**

```
[arranque] Modelo cargado: tc-usdt-bob-direccion@champion (version 1, run 98f86de4...) en el pod <id>
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Probá los tres endpoints:

```bash
curl -s http://localhost:8000/health; echo
curl -s http://localhost:8000/model-info; echo
```

Para `/predict` hace falta un historial de al menos 31 días. Hay un archivo
armado a partir de tus propios datos:

```bash
python - <<'PY' > /tmp/peticion.json
import json, sys
sys.path.insert(0, "src")
import config as cfg, features as f
serie = f.cargar_serie_diaria(cfg.CSV_COMPLETO).tail(40)
print(json.dumps({"historial": [
    {"fecha": i.strftime("%Y-%m-%d"), "precio": round(float(v), 4)}
    for i, v in serie["precio"].items()]}))
PY

curl -s -X POST http://localhost:8000/predict \
     -H 'Content-Type: application/json' \
     -d @/tmp/peticion.json; echo
```

**Deberías ver algo como:**

```json
{"fecha_referencia":"2026-07-31","precio_referencia":11.984,
 "fecha_predicha":"2026-08-01","direccion":"NO SUBE","clase":0,
 "probabilidad_sube":0.2677,"model_version":1,"model_alias":"champion",
 "run_id":"98f86de4...","served_by_pod":"<id del contenedor>"}
```

> **CAPTURA 16** — las respuestas de los tres endpoints.
>
> *Texto para el informe:* «El contenedor levanta el servicio y responde
> peticiones de inferencia sin ningún paso manual adicional. El campo
> `run_id` de la respuesta coincide con el del experimento en MLflow, y
> `served_by_pod` identifica qué instancia respondió: es lo que permitirá
> demostrar el balanceo de carga en la Fase 3.»

### 5.4 Limpiar

```bash
docker stop prueba-tc && docker rm prueba-tc
```

---

## Paso 6 — Fase 3: Kubernetes

### 6.1 Mirar los manifiestos

```bash
cat k8s/deployment.yaml
cat k8s/service.yaml
```

Dos cosas que te pueden preguntar:

- **Tres sondas distintas**: `startupProbe` da hasta 60 s para cargar el
  modelo; `readinessProbe` decide si el pod recibe tráfico; `livenessProbe`
  reinicia un proceso colgado.
- **NodePort y no `port-forward`**: `port-forward` abre un túnel a un solo pod
  y haría imposible demostrar el balanceo.

### 6.2 Desplegar

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

**Deberías ver:**

```
deployment.apps/tc-usdt-api created
service/tc-usdt-api-service created
```

Esperá a que los pods estén listos:

```bash
kubectl wait --for=condition=available --timeout=180s deployment/tc-usdt-api
kubectl get pods -l app=tc-usdt-api -o wide
```

**Deberías ver 3 pods en `Running` y `READY 1/1`:**

```
NAME                           READY   STATUS    RESTARTS   AGE
tc-usdt-api-7d4b9c8f5-2xk9p    1/1     Running   0          45s
tc-usdt-api-7d4b9c8f5-8mnqr    1/1     Running   0          45s
tc-usdt-api-7d4b9c8f5-vw3tz    1/1     Running   0          45s
```

Si algún pod queda en `ErrImageNeverPull`, mirá
[Problemas frecuentes](#problemas-frecuentes).

### 6.3 Verificar que el Service responde

```bash
curl -s http://localhost:30080/health; echo
```

### 6.4 Correr las cuatro demostraciones

```bash
./scripts/05_pruebas_kubernetes.sh
```

Tarda ~2 minutos y va mostrando todo en pantalla mientras lo guarda en
`evidencia/evidencia_kubernetes.txt`.

**Sacá capturas mientras corre** — especialmente en la demostración 3, cuando
se ve el pod viejo en `Terminating` y el nuevo creándose.

> **CAPTURA 17** — demostración 1: `kubectl get pods -o wide` con 3 pods en
> `Running`.
>
> *Texto para el informe:* «Las tres réplicas del servicio en estado `Running`
> simultáneamente, cada una con su propia IP dentro del clúster.»

> **CAPTURA 18** — demostración 2: las 20 peticiones con el pod que respondió
> cada una, y el conteo final.
>
> *Texto para el informe:* «Veinte peticiones sucesivas al Service, atendidas
> por pods distintos. Cada respuesta incluye `served_by_pod`, que es el
> hostname del contenedor y en Kubernetes coincide con el nombre del pod. El
> reparto lo hace el kube-proxy del Service; se usa NodePort y no
> `port-forward` porque este último abre un túnel contra un único pod.»

> **CAPTURA 19** — demostración 3: el estado justo después de eliminar el pod,
> con el viejo en `Terminating` y el nuevo en `ContainerCreating`.
>
> *Texto para el informe:* «Autorreparación. Al eliminar un pod manualmente,
> el Deployment detecta que el estado real (2 réplicas) no coincide con el
> deseado (3) y crea uno nuevo automáticamente. El servicio sigue respondiendo
> durante el reemplazo, porque las otras dos réplicas siguen en el balanceo.»

> **CAPTURA 20** — demostración 4: los 5 pods tras escalar, y la vuelta a 3.
>
> *Texto para el informe:* «Escalado horizontal. `kubectl scale` cambia el
> número deseado de réplicas y el Deployment crea o elimina pods hasta
> alcanzarlo.»

> **CAPTURA 21** — la salida de `/model-info` al final del script.
>
> *Texto para el informe:* «El servicio desplegado en el clúster reporta la
> versión y el `run_id` del modelo que está sirviendo. Coinciden con
> `MODELO_DESPLEGADO.md` y con el Model Registry de MLflow: la trazabilidad se
> mantiene de punta a punta.»

### 6.5 Guardar evidencia adicional

```bash
kubectl get all -l app=tc-usdt-api > evidencia/estado_cluster.txt
kubectl describe deployment tc-usdt-api > evidencia/describe_deployment.txt
kubectl logs -l app=tc-usdt-api --tail=30 > evidencia/logs_pods.txt
```

---

## Paso 7 — Extra: interfaz web

Vale hasta 15 puntos, **solo si el proyecto base está completo**.

### 7.1 Instalar la interfaz en su PROPIO entorno

La interfaz va en un entorno virtual separado, no en el `.venv` del proyecto.
No es manía de orden: la consigna exige que el consumo de la API sea real
contra el servicio en Kubernetes, y la única forma de demostrarlo sin lugar a
dudas es que la interfaz **no tenga instaladas** las librerías de modelado.
Si comparte entorno con MLflow, podría cargar el modelo y nadie podría
descartar que lo hace.

En una terminal nueva:

```bash
cd ruta/donde/clonaste/usdt-mlops

python3 -m venv .venv-ui
.venv-ui/bin/pip install -q --upgrade pip
.venv-ui/bin/pip install -q -r ui/requirements.txt
echo ".venv-ui/" >> .gitignore
```

Solo instala `streamlit`, `requests` y `pandas`.

> **Si ya instalaste `ui/requirements.txt` dentro del `.venv` principal**,
> limpialo. Streamlit arrastra `pyarrow` a una versión más vieja que la que
> resuelve MLflow:
> ```bash
> .venv/bin/pip uninstall -y -q streamlit altair pydeck watchdog
> .venv/bin/pip install -q "pyarrow==25.0.0"
> ```

### 7.1.1 Verificar la separación

```bash
.venv-ui/bin/python -c "import mlflow"    # debe fallar
.venv-ui/bin/python -c "import sklearn"   # debe fallar
.venv-ui/bin/python -c "import xgboost"   # debe fallar
.venv-ui/bin/pip list | grep -iE "streamlit|requests|pandas"
```

Tres `ModuleNotFoundError` y después la lista con solo esos tres paquetes.

> **CAPTURA 22a** — los tres errores de importación y la lista de paquetes.
>
> *Texto para el informe:* «La interfaz corre en un entorno virtual propio que
> no tiene instaladas MLflow, scikit-learn ni XGBoost. No puede cargar el
> modelo ni aunque se lo pidiera: es un cliente HTTP puro contra el servicio
> desplegado en Kubernetes. La separación no es una convención documentada
> sino una restricción verificable.»

### 7.1.2 Levantar la interfaz

```bash
.venv-ui/bin/streamlit run ui/app_streamlit.py
```

No actives el `.venv` principal antes: usá el binario de `.venv-ui` directo.

La primera vez Streamlit pide un correo para su boletín. **Dejalo en blanco y
dale Enter**, es opcional.

Se abre en <http://localhost:8501>.

### 7.2 Recorrerla

1. **Comprobar estado** en la barra lateral → tiene que decir qué pod respondió.
2. **Ver modelo desplegado** → muestra versión, alias y `run_id`.
3. **Lanzar peticiones** (balanceo) → 20 peticiones y cuántas contestó cada pod.
4. En el cuerpo: elegí días de historial y **Consultar al servicio**.

> **CAPTURA 22** — la interfaz con una predicción hecha, mostrando el pod que
> respondió y la versión del modelo.
>
> *Texto para el informe:* «Interfaz web consumiendo la API real desplegada en
> Kubernetes a través del NodePort. No carga el modelo ni calcula variables:
> es un cliente HTTP puro. Si el clúster estuviera apagado, no podría predecir
> nada, lo que demuestra que no hay ningún atajo local.»

> **CAPTURA 23** — el panel de balanceo mostrando varios pods.
>
> *Texto para el informe:* «La interfaz reproduce la demostración de balanceo
> de carga de la Fase 3 contra el servicio real.»

Cortá con `Ctrl+C` cuando termines.

---

## Paso 8 — Cerrar el ciclo: versión 2

El enunciado exige **más de una versión registrada**. Pero en vez de entrenar
dos veces porque sí, acá la versión 2 aparece como **respuesta al monitoreo**:
el Paso 4 detectó deriva sostenida, y la reacción correcta es reentrenar.

### 8.1 Reentrenar con todos los datos

```bash
./scripts/06_reentrenar_v2.sh
```

**Deberías ver:**

```
Datos hasta      : 2026-07-31
Dias utilizables : 488  (mucho mas que los 259 de la v1)
...
Registrado 'tc-usdt-bob-direccion' version 2  (run ...)
  Alias 'champion' NO movido (--sin-alias): la version 2 queda registrada pero no desplegada.
```

Fijate que el script usa `--sin-alias` a propósito: **promover una versión es
una decisión explícita**, no un efecto secundario de entrenar.

### 8.2 Ver las dos versiones en el Registry

Volvé a la pestaña de MLflow (<http://localhost:5000>) → **Models** →
`tc-usdt-bob-direccion`. Ahora hay dos versiones, y `champion` sigue en la 1.

> **CAPTURA 24** — el Model Registry con las dos versiones y el alias en la v1.
>
> *Texto para el informe:* «Dos versiones registradas bajo el mismo nombre
> estable. La versión 2 se entrenó como respuesta al concept drift detectado
> por el monitoreo, incorporando los datos posteriores al cambio de régimen
> cambiario. Queda registrada sin alias: promoverla a producción es una
> decisión explícita y separada.»

### 8.3 Promover la versión 2 y ver el efecto

Este es el cierre del ciclo de vida completo.

```bash
python - <<'PY'
import sys; sys.path.insert(0, "src")
import mlflow, config as cfg
cfg.configurar_mlflow()
cliente = mlflow.MlflowClient()
cliente.set_registered_model_alias(cfg.REGISTERED_MODEL_NAME, cfg.DEPLOYMENT_ALIAS, 2)
version = cliente.get_model_version_by_alias(cfg.REGISTERED_MODEL_NAME, cfg.DEPLOYMENT_ALIAS)
print(f"Alias '{cfg.DEPLOYMENT_ALIAS}' -> version {version.version} (run {version.run_id})")
PY
```

Para que el clúster tome la versión nueva hay que **reconstruir la imagen y
reiniciar el despliegue**, porque el store viaja dentro de la imagen:

```bash
docker build -t tc-usdt-api:2.0 .
kubectl set image deployment/tc-usdt-api tc-usdt-api=tc-usdt-api:2.0
kubectl rollout status deployment/tc-usdt-api
curl -s http://localhost:30080/model-info; echo
```

**Deberías ver** `"version":2` en la respuesta.

> **CAPTURA 25** — el `rollout` y la respuesta de `/model-info` mostrando la
> versión 2.
>
> *Texto para el informe:* «Ciclo de vida cerrado: el monitoreo detectó
> degradación, se reentrenó, se registró una versión nueva, se movió el alias
> y se actualizó el despliegue mediante una actualización gradual, sin
> interrumpir el servicio.»

Si querés volver a la versión 1:

```bash
kubectl rollout undo deployment/tc-usdt-api
```

---

## Paso 9 — Repositorio Git

**Es obligatorio**, y el enunciado avisa que el historial de commits se revisa
como evidencia del reparto de trabajo.

> **El repositorio ya existe: `github.com/maitemilca/usdt-mlops`.**
> No corras `git init` ni `git remote add`. Solo se commitea lo que se va
> generando.

### 9.1 Ver qué hay pendiente

```bash
git status --short
```

Comprobá que **no** aparezcan `.venv/`, `.venv-ui/` ni `mlflow_store/`: el
`.gitignore` los excluye. Si ves un archivo `.~lock.*#`, es de LibreOffice —
cerrá el programa antes de seguir.

### 9.2 Commitear lo pendiente

Cada uno commitea los componentes que le tocan según `REPARTO_TRABAJO.md`, con
mensajes que digan qué fase cubren:

```bash
git config user.name "Tu Nombre"
git config user.email "tu@correo.com"

git add <los archivos de tu parte>
git commit -m "Descripcion clara de que cubre este commit"
git push
```

### 9.3 Versionar la evidencia generada

Al terminar de correr las fases quedan archivos de evidencia que por defecto
están ignorados, porque durante el desarrollo cambian en cada ejecución y
generarían conflictos entre las dos máquinas:

```
evidencia/evidencia_deriva.txt
evidencia/evidencia_kubernetes.txt
evidencia/estado_cluster.txt
evidencia/describe_deployment.txt
evidencia/logs_pods.txt
resultados/data_drift.png
resultados/concept_drift.png
MODELO_DESPLEGADO.md
```

**Súbanlos una sola vez, al final, cuando los dos hayan terminado de
ejecutar.** Son ~280 KB en total y hacen que el repositorio quede
autocontenido: quien abra el enlace ve el código y la evidencia sin
descargar nada más.

```bash
git add -f evidencia/*.txt resultados/*.png MODELO_DESPLEGADO.md
git commit -m "Evidencia de ejecucion de las fases 1, 2, 3 y 6"
git push
```

El `-f` fuerza el `add` saltándose el `.gitignore`.

### 9.4 Verificar que el historial respalde el reparto

```bash
git log --oneline --format='%an  %s'
```

Contrastá esa salida con la tabla de `REPARTO_TRABAJO.md`. Si alguien figura
como responsable de un componente que nunca commiteó, hay que corregir la
tabla o repartir de nuevo — el enunciado dice que ese historial se revisa
como evidencia.

> **CAPTURA 26** — `git log --oneline` con los commits de los dos integrantes.
>
> *Texto para el informe:* «Historial de commits del repositorio, organizado
> por fase del proyecto y con la autoría de cada integrante, como evidencia
> del reparto de trabajo declarado.»

## Paso 10 — Armar la entrega

El enunciado pide: **enlace al repositorio + un comprimido con documentación y
evidencia**.

### 10.1 Verificación final

```bash
ls evidencia/
ls resultados/
cat MODELO_DESPLEGADO.md
kubectl get pods -l app=tc-usdt-api
```

Deberías tener:
- `evidencia/evidencia_kubernetes.txt`
- `evidencia/evidencia_deriva.txt`
- `evidencia/estado_cluster.txt`, `describe_deployment.txt`, `logs_pods.txt`
- `resultados/data_drift.png`, `resultados/concept_drift.png`

### 10.2 Guardar las capturas

```bash
mkdir -p evidencia/capturas
# copiá ahí las 26 capturas, nombradas 01_nodo_ready.png, 02_entorno.png, ...
```

### 10.3 Comprimir

```bash
cd ..
zip -r entrega_ProyectoFinal_ElmarRodas.zip version-elmar \
    -x "version-elmar/.venv/*" \
    -x "version-elmar/mlflow_store/*" \
    -x "version-elmar/.git/*" \
    -x "version-elmar/**/__pycache__/*" \
    -x "version-elmar/.pytest_cache/*"
ls -lh entrega_ProyectoFinal_ElmarRodas.zip
```

### 10.4 Lista de control

- [ ] Repositorio Git con historial por fases y subido
- [ ] `REPARTO_TRABAJO.md` completo y consistente con los commits
- [ ] 26 capturas en el Word, con su explicación
- [ ] `ARQUITECTURA.md` con la versión desplegada y su `run_id`
- [ ] Dos versiones en el Model Registry
- [ ] Evidencia de las 4 demostraciones de Kubernetes
- [ ] Monitores de deriva en verde y en rojo, con sus códigos de salida
- [ ] Criterio de reentrenamiento y label delay documentados
- [ ] Interfaz web funcionando contra el clúster
- [ ] Los dos integrantes recorrieron el flujo completo al menos una vez

---

## Problemas frecuentes

**`permission denied ... /var/run/docker.sock`**
El contexto de Docker está mal. `docker context use desktop-linux`

**`ErrImageNeverPull` o `ImagePullBackOff` en los pods**
Kubernetes no ve la imagen local. Verificá que exista: `docker images | grep
tc-usdt-api`. Si existe pero el pod falla, el clúster no está compartiendo el
almacén de imágenes; probá reconstruir con
`docker build -t tc-usdt-api:1.0 .` y luego
`kubectl rollout restart deployment/tc-usdt-api`.

**La interfaz de MLflow aparece vacía**
Corriste `mlflow ui` sin `--backend-store-uri`. Usá el comando completo del
paso 3.1.

**Los pods se reinician en bucle (`CrashLoopBackOff`)**
Mirá el log: `kubectl logs -l app=tc-usdt-api --tail=50`. Si dice que no
encuentra el modelo, la reescritura de rutas falló: reconstruí la imagen y
revisá que `mlflow_store/` exista antes del `docker build`.

**`curl: (7) Failed to connect to localhost port 30080`**
El Service no está aplicado o los pods no están listos.
`kubectl get svc tc-usdt-api-service` y `kubectl get pods -l app=tc-usdt-api`

**Un solo pod contesta todas las peticiones**
Estás usando `port-forward` en vez del NodePort. Consultá
`http://localhost:30080`.

**La máquina se pone muy lenta durante la Fase 3**
Cerrá pestañas de Chrome y bajá a 3 réplicas:
`kubectl scale deployment tc-usdt-api --replicas=3`

**`ModuleNotFoundError` al correr un script**
No activaste el entorno: `source .venv/bin/activate`

---

## Preguntas de defensa

Recordá que **te pueden preguntar por cualquier parte, no solo por la que
hiciste vos**.

### Sobre el modelo

**¿Por qué clasificación y no regresión, si la actividad anterior fue
regresión?**
Porque lo medimos. Probamos predecir el valor exacto con Ridge y XGBoost en
horizontes de 1 a 30 días, con variables de nivel y de retorno, y con
validación walk-forward. El baseline ingenuo ganó en todos los casos. No es un
problema de implementación: a frecuencia diaria un tipo de cambio se comporta
como un paseo aleatorio, y que el baseline sea imbatible en nivel es un
resultado clásico en econometría cambiaria (Meese-Rogoff, 1983). El signo del
movimiento sí es aprendible, y ahí el modelo sí supera a su baseline.

**¿Por qué frecuencia diaria y no horaria?**
La serie tiene 2.937 cotizaciones en 700 días, muy irregulares. A frecuencia
horaria habría que rellenar el 87% de las casillas hacia adelante, y el modelo
solo aprendería que el precio de la próxima hora es igual al de esta. Por día,
el 71% tiene cotización real.

**¿Por qué exactitud balanceada y no exactitud?**
Las clases son 42/58. Un modelo que dijera siempre "no sube" sacaría 58% de
exactitud sin haber aprendido nada; en exactitud balanceada saca 0,50, que es
exactamente el azar.

**¿Por qué elegiste `xgboost_cfg2` si `bosque_cfg3` tiene mejor exactitud en
el test?**
Porque la selección se hace por validación walk-forward sobre el conjunto de
entrenamiento, no mirando el test. El test son 52 días: tres aciertos de
diferencia mueven la métrica 6 puntos. Y si eligiéramos mirando el test,
dejaría de ser una evaluación independiente.

**¿Por qué la división es cronológica y no aleatoria?**
Porque es una serie temporal. Mezclar filas al azar dejaría días futuros en el
entrenamiento, y el modelo se evaluaría sobre información que ya vio.

**¿Por qué filtrás los días sin cotización real?**
Porque si el día siguiente no tuvo cotización, su precio es una copia del
anterior y la etiqueta "sube" da 0 por construcción, no porque el mercado se
haya movido. Con esas filas dentro, el balance es 72/28 y el baseline queda
artificialmente inflado; filtrando queda 42/58.

### Sobre MLflow

**¿Qué representa cada run?**
Una configuración de hiperparámetros entrenada sobre exactamente los mismos
datos, división y semilla. Eso es lo que las hace comparables.

**¿Por qué hay dos versiones registradas?**
No es para cumplir el requisito: la versión 2 es la respuesta al concept drift
que detectó el monitoreo. La v1 se entrenó con datos hasta diciembre de 2025;
el monitor midió su degradación sobre los siete meses siguientes y la alarma
se disparó en febrero de 2026. Reentrenar es la reacción correcta.

**¿Por qué la v2 quedó sin alias?**
Porque promover un modelo a producción es una decisión explícita, no un efecto
secundario de entrenar. El entrenamiento registra; la promoción se hace aparte.

### Sobre Docker

**¿Por qué copiás el store en vez de reentrenar en el build?**
Porque reentrenar genera un `run_id` nuevo, distinto del que se muestra en la
interfaz de MLflow, y eso rompe la trazabilidad que pide el enunciado.
Copiando el store, el modelo que responde en Kubernetes es literalmente el
mismo run.

**¿Y por qué hay que reescribir rutas?**
Porque MLflow guarda rutas absolutas de artefactos en su base de datos. Las de
la máquina de desarrollo no existen dentro del contenedor. Son cuatro columnas
en el sqlite y `portar_store.py` las actualiza de forma determinista.

**¿Cómo sabés que el contenedor no depende de nada del anfitrión?**
Porque el `.dockerignore` deja fuera `data/`, `.venv/` y todo lo demás: dentro
solo entran el código, el store y las dependencias fijadas.

### Sobre Kubernetes

**¿Por qué NodePort y no `port-forward`?**
`port-forward` abre un túnel contra un único pod y lo mantiene toda la sesión;
con eso todas las peticiones las contesta el mismo pod y no se puede demostrar
el balanceo. NodePort pasa por el kube-proxy real del Service.

**¿Por qué tres sondas distintas?**
`startupProbe` le da tiempo al arranque para cargar el modelo sin que la
`livenessProbe` lo mate; `readinessProbe` saca del balanceo a un pod que no
puede responder; `livenessProbe` reinicia un proceso colgado.

**¿Cómo funciona la autorreparación?**
El Deployment compara el estado real con el deseado. Si borrás un pod quedan
2 de 3, y crea uno nuevo. El Service lo encuentra por etiqueta, no por nombre,
así que el pod nuevo entra al balanceo automáticamente.

**¿Qué pasaría si un pod se queda sin memoria?**
Con `limits.memory: 256Mi`, el kernel lo mata (OOMKilled) y Kubernetes lo
reinicia. Los otros dos siguen atendiendo.

### Sobre deriva

**¿Por qué KS para unas variables y PSI para otras?**
KS compara distribuciones acumuladas completas y sirve para variables
continuas, sin suponer normalidad —importante, porque los retornos cambiarios
tienen colas pesadas. Para `dia_semana` (7 categorías) y `es_fin_semana`
(binaria), KS no tiene interpretación útil; PSI compara frecuencias de
categoría, que es lo que importa.

**¿De dónde salen los umbrales?**
α = 0,05 para KS es el nivel estándar de significancia. Los 0,10 y 0,25 de PSI
son los umbrales consolidados en riesgo crediticio, donde nació el índice.

**¿Por qué el control es un reparto aleatorio y no el conjunto de prueba?**
Porque el test es un tramo posterior en el tiempo, y en una serie cambiaria
eso ya trae un cambio de nivel: marcaría deriva aunque no hubiera ningún
problema. Con un reparto aleatorio, las dos mitades vienen de la misma
distribución por construcción.

**¿Por qué el criterio de reentrenamiento es 0,50 y dos meses?**
0,50 es el valor exacto del azar en exactitud balanceada: por debajo, el
modelo induce decisiones peores que tirar una moneda. Es un umbral con
significado propio. Dos meses porque cada lote tiene ~25 días con etiqueta y
un solo mes se mueve varios puntos por azar.

**En el control sintético, ¿por qué con el 50% invertido no dispara?**
Porque con la mitad de las etiquetas dadas vuelta el modelo acierta en un
tramo y falla en el otro, así que su rendimiento real *es* el del azar. El
monitor está reportando la verdad. Lo que muestra el barrido es que una
inversión parcial es el caso más difícil de detectar.

**¿Qué hacés con el retraso de etiqueta?**
Acá es corto —la etiqueta de hoy se sabe mañana—, pero con lotes mensuales un
mes malo recién se confirma cuando terminó. Mientras tanto: el monitor de data
drift funciona sin etiquetas y es la alerta temprana; se vigila la
distribución de las probabilidades devueltas, porque si el modelo empieza a
responder siempre lo mismo perdió capacidad de discriminar; y se usa el error
del lote anterior como estimación del actual.

**¿Por qué los tests pasan si los monitores fallan?**
Son cosas distintas. Los tests verifican que el *detector* es confiable —que
da verde con datos limpios y rojo con datos derivados—; por eso todos pasan.
Los monitores son la *puerta* que falla en rojo cuando llega un lote derivado.
Un monitor que se cae solo no se puede distinguir de un monitor roto, así que
primero se prueba el detector y después se lo usa como puerta.

### Sobre el TCO

**¿Por qué el tipo de cambio oficial no es una variable del modelo?**
Porque antes del 29 de junio de 2026 fue una constante (6,96 Bs desde 2011)
durante toda la ventana de entrenamiento, y después existen solo 24 días de
serie variable. Una constante no aporta información y 24 observaciones no
alcanzan. Su papel es documental: fecha y cuantifica el cambio de régimen que
sostiene el análisis de deriva.
