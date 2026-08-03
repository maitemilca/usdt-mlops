# Comparación entre las dos versiones

Documento interno del equipo.
`usdt-mlops` (versión inicial) frente a `version-elmar` (versión actual).

La versión inicial se ejecutó completa en una máquina con Docker y Kubernetes.
Al hacerlo aparecieron un problema de fondo en los datos y tres errores que
solo se ven al ejecutar, y eso llevó a cambiar tres decisiones de diseño.

Esto no es una lista de correcciones: es el registro de **qué cambió y por
qué**, con la evidencia detrás. Importa porque la defensa es individual y
sobre cualquier parte del proyecto: los dos tenemos que poder sostener estas
decisiones, no solo conocerlas.

---

## 1. Lo que se conservó

La arquitectura de la versión actual es en buena parte la de la versión
inicial:

- **La estructura del proyecto** — la separación `config.py` / `features.py` /
  `train.py`, con las constantes compartidas en un solo lugar.
- **El módulo de variables compartido** entre entrenamiento y servicio, para
  evitar el desfase entre uno y otro.
- **Model Registry con alias** en vez de stages, y carga por
  `models:/nombre@alias` en lugar de un archivo suelto.
- **El control de data drift como reparto aleatorio.** Es la mejor idea de la
  versión inicial. Se había probado usar `X_test` como caso verde y marcaba
  deriva igual, porque en una serie cambiaria el tramo posterior ya trae un
  cambio de nivel. La conclusión —que el verde tiene que ser un reparto
  aleatorio— es correcta y se mantuvo sin cambios.
- **El TCO del BCB como segunda fuente.** Que la flexibilización del 29 de
  junio quedara fuera de la ventana de entrenamiento es lo que le da sustancia
  a toda la Fase 6.
- **NodePort en vez de `port-forward`**, y devolver `served_by_pod` como
  evidencia de balanceo.
- **La interfaz Streamlit como cliente HTTP puro.**
- **KS + PSI** como pruebas de deriva.

### Cuánto se reutilizó, medido

| Concepto | Medición |
|---|---|
| Total de Python en la versión actual | 2.273 líneas |
| Reutilizado literalmente (`parse_tco.py`) | 89 líneas (~4%) |
| `TCO_bcb_crudo.csv` | idéntico |
| `tco_oficial_diario.csv` | regenerado con `parse_tco.py`, **sale byte por byte idéntico** |

**Cómo leer ese 4%.** Medido en líneas de código el aporte inicial parece
marginal, y esa lectura es equivocada. La separación de módulos, el Registry
con alias, el control aleatorio del drift, el NodePort, la interfaz sin lógica
de modelo: son decisiones de diseño que se tomaron en la versión inicial y que
la actual mantiene. Reescribir el código para pasar de regresión a
clasificación no cambia de quién es la arquitectura.

---

## 2. Los tres cambios de fondo

| | Versión inicial | Versión actual | Motivo |
|---|---|---|---|
| Frecuencia | Horaria | **Diaria** | El 95% de los datos horarios era relleno |
| Objetivo | Regresión (valor) | **Clasificación (dirección)** | Ningún modelo de regresión le gana al baseline |
| Contenedor | Reentrena en el build | **Copia el store y reescribe rutas** | Reentrenar genera un `run_id` nuevo y rompe la trazabilidad |

### Cambio 1 · Frecuencia horaria → diaria

El CSV de entrenamiento tiene **556 observaciones reales en 466 días** (1,19
por día). Remuestrearlas a frecuencia horaria produce 11.193 filas de las
cuales solo 545 son genuinas.

```
HORARIA (inicial)                  DIARIA (actual)
  filas de la rejilla   11.193       filas de la rejilla    700
  con cotización real      545       con cotización real    497
  proporción real         4,9%       proporción real         71%   (99% en 2026)
```

Con el 95% de las filas siendo copias del valor anterior, el modelo aprende
que el precio de la próxima hora es igual al de esta. De ahí sale el R² de
0,998856. La documentación original lo delata sin querer: *"Naive quedó a solo
~0,001 Bs de Ridge"* — esa distancia mínima no dice que Ridge sea bueno, dice
que el problema es trivial porque los datos son mayormente sintéticos.

