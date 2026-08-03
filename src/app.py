"""
Fase 2 -- Servicio de inferencia (FastAPI).

Responde si el tipo de cambio USDT/BOB sube manana, dado el historial reciente.

El modelo se carga SIEMPRE por referencia al Model Registry
(`models:/{nombre}@{alias}`), nunca desde un archivo .pkl suelto. Esa es la
diferencia entre un servicio trazable y uno que sirve "un modelo que estaba
por ahi": con la referencia al registro, en cualquier momento se puede
preguntar al servicio de que version y de que run salio lo que esta
respondiendo, y contrastarlo con la interfaz de MLflow.

Endpoints:
    GET  /health      estado del servicio y que pod respondio
    GET  /model-info  version, alias y run del modelo que esta sirviendo
    POST /predict     prediccion de direccion para el dia siguiente
"""
from __future__ import annotations

import socket
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import List

import mlflow
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import config as cfg
from features import (
    COLUMNAS_FEATURES,
    COLUMNA_PRECIO,
    MINIMO_DIAS_HISTORIA,
    construir_features,
)

# Dentro de Kubernetes el hostname del contenedor es el nombre del pod. Se
# devuelve en cada respuesta: es la evidencia de balanceo de carga que pide
# la Fase 3 (peticiones sucesivas contestadas por pods distintos).
HOSTNAME = socket.gethostname()

REFERENCIA_MODELO = f"models:/{cfg.REGISTERED_MODEL_NAME}@{cfg.DEPLOYMENT_ALIAS}"

# Estado del proceso. Se llena una sola vez al arrancar: cargar el modelo en
# cada peticion multiplicaria la latencia sin ninguna ventaja.
_estado: dict = {"modelo": None, "version": None, "run_id": None, "error": None}


def cargar_modelo_nativo(referencia: str):
    """
    Carga el modelo en su formato nativo, probando los sabores que registra
    train.py.

    Se usa el modelo nativo y no el envoltorio pyfunc porque pyfunc solo
    expone `predict()`: devolveria la clase (sube / no sube) pero no la
    probabilidad, y la probabilidad es justamente lo util para decidir. Como
    la familia ganadora puede cambiar entre entrenamientos (sklearn o
    XGBoost), se prueban ambos sabores en orden.
    """
    ultimo_error = None
    for sabor in (mlflow.sklearn, mlflow.xgboost):
        try:
            return sabor.load_model(referencia)
        except Exception as exc:  # noqa: BLE001 - se prueba el siguiente sabor
            ultimo_error = exc
    raise RuntimeError(f"Ningun sabor de MLflow pudo cargar {referencia}: {ultimo_error}")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """
    Carga el modelo al arrancar el proceso.

    Si falla, el servicio igual levanta pero /health responde "cargando" y no
    pasa la readinessProbe: Kubernetes no le manda trafico a un pod que no
    puede predecir, en vez de dejarlo devolver errores a los usuarios.
    """
    cfg.configurar_mlflow()
    try:
        cliente = mlflow.MlflowClient()
        version = cliente.get_model_version_by_alias(
            cfg.REGISTERED_MODEL_NAME, cfg.DEPLOYMENT_ALIAS
        )
        _estado["modelo"] = cargar_modelo_nativo(REFERENCIA_MODELO)
        _estado["version"] = version.version
        _estado["run_id"] = version.run_id
        print(f"[arranque] Modelo cargado: {cfg.REGISTERED_MODEL_NAME}"
              f"@{cfg.DEPLOYMENT_ALIAS} (version {version.version}, "
              f"run {version.run_id}) en el pod {HOSTNAME}")
    except Exception as exc:  # noqa: BLE001 - se reporta por /health
        _estado["error"] = str(exc)
        print(f"[arranque] ERROR cargando el modelo: {exc}")

    yield


app = FastAPI(
    title="Predictor de direccion del TC USDT/BOB",
    description="Predice si el tipo de cambio del dolar paralelo en Bolivia sube manana.",
    version="1.0",
    lifespan=ciclo_de_vida,
)


class PuntoPrecio(BaseModel):
    fecha: str = Field(..., description="Fecha en formato ISO, ej. 2026-07-30")
    precio: float = Field(..., gt=0, description="Tipo de cambio USDT/BOB de ese dia")


