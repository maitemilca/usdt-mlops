"""
Fase 1 -- Entrenamiento, seguimiento de experimentos y registro en MLflow.

Problema: dado el historial del tipo de cambio USDT/BOB del mercado P2P
boliviano, predecir si manana SUBE o NO SUBE. Es clasificacion binaria.

Que hace, en orden:
  1. Carga la serie y construye las variables (features.py), filtrando hasta
     la fecha de corte que se le pase.
  2. Divide train/test cronologicamente (80/20, sin mezclar).
  3. Entrena y registra en MLflow cuatro familias, comparables entre si porque
     comparten division, variables y semilla:
        - Clase mayoritaria: predice siempre la clase mas frecuente del train.
          Es la vara minima; un modelo que no le gana no aporta nada.
        - Regresion logistica, 3 valores de C
        - Random Forest, 3 configuraciones
        - XGBoost, 3 configuraciones
     Son 10 corridas en total, muy por encima de las 5 que pide la consigna.
  4. Elige la ganadora por validacion walk-forward sobre el conjunto de
     entrenamiento (nunca mirando el test: seleccionar sobre el conjunto de
     prueba lo invalida como evaluacion independiente).
  5. Registra esa corrida en el Model Registry bajo un nombre estable, y
     opcionalmente le pone el alias de despliegue.
  6. Escribe MODELO_DESPLEGADO.md con el detalle exacto de version y run.

Uso:
    python train.py                              # version 1 (corte de config.py)
    python train.py --hasta 2026-07-31 --nota "reentrenamiento por deriva"
    python train.py --hasta 2026-07-31 --sin-alias   # registra sin desplegar
"""
from __future__ import annotations

import argparse
import platform
from datetime import datetime, timezone

import matplotlib

matplotlib.use("Agg")  # backend sin ventana: necesario para correr sin escritorio
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

import config as cfg
from features import COLUMNA_OBJETIVO, COLUMNAS_FEATURES, division_temporal, preparar

# --- Rejillas de hiperparametros -----------------------------------------
# C es la inversa de la fuerza de regularizacion: C chico regulariza mas.
CONFIGS_LOGISTICA = [{"C": 0.05}, {"C": 1.0}, {"C": 10.0}]

# Arboles poco profundos y hojas grandes: con ~200 filas de entrenamiento, un
# bosque profundo memoriza el ruido del periodo en vez de aprender la senal.
CONFIGS_BOSQUE = [
    {"n_estimators": 200, "max_depth": 3, "min_samples_leaf": 10},
    {"n_estimators": 400, "max_depth": 6, "min_samples_leaf": 5},
    {"n_estimators": 600, "max_depth": 10, "min_samples_leaf": 2},
]

CONFIGS_XGBOOST = [
    {"n_estimators": 150, "max_depth": 2, "learning_rate": 0.05},
    {"n_estimators": 300, "max_depth": 3, "learning_rate": 0.05},
    {"n_estimators": 500, "max_depth": 4, "learning_rate": 0.03},
]


def calcular_metricas(y_real, y_pred, y_prob=None) -> dict:
    """
    Metricas de clasificacion. La principal es la exactitud balanceada
    obtenida por validacion walk-forward (ver config.py).

    - exactitud: proporcion de aciertos. Facil de leer, pero sensible al
      balance de clases.
    - exactitud_balanceada: promedio de la tasa de acierto en cada clase.
      Es 0,5 si el modelo predice siempre lo mismo, sin importar el balance.
    - f1 / precision / exhaustividad: sobre la clase "sube", que es la
      accionable (si el modelo dice que sube, conviene comprar hoy).
    - roc_auc: probabilidad de que el modelo asigne mas probabilidad de subida
      a un dia que efectivamente subio que a uno que no. 0,5 es azar.
    """
    m = {
        "exactitud": float(accuracy_score(y_real, y_pred)),
        "exactitud_balanceada": float(balanced_accuracy_score(y_real, y_pred)),
        "f1_sube": float(f1_score(y_real, y_pred, zero_division=0)),
        "precision_sube": float(precision_score(y_real, y_pred, zero_division=0)),
        "exhaustividad_sube": float(recall_score(y_real, y_pred, zero_division=0)),
    }
    # El AUC no existe si el conjunto de prueba tiene una sola clase.
    if y_prob is not None and len(np.unique(y_real)) > 1:
        m["roc_auc"] = float(roc_auc_score(y_real, y_prob))
    return m


