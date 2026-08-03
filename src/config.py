"""
Configuracion central del proyecto.

Todo lo que sea una constante compartida vive aqui: nombres de experimento y
de modelo registrado, semilla, fechas de corte y rutas. La razon es que el
entrenamiento (train.py), el servicio de inferencia (app.py) y los monitores
de deriva (monitor_*.py) tienen que coincidir exactamente en estos valores.
Si el servicio buscara un nombre de modelo distinto al que registra el
entrenamiento, la trazabilidad que pide la consigna se rompe en silencio.

Las rutas se derivan de la ubicacion de este archivo, no del directorio desde
el que ejecutas. Eso hace que funcione igual en tu maquina (donde la raiz es
.../version-elmar) y dentro del contenedor (donde la raiz es /app).
"""
from __future__ import annotations

from pathlib import Path

# --- Rutas ---------------------------------------------------------------
# config.py vive en <raiz>/src/, asi que la raiz es el padre de su carpeta.
RAIZ = Path(__file__).resolve().parent.parent

DIR_DATOS = RAIZ / "data"
DIR_STORE = RAIZ / "mlflow_store"       # base de datos + artefactos de MLflow
DIR_RESULTADOS = RAIZ / "resultados"    # graficos que generan los monitores
DIR_EVIDENCIA = RAIZ / "evidencia"      # salidas para adjuntar al informe

CSV_COMPLETO = DIR_DATOS / "usdtbol_full.csv"
CSV_TCO_DIARIO = DIR_DATOS / "tco_oficial_diario.csv"

# --- MLflow --------------------------------------------------------------
# Backend sqlite (no el store de archivos por defecto) porque el Model
# Registry con alias necesita una base de datos relacional.
#
# .as_uri() y no .as_posix() para ARTIFACT_ROOT: MLflow resuelve el
# repositorio de artefactos mirando el ESQUEMA de la URI (file, s3, etc.).
# .as_posix()  por .as_uri para que funciones en windows y linux dado -- sin esquema -- y MLflow
# interpreta "E" como si fuera el esquema (como en "e://algo"), que no esta
# registrado, y falla con "Could not find a registered artifact repository".
# .as_uri() arma la URI completa ("file:///E:/MIAV1E3/") con el esquema
# "file" explicito, que si esta registrado, en Windows y en Linux por igual.
TRACKING_URI = f"sqlite:///{(DIR_STORE / 'mlflow.db').as_posix()}"
ARTIFACT_ROOT = (DIR_STORE / "mlartifacts").as_uri()

MLFLOW_EXPERIMENT_NAME = "tc_usdt_bolivia_diario"

# Nombre estable en el Model Registry. No cambia nunca: lo que cambia son las
# versiones que se registran bajo el.
REGISTERED_MODEL_NAME = "tc-usdt-bob-direccion"

# Alias que marca cual de las versiones registradas es la que esta desplegada.
# Los "stages" (Staging/Production) estan deprecados desde MLflow 2.9.
DEPLOYMENT_ALIAS = "champion"

# --- Reproducibilidad ----------------------------------------------------
RANDOM_SEED = 42
TRAIN_PROP = 0.8          # division cronologica 80/20 (NO aleatoria)

# --- Fechas del escenario ------------------------------------------------
# Corte que define la version 1 del modelo: simula "el modelo que pusimos en
# produccion en diciembre de 2025". Todo lo posterior queda como holdout real
# para las pruebas de deriva. Cambiar esta fecha y volver a entrenar es todo
# lo que hace falta para incorporar datos nuevos.
FECHA_CORTE_V1 = "2025-12-11"

# 29-jun-2026: el BCB abandona el tipo de cambio fijo de 6,96 Bs vigente desde
# 2011 y pasa a un regimen flexible (Resolucion de Directorio BCB 88/2026).
# Es el cambio de regimen que usamos como escenario de deriva real.
FECHA_FLEXIBILIZACION = "2026-06-29"
TCO_FIJO_HISTORICO = 6.96

# --- Metrica principal ---------------------------------------------------
# Exactitud balanceada: el promedio de la tasa de acierto en cada clase.
#
# Por que esta y no la exactitud a secas: las clases estan desbalanceadas
# (42% de dias al alza). Un modelo que dijera siempre "no sube" sacaria 58% de
# exactitud sin haber aprendido nada; en exactitud balanceada sacaria 0,50,
# que es exactamente lo que vale el azar. Ademas es robusta al balance, y eso
# importa en el monitoreo de deriva: cada lote tiene una proporcion distinta
# de dias al alza, y la exactitud simple subiria o bajaria solo por eso,
# confundiendo un cambio de balance con una degradacion real del modelo.
#
# Por que no el ROC AUC, que tambien es robusto: el AUC mide si el modelo
# ORDENA bien los dias por probabilidad, pero el servicio despliega una
# DECISION (sube / no sube) en el umbral 0,5. Se dio el caso concreto de un
# modelo con AUC alto (0,755) y exactitud balanceada por debajo del azar
# (0,474): ordenaba bien pero decidia mal. El AUC se sigue registrando como
# metrica secundaria en todos los runs.
METRICA_PRINCIPAL = "exactitud_balanceada_cv"
METRICA_AZAR = 0.5

# Numero de particiones de la validacion walk-forward (ver train.py).
N_PARTICIONES_CV = 5


def configurar_mlflow() -> None:
    """
    Apunta MLflow al store local del proyecto.

    Hay que llamarla antes de cualquier operacion de MLflow, en todos los
    scripts. Crea el directorio del store si no existe, para que la primera
    ejecucion en una maquina limpia no falle.
    """
    import mlflow

    DIR_STORE.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(TRACKING_URI)