El riesgo en la defensa era una pregunta de una línea: *¿cuántas observaciones
reales tienen por hora?*

Además se excluyen del entrenamiento las filas cuya **etiqueta** saldría de un
día rellenado: si mañana no tuvo cotización, su precio es copia del de hoy y
"subió" daría 0 por construcción. Filtrando, el balance pasa de 72/28 a 42/58.

### Cambio 2 · Regresión → clasificación de dirección

Es el cambio más grande y el que rompe la continuidad con la Actividad 5.
Antes de cambiarlo se intentó salvar la regresión por todos los caminos:

| Variante probada | Resultado |
|---|---|
| Nivel de precio, horizontes de 1 a 30 días | Naive gana en los **9** horizontes |
| Retornos en vez de niveles | Naive gana (Ridge mejora, queda a −5%) |
| Solo días con cotización real | Naive gana |
| Walk-forward, 5 particiones, 2 ventanas | Naive gana en los **10** folds |
| Promedio de los próximos 7 días | Naive gana (−15%) |

No es un defecto de implementación: a frecuencia diaria un tipo de cambio se
comporta como un paseo aleatorio, y que el baseline sea imbatible en nivel es
un resultado clásico en econometría cambiaria (Meese y Rogoff, 1983). En la
versión horaria quedaba tapado porque el relleno hacía indistinguibles a Naive
y Ridge.

El problema práctico: desplegar un modelo de regresión significaba servir algo
peor que una línea de código.

Prediciendo el **signo** del movimiento sí hay señal:

| | walk-forward (selección) | test cronológico |
|---|---|---|
| baseline de clase mayoritaria | 0,5000 | 0,5000 |
| **modelo desplegado** (XGBoost) | **0,5860** | **0,6410** · AUC 0,621 |

Consecuencias: las variables pasaron de niveles a **retornos** (un modelo
entrenado con precios de 9-10 Bs extrapola mal cuando el TC llega a 12);
desaparece el problema de `dayofyear`, que había que excluir a mano del
veredicto; y la métrica principal pasa a ser exactitud balanceada por
validación walk-forward.

**Cuántos modelos se comparan.** No cambió el enfoque: en las dos versiones se
comparan varios y se despliega uno.

| | Inicial | Actual |
|---|---|---|
| Corridas totales | 8 | 10 |
| Familias reales | 2 (Ridge, XGBoost) | 3 (Logística, Random Forest, XGBoost) |
| Criterio de selección | Mejor R² **en el test** | Walk-forward, test intacto |
| Modelos desplegados | 1 | 1 |

El cambio de criterio es defendible por sí solo: elegir por la métrica del
test lo invalida como evaluación independiente. Se nota en el resultado —
`bosque_cfg3` es mejor en el test (0,705 contra 0,641) y aun así no se
desplegó.

### Cambio 3 · El contenedor ya no reentrena

El `Dockerfile` original corría `train.py` durante el build, con un
razonamiento correcto: MLflow guarda rutas absolutas y copiar el store de otra
máquina no funcionaría.

El problema es que reentrenar genera un **`run_id` nuevo**, distinto del que se
muestra en `mlflow ui` durante la defensa. El propio README lo reconocía. Pero
eso es justo lo que pide el punto 3.3.2: trazabilidad entre el modelo que
sirve y el experimento que lo produjo. Un examinador puede pedir el `run_id`
al servicio y no encontrarlo en MLflow.

Se comprobó que el store **sí es portable**: las rutas absolutas viven en
cuatro columnas del sqlite, y `src/portar_store.py` las reescribe durante el
build. Verificado: el `run_id` `98f86de4...` es idéntico en el `mlflow ui`
local, en el contenedor y en los pods, y la predicción sale igual bit a bit.

---

## 3. Errores encontrados al ejecutar

La versión inicial se escribió en un entorno sin Docker ni Kubernetes —está
dicho en sus notas—, así que las Fases 2, 3 y el extra nunca se ejecutaron. Al
correrlas aparecieron tres fallos; los dos primeros son de la lógica nueva.