def validacion_walk_forward(fabrica, X, y, n_particiones: int) -> dict:
    """
    Validacion cruzada respetando el orden temporal (walk-forward).

    Por que hace falta: el test cronologico final son ~50 dias. Una diferencia
    de 3 aciertos mueve la metrica 6 puntos, asi que elegir el modelo por ese
    solo numero es elegir por ruido. TimeSeriesSplit entrena con el pasado y
    evalua con el futuro inmediato, cinco veces sobre ventanas crecientes, y
    promedia: el resultado es mucho mas estable.

    Por que no una validacion cruzada normal: mezclar filas al azar pondria
    dias futuros en el entrenamiento (fuga de informacion).

    Se corre SOLO sobre el conjunto de entrenamiento. El test cronologico
    queda intacto como evaluacion final independiente, no se usa para elegir.
    """
    particiones = TimeSeriesSplit(n_splits=n_particiones)
    balanceadas, aucs = [], []

    for idx_tr, idx_te in particiones.split(X):
        X_tr, X_te = X.iloc[idx_tr], X.iloc[idx_te]
        y_tr, y_te = y.iloc[idx_tr], y.iloc[idx_te]

        # Una particion puede quedar con una sola clase; no aporta senal.
        if y_tr.nunique() < 2 or y_te.nunique() < 2:
            continue

        modelo = fabrica()
        modelo.fit(X_tr, y_tr)
        balanceadas.append(balanced_accuracy_score(y_te, modelo.predict(X_te)))
        aucs.append(roc_auc_score(y_te, modelo.predict_proba(X_te)[:, 1]))

    if not balanceadas:
        return {"exactitud_balanceada_cv": float("nan"), "roc_auc_cv": float("nan"),
                "desv_exactitud_balanceada_cv": float("nan")}

    return {
        "exactitud_balanceada_cv": float(np.mean(balanceadas)),
        "desv_exactitud_balanceada_cv": float(np.std(balanceadas)),
        "roc_auc_cv": float(np.mean(aucs)),
    }


