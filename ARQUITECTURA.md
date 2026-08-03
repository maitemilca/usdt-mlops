# Documento de arquitectura

Proyecto final — Módulo MLOps y puesta en producción
Maestría en Ciencia de Datos e IA, UAGRM

---

## 1. Qué resuelve el sistema

Predice si el tipo de cambio del dólar paralelo en Bolivia (USDT/BOB, mercado
P2P de Binance) **sube o no sube mañana**. Es clasificación binaria.

La pregunta operativa que responde es la que se hace cualquiera que maneje
dólares en Bolivia: *¿conviene comprar hoy o esperar?* No intenta acertar el
valor exacto, y hay una razón medida detrás de esa decisión (sección 3).

---

## 2. Vista general

```
                      data/usdtbol_full.csv
                    (2.937 cotizaciones P2P)
                               |
                    src/features.py  (serie diaria + variables estacionarias)
                               |
        +----------------------+----------------------+
        |                                             |
        v                                             v
  FASE 1: src/train.py                        FASE 6: monitores
  10 corridas en MLflow                       monitor_data_drift.py     (6.1)
  seleccion walk-forward                      monitor_concept_drift.py  (6.2)
        |                                             |
        v                                             |
  MLflow Model Registry                               |
  tc-usdt-bob-direccion                               |
  v1 --alias--> @champion                             |
        |                                             |
        v                                             |
  FASE 2: Dockerfile                                  |
  copia el store + portar_store.py                    |
  imagen tc-usdt-api:1.0                              |
        |                                             |
        v                                             |
  FASE 3: Kubernetes                                  |
  Deployment (3 replicas) + Service NodePort:30080    |
        |                                             |
        +----------------> EXTRA: ui/app_streamlit.py |
                           (cliente HTTP puro)        |
                                                      |
        <---- reentrenar (v2) <--- alarma sostenida <-+
```

La rama de monitoreo corre en paralelo y **realimenta** la Fase 1: cuando el
criterio de reentrenamiento se dispara, se entrena una versión nueva y se
decide si mover el alias.

---

## 3. Fase 1 — Modelo y trazabilidad

### 3.1 Por qué clasificación y no regresión

