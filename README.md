# Predictor de dirección del tipo de cambio USDT/BOB

Proyecto final — Módulo MLOps y puesta en producción
Maestría en Ciencia de Datos e IA, UAGRM

Predice si el dólar paralelo en Bolivia **sube o no sube mañana**, y lleva ese
modelo desde el experimento hasta un despliegue con réplicas y monitoreo de
deriva.

---

## Por dónde empezar

| Si querés... | Abrí |
|---|---|
| **Ejecutar el proyecto de cero** | **[`GUIA_PASO_A_PASO.md`](GUIA_PASO_A_PASO.md)** |
| Entender las decisiones de diseño | [`ARQUITECTURA.md`](ARQUITECTURA.md) |
| Ver qué cambió respecto a la versión inicial | [`COMPARACION_VERSIONES.md`](COMPARACION_VERSIONES.md) |
| Saber qué versión está desplegada | [`MODELO_DESPLEGADO.md`](MODELO_DESPLEGADO.md) |
| Conocer los datos | [`data/DATA_SOURCES.md`](data/DATA_SOURCES.md) |
| Ver el reparto entre integrantes | [`REPARTO_TRABAJO.md`](REPARTO_TRABAJO.md) |

La guía paso a paso está pensada para seguirse de arriba abajo sin saltarse
nada, e indica en qué momento tomar cada captura para el informe.

---

## Arranque rápido

```bash
./scripts/01_preparar_entorno.sh      # entorno virtual + dependencias
./scripts/02_entrenar.sh              # Fase 1: 10 corridas en MLflow, registra v1
./scripts/03_pruebas.sh               # 12 pruebas del detector de deriva
./scripts/04_monitores_deriva.sh      # Fase 6: data drift + concept drift

docker build -t tc-usdt-api:1.0 .     # Fase 2
kubectl apply -f k8s/                 # Fase 3
./scripts/05_pruebas_kubernetes.sh    # las 4 demostraciones exigidas

streamlit run ui/app_streamlit.py     # extra: interfaz contra el clúster
```

---

## Estructura

```
version-elmar/
├── GUIA_PASO_A_PASO.md      guía completa de ejecución
├── ARQUITECTURA.md          decisiones de diseño y justificaciones
├── REPARTO_TRABAJO.md       tabla de integrantes
├── MODELO_DESPLEGADO.md     generado por train.py: versión y run desplegados
├── Dockerfile               imagen del servicio
├── requirements.txt         12 dependencias fijadas por versión exacta
│
├── data/                    serie P2P + TCO oficial del BCB
├── src/
│   ├── config.py            constantes compartidas (semilla, fechas, nombres)
│   ├── features.py          serie diaria y variables estacionarias
│   ├── train.py             Fase 1: entrenamiento, MLflow, registro
│   ├── app.py               Fase 2: servicio FastAPI
│   ├── portar_store.py      hace portable el store de MLflow al contenedor
│   ├── drift_common.py      pruebas KS y PSI con sus umbrales
│   ├── monitor_data_drift.py      Fase 6.1 (puerta: sale 0 o 1)
│   ├── monitor_concept_drift.py   Fase 6.2 (puerta: sale 0 o 1)
│   └── parse_tco.py         procesa el reporte crudo del BCB
├── tests/                   12 pruebas del detector de deriva
├── scripts/                 flujo numerado 01 a 06
├── k8s/                     Deployment (3 réplicas) + Service NodePort
├── ui/                      interfaz Streamlit (puntos extra)
├── resultados/              gráficos generados por los monitores
└── evidencia/               salidas para adjuntar al informe
```

---

## Resumen de resultados

**Modelo desplegado:** `tc-usdt-bob-direccion` v1, alias `champion`
(XGBoost, n_estimators=300, max_depth=3, learning_rate=0,05)

| | walk-forward (selección) | test cronológico |
|---|---|---|
| baseline clase mayoritaria | 0,5000 | 0,5000 |
| modelo desplegado | 0,5860 | 0,6410 balanceada · AUC 0,621 |

**Data drift:** control en verde; los tres lotes derivados en rojo.
**Concept drift:** alarma en 2026-02; el peor mes es 2026-06, el de la
flexibilización cambiaria del BCB.

---

## Dos cosas que conviene saber antes de leer el código

**El modelo predice dirección, no valor.** Se probó predecir el valor exacto
con regresión en 9 horizontes, con niveles y con retornos, y con validación
walk-forward: el baseline ingenuo ganó en todos los casos. A frecuencia diaria
un tipo de cambio es un paseo aleatorio (Meese-Rogoff). El signo del
movimiento sí es aprendible. El detalle está en `ARQUITECTURA.md`, sección 3.1.

**El contenedor no reentrena.** Copia el store de MLflow y le reescribe las
rutas, para que el modelo que responde en Kubernetes sea el mismo `run_id` que
se ve en `mlflow ui`. Reentrenar en el build habría sido más simple, pero
rompe la trazabilidad que pide el enunciado. Ver `ARQUITECTURA.md`, sección 4.