def grafico_evaluacion(y_real, y_pred, y_prob, titulo: str) -> plt.Figure:
    """
    Matriz de confusion + curva ROC, adjuntas a cada run.

    Sirven en la defensa: en la interfaz de MLflow se abre un run y se ve de
    inmediato si el modelo esta prediciendo una sola clase o discriminando de
    verdad, sin tener que interpretar solo un numero.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))

    mc = confusion_matrix(y_real, y_pred, labels=[0, 1])
    ax1.imshow(mc, cmap="Blues")
    ax1.set_xticks([0, 1], ["pred: no sube", "pred: sube"])
    ax1.set_yticks([0, 1], ["real: no sube", "real: sube"])
    for i in range(2):
        for j in range(2):
            ax1.text(j, i, str(mc[i, j]), ha="center", va="center",
                     color="white" if mc[i, j] > mc.max() / 2 else "black", fontsize=14)
    ax1.set_title("Matriz de confusion")

    if y_prob is not None and len(np.unique(y_real)) > 1:
        fpr, tpr, _ = roc_curve(y_real, y_prob)
        ax2.plot(fpr, tpr, linewidth=2, label=f"AUC = {roc_auc_score(y_real, y_prob):.3f}")
    ax2.plot([0, 1], [0, 1], "--", color="gray", label="azar (0,500)")
    ax2.set_xlabel("Falsos positivos")
    ax2.set_ylabel("Verdaderos positivos")
    ax2.set_title("Curva ROC")
    ax2.legend()
    ax2.grid(alpha=0.3)

    fig.suptitle(titulo)
    fig.tight_layout()
    return fig


def _registrar_run(nombre, familia, parametros, y_test, y_pred, y_prob, contexto,
                   metricas_cv=None, modelo=None, sabor=None) -> tuple[str, float, str | None]:
    """
    Abre un run de MLflow y registra parametros, metricas, graficos y modelo.

    Devuelve (run_id, metrica_principal, uri_del_modelo). La uri es None para
    el baseline, que no produce un artefacto desplegable.
    """
    with mlflow.start_run(run_name=nombre) as run:
        metricas = calcular_metricas(y_test, y_pred, y_prob)
        if metricas_cv:
            metricas.update(metricas_cv)

        # Las claves con "_" inicial son de uso interno (el ejemplo de entrada
        # para la firma del modelo), no son parametros del experimento.
        mlflow.log_params({**parametros,
                           **{k: v for k, v in contexto.items() if not k.startswith("_")}})
        mlflow.log_metrics({k: v for k, v in metricas.items() if not np.isnan(v)})
        mlflow.set_tags({"familia": familia, "fase": "1-entrenamiento"})

        fig = grafico_evaluacion(y_test, y_pred, y_prob, f"{nombre} -- test cronologico")
        mlflow.log_figure(fig, "evaluacion.png")
        plt.close(fig)

        uri = None
        if modelo is not None and sabor is not None:
            info = sabor.log_model(
                modelo, name="model",
                # float64 evita el aviso de MLflow sobre columnas enteras
                # (dia_semana, es_fin_semana), que no admiten NaN.
                input_example=contexto["_ejemplo"].astype("float64"),
            )
            uri = info.model_uri

        principal = metricas.get(cfg.METRICA_PRINCIPAL, float("nan"))
        print(f"  [{nombre:<26}] {cfg.METRICA_PRINCIPAL}={principal:.4f}  |  "
              f"test: balanceada={metricas['exactitud_balanceada']:.4f}  "
              f"exactitud={metricas['exactitud']:.4f}  "
              f"auc={metricas.get('roc_auc', float('nan')):.4f}")
        return run.info.run_id, principal, uri


def construir_especificaciones(y_train) -> list[dict]:
    """
    Define todas las corridas: nombre, familia, hiperparametros y una FABRICA
    que construye el modelo sin entrenar.

    Se usa una fabrica y no una instancia porque la validacion walk-forward
    necesita un modelo limpio en cada particion; reutilizar el mismo objeto
    arrastraria el ajuste de la particion anterior.

    `class_weight="balanced"` (y su equivalente `scale_pos_weight` en XGBoost)
    compensa el desbalance 42/58 penalizando mas los errores en la clase
    minoritaria. Sin esto los modelos tienden a predecir siempre "no sube",
    que da buena exactitud simple pero exactitud balanceada de 0,50.
    """
    # Proporcion negativos/positivos: lo que XGBoost espera en scale_pos_weight.
    n_pos = int(y_train.sum())
    peso_positivo = (len(y_train) - n_pos) / max(n_pos, 1)

    especificaciones = []

    for params in CONFIGS_LOGISTICA:
        especificaciones.append({
            "nombre": f"logistica_C_{params['C']}",
            "familia": "logistica",
            "params": {"tipo_modelo": "logistica", **params},
            "descripcion": f"C={params['C']}",
            "sabor": mlflow.sklearn,
            # StandardScaler dentro del Pipeline: la logistica es sensible a la
            # escala y las variables van de 1e-3 (retornos) a 6 (dia_semana).
            # Al ir en el Pipeline, el escalado viaja DENTRO del modelo
            # registrado y el servicio no tiene que replicarlo.
            "fabrica": (lambda p=params: Pipeline([
                ("escalado", StandardScaler()),
                ("clasificador", LogisticRegression(
                    max_iter=3000, class_weight="balanced",
                    random_state=cfg.RANDOM_SEED, **p)),
            ])),
        })

    for i, params in enumerate(CONFIGS_BOSQUE, start=1):
        especificaciones.append({
            "nombre": f"bosque_cfg{i}",
            "familia": "random_forest",
            "params": {"tipo_modelo": "random_forest", **params},
            "descripcion": ", ".join(f"{k}={v}" for k, v in params.items()),
            "sabor": mlflow.sklearn,
            "fabrica": (lambda p=params: RandomForestClassifier(
                **p, class_weight="balanced", random_state=cfg.RANDOM_SEED, n_jobs=-1)),
        })

    for i, params in enumerate(CONFIGS_XGBOOST, start=1):
        especificaciones.append({
            "nombre": f"xgboost_cfg{i}",
            "familia": "xgboost",
            "params": {"tipo_modelo": "xgboost", **params},
            "descripcion": ", ".join(f"{k}={v}" for k, v in params.items()),
            "sabor": mlflow.xgboost,
            "fabrica": (lambda p=params, w=peso_positivo: XGBClassifier(
                **p, subsample=0.9, colsample_bytree=0.9, scale_pos_weight=w,
                random_state=cfg.RANDOM_SEED, verbosity=0, eval_metric="logloss")),
        })

    return especificaciones


def entrenar_todo(X_train, X_test, y_train, y_test, contexto):
    """Corre el baseline y todas las especificaciones; devuelve los candidatos."""
    candidatos = []  # (metrica_principal, run_id, uri, nombre, descripcion)

    print("\n-- Baseline --")
    # Clase mayoritaria: predice siempre la clase mas frecuente del train. No
    # aprende nada, por eso no genera artefacto y no compite por el despliegue:
    # es el piso contra el que se mide todo lo demas. Su exactitud balanceada
    # es 0,50 por construccion.
    mayoritaria = int(y_train.mode()[0])
    _registrar_run(
        "baseline_clase_mayoritaria", "baseline",
        {"tipo_modelo": "clase_mayoritaria", "clase_predicha": mayoritaria},
        y_test, np.full(len(y_test), mayoritaria),
        np.full(len(y_test), float(y_train.mean())),  # probabilidad constante -> AUC 0,5
        contexto,
        metricas_cv={"exactitud_balanceada_cv": cfg.METRICA_AZAR, "roc_auc_cv": cfg.METRICA_AZAR},
    )

    familia_actual = None
    for esp in construir_especificaciones(y_train):
        if esp["familia"] != familia_actual:
            familia_actual = esp["familia"]
            print(f"\n-- {familia_actual} --")

        # 1) Validacion walk-forward SOLO sobre el train: es lo que decide.
        metricas_cv = validacion_walk_forward(
            esp["fabrica"], X_train, y_train, cfg.N_PARTICIONES_CV
        )

        # 2) Ajuste final con todo el train y evaluacion en el test intacto.
        modelo = esp["fabrica"]()
        modelo.fit(X_train, y_train)

        run_id, principal, uri = _registrar_run(
            esp["nombre"], esp["familia"], esp["params"],
            y_test, modelo.predict(X_test), modelo.predict_proba(X_test)[:, 1],
            contexto, metricas_cv=metricas_cv, modelo=modelo, sabor=esp["sabor"],
        )
        candidatos.append((principal, run_id, uri, esp["nombre"], esp["descripcion"]))

    return candidatos


def registrar_ganador(ganador, poner_alias: bool, nota: str, contexto: dict) -> None:
    """Registra la mejor corrida en el Model Registry y marca el alias."""
    metrica_principal, run_id, uri_modelo, nombre, hiperparams = ganador

    version = mlflow.register_model(uri_modelo, cfg.REGISTERED_MODEL_NAME)
    cliente = mlflow.MlflowClient()

    # Se leen las metricas reales del run (no se reutiliza el valor que
    # decidio la seleccion): asi el reporte muestra tanto el criterio de
    # seleccion (CV) como el desempeno en el test cronologico, cada uno con
    # su nombre correcto.
    metricas_run = cliente.get_run(run_id).data.metrics
    balanceada_test = metricas_run.get("exactitud_balanceada", float("nan"))
    auc_test = metricas_run.get("roc_auc", float("nan"))

    # La descripcion se ve en la interfaz del Model Registry: es lo que
    # permite explicar en vivo por que existe cada version.
    cliente.update_model_version(
        name=cfg.REGISTERED_MODEL_NAME, version=version.version,
        description=(
            f"{nota}\n\n"
            f"Corrida ganadora: {nombre} ({hiperparams})\n"
            f"{cfg.METRICA_PRINCIPAL} (criterio de seleccion): {metrica_principal:.4f}\n"
            f"Exactitud balanceada en test: {balanceada_test:.4f}\n"
            f"ROC AUC en test: {auc_test:.4f}\n"
            f"Datos hasta: {contexto['fecha_corte']}\n"
            f"Filas de entrenamiento: {contexto['n_train']}"
        ),
    )
    cliente.set_model_version_tag(cfg.REGISTERED_MODEL_NAME, version.version,
                                 "fecha_corte_datos", contexto["fecha_corte"])
    cliente.set_model_version_tag(cfg.REGISTERED_MODEL_NAME, version.version,
                                 "roc_auc_test", f"{auc_test:.4f}")

    print(f"\nRegistrado '{cfg.REGISTERED_MODEL_NAME}' version {version.version}  (run {run_id})")

    if not poner_alias:
        print(f"  Alias '{cfg.DEPLOYMENT_ALIAS}' NO movido (--sin-alias): la version "
              f"{version.version} queda registrada pero no desplegada.")
        return

    cliente.set_registered_model_alias(cfg.REGISTERED_MODEL_NAME, cfg.DEPLOYMENT_ALIAS, version.version)
    print(f"  Alias '{cfg.DEPLOYMENT_ALIAS}' -> version {version.version}")
    _escribir_ficha(version.version, run_id, nombre, hiperparams, metrica_principal,
                    balanceada_test, auc_test, nota, contexto)


def _escribir_ficha(version, run_id, nombre, hiperparams, metrica_principal,
                    balanceada_test, auc_test, nota, contexto) -> None:
    """
    Deja por escrito que version esta desplegada y de que run salio.

    La consigna 3.3.2 pide exactamente esto: que el documento de arquitectura
    indique que version del registro corresponde al modelo desplegado y a que
    run pertenece.
    """
    ficha = cfg.RAIZ / "MODELO_DESPLEGADO.md"
    ficha.write_text(f"""# Modelo desplegado