Se probó primero predecir el valor exacto del tipo de cambio, que era lo
natural viniendo de la Actividad 5. **Ningún modelo de regresión le ganó al
baseline ingenuo** ("mañana vale lo mismo que hoy):

| Variante probada | Resultado |
|---|---|
| Nivel de precio, horizontes de 1 a 30 días | Naive gana en los 9 horizontes |
| Retornos en vez de niveles | Naive gana (Ridge se queda a −5%) |
| Solo días con cotización real | Naive gana |
| Walk-forward, 5 particiones, 2 ventanas | Naive gana en las 10 |
| Promedio de los próximos 7 días | Naive gana (−15%) |

No es un defecto de implementación: a frecuencia diaria un tipo de cambio se
comporta como un paseo aleatorio, y que el baseline sea imbatible en nivel es
un resultado clásico en econometría cambiaria (Meese y Rogoff, 1983).

Predecir el **signo** del movimiento sí es aprendible, porque hay
autocorrelación en la dirección y en la volatilidad. Con ese objetivo, el
modelo sí supera a su baseline.

### 3.2 Datos y variables

- Frecuencia diaria; 259 días utilizables hasta la fecha de corte.
- División cronológica 80/20: 207 entrenamiento / 52 prueba. Nunca aleatoria.
- Semilla fija 42, declarada en `src/config.py`.
- Balance de clases: 41,7% de días al alza.
- **Solo se usan filas cuya etiqueta viene de una cotización real.** Si el día
  siguiente no tuvo cotización, su precio es una copia del anterior y "sube"
  daría 0 por construcción. Filtrando, el balance pasa de 72/28 a 42/58.

Ocho variables, todas **estacionarias**:

| Variable | Tipo | Prueba de deriva |
|---|---|---|
| `ret_1d`, `ret_3d`, `ret_7d` | retornos | KS |
| `vol_7d` | volatilidad 7 días | KS |
| `desv_media_7d`, `desv_media_30d` | desviación relativa a la media móvil | KS |
| `dia_semana` | discreta (7 categorías) | PSI |
| `es_fin_semana` | discreta (binaria) | PSI |

Se usan retornos y no niveles porque un modelo entrenado con precios de 9-10
Bs no sabe qué hacer cuando el tipo de cambio llega a 12: estaría
extrapolando. Un movimiento del 1% es el mismo dato tenga el TC el valor que
tenga.

### 3.3 Corridas y selección

10 corridas en el experimento `tc_usdt_bolivia_diario`, todas comparables
porque comparten división, variables y semilla:

- 1 baseline de clase mayoritaria
- 3 regresiones logísticas (C = 0,05 / 1 / 10)
- 3 Random Forest
- 3 XGBoost

**Métrica principal: exactitud balanceada por validación walk-forward.**

Dos decisiones que conviene poder justificar:

- *Balanceada y no exactitud simple*: con clases 42/58, un modelo que dijera
  siempre "no sube" sacaría 58% de exactitud sin haber aprendido nada. En
  exactitud balanceada saca 0,50, que es exactamente el azar.
- *Walk-forward y no el test cronológico*: el test son 52 días; tres aciertos
  de diferencia mueven la métrica 6 puntos. Elegir por ese único número es
  elegir por ruido. La validación walk-forward promedia 5 particiones sobre el
  entrenamiento, y **el test queda intacto** como evaluación independiente.

Esto último tiene una consecuencia visible en los resultados: `bosque_cfg3`
luce mejor en el test (0,705) que el modelo elegido, pero se eligió
`xgboost_cfg2` porque ganó en walk-forward. Seleccionar mirando el test
invalidaría el test.

### 3.4 Resultados

| | walk-forward (selección) | test cronológico (independiente) |
|---|---|---|
| baseline clase mayoritaria | 0,5000 | 0,5000 |
| **xgboost_cfg2 (desplegado)** | **0,5860** | **0,6410** balanceada · 0,7308 exactitud · AUC 0,621 |

Las 9 configuraciones reales superan al baseline en walk-forward.

### 3.5 Trazabilidad — requisito 3.3.2

| Campo | Valor |
|---|---|
| Modelo registrado | `tc-usdt-bob-direccion` |
| Versión desplegada | **1** |
| Alias | `champion` |
| Corrida de origen | `xgboost_cfg2` |
| Hiperparámetros | n_estimators=300, max_depth=3, learning_rate=0,05 |
| Experimento | `tc_usdt_bolivia_diario` |

El `run_id` exacto está en `MODELO_DESPLEGADO.md`, generado automáticamente
por `train.py`. El servicio consume el modelo por
`models:/tc-usdt-bob-direccion@champion`, nunca por una ruta de archivo.

**Versión 2:** se registra en el paso 6 del flujo, como respuesta al concept
drift detectado. Queda registrada sin alias: promover una versión a producción
es una decisión explícita, no un efecto secundario de entrenar.

---

## 4. Fase 2 — Contenerización

`Dockerfile` propio, `python:3.12-slim`, 12 dependencias fijadas por versión
exacta en `requirements.txt` (incluida `mlflow==3.15.0`).

**La decisión de diseño que diferencia esta implementación:** la imagen
**copia** el store de MLflow entrenado en la máquina de desarrollo y le
reescribe las rutas con `src/portar_store.py`, en vez de reentrenar durante el
build.

El camino fácil habría sido correr `train.py` dentro del build. Pero eso
genera un `run_id` nuevo, distinto del que se muestra en la interfaz de MLflow
durante la defensa: se rompe justamente la trazabilidad que pide el enunciado.
Copiando el store, el modelo que responde en Kubernetes es **literalmente el
mismo run** que se ve en `mlflow ui`, con el mismo identificador.

El obstáculo técnico es que MLflow guarda rutas absolutas de artefactos en su
base de datos, y las de la máquina de desarrollo no existen dentro del
contenedor. Son cuatro columnas en el sqlite; `portar_store.py` las reescribe
de forma determinista durante el build.

Otras decisiones: usuario sin privilegios (uid 10001), `HEALTHCHECK` a nivel
de imagen, dependencias en su propia capa para aprovechar la caché.

Endpoints: `/health`, `/model-info`, `/predict`.

---

## 5. Fase 3 — Kubernetes

- `Deployment` con 3 réplicas y actualización gradual (nunca baja de 2 pods).
- `Service` de tipo **NodePort** en el 30080.
- Tres sondas: `startupProbe` (hasta 60 s para cargar el modelo),
  `readinessProbe` (un pod sin modelo no recibe tráfico) y `livenessProbe`
  (reinicia un proceso colgado).
- Límites de 256Mi por pod, ajustados a una máquina de 13 GB con Docker
  Desktop corriendo: 5 réplicas ocupan 1,25 GB como máximo.

**Por qué NodePort y no `port-forward`:** `port-forward` abre un túnel contra
un único pod y lo mantiene toda la sesión. Con eso, cien peticiones seguidas
las contesta siempre el mismo pod y sería imposible demostrar el balanceo.
NodePort pasa por el kube-proxy real del Service.

Cada respuesta incluye `served_by_pod` (el hostname del contenedor, que en
Kubernetes es el nombre del pod): es la evidencia directa del balanceo.

Las cuatro demostraciones están automatizadas en
`scripts/05_pruebas_kubernetes.sh`, que deja el registro en
`evidencia/evidencia_kubernetes.txt`.

---

## 6. Fase 6 — Monitoreo de deriva

### 6.1 Data drift

KS para las 6 variables continuas, PSI para las 2 discretas. La justificación
completa de por qué cada prueba, y de dónde salen los umbrales (α = 0,05 para
KS; 0,10 / 0,25 para PSI), está en el encabezado de `src/drift_common.py`.

Un detalle de implementación que suele estar mal resuelto: el PSI habitual
reparte los datos en deciles, lo que sobre una variable discreta produce
intervalos vacíos o repetidos. Aquí `calcular_psi_discreto` trabaja sobre las
categorías observadas.

Resultados (baseline = X_train de la versión 1, 207 filas):

| Escenario | n | Veredicto | Código de salida |
|---|---|---|---|
| Control (mitad aleatoria del baseline) | 104 | **VERDE** | 0 |
| Holdout previo a la flexibilización | 197 | **ROJO** | 1 |
| Holdout posterior a la flexibilización | 32 | **ROJO** | 1 |
| Deriva inyectada a propósito | 207 | **ROJO** | 1 |

El control es un reparto **aleatorio** del baseline y no el test cronológico,
a propósito: el test es un tramo posterior en el tiempo y en una serie
cambiaria eso ya trae un cambio de nivel, así que marcaría deriva aunque no
hubiera ningún problema.

### 6.2 Concept drift

Se mide la exactitud balanceada del modelo desplegado sobre lotes mensuales
del holdout real:

| Mes | n | Exactitud balanceada |
|---|---|---|
| 2025-12 | 21 | 0,611 |
| 2026-01 | 31 | 0,478 |
| 2026-02 | 27 | 0,471 |
| 2026-03 | 30 | 0,431 |
| 2026-04 | 30 | 0,600 |
| 2026-05 | 31 | 0,546 |
| **2026-06** | 29 | **0,277** ← mes de la flexibilización |
| 2026-07 | 30 | 0,583 |

**Criterio de reentrenamiento:** alarma si la exactitud balanceada cae por
debajo de **0,50 durante 2 meses seguidos**.

- *Por qué 0,50*: es el valor exacto del azar en esta métrica. Por debajo, el
  modelo no solo dejó de aportar: induce decisiones peores que tirar una
  moneda. Es un umbral con significado propio, no elegido a dedo.
- *Por qué 2 meses*: cada lote tiene ~25 días con etiqueta; con esa cantidad
  un solo mes se mueve varios puntos por azar.

**Con los datos reales la alarma se habría disparado en 2026-02**, y el peor
mes es junio de 2026 — el de la flexibilización cambiaria.

**Control sintético:** se invierten las etiquetas de una fracción creciente
del test, dejando las entradas intactas (concept drift puro).

| Invertido | Exactitud balanceada | ¿Dispara? |
|---|---|---|
| 0% | 0,641 | no |
| 25% | 0,577 | no |
| 50% | 0,529 | no |
| 75% | 0,520 | no |
| 100% | **0,359** | **sí** |

Que con el 50% no dispare no es un fallo: con la mitad de las etiquetas dadas
vuelta el modelo acierta en un tramo y falla en el otro, y su rendimiento real
*es* el del azar. El monitor está reportando la verdad. Lo que muestra el
barrido es que una inversión parcial es el caso más difícil de detectar.

### 6.3 Retraso de etiqueta

En este modelo el retraso es corto: la etiqueta de hoy se conoce mañana. Es
mucho más cómodo que un modelo de riesgo crediticio, donde confirmar un
incumplimiento toma meses. Pero con lotes mensuales, un mes malo recién se
confirma cuando ya terminó.

Mientras tanto: el monitor de data drift funciona **sin etiquetas** y es la
alerta temprana; se vigila la distribución de las probabilidades devueltas
(si el modelo empieza a responder siempre lo mismo o se concentra en 0,5,
perdió capacidad de discriminar); y se usa el error del lote anterior como
estimación del actual.

---

## 7. Pruebas automatizadas

`tests/test_deteccion_deriva.py` — 12 pruebas, todas en verde.

La separación es intencional: **las pruebas verifican que el detector es
confiable**; **los monitores son la puerta** que falla en rojo. Un monitor que
se cae solo no se puede distinguir de un monitor roto, así que primero se
prueba el detector y después se lo usa como puerta.

---

## 8. Mapa consigna → entregable

| Requisito | Dónde está |
|---|---|
| Script reproducible, semilla, división documentada | `src/train.py`, `src/config.py` |
| ≥5 corridas con distintos hiperparámetros | 10 corridas en `tc_usdt_bolivia_diario` |
| Registro y versionado, >1 versión | `tc-usdt-bob-direccion` v1 y v2 |
| Versión desplegada marcada explícitamente | alias `@champion`, `MODELO_DESPLEGADO.md` |
| Dockerfile propio, dependencias fijadas | `Dockerfile`, `requirements.txt` |
| 3+ réplicas, balanceo, autorreparación, escalado | `k8s/`, `evidencia/evidencia_kubernetes.txt` |
| Data drift: prueba por tipo, umbral, verde/rojo | `src/monitor_data_drift.py`, `src/drift_common.py` |
| Concept drift: degradación, criterio, label delay | `src/monitor_concept_drift.py` |
| Extra: UI contra la API en Kubernetes | `ui/app_streamlit.py` |