class PeticionPrediccion(BaseModel):
    historial: List[PuntoPrecio] = Field(
        ...,
        description=(
            f"Serie diaria reciente. Hacen falta al menos {MINIMO_DIAS_HISTORIA} "
            "dias para poder calcular la desviacion contra la media de 30 dias."
        ),
    )


@app.get("/health")
def health():
    """Sonda de salud. La usan readinessProbe y livenessProbe del Deployment."""
    return {
        "estado": "ok" if _estado["modelo"] is not None else "cargando",
        "served_by_pod": HOSTNAME,
        "error": _estado["error"],
    }


@app.get("/model-info")
def model_info():
    """Trazabilidad en vivo: que version y que run esta sirviendo este pod."""
    if _estado["modelo"] is None:
        raise HTTPException(status_code=503, detail=f"Modelo no cargado: {_estado['error']}")
    return {
        "modelo_registrado": cfg.REGISTERED_MODEL_NAME,
        "alias": cfg.DEPLOYMENT_ALIAS,
        "version": _estado["version"],
        "run_id": _estado["run_id"],
        "experimento": cfg.MLFLOW_EXPERIMENT_NAME,
        "variables": COLUMNAS_FEATURES,
        "minimo_dias_historia": MINIMO_DIAS_HISTORIA,
        "served_by_pod": HOSTNAME,
    }


@app.post("/predict")
def predict(peticion: PeticionPrediccion):
    """
    Predice la direccion del tipo de cambio para el dia siguiente.

    Reconstruye la serie diaria a partir del historial recibido y aplica el
    MISMO `construir_features` que uso el entrenamiento. Reimplementar aqui el
    calculo de variables seria la forma mas rapida de introducir un desfase
    silencioso entre entrenamiento y produccion.
    """
    if _estado["modelo"] is None:
        raise HTTPException(status_code=503, detail=f"Modelo no cargado: {_estado['error']}")

    if len(peticion.historial) < MINIMO_DIAS_HISTORIA:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Se necesitan al menos {MINIMO_DIAS_HISTORIA} dias de historial; "
                f"se recibieron {len(peticion.historial)}."
            ),
        )

    df = pd.DataFrame(
        [{"fecha": p.fecha, COLUMNA_PRECIO: p.precio} for p in peticion.historial]
    )
    try:
        df["fecha"] = pd.to_datetime(df["fecha"])
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Fechas invalidas: {exc}") from exc

    # Rejilla diaria continua: los rezagos y las medias moviles necesitan que
    # no falten dias en el calendario, aunque no haya habido cotizacion.
    serie = (
        df.set_index("fecha")[COLUMNA_PRECIO]
        .sort_index()
        .resample("D")
        .mean()
        .ffill()
        .to_frame(name=COLUMNA_PRECIO)
    )
    serie["obs_real"] = True

    caracteristicas = construir_features(serie).dropna(subset=COLUMNAS_FEATURES)
    if caracteristicas.empty:
        raise HTTPException(
            status_code=422,
            detail=("No se pudo construir un vector de variables valido: revise que "
                    "el historial cubra dias consecutivos suficientes."),
        )

    ultima = caracteristicas.iloc[-1:]
    X = ultima[COLUMNAS_FEATURES].astype("float64")

    modelo = _estado["modelo"]
    clase = int(modelo.predict(X)[0])
    probabilidad = float(modelo.predict_proba(X)[0][1])

    ultimo_dia = serie.index[-1]
    return {
        "fecha_referencia": ultimo_dia.date().isoformat(),
        "precio_referencia": float(serie[COLUMNA_PRECIO].iloc[-1]),
        "fecha_predicha": (ultimo_dia + timedelta(days=1)).date().isoformat(),
        "direccion": "SUBE" if clase == 1 else "NO SUBE",
        "clase": clase,
        "probabilidad_sube": probabilidad,
        "model_version": _estado["version"],
        "model_alias": cfg.DEPLOYMENT_ALIAS,
        "run_id": _estado["run_id"],
        "served_by_pod": HOSTNAME,
    }