> Generado automaticamente por `src/train.py`. No editar a mano.

| Campo | Valor |
|---|---|
| Nombre registrado | `{cfg.REGISTERED_MODEL_NAME}` |
| Version | **{version}** |
| Alias de despliegue | `{cfg.DEPLOYMENT_ALIAS}` |
| Run de origen | `{run_id}` |
| Experimento | `{cfg.MLFLOW_EXPERIMENT_NAME}` |
| Corrida ganadora | `{nombre}` |
| Hiperparametros | {hiperparams} |
| {cfg.METRICA_PRINCIPAL} (criterio de seleccion) | {metrica_principal:.4f} |
| Exactitud balanceada en test | {balanceada_test:.4f} |
| ROC AUC en test | {auc_test:.4f} |
| Datos hasta | {contexto['fecha_corte']} |
| Filas train / test | {contexto['n_train']} / {contexto['n_test']} |
| Semilla | {cfg.RANDOM_SEED} |
| Motivo | {nota} |
| Entrenado el | {datetime.now(timezone.utc).isoformat(timespec='seconds')} |
| Python | {platform.python_version()} |

El servicio de inferencia carga este modelo por la referencia
`models:/{cfg.REGISTERED_MODEL_NAME}@{cfg.DEPLOYMENT_ALIAS}`, nunca por una ruta
de archivo. Mover el alias a otra version y reiniciar los pods es todo lo que
hace falta para cambiar el modelo en produccion.
""", encoding="utf-8")
    print(f"  Ficha escrita en {ficha.relative_to(cfg.RAIZ)}")


def main(hasta: str, nota: str, poner_alias: bool) -> None:
    cfg.configurar_mlflow()

    # El experimento apunta al directorio de artefactos del store del proyecto,
    # para que base de datos y artefactos vivan juntos y el conjunto se pueda
    # copiar a la imagen de Docker (ver src/portar_store.py).
    if mlflow.get_experiment_by_name(cfg.MLFLOW_EXPERIMENT_NAME) is None:
        mlflow.create_experiment(cfg.MLFLOW_EXPERIMENT_NAME, artifact_location=cfg.ARTIFACT_ROOT)
    mlflow.set_experiment(cfg.MLFLOW_EXPERIMENT_NAME)

    df = preparar(cfg.CSV_COMPLETO, hasta=hasta)
    X_train, X_test, y_train, y_test = division_temporal(df, cfg.TRAIN_PROP)

    print(f"Datos hasta      : {hasta}")
    print(f"Dias utilizables : {len(df)}  (solo dias con cotizacion real al dia siguiente)")
    print(f"Balance          : {100 * df[COLUMNA_OBJETIVO].mean():.1f}% de dias al alza")
    print(f"Train / Test     : {len(X_train)} / {len(X_test)}  (division cronologica 80/20)")
    print(f"Variables        : {len(COLUMNAS_FEATURES)} -> {', '.join(COLUMNAS_FEATURES)}")

    contexto = {
        "fecha_corte": hasta or "sin_corte",
        "train_prop": cfg.TRAIN_PROP,
        "semilla": cfg.RANDOM_SEED,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "n_variables": len(COLUMNAS_FEATURES),
        "frecuencia": "diaria",
        "objetivo": "direccion_1d",
        "_ejemplo": X_train.iloc[:2],
    }

    candidatos = entrenar_todo(X_train, X_test, y_train, y_test, contexto)

    # nan al final: si a un modelo no se le pudo calcular el AUC, no gana.
    ganador = max(candidatos, key=lambda c: (-1 if np.isnan(c[0]) else c[0]))
    print(f"\nMejor por {cfg.METRICA_PRINCIPAL}: {ganador[3]} ({ganador[4]})  = {ganador[0]:.4f}")

    registrar_ganador(ganador, poner_alias, nota, contexto)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--hasta", default=cfg.FECHA_CORTE_V1,
                   help=f"Usar datos hasta esta fecha inclusive (por defecto {cfg.FECHA_CORTE_V1})")
    p.add_argument("--nota", default="Version inicial: entrenada antes de la flexibilizacion cambiaria del BCB.",
                   help="Motivo del entrenamiento; queda en la descripcion de la version registrada")
    p.add_argument("--sin-alias", action="store_true",
                   help="Registrar la version sin moverle el alias de despliegue")
    args = p.parse_args()

    main(hasta=args.hasta, nota=args.nota, poner_alias=not args.sin_alias)