| Error | Causa | Corrección |
|---|---|---|
| El lote posterior a la flexibilización quedaba en 2 filas | Cargar la serie ya recortada hace que las medias móviles consuman el lote | Construir las variables sobre la serie completa y recortar después. Pasó a 32 filas |
| El control sintético de concept drift no disparaba | No era un bug: con la mitad de las etiquetas invertidas el rendimiento real *es* el del azar | Barrido de intensidad (0-100%). Con inversión total: 0,359, dispara |
| `CreateContainerConfigError`: los 3 pods no arrancaban | El `Dockerfile` declaraba el usuario por nombre y el manifiesto pedía `runAsNonRoot`; el kubelet no puede resolver un nombre a UID | `USER 10001` y `runAsUser: 10001` |

---

## 4. Otros ajustes

- **PSI sobre variables discretas.** La versión heredada del demo reparte en
  deciles, lo que sobre `dia_semana` produce intervalos vacíos o repetidos.
  Ahora se calcula sobre frecuencias de categoría.
- **Los monitores fallan de verdad.** Antes imprimían el veredicto pero
  terminaban siempre en código 0. Ahora salen 0 (verde) o 1 (rojo), como pide
  la consigna. Aparte hay 12 pruebas `pytest` que verifican el detector.
- **Scripts en bash** en vez de PowerShell.
- **Kubernetes**: se agregó `startupProbe` (sin ella la `livenessProbe` puede
  matar el pod durante un arranque lento) y los límites bajaron de 512Mi a
  256Mi.
- **`@app.on_event("startup")`** está deprecado; se usa `lifespan`.
- **Las dos versiones del registro tienen una razón.** La v2 no se entrena para
  cumplir el requisito: aparece como respuesta al concept drift detectado, y se
  registra **sin alias**, porque promover a producción es una decisión aparte.

---

## 5. Qué hay que rehacer

| Material | Estado |
|---|---|
| `FASE6_DRIFT.md` | **Rehacer** — todos los números cambian |
| `docs/arquitectura.png` | **Actualizar** — dibuja el flujo viejo |
| `DEPLOYED_MODEL.md` | Reemplazado por `MODELO_DESPLEGADO.md` |
| Resultados de `train.py` (R²=0,998856) | Ya no aplican |
| `results/*.png` | Regenerados en `resultados/` |
| `ARQUITECTURA.md` | Reescrito, misma estructura |
| Estructura, `config.py`, Model Registry | Sin cambios |
| `parse_tco.py`, `DATA_SOURCES.md` | Conservados |
| Enfoque de la UI | Conservado, reescrito para clasificación |

Cambió también el criterio de reentrenamiento:

| | Inicial | Actual |
|---|---|---|
| Métrica | MAE semanal | Exactitud balanceada mensual |
| Umbral | MAE > 1,5× la referencia | < 0,50 (el azar) |
| Sostenido | 2 semanas | 2 meses |
| Se dispara en | 2026-08-02 | 2026-02 |

El umbral de 0,50 es defendible por sí solo: es el valor exacto del azar en
esa métrica, no un número elegido a dedo.

Y el hallazgo original —*"data drift no implicó concept drift sostenido"*—
**cambia de signo**. Con el modelo de dirección hay degradación clara, y el
peor mes es junio de 2026, el de la flexibilización:

```
2025-12  0.611
2026-01  0.478  ─┐
2026-02  0.471  ─┴─►  alarma: 2 meses seguidos bajo el azar
2026-03  0.431
2026-04  0.600
2026-05  0.546
2026-06  0.277  ◄──  mes de la flexibilización cambiaria
2026-07  0.583
```

---

## 6. Estado de verificación

| Fase | Inicial | Actual |
|---|---|---|
| 1 · MLflow | Ejecutada | Ejecutada — 10 corridas, v1 con alias |
| 2 · Docker | Escrita, no ejecutada | **Ejecutada** — build y contenedor probados |
| 3 · Kubernetes | Escrita, no ejecutada | **Ejecutada** — 3 pods, 4 demostraciones |
| 6 · Drift | Ejecutada | Ejecutada — más 12 pruebas pytest |
| Extra · UI | Escrita, no ejecutada | Escrita, pendiente de probar en vivo |

No es un reproche: el entorno donde se escribió la versión inicial no tenía
Docker ni Kubernetes. Pero es la razón por la que los tres errores de la
sección 3 no podían haber aparecido antes.

El reparto de trabajo y el plan para integrar todo al repositorio están en
`REPARTO_TRABAJO.md`.